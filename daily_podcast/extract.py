"""
Note extraction module.

Connects to reMarkable Cloud, finds documents modified in a date range,
and extracts text content (typed + handwritten via OCR).

Supports:
- Scope filtering: restrict to specific folder/document paths
- Time window filtering: 1d, 7d, 30d, or all
- Date-header filtering: if notes contain date headers (e.g.
  "March 9, 2026" or "3/9/2026"), only content under dates within the
  requested range is returned.
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

from daily_podcast.config import PodcastConfig

logger = logging.getLogger(__name__)


# Patterns for recognizing date headers in extracted text.
# Order matters — more specific patterns are tried first.
# All patterns accept both 2-digit and 4-digit years.
_DATE_PATTERNS = [
    # "March 9, 2026" / "Mar 9, 26" / "March 9 2026" / "MAR 9,26"
    re.compile(
        r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),?\s*(?P<year>\d{2,4})$"
    ),
    # "9 March 2026" / "9 March 26"
    re.compile(
        r"^(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+),?\s*(?P<year>\d{2,4})$"
    ),
    # "FEB 1825" — OCR artifact where "FEB 18, 25" loses the comma/space
    # Day (1-2 digits) concatenated with 2-digit year
    re.compile(
        r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?P<year>\d{2})$"
    ),
    # "2026-03-09" (ISO format, 4-digit year only to avoid ambiguity with m-d-y)
    re.compile(r"^(?P<year>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})$"),
    # "03/09/2026" or "3/9/26"
    re.compile(r"^(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<year>\d{2,4})$"),
    # "03-09-2026" or "3-9-26" (only matched after ISO fails above)
    re.compile(r"^(?P<m>\d{1,2})-(?P<d>\d{1,2})-(?P<year>\d{2,4})$"),
]

_FULL_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTH_NAMES = {}
for _i, _name in enumerate(_FULL_MONTH_NAMES):
    if _name:
        _MONTH_NAMES[_name.lower()] = _i
        _MONTH_NAMES[_name[:3].lower()] = _i


# --- Time window helpers ---

TIME_WINDOW_DAYS = {
    "1d": 1,
    "7d": 7,
    "30d": 30,
    "all": None,
}


def _parse_scope(scope: str) -> list[str]:
    """Parse scope string — JSON list or single path."""
    if not scope or scope == "/":
        return ["/"]
    try:
        paths = json.loads(scope)
        if isinstance(paths, list):
            return [p.strip().rstrip("/") for p in paths if p.strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return [scope.strip().rstrip("/")]


def _path_matches_scope(doc_path: str, scope_paths: list[str]) -> bool:
    """Check if a document path falls under any of the scope paths."""
    for scope_path in scope_paths:
        if scope_path == "/" or scope_path == "":
            return True
        if doc_path.startswith(scope_path):
            return True
    return False


def _extract_date_from_text(text: str) -> Optional[datetime]:
    """Try to match text against known date patterns. Returns date or None."""
    for pattern in _DATE_PATTERNS:
        m = pattern.match(text)
        if not m:
            continue
        try:
            groups = m.groupdict()
            if "month" in groups:
                month_str = groups["month"].lower()
                month = _MONTH_NAMES.get(month_str)
                if month is None:
                    continue
                day = int(groups["day"])
            else:
                month = int(groups["m"])
                day = int(groups["d"])
            year = int(groups["year"])
            if year < 100:
                year += 2000
            return datetime(year, month, day)
        except (ValueError, KeyError):
            continue
    return None


# Pattern to split on common separators that precede an inline date,
# e.g. "Morning Prayer ------------ Mar 20, 26" or "TOPIC — 3/9/26"
_INLINE_DATE_SEP = re.compile(r"[-]{2,}|[—–]|[|/]{2,}")


def _parse_date_header(line: str) -> Optional[datetime]:
    """Try to parse a single line as a date header. Returns date or None.

    Handles both standalone dates ("March 9, 2026") and inline dates
    where the date appears after a separator ("Morning Prayer --- Mar 9, 26").
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return None

    # First try: the whole line is a date (short lines only)
    if len(stripped) <= 40:
        result = _extract_date_from_text(stripped)
        if result is not None:
            return result

    # Second try: date appears after a separator (dashes, pipes, em-dashes)
    parts = _INLINE_DATE_SEP.split(stripped)
    if len(parts) > 1:
        # Check the last segment — date is typically at the end
        tail = parts[-1].strip()
        if tail:
            result = _extract_date_from_text(tail)
            if result is not None:
                return result

    return None


