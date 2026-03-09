"""
API routes for episodes, reMarkable device management, settings, and generation.
All routes require authentication.
"""

import asyncio
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
    User,
    UserSettings,
    async_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --- Pydantic models ---


class RegisterDeviceRequest(BaseModel):
    code: str


class GenerateRequest(BaseModel):
    date: str  # YYYY-MM-DD


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


# --- Episodes ---


@router.get("/episodes")
async def list_episodes(user: User = Depends(get_current_user)):
    """List all episodes for the current user, newest first."""
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.user_id == user.id)
            .order_by(Episode.date.desc())
        )
        episodes = result.scalars().all()
        return [
            {
                "id": ep.id,
                "date": ep.date,
                "title": ep.title,
                "status": ep.status,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
            }
            for ep in episodes
        ]


@router.get("/episodes/{date}")
async def get_episode(date: str, user: User = Depends(get_current_user)):
    """Get a specific episode by date, including script text."""
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.user_id == user.id, Episode.date == date)
        )
        ep = result.scalar_one_or_none()
        if ep is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        return {
            "id": ep.id,
            "date": ep.date,
            "title": ep.title,
            "script_text": ep.script_text,
            "notes_text": ep.notes_text,
            "status": ep.status,
            "audio_path": ep.audio_path,
            "created_at": ep.created_at.isoformat() if ep.created_at else None,
        }


@router.get("/episodes/{date}/audio")
async def stream_audio(date: str, user: User = Depends(get_current_user)):
    """Stream the MP3 file for an episode."""
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.user_id == user.id, Episode.date == date)
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
        filename=f"episode-{date}.mp3",
    )


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


# --- Generation ---


@router.post("/generate")
async def generate_episode(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Trigger podcast generation for a specific date."""
    from api.worker import run_pipeline_for_user

    date = body.date

    # Check if episode already exists and is processing/ready
    async with async_session() as db:
        result = await db.execute(
            select(Episode)
            .where(Episode.user_id == user.id, Episode.date == date)
        )
        existing = result.scalar_one_or_none()
        if existing and existing.status == "ready":
            return {
                "status": existing.status,
                "message": "Episode is already ready",
            }

        # Create or reset episode record
        if existing:
            existing.status = "pending"
            existing.script_text = None
            existing.notes_text = None
            existing.audio_path = None
            existing.title = None
            await db.commit()
            episode_id = existing.id
        else:
            episode = Episode(user_id=user.id, date=date, status="pending")
            db.add(episode)
            await db.commit()
            episode_id = episode.id

    # Run pipeline in background
    background_tasks.add_task(run_pipeline_for_user, user.id, date)

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
            # Create default settings
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
