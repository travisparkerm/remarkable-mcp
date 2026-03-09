"""
RSS feed generator module.

Generates a podcast-compatible RSS XML feed from episode files.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent
from zoneinfo import ZoneInfo

from daily_podcast.config import PodcastConfig

logger = logging.getLogger(__name__)

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _format_rfc2822(dt: datetime) -> str:
    """Format a datetime as RFC 2822 for RSS pubDate."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _get_mp3_duration_seconds(mp3_path: Path) -> int:
    """Estimate MP3 duration from file size (128kbps bitrate)."""
    file_size = mp3_path.stat().st_size
    # 128 kbps = 16000 bytes/sec
    return max(1, file_size // 16000)


def _format_duration(seconds: int) -> str:
    """Format seconds as HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def generate_feed(config: PodcastConfig, episode_date: Optional[datetime] = None) -> Path:
    """
    Generate (or regenerate) the podcast RSS feed XML from all episodes in the episodes directory.

    Args:
        config: Pipeline configuration.
        episode_date: Date of the latest episode (for logging). Not used in generation
                      since we scan the directory.

    Returns:
        Path to the generated feed.xml file.
    """
    episodes_dir = config.episodes_dir
    episodes_dir.mkdir(parents=True, exist_ok=True)
    feed_path = episodes_dir / "feed.xml"
    tz = ZoneInfo(config.timezone)

    # Discover all episode MP3 files
    mp3_files = sorted(episodes_dir.glob("episode-*.mp3"), reverse=True)
    if not mp3_files:
        logger.warning("No episodes found in %s", episodes_dir)
        return feed_path

    base_url = config.feed_base_url.rstrip("/")

    # Build RSS XML
    rss = Element("rss", version="2.0")
    rss.set("xmlns:itunes", ITUNES_NS)
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = config.feed_title
    SubElement(channel, "description").text = (
        f"Daily audio recaps of handwritten notes from reMarkable."
    )
    SubElement(channel, "language").text = "en"
    SubElement(channel, "generator").text = "remarkable-podcast"

    # Link and self-referencing atom link
    feed_url = f"{base_url}/feed.xml"
    SubElement(channel, "link").text = feed_url
    atom_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", feed_url)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # iTunes metadata
    SubElement(channel, f"{{{ITUNES_NS}}}author").text = "reMarkable Podcast"
    SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = "false"
    category = SubElement(channel, f"{{{ITUNES_NS}}}category")
    category.set("text", "Personal Journals")

    # Add episodes
    for mp3_path in mp3_files:
        # Parse date from filename: episode-YYYY-MM-DD.mp3
        stem = mp3_path.stem  # episode-YYYY-MM-DD
        date_str = stem.replace("episode-", "")
        try:
            ep_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                hour=21, minute=0, tzinfo=tz
            )
        except ValueError:
            logger.warning("Skipping file with unexpected name: %s", mp3_path.name)
            continue

        file_size = mp3_path.stat().st_size
        duration_secs = _get_mp3_duration_seconds(mp3_path)
        ep_url = f"{base_url}/{mp3_path.name}"

        # Read the script file if it exists (for description)
        script_path = episodes_dir / f"script-{date_str}.txt"
        description = f"Daily notes recap for {date_str}"
        if script_path.exists():
            script_text = script_path.read_text()
            description = script_text[:200] + ("..." if len(script_text) > 200 else "")

        item = SubElement(channel, "item")
        SubElement(item, "title").text = f"Notes for {date_str}"
        SubElement(item, "description").text = description
        SubElement(item, "pubDate").text = _format_rfc2822(ep_date)
        SubElement(item, "guid", isPermaLink="true").text = ep_url

        enclosure = SubElement(item, "enclosure")
        enclosure.set("url", ep_url)
        enclosure.set("length", str(file_size))
        enclosure.set("type", "audio/mpeg")

        SubElement(item, f"{{{ITUNES_NS}}}duration").text = _format_duration(duration_secs)
        SubElement(item, f"{{{ITUNES_NS}}}explicit").text = "false"

    # Write feed
    tree = ElementTree(rss)
    indent(tree, space="  ")
    tree.write(feed_path, encoding="unicode", xml_declaration=True)

    logger.info("Feed generated: %s (%d episodes)", feed_path, len(mp3_files))
    return feed_path
