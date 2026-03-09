"""
Background worker that runs the podcast pipeline for a specific user.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from api.database import Episode, RemarkableDevice, UserSettings, async_session

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


async def run_pipeline_for_user(user_id: int, date_str: str):
    """
    Run the full podcast pipeline for a user and date.

    Loads the user's reMarkable token and settings from the database,
    configures the pipeline, runs extract -> summarize -> speak,
    and stores results in data/episodes/{user_id}/.
    """
    import asyncio

    # Load user's device token and settings
    async with async_session() as db:
        # Get device token
        result = await db.execute(
            select(RemarkableDevice)
            .where(RemarkableDevice.user_id == user_id)
            .order_by(RemarkableDevice.registered_at.desc())
        )
        device = result.scalar_one_or_none()
        if device is None:
            await _fail_episode(db, user_id, date_str, "No reMarkable device registered")
            return

        # Get user settings
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        # Mark episode as processing
        result = await db.execute(
            select(Episode)
            .where(Episode.user_id == user_id, Episode.date == date_str)
        )
        episode = result.scalar_one_or_none()
        if episode:
            episode.status = "processing"
            await db.commit()

        device_token = device.device_token
        tz = settings.timezone if settings else "Europe/Warsaw"
        voice_id = settings.elevenlabs_voice_id if settings else None
        voice_desc = settings.podcast_voice_description if settings else None
        target_words = settings.target_word_count if settings else 350
        personality = settings.personality if settings else "analyst"

    # Run the CPU/IO-bound pipeline in a thread
    try:
        result = await asyncio.to_thread(
            _run_pipeline_sync,
            user_id,
            date_str,
            device_token,
            tz,
            voice_id,
            voice_desc,
            target_words,
            personality,
        )
    except Exception as e:
        logger.exception("Pipeline failed for user %d, date %s", user_id, date_str)
        async with async_session() as db:
            await _fail_episode(db, user_id, date_str, str(e))
        return

    # Update episode in DB
    async with async_session() as db:
        res = await db.execute(
            select(Episode)
            .where(Episode.user_id == user_id, Episode.date == date_str)
        )
        episode = res.scalar_one_or_none()
        if episode:
            episode.status = result["status"]
            episode.title = result.get("title")
            episode.script_text = result.get("script_text")
            episode.notes_text = result.get("notes_text")
            episode.audio_path = result.get("audio_path")
            await db.commit()


def _run_pipeline_sync(
    user_id: int,
    date_str: str,
    device_token: str,
    timezone_str: str,
    voice_id: str | None,
    voice_desc: str | None,
    target_words: int,
    personality: str = "analyst",
) -> dict:
    """
    Synchronous pipeline execution. Runs in a thread.
    Returns a dict with episode data.
    """
    from daily_podcast.config import PodcastConfig, load_config
    from daily_podcast.extract import extract_notes
    from daily_podcast.personalities import get_voice_id
    from daily_podcast.speak import generate_audio
    from daily_podcast.summarize import generate_podcast_script

    # Build config from env-based defaults
    config = load_config()

    # Override with the user's device token AFTER load_config
    # (load_config loads .env.local which may have a stale REMARKABLE_TOKEN)
    rmapi_file = Path.home() / ".rmapi"
    rmapi_file.write_text(device_token)
    os.environ["REMARKABLE_TOKEN"] = device_token
    config.remarkable_token = device_token
    config.timezone = timezone_str
    config.episodes_dir = DATA_DIR / "episodes" / str(user_id)
    config.remarkable_token = device_token

    # Use user's custom voice ID, or fall back to the personality's default
    if voice_id:
        config.elevenlabs_voice_id = voice_id
    elif personality:
        personality_voice = get_voice_id(personality)
        if personality_voice:
            config.elevenlabs_voice_id = personality_voice
    if voice_desc:
        config.podcast_voice = voice_desc
    if target_words:
        config.podcast_target_length = target_words

    config.episodes_dir.mkdir(parents=True, exist_ok=True)

    tz = ZoneInfo(timezone_str)
    target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)

    # Step 1: Extract notes
    logger.info("User %d: extracting notes for %s", user_id, date_str)
    notes_text = extract_notes(config, target_date)
    if not notes_text:
        return {
            "status": "ready",
            "title": f"No notes for {date_str}",
            "notes_text": "",
            "script_text": "No notes were found for this date.",
        }

    # Save raw notes
    notes_path = config.episodes_dir / f"notes-{date_str}.txt"
    notes_path.write_text(notes_text)

    # Step 2: Generate script
    logger.info("User %d: generating script for %s", user_id, date_str)
    script = generate_podcast_script(notes_text, config, personality=personality)

    script_path = config.episodes_dir / f"script-{date_str}.txt"
    script_path.write_text(script)

    # Step 3: Generate audio
    logger.info("User %d: generating audio for %s", user_id, date_str)
    mp3_path = config.episodes_dir / f"episode-{date_str}.mp3"
    generate_audio(script, mp3_path, config)

    return {
        "status": "ready",
        "title": f"Episode for {date_str}",
        "script_text": script,
        "notes_text": notes_text,
        "audio_path": str(mp3_path),
    }


async def _fail_episode(db, user_id: int, date_str: str, error: str):
    """Mark an episode as failed."""
    result = await db.execute(
        select(Episode)
        .where(Episode.user_id == user_id, Episode.date == date_str)
    )
    episode = result.scalar_one_or_none()
    if episode:
        episode.status = "failed"
        episode.script_text = f"Error: {error}"
        await db.commit()
    logger.error("Episode failed for user %d, date %s: %s", user_id, date_str, error)
