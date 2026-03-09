"""
Main pipeline orchestrator.

Chains: extract → summarize → speak → publish
"""

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from daily_podcast.config import PodcastConfig
from daily_podcast.extract import extract_notes
from daily_podcast.feed import generate_feed
from daily_podcast.speak import generate_audio
from daily_podcast.summarize import generate_podcast_script

logger = logging.getLogger(__name__)


def run_pipeline(
    config: PodcastConfig,
    target_date: Optional[datetime] = None,
    days: int = 1,
) -> bool:
    """
    Run the full daily podcast pipeline.

    Args:
        config: Pipeline configuration.
        target_date: Date to generate episode for. Defaults to today.
        days: Number of days to look back for notes (1 = just target_date).

    Returns:
        True if an episode was generated, False if skipped (no notes).
    """
    tz = ZoneInfo(config.timezone)
    if target_date is None:
        target_date = datetime.now(tz)

    date_str = target_date.strftime("%Y-%m-%d")
    episodes_dir = config.episodes_dir
    episodes_dir.mkdir(parents=True, exist_ok=True)

    # Idempotency check — skip if episode already exists
    mp3_path = episodes_dir / f"episode-{date_str}.mp3"
    if mp3_path.exists():
        logger.info("Episode for %s already exists, skipping.", date_str)
        return False

    # Step 1: Extract notes
    logger.info("=== Step 1: Extracting notes for %s (%d day(s)) ===", date_str, days)
    notes_text = extract_notes(config, target_date, days=days)
    if not notes_text:
        logger.info("No notes found. Skipping episode generation.")
        return False

    # Save raw notes for reference
    notes_path = episodes_dir / f"notes-{date_str}.txt"
    notes_path.write_text(notes_text)
    logger.info("Raw notes saved: %s", notes_path)

    # Step 2: Generate podcast script
    logger.info("=== Step 2: Generating podcast script ===")
    script = generate_podcast_script(notes_text, config)

    # Save script for reference and feed description
    script_path = episodes_dir / f"script-{date_str}.txt"
    script_path.write_text(script)
    logger.info("Script saved: %s", script_path)

    # Step 3: Generate audio
    logger.info("=== Step 3: Generating audio ===")
    generate_audio(script, mp3_path, config)

    # Step 4: Regenerate RSS feed
    logger.info("=== Step 4: Updating RSS feed ===")
    feed_path = generate_feed(config, target_date)
    logger.info("Feed updated: %s", feed_path)

    logger.info("=== Done! Episode for %s is ready. ===", date_str)
    return True