def _filter_content_by_date_regex(
    text: str,
    day_start: datetime,
    day_end: datetime,
    tail_chars: int = 3000,
) -> str:
    """
    Regex-based fallback: filter text to content under date headers
    within [day_start, day_end). Used when AI filtering is unavailable.
    """
    lines = text.split("\n")
    sections: list[tuple[Optional[datetime], list[str]]] = []
    current_date: Optional[datetime] = None
    current_lines: list[str] = []
    found_any_date = False

    for line in lines:
        parsed = _parse_date_header(line)
        if parsed is not None:
            found_any_date = True
            sections.append((current_date, current_lines))
            current_date = parsed
            current_lines = [line]
        else:
            current_lines.append(line)

    sections.append((current_date, current_lines))

    if not found_any_date:
        if len(text) <= tail_chars:
            return text
        return "...\n" + text[-tail_chars:]

    start_date = day_start.date() if hasattr(day_start, 'date') else day_start
    end_date = day_end.date() if hasattr(day_end, 'date') else day_end

    kept: list[str] = []
    for section_date, section_lines in sections:
        if section_date is None:
            preamble = "\n".join(section_lines).strip()
            if preamble:
                kept.append(preamble)
        elif start_date <= section_date.date() < end_date:
            kept.append("\n".join(section_lines).strip())

    return "\n\n".join(kept)


