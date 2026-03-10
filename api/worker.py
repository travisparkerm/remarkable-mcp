"""
Background worker that runs the podcast pipeline for shows.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from api.database import Episode, RemarkableDevice, Show, UserSettings, async_session
from daily_podcast.extract import TIME_WINDOW_DAYS

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


async def run_pipeline_for_show(show_id: int, episode_id: int):
    """
    Run the full podcast pipeline for a show's episode.

    Loads the show config, user's reMarkable token and settings,
    runs extract -> summarize -> speak, and updates the episode record.
    """
    import asyncio

    # Load show, device token, and user settings
    async with async_session() as db:
        show = await db.get(Show, show_id)
        if not show:
            logger.error("Show %d not found", show_id)
            return

        result = await db.execute(
            select(RemarkableDevice)
            .where(RemarkableDevice.user_id == show.user_id)
            .order_by(RemarkableDevice.registered_at.desc())
        )
        device = result.scalar_one_or_none()
        if device is None:
            await _fail_episode(db, episode_id, "No reMarkable device registered")
            return

        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == show.user_id)
        )
        settings = result.scalar_one_or_none()

        # Mark episode as processing
        episode = await db.get(Episode, episode_id)
        if episode:
            episode.status = "processing"
            await db.commit()

        device_token = device.device_token
        tz = settings.timezone if settings else "Europe/Warsaw"
        user_id = show.user_id

        # Show-level config
        show_config = {
            "name": show.name,
            "slug": show.slug,
            "scope": show.scope,
            "time_window": show.time_window,
            "character": show.character,
            "voice_id": show.voice_id,
            "target_word_count": show.target_word_count,
        }

        # Fall back to user settings for voice_id if show doesn't have one
        if not show_config["voice_id"] and settings:
            show_config["voice_id"] = settings.elevenlabs_voice_id

    try:
        result = await asyncio.to_thread(
            _run_show_pipeline_sync,
            user_id,
            device_token,
            tz,
            show_config,
            episode_id,
        )
    except Exception as e:
        logger.exception("Pipeline failed for show %d, episode %d", show_id, episode_id)
        async with async_session() as db:
            await _fail_episode(db, episode_id, str(e))
        return

    # Update episode and show in DB
    async with async_session() as db:
        episode = await db.get(Episode, episode_id)
        if episode:
            episode.status = result["status"]
            episode.title = result.get("title")
            episode.script_text = result.get("script_text")
            episode.notes_text = result.get("notes_text")
            episode.audio_path = result.get("audio_path")
            await db.commit()

        show = await db.get(Show, show_id)
        if show:
            show.last_run_at = datetime.now(timezone.utc)
            await db.commit()


def _update_episode_sync(episode_id: int, **fields):
    """Synchronously update episode fields from a worker thread."""
    import asyncio

    async def _do_update():
        async with async_session() as db:
            episode = await db.get(Episode, episode_id)
            if episode:
                for key, value in fields.items():
                    setattr(episode, key, value)
                await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_do_update())
    finally:
        loop.close()


def _run_show_pipeline_sync(
    user_id: int,
    device_token: str,
    timezone_str: str,
    show_config: dict,
    episode_id: int = 0,
) -> dict:
    """
    Synchronous pipeline execution for a show. Runs in a thread.
    Returns a dict with episode data.
    """
    from daily_podcast.config import load_config
    from daily_podcast.extract import TIME_WINDOW_DAYS, extract_notes
    from daily_podcast.personalities import get_system_prompt, get_voice_id
    from daily_podcast.speak import generate_audio
    from daily_podcast.summarize import generate_podcast_script

    config = load_config()

    # Override with user's device token
    rmapi_file = Path.home() / ".rmapi"
    rmapi_file.write_text(device_token)
    os.environ["REMARKABLE_TOKEN"] = device_token
    config.remarkable_token = device_token
    config.timezone = timezone_str

    show_slug = show_config["slug"]
    config.episodes_dir = DATA_DIR / "episodes" / str(user_id) / show_slug
    config.episodes_dir.mkdir(parents=True, exist_ok=True)

    # Voice: show-level > personality default
    voice_id = show_config.get("voice_id")
    character = show_config.get("character", "analyst")
    if voice_id:
        config.elevenlabs_voice_id = voice_id
    else:
        personality_voice = get_voice_id(character)
        if personality_voice:
            config.elevenlabs_voice_id = personality_voice

    target_words = show_config.get("target_word_count", 350)
    config.podcast_target_length = target_words

    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")

    # Determine days from time_window
    time_window = show_config.get("time_window", "7d")
    days = TIME_WINDOW_DAYS.get(time_window, 7)

    scope = show_config.get("scope", "/")

    # Step 1: Extract notes
    _update_episode_sync(episode_id, status="extracting")
    logger.info("Show '%s': extracting notes (window=%s, scope=%s)",
                show_config["name"], time_window, scope)
    notes_text = extract_notes(config, now, days=days, scope=scope)
    if not notes_text:
        return {
            "status": "failed",
            "title": f"{show_config['name']} — No notes found",
            "notes_text": "",
            "script_text": "No notes were found for this show's scope and time window.",
        }

    # Save raw notes + update DB so frontend can see progress
    notes_path = config.episodes_dir / f"notes-{date_str}.txt"
    notes_path.write_text(notes_text)
    _update_episode_sync(episode_id, status="summarizing", notes_text=notes_text)

    # Step 2: Generate script
    logger.info("Show '%s': generating script (character=%s)", show_config["name"], character)
    title, script = generate_podcast_script(notes_text, config, personality=character)

    script_path = config.episodes_dir / f"script-{date_str}.txt"
    script_path.write_text(script)
    _update_episode_sync(episode_id, status="generating_audio", title=title, script_text=script)

    # Step 3: Generate audio
    logger.info("Show '%s': generating audio", show_config["name"])
    mp3_path = config.episodes_dir / f"{show_slug}-{date_str}-{episode_id}.mp3"
    generate_audio(script, mp3_path, config)

    return {
        "status": "ready",
        "title": title,
        "script_text": script,
        "notes_text": notes_text,
        "audio_path": str(mp3_path),
    }


async def _fail_episode(db, episode_id: int, error: str):
    """Mark an episode as failed."""
    episode = await db.get(Episode, episode_id)
    if episode:
        episode.status = "failed"
        episode.script_text = f"Error: {error}"
        await db.commit()
    logger.error("Episode %d failed: %s", episode_id, error)


# --- Scheduler ---


async def check_scheduled_shows():
    """
    Check all active scheduled shows and generate episodes for any that are due.
    Called periodically by the background scheduler.
    """
    from datetime import timedelta

    now_utc = datetime.now(timezone.utc)

    async with async_session() as db:
        result = await db.execute(
            select(Show).where(
                Show.is_active == True,
                Show.cadence != "on-demand",
            )
        )
        shows = result.scalars().all()

    for show in shows:
        try:
            if _is_show_due(show, now_utc):
                logger.info("Scheduler: show '%s' (id=%d) is due, generating episode",
                            show.name, show.id)
                async with async_session() as db:
                    date_str = now_utc.strftime("%Y-%m-%d")
                    episode = Episode(
                        user_id=show.user_id,
                        show_id=show.id,
                        date=date_str,
                        status="pending",
                        title=f"{show.name} — {date_str}",
                    )
                    db.add(episode)
                    await db.commit()
                    await db.refresh(episode)
                    episode_id = episode.id

                await run_pipeline_for_show(show.id, episode_id)
        except Exception:
            logger.exception("Scheduler error for show %d (%s)", show.id, show.name)


def _is_show_due(show: Show, now_utc: datetime) -> bool:
    """Check if a scheduled show is due to run."""
    from datetime import timedelta

    cadence = show.cadence
    last_run = show.last_run_at

    if cadence == "on-demand":
        return False

    # If never run, it's due
    if last_run is None:
        return True

    # Ensure last_run is tz-aware
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)

    elapsed = now_utc - last_run

    if cadence == "daily":
        return elapsed >= timedelta(hours=20)  # ~daily with margin
    elif cadence == "weekly":
        return elapsed >= timedelta(days=6, hours=20)
    elif cadence == "monthly":
        return elapsed >= timedelta(days=28)

    return False
