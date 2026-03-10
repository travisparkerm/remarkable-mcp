"""
API routes for shows, episodes, reMarkable device management, settings, and generation.
All routes require authentication.
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import get_current_user
from api.database import (
    Episode,
    RemarkableDevice,
    Show,
    User,
    UserSettings,
    _slugify,
    async_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# In-memory cache for reMarkable library per user (user_id -> (timestamp, items))
_library_cache: dict[int, tuple[float, list[dict]]] = {}
LIBRARY_CACHE_TTL = 300  # 5 minutes


# --- Serialization helpers ---


def _serialize_show(s: Show) -> dict:
    """Convert Show ORM object to API response dict."""
    return {
        "id": s.id,
        "name": s.name,
        "slug": s.slug,
        "source_type": s.source_type,
        "source_config": s.source_config,
        "scope": s.scope,
        "time_window": s.time_window,
        "character": s.character,
        "cadence": s.cadence,
        "schedule": s.schedule,
        "voice_id": s.voice_id,
        "target_word_count": s.target_word_count,
        "is_active": s.is_active,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _serialize_episode(ep: Episode, include_text: bool = False) -> dict:
    """Convert Episode ORM object to API response dict."""
    d = {
        "id": ep.id,
        "show_id": ep.show_id,
        "date": ep.date,
        "title": ep.title,
        "status": ep.status,
        "created_at": ep.created_at.isoformat() if ep.created_at else None,
    }
    if include_text:
        d["script_text"] = ep.script_text
        d["notes_text"] = ep.notes_text
        d["audio_path"] = ep.audio_path
    return d


# --- Pydantic models ---


class RegisterDeviceRequest(BaseModel):
    code: str


class GenerateRequest(BaseModel):
    date: str  # YYYY-MM-DD


class ShowCreate(BaseModel):
    name: str
    source_type: str = "remarkable"  # remarkable, photo_library
    source_config: str | None = None  # JSON
    scope: str = "/"  # JSON list of paths or single path (remarkable)
    time_window: str = "7d"  # 1d, 7d, 30d, all
    character: str = "analyst"
    cadence: str = "on-demand"  # daily, weekly, monthly, on-demand
    schedule: str | None = None
    voice_id: str | None = None
    target_word_count: int = 350


class ShowUpdate(BaseModel):
    name: str | None = None
    source_type: str | None = None
    source_config: str | None = None
    scope: str | None = None
    time_window: str | None = None
    character: str | None = None
    cadence: str | None = None
    schedule: str | None = None
    voice_id: str | None = None
    target_word_count: int | None = None
    is_active: bool | None = None


class SettingsUpdate(BaseModel):
    timezone: str | None = None
    elevenlabs_voice_id: str | None = None
    podcast_voice_description: str | None = None
    target_word_count: int | None = None
    personality: str | None = None


# --- Personalities ---


@router.get("/personalities")
async def list_personalities():
    """List all available podcast personalities."""
    from daily_podcast.personalities import list_personalities

    return list_personalities()


# --- Shows ---


@router.get("/shows")
async def list_shows(user: User = Depends(get_current_user)):
    """List all shows for the current user."""
    async with async_session() as db:
        result = await db.execute(
            select(Show)
            .where(Show.user_id == user.id)
            .order_by(Show.created_at.desc())
        )
        shows = result.scalars().all()
        return [_serialize_show(s) for s in shows]


@router.post("/shows")
async def create_show(body: ShowCreate, user: User = Depends(get_current_user)):
    """Create a new show."""
    slug = _slugify(body.name)
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid show name")

    async with async_session() as db:
        # Check for duplicate slug
        result = await db.execute(
            select(Show).where(Show.user_id == user.id, Show.slug == slug)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A show with this name already exists")

        show = Show(
            user_id=user.id,
            name=body.name,
            slug=slug,
            source_type=body.source_type,
            source_config=body.source_config,
            scope=body.scope,
            time_window=body.time_window,
            character=body.character,
            cadence=body.cadence,
            schedule=body.schedule,
            voice_id=body.voice_id,
            target_word_count=body.target_word_count,
        )
        db.add(show)
        await db.commit()
        await db.refresh(show)

        return _serialize_show(show)


@router.get("/shows/{show_id}")
async def get_show(show_id: int, user: User = Depends(get_current_user)):
    """Get a specific show."""
    async with async_session() as db:
        result = await db.execute(
            select(Show).where(Show.id == show_id, Show.user_id == user.id)
        )
        show = result.scalar_one_or_none()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

        return _serialize_show(show)


@router.put("/shows/{show_id}")
async def update_show(
    show_id: int, body: ShowUpdate, user: User = Depends(get_current_user)
):
    """Update a show."""
    async with async_session() as db:
        result = await db.execute(
            select(Show).where(Show.id == show_id, Show.user_id == user.id)
        )
        show = result.scalar_one_or_none()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

        if body.name is not None:
            show.name = body.name
            show.slug = _slugify(body.name)
        if body.source_type is not None:
            show.source_type = body.source_type
        if body.source_config is not None:
            show.source_config = body.source_config
        if body.scope is not None:
            show.scope = body.scope
        if body.time_window is not None:
            show.time_window = body.time_window
        if body.character is not None:
            show.character = body.character
        if body.cadence is not None:
            show.cadence = body.cadence
        if body.schedule is not None:
            show.schedule = body.schedule
        if body.voice_id is not None:
            show.voice_id = body.voice_id
        if body.target_word_count is not None:
            show.target_word_count = body.target_word_count
        if body.is_active is not None:
            show.is_active = body.is_active

        await db.commit()
        return {"status": "ok"}


@router.delete("/shows/{show_id}")
async def delete_show(show_id: int, user: User = Depends(get_current_user)):
    """Delete a show and all its episodes."""
    async with async_session() as db:
        result = await db.execute(
            select(Show).where(Show.id == show_id, Show.user_id == user.id)
        )
        show = result.scalar_one_or_none()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

        # Delete episode files
        ep_result = await db.execute(
            select(Episode).where(Episode.show_id == show_id)
        )
        for ep in ep_result.scalars().all():
            if ep.audio_path:
                audio_file = Path(ep.audio_path)
                if audio_file.exists():
                    audio_file.unlink()
            await db.delete(ep)

        await db.delete(show)
        await db.commit()

    return {"status": "ok"}


# --- Episodes ---


@router.get("/episodes")
async def list_episodes(
    user: User = Depends(get_current_user),
    show_id: int | None = None,
):
    """List episodes, optionally filtered by show."""
    async with async_session() as db:
        query = select(Episode).where(Episode.user_id == user.id)
        if show_id is not None:
            query = query.where(Episode.show_id == show_id)
        query = query.order_by(Episode.created_at.desc())

        result = await db.execute(query)
        episodes = result.scalars().all()
        return [_serialize_episode(ep) for ep in episodes]


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: int, user: User = Depends(get_current_user)):
    """Get a specific episode by ID."""
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.id == episode_id, Episode.user_id == user.id)
        )
        ep = result.scalar_one_or_none()
        if ep is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        return _serialize_episode(ep, include_text=True)


@router.get("/episodes/{episode_id}/audio")
async def stream_audio(episode_id: int, user: User = Depends(get_current_user)):
    """Stream the MP3 file for an episode."""
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.id == episode_id, Episode.user_id == user.id)
        )
        ep = result.scalar_one_or_none()
        if ep is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        if ep.status != "ready" or not ep.audio_path:
            raise HTTPException(status_code=404, detail="Audio not available")

    audio_file = Path(ep.audio_path)
    if not audio_file.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        audio_file,
        media_type="audio/mpeg",
        filename=f"episode-{ep.date}.mp3",
        headers={"Cache-Control": "no-cache"},
    )


@router.delete("/episodes/{episode_id}")
async def delete_episode(episode_id: int, user: User = Depends(get_current_user)):
    """Delete an episode and its associated files."""
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.id == episode_id, Episode.user_id == user.id)
        )
        ep = result.scalar_one_or_none()
        if ep is None:
            raise HTTPException(status_code=404, detail="Episode not found")

        if ep.audio_path:
            audio_file = Path(ep.audio_path)
            if audio_file.exists():
                audio_file.unlink()

        await db.delete(ep)
        await db.commit()

    return {"status": "ok"}


# --- reMarkable device ---


@router.post("/remarkable/register")
async def register_device(
    body: RegisterDeviceRequest, user: User = Depends(get_current_user)
):
    """Register a reMarkable device using a one-time code."""
    from remarkable_mcp.api import register_and_get_token as rm_register

    try:
        device_token = rm_register(body.code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration failed: {e}")

    async with async_session() as db:
        device = RemarkableDevice(user_id=user.id, device_token=device_token)
        db.add(device)
        await db.commit()

    return {"status": "ok", "message": "Device registered successfully"}


@router.post("/remarkable/disconnect")
async def disconnect_device(user: User = Depends(get_current_user)):
    """Remove all registered reMarkable devices for the user."""
    async with async_session() as db:
        result = await db.execute(
            select(RemarkableDevice).where(RemarkableDevice.user_id == user.id)
        )
        devices = result.scalars().all()
        for device in devices:
            await db.delete(device)
        await db.commit()
    return {"status": "ok"}


@router.get("/remarkable/status")
async def remarkable_status(user: User = Depends(get_current_user)):
    """Check whether the user has a connected reMarkable device."""
    async with async_session() as db:
        result = await db.execute(
            select(RemarkableDevice).where(RemarkableDevice.user_id == user.id)
        )
        device = result.scalar_one_or_none()
        return {
            "connected": device is not None,
            "registered_at": (
                device.registered_at.isoformat() if device else None
            ),
        }


@router.get("/remarkable/library")
async def remarkable_library(
    user: User = Depends(get_current_user),
    refresh: bool = False,
):
    """Browse the user's reMarkable library (folder/document tree).
    Results are cached for 5 minutes. Pass ?refresh=true to force a fresh fetch.
    """
    import time

    from daily_podcast.extract import browse_library

    # Check cache first
    if not refresh and user.id in _library_cache:
        cached_at, cached_items = _library_cache[user.id]
        if time.time() - cached_at < LIBRARY_CACHE_TTL:
            return cached_items

    async with async_session() as db:
        result = await db.execute(
            select(RemarkableDevice)
            .where(RemarkableDevice.user_id == user.id)
            .order_by(RemarkableDevice.registered_at.desc())
        )
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(status_code=400, detail="No reMarkable device connected")
        device_token = device.device_token

    try:
        items = await asyncio.wait_for(
            asyncio.to_thread(browse_library, device_token),
            timeout=120,
        )
        # Cache the result
        _library_cache[user.id] = (time.time(), items)
        return items
    except asyncio.TimeoutError:
        logger.error("Browse library timed out for user %d", user.id)
        raise HTTPException(status_code=504, detail="reMarkable Cloud took too long to respond. Try again.")
    except Exception as e:
        logger.exception("Failed to browse reMarkable library")
        raise HTTPException(status_code=500, detail=f"Failed to browse library: {e}")


# --- Generation ---


@router.post("/shows/{show_id}/generate")
async def generate_show_episode(
    show_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Trigger episode generation for a specific show."""
    from api.worker import create_episode_for_show, run_pipeline_for_show

    async with async_session() as db:
        result = await db.execute(
            select(Show).where(Show.id == show_id, Show.user_id == user.id)
        )
        show = result.scalar_one_or_none()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

    episode_id = await create_episode_for_show(show)
    background_tasks.add_task(run_pipeline_for_show, show_id, episode_id)

    return {"status": "pending", "episode_id": episode_id}


# --- Settings ---


@router.get("/settings")
async def get_settings(user: User = Depends(get_current_user)):
    """Get current user settings."""
    async with async_session() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(user_id=user.id)
            db.add(settings)
            await db.commit()
            await db.refresh(settings)

        return {
            "timezone": settings.timezone,
            "elevenlabs_voice_id": settings.elevenlabs_voice_id,
            "podcast_voice_description": settings.podcast_voice_description,
            "target_word_count": settings.target_word_count,
            "personality": settings.personality or "analyst",
        }


@router.put("/settings")
async def update_settings(
    body: SettingsUpdate, user: User = Depends(get_current_user)
):
    """Update user settings."""
    async with async_session() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(user_id=user.id)
            db.add(settings)

        if body.timezone is not None:
            settings.timezone = body.timezone
        if body.elevenlabs_voice_id is not None:
            settings.elevenlabs_voice_id = body.elevenlabs_voice_id
        if body.podcast_voice_description is not None:
            settings.podcast_voice_description = body.podcast_voice_description
        if body.target_word_count is not None:
            settings.target_word_count = body.target_word_count
        if body.personality is not None:
            settings.personality = body.personality

        await db.commit()

    return {"status": "ok"}
