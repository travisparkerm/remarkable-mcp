"""
Note extraction module.

Connects to reMarkable Cloud, finds documents modified in a date range,
and extracts text content (typed + handwritten via OCR).
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

from daily_podcast.config import PodcastConfig

logger = logging.getLogger(__name__)


def extract_notes(
    config: PodcastConfig,
    target_date: Optional[datetime] = None,
    days: int = 1,
) -> str:
    """
    Extract all notes modified in the date range from reMarkable Cloud.

    Args:
        config: Pipeline configuration.
        target_date: End date of the range. Defaults to today in configured timezone.
        days: Number of days to look back (1 = just target_date, 7 = last week).

    Returns:
        Concatenated text with document titles as section headers.
        Empty string if no notes were found.
    """
    from remarkable_mcp.api import get_item_path, get_items_by_id, get_rmapi
    from remarkable_mcp.extract import extract_text_from_document_zip

    tz = ZoneInfo(config.timezone)
    if target_date is None:
        target_date = datetime.now(tz)

    # Date range boundaries
    day_end = target_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    day_start = day_end - timedelta(days=days)

    logger.info(
        "Extracting notes from %s to %s (%d day(s))",
        day_start.strftime("%Y-%m-%d"),
        (day_end - timedelta(days=1)).strftime("%Y-%m-%d"),
        days,
    )

    client = get_rmapi()
    all_items = client.get_meta_items()
    items_by_id = get_items_by_id(all_items)

    # Filter to documents (not folders) modified in date range
    root_path = config.remarkable_root_path.strip().rstrip("/")
    matched_docs = []

    for item in all_items:
        if item.is_folder:
            continue
        if item.last_modified is None:
            continue

        # Make last_modified timezone-aware if it isn't already
        mod_time = item.last_modified
        if mod_time.tzinfo is None:
            mod_time = mod_time.replace(tzinfo=tz)

        if not (day_start <= mod_time < day_end):
            continue

        # Filter by root path if configured
        if root_path and root_path != "/":
            doc_path = get_item_path(item, items_by_id)
            if not doc_path.startswith(root_path):
                continue

        matched_docs.append(item)

    if not matched_docs:
        logger.info("No documents modified in date range.")
        return ""

    logger.info("Found %d document(s) modified in date range.", len(matched_docs))

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
            if combined:
                sections.append(f"## {doc.VissibleName}\n\n{combined}")
            else:
                logger.info("  No extractable text in %s", doc.VissibleName)

        except Exception as e:
            logger.warning("Failed to extract text from %s: %s", doc.VissibleName, e)
            continue

    if not sections:
        logger.info("No extractable text found in matched documents.")
        return ""

    result = "\n\n---\n\n".join(sections)
    logger.info("Extracted %d characters from %d document(s).", len(result), len(sections))
    return result
