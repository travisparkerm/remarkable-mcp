"""
Photo Library API routes: upload, albums, OCR, and CRUD.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import get_current_user
from api.database import Album, Photo, User, async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/photos", tags=["photos"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PHOTOS_DIR = DATA_DIR / "photos"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp", "application/octet-stream", ""}


# --- Pydantic models ---


class AlbumCreate(BaseModel):
    name: str
    description: str | None = None


class AlbumUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class PhotoUpdate(BaseModel):
    user_date: str | None = None
    user_notes: str | None = None
    album_id: int | None = None
    ocr_text: str | None = None


class PhotoBatchUpdate(BaseModel):
    photo_ids: list[int]
    album_id: int | None = None


# --- Helpers ---


def _photo_dir(user_id: int) -> Path:
    d = PHOTOS_DIR / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _thumbnail_dir(user_id: int) -> Path:
    d = THUMBNAILS_DIR / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _photo_response(p: Photo) -> dict:
    return {
        "id": p.id,
        "album_id": p.album_id,
        "filename": p.filename,
        "ocr_status": p.ocr_status,
        "ocr_text": p.ocr_text,
        "ocr_confidence": p.ocr_confidence,
        "ocr_completed_at": p.ocr_completed_at.isoformat() if p.ocr_completed_at else None,
        "user_date": p.user_date,
        "user_notes": p.user_notes,
        "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
        "has_thumbnail": bool(p.thumbnail_path),
    }


def _album_response(a: Album) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


async def _generate_thumbnail(image_path: Path, thumb_path: Path):
    """Generate a thumbnail using PIL in a thread."""
    def _do():
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img.thumbnail((300, 300))
                # Convert HEIC/HEIF to RGB for JPEG output
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=80)
        except Exception:
            logger.exception("Failed to generate thumbnail for %s", image_path)

    await asyncio.to_thread(_do)


async def _run_ocr_for_photo(photo_id: int):
    """Run Google Vision OCR on a photo and update its record."""
    async with async_session() as db:
        photo = await db.get(Photo, photo_id)
        if not photo or photo.ocr_status not in ("pending", "failed"):
            return
        photo.ocr_status = "processing"
        await db.commit()

    try:
        text, confidence = await asyncio.to_thread(_ocr_sync, photo.file_path)
    except Exception as e:
        logger.exception("OCR failed for photo %d", photo_id)
        async with async_session() as db:
            photo = await db.get(Photo, photo_id)
            if photo:
                photo.ocr_status = "failed"
                photo.ocr_text = f"OCR error: {e}"
                await db.commit()
        return

    async with async_session() as db:
        photo = await db.get(Photo, photo_id)
        if photo:
            photo.ocr_status = "ready"
            photo.ocr_text = text
            photo.ocr_confidence = confidence
            photo.ocr_completed_at = datetime.now(timezone.utc)
            await db.commit()


def _ocr_sync(file_path: str) -> tuple[str, float | None]:
    """Synchronous Google Vision OCR on an image file. Returns (text, confidence)."""
    import io

    from google.cloud import vision
    from PIL import Image

    # Ensure we send JPEG/PNG bytes that Vision API can handle
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext in (".jpg", ".jpeg", ".png"):
        image_bytes = p.read_bytes()
    else:
        # Convert to JPEG for compatibility
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        img = Image.open(p)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        image_bytes = buf.getvalue()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(response.error.message)

    texts = response.text_annotations
    if not texts:
        return "", None

    full_text = texts[0].description.strip()
    # Average confidence from individual word annotations
    confidence = None
    if len(texts) > 1:
        confs = [
            t.confidence for t in response.full_text_annotation.pages[0].blocks
            if hasattr(t, "confidence") and t.confidence
        ] if response.full_text_annotation and response.full_text_annotation.pages else []
        if confs:
            confidence = sum(confs) / len(confs)

    return full_text, confidence


# --- Albums ---


@router.get("/albums")
async def list_albums(user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Album).where(Album.user_id == user.id).order_by(Album.created_at.desc())
        )
        albums = result.scalars().all()

        # Get photo counts per album
        album_list = []
        for a in albums:
            count_result = await db.execute(
                select(Photo.id).where(Photo.album_id == a.id)
            )
            count = len(count_result.all())
            resp = _album_response(a)
            resp["photo_count"] = count
            album_list.append(resp)

        return album_list


@router.post("/albums")
async def create_album(body: AlbumCreate, user: User = Depends(get_current_user)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Album name is required")

    async with async_session() as db:
        album = Album(user_id=user.id, name=body.name.strip(), description=body.description)
        db.add(album)
        await db.commit()
        await db.refresh(album)
        return _album_response(album)


@router.put("/albums/{album_id}")
async def update_album(album_id: int, body: AlbumUpdate, user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Album).where(Album.id == album_id, Album.user_id == user.id)
        )
        album = result.scalar_one_or_none()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")

        if body.name is not None:
            album.name = body.name.strip()
        if body.description is not None:
            album.description = body.description

        await db.commit()
        return {"status": "ok"}


@router.delete("/albums/{album_id}")
async def delete_album(album_id: int, user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Album).where(Album.id == album_id, Album.user_id == user.id)
        )
        album = result.scalar_one_or_none()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")

        # Unlink photos from album (don't delete them)
        photos_result = await db.execute(
            select(Photo).where(Photo.album_id == album_id)
        )
        for p in photos_result.scalars().all():
            p.album_id = None

        await db.delete(album)
        await db.commit()

    return {"status": "ok"}


# --- Photo Upload ---


@router.post("/upload")
async def upload_photos(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    files: list[UploadFile] = File(...),
    album_id: int | None = None,
):
    """Upload one or more photos. OCR runs automatically in the background."""
    if album_id:
        async with async_session() as db:
            result = await db.execute(
                select(Album).where(Album.id == album_id, Album.user_id == user.id)
            )
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Album not found")

    uploaded = []
    photo_dir = _photo_dir(user.id)
    thumb_dir = _thumbnail_dir(user.id)
    logger.info("Upload request: %d files, album_id=%s, user=%d", len(files), album_id, user.id)

    for f in files:
        # Validate type
        content_type = f.content_type or ""
        orig_filename = f.filename or ""
        file_ext = orig_filename.lower().rsplit(".", 1)[-1] if "." in orig_filename else ""
        logger.info(
            "Upload file: %s, content_type=%s, ext=%s",
            orig_filename, content_type, file_ext,
        )
        if content_type not in ALLOWED_TYPES:
            # Also allow by extension
            if file_ext not in ("jpg", "jpeg", "png", "heic", "heif"):
                logger.warning("Skipping file %s: unsupported type", orig_filename)
                continue  # Skip unsupported files

        # Read file
        data = await f.read()
        if len(data) > MAX_UPLOAD_SIZE:
            logger.warning("Skipping file %s: too large (%d bytes)", orig_filename, len(data))
            continue  # Skip oversized files

        # Save to disk — convert HEIC/HEIF to JPEG immediately
        orig_ext = (f.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
        file_id = uuid.uuid4().hex[:12]

        if orig_ext in ("heic", "heif"):
            # Convert HEIC to JPEG using pillow-heif
            import io
            try:
                from PIL import Image
                import pillow_heif
                pillow_heif.register_heif_opener()
                img = Image.open(io.BytesIO(data))
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=90)
                data = buf.getvalue()
            except Exception:
                logger.exception("Failed to convert HEIC for %s", f.filename)
                continue
            ext = "jpg"
        else:
            ext = orig_ext

        filename = f"{file_id}.{ext}"
        file_path = photo_dir / filename
        file_path.write_bytes(data)

        thumb_path = thumb_dir / f"{file_id}_thumb.jpg"

        # Create DB record
        async with async_session() as db:
            photo = Photo(
                user_id=user.id,
                album_id=album_id,
                filename=f.filename or filename,
                file_path=str(file_path),
                thumbnail_path=str(thumb_path),
                ocr_status="pending",
            )
            db.add(photo)
            await db.commit()
            await db.refresh(photo)
            photo_id = photo.id

        # Queue background work: thumbnail + OCR
        background_tasks.add_task(_generate_thumbnail, file_path, thumb_path)
        background_tasks.add_task(_run_ocr_for_photo, photo_id)

        uploaded.append({"id": photo_id, "filename": f.filename})

    return {"uploaded": uploaded, "count": len(uploaded)}


# --- Photo CRUD ---


@router.get("")
async def list_photos(
    user: User = Depends(get_current_user),
    album_id: int | None = None,
):
    """List photos, optionally filtered by album. album_id=0 returns unsorted photos."""
    async with async_session() as db:
        query = select(Photo).where(Photo.user_id == user.id)
        if album_id is not None:
            if album_id == 0:
                query = query.where(Photo.album_id == None)
            else:
                query = query.where(Photo.album_id == album_id)
        query = query.order_by(Photo.uploaded_at.desc())

        result = await db.execute(query)
        photos = result.scalars().all()
        return [_photo_response(p) for p in photos]


@router.get("/{photo_id}")
async def get_photo(photo_id: int, user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
        )
        photo = result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        return _photo_response(photo)


@router.get("/{photo_id}/image")
async def get_photo_image(photo_id: int, user: User = Depends(get_current_user)):
    """Serve the full-size photo image."""
    async with async_session() as db:
        result = await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
        )
        photo = result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

    file_path = Path(photo.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(file_path, media_type="image/jpeg")


@router.get("/{photo_id}/thumbnail")
async def get_photo_thumbnail(photo_id: int, user: User = Depends(get_current_user)):
    """Serve the thumbnail image."""
    async with async_session() as db:
        result = await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
        )
        photo = result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

    if photo.thumbnail_path:
        thumb = Path(photo.thumbnail_path)
        if thumb.exists():
            return FileResponse(thumb, media_type="image/jpeg")

    # Fall back to full image
    file_path = Path(photo.file_path)
    if file_path.exists():
        return FileResponse(file_path, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Thumbnail not found")


@router.put("/{photo_id}")
async def update_photo(photo_id: int, body: PhotoUpdate, user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
        )
        photo = result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        if body.user_date is not None:
            photo.user_date = body.user_date or None
        if body.user_notes is not None:
            photo.user_notes = body.user_notes or None
        if body.album_id is not None:
            photo.album_id = body.album_id if body.album_id > 0 else None
        if body.ocr_text is not None:
            # Manual OCR text edit
            photo.ocr_text = body.ocr_text
            photo.ocr_status = "ready"

        await db.commit()
        return {"status": "ok"}


@router.delete("/{photo_id}")
async def delete_photo(photo_id: int, user: User = Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
        )
        photo = result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        # Delete files
        for path_str in (photo.file_path, photo.thumbnail_path):
            if path_str:
                p = Path(path_str)
                if p.exists():
                    p.unlink()

        await db.delete(photo)
        await db.commit()

    return {"status": "ok"}


@router.post("/{photo_id}/retry-ocr")
async def retry_ocr(
    photo_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Retry OCR for a failed or completed photo."""
    async with async_session() as db:
        result = await db.execute(
            select(Photo).where(Photo.id == photo_id, Photo.user_id == user.id)
        )
        photo = result.scalar_one_or_none()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        photo.ocr_status = "pending"
        await db.commit()

    background_tasks.add_task(_run_ocr_for_photo, photo_id)
    return {"status": "ok"}


@router.post("/batch-update")
async def batch_update_photos(body: PhotoBatchUpdate, user: User = Depends(get_current_user)):
    """Move multiple photos to an album."""
    async with async_session() as db:
        for pid in body.photo_ids:
            result = await db.execute(
                select(Photo).where(Photo.id == pid, Photo.user_id == user.id)
            )
            photo = result.scalar_one_or_none()
            if photo:
                photo.album_id = body.album_id if body.album_id and body.album_id > 0 else None

        await db.commit()

    return {"status": "ok"}