def _filter_content_by_date_ai(
    text: str,
    day_start: datetime,
    day_end: datetime,
    anthropic_api_key: str,
) -> Optional[str]:
    """
    Use Claude to identify date sections in handwritten notes and extract
    only content written within [day_start, day_end).

    Returns filtered text, or None if the AI call fails (caller should
    fall back to regex).
    """
    import anthropic

    start_str = day_start.strftime("%B %-d, %Y")
    end_str = (day_end - timedelta(days=1)).strftime("%B %-d, %Y")

    if start_str == end_str:
        date_range_desc = start_str
    else:
        date_range_desc = f"{start_str} through {end_str}"

    prompt = f"""You are analyzing OCR-extracted text from a handwritten notebook. The text contains entries from different dates. People typically write a date (in any format — "Mar 10, 26", "March 10 2026", "3/10/26", right-aligned dates, inline dates, etc.) followed by their notes for that day.

Extract ONLY the content that was written on or between: {date_range_desc}

Rules:
- Look for any date indicators: explicit dates, month/day headers, or contextual clues
- Include the date header line itself and all content under it until the next date
- If the notebook has a title/header before any dates, include it for context
- If you cannot identify any date structure, return the content from the END of the document (most recent entries are typically at the end)
- Return ONLY the extracted text — no commentary, no explanations
- If nothing matches the date range, return exactly: NO_MATCH

Here is the notebook text:

{text}"""

    try:
        client = anthropic.Anthropic(api_key=anthropic_api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        result = message.content[0].text.strip()
        if result == "NO_MATCH":
            return ""
        return result
    except Exception as e:
        logger.warning("AI date filtering failed, falling back to regex: %s", e)
        return None


def filter_content_by_date(
    text: str,
    day_start: datetime,
    day_end: datetime,
    tail_chars: int = 3000,
    anthropic_api_key: Optional[str] = None,
) -> str:
    """
    Filter extracted text to only include content under date headers
    that fall within [day_start, day_end).

    Uses AI (Claude Haiku) when an API key is provided for robust date
    detection in handwritten notes. Falls back to regex-based parsing.
    """
    # Try AI-powered filtering first (handles arbitrary date formats)
    if anthropic_api_key and len(text) > 0:
        ai_result = _filter_content_by_date_ai(
            text, day_start, day_end, anthropic_api_key
        )
        if ai_result is not None:
            logger.info("AI date filtering returned %d chars.", len(ai_result))
            return ai_result

    # Fallback: regex-based filtering
    return _filter_content_by_date_regex(text, day_start, day_end, tail_chars)


def extract_notes(
    config: PodcastConfig,
    target_date: Optional[datetime] = None,
    days: int = 1,
    scope: str = "/",
) -> str:
    """
    Extract notes from reMarkable Cloud for a date range and scope.

    Documents modified in the date range are downloaded and OCR'd. Then,
    if a document contains date headers (e.g. "March 9, 2026"), only
    content under dates within the range is kept. Documents without date
    headers are included in full (filtered only by modification time).

    Args:
        config: Pipeline configuration.
        target_date: End date of the range. Defaults to today in configured timezone.
        days: Number of days to look back (1 = just target_date, 7 = last week).
            Use None or 0 for "all time" (no time filter).
        scope: Folder/document path(s) to restrict extraction to.
            Can be a single path string or JSON list of paths.

    Returns:
        Concatenated text with document titles as section headers.
        Empty string if no notes were found.
    """
    from remarkable_mcp.api import get_item_path, get_items_by_id, get_rmapi
    from remarkable_mcp.extract import extract_text_from_document_zip

    tz = ZoneInfo(config.timezone)
    if target_date is None:
        target_date = datetime.now(tz)

    scope_paths = _parse_scope(scope)
    no_time_filter = days is None or days == 0

    # Date range boundaries (only used if time filtering is active)
    if not no_time_filter:
        day_end = target_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        day_start = day_end - timedelta(days=days)
    else:
        day_start = None
        day_end = None

    if no_time_filter:
        logger.info("Extracting all notes (no time filter), scope: %s", scope_paths)
    else:
        logger.info(
            "Extracting notes from %s to %s (%d day(s)), scope: %s",
            day_start.strftime("%Y-%m-%d"),
            (day_end - timedelta(days=1)).strftime("%Y-%m-%d"),
            days,
            scope_paths,
        )

    client = get_rmapi()
    all_items = client.get_meta_items()
    items_by_id = get_items_by_id(all_items)

    # Filter to documents (not folders) within scope and time range
    matched_docs = []

    for item in all_items:
        if item.is_folder:
            continue

        # Filter by scope
        doc_path = get_item_path(item, items_by_id)
        if not _path_matches_scope(doc_path, scope_paths):
            continue

        # Filter by time window (if applicable)
        if not no_time_filter:
            if item.last_modified is None:
                continue
            mod_time = item.last_modified
            if mod_time.tzinfo is None:
                mod_time = mod_time.replace(tzinfo=tz)
            if not (day_start <= mod_time < day_end):
                continue

        matched_docs.append(item)

    if not matched_docs:
        logger.info("No documents matched scope/time filter.")
        return ""

    logger.info("Found %d document(s) matching scope/time filter.", len(matched_docs))

    # Extract text from each document
    sections: List[str] = []
    include_ocr = bool(
        config.google_vision_api_key or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )

    for doc in matched_docs:
        doc_path = get_item_path(doc, items_by_id)
        logger.info("Processing: %s", doc_path)

        try:
            raw_zip = client.download(doc)
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp.write(raw_zip)
                tmp_path = Path(tmp.name)

            try:
                content = extract_text_from_document_zip(
                    tmp_path, include_ocr=include_ocr, doc_id=doc.ID
                )
            finally:
                tmp_path.unlink(missing_ok=True)

            # Combine typed text and handwritten OCR text
            text_parts = []
            if content.get("typed_text"):
                text_parts.extend(content["typed_text"])
            if content.get("handwritten_text"):
                text_parts.extend(content["handwritten_text"])
            if content.get("highlights"):
                text_parts.append("Highlights: " + " | ".join(content["highlights"]))

            combined = "\n".join(text_parts).strip()
            if not combined:
                logger.info("  No extractable text in %s", doc.VissibleName)
                continue

            # Apply date-header filtering only when time filtering is active
            if not no_time_filter:
                filtered = filter_content_by_date(
                    combined, day_start, day_end,
                    anthropic_api_key=config.anthropic_api_key or None,
                )
                if filtered.strip():
                    sections.append(f"## {doc.VissibleName}\n\n{filtered}")
                else:
                    logger.info(
                        "  %s has date headers but none in target range, skipping.",
                        doc.VissibleName,
                    )
            else:
                # All-time: include the full document
                sections.append(f"## {doc.VissibleName}\n\n{combined}")

        except Exception as e:
            logger.warning("Failed to extract text from %s: %s", doc.VissibleName, e)
            continue

    if not sections:
        logger.info("No extractable text found in matched documents.")
        return ""

    result = "\n\n---\n\n".join(sections)
    logger.info("Extracted %d characters from %d document(s).", len(result), len(sections))
    return result


def browse_library(device_token: str) -> list[dict]:
    """
    Browse the reMarkable library and return folder/document tree.

    Returns a flat list of items with path, type, and metadata.
    """
    import os
    from pathlib import Path as _Path

    from remarkable_mcp.api import get_item_path, get_items_by_id, get_rmapi

    # Set up token
    rmapi_file = _Path.home() / ".rmapi"
    rmapi_file.write_text(device_token)
    os.environ["REMARKABLE_TOKEN"] = device_token

    client = get_rmapi()
    all_items = client.get_meta_items()
    items_by_id = get_items_by_id(all_items)

    result = []
    for item in all_items:
        path = get_item_path(item, items_by_id)
        entry = {
            "id": item.ID,
            "name": item.VissibleName,
            "path": path,
            "is_folder": item.is_folder,
            "parent_id": item.Parent if hasattr(item, "Parent") else None,
        }
        if item.last_modified:
            entry["last_modified"] = item.last_modified.isoformat()
        result.append(entry)

    # Sort: folders first, then alphabetically
    result.sort(key=lambda x: (not x["is_folder"], x["path"].lower()))
    return result
