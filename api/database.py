"""
Database models and session management.
SQLite via SQLAlchemy async + aiosqlite.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import ForeignKey, String, Text, Integer, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DATABASE_DIR = Path(__file__).resolve().parent.parent / "data"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_DIR / 'remarkable_podcast.db'}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _slugify(text: str) -> str:
    """Generate a URL-safe slug from text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64]


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    picture: Mapped[str] = mapped_column(String(512), nullable=True)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    devices: Mapped[list["RemarkableDevice"]] = relationship(back_populates="user")
    shows: Mapped[list["Show"]] = relationship(back_populates="user")
    episodes: Mapped[list["Episode"]] = relationship(back_populates="user")
    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False)


class RemarkableDevice(Base):
    __tablename__ = "remarkable_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_token: Mapped[str] = mapped_column(Text, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="devices")


class Show(Base):
    __tablename__ = "shows"
    __table_args__ = (UniqueConstraint("user_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="/")  # JSON list of paths
    time_window: Mapped[str] = mapped_column(String(10), nullable=False, default="7d")  # 1d, 7d, 30d, all
    character: Mapped[str] = mapped_column(String(32), nullable=False, default="analyst")
    cadence: Mapped[str] = mapped_column(String(20), nullable=False, default="on-demand")  # daily, weekly, monthly, on-demand
    schedule: Mapped[str] = mapped_column(String(64), nullable=True)  # e.g. "friday 18:00", "1st 09:00"
    voice_id: Mapped[str] = mapped_column(String(255), nullable=True)
    target_word_count: Mapped[int] = mapped_column(Integer, default=350)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="shows")
    episodes: Mapped[list["Episode"]] = relationship(back_populates="show")


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    show_id: Mapped[int] = mapped_column(ForeignKey("shows.id"), nullable=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    script_text: Mapped[str] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str] = mapped_column(String(512), nullable=True)
    notes_text: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / processing / ready / failed
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="episodes")
    show: Mapped["Show"] = relationship(back_populates="episodes")


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw")
    elevenlabs_voice_id: Mapped[str] = mapped_column(String(255), nullable=True)
    podcast_voice_description: Mapped[str] = mapped_column(Text, nullable=True)
    target_word_count: Mapped[int] = mapped_column(Integer, default=350)
    personality: Mapped[str] = mapped_column(String(32), default="analyst")

    user: Mapped["User"] = relationship(back_populates="settings")


async def init_db():
    """Create all tables and run lightweight migrations."""
    import sqlalchemy as sa

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migrate: add show_id column to episodes if missing
        result = await conn.execute(sa.text("PRAGMA table_info(episodes)"))
        columns = {row[1] for row in result}
        if "show_id" not in columns:
            await conn.execute(
                sa.text("ALTER TABLE episodes ADD COLUMN show_id INTEGER REFERENCES shows(id)")
            )
