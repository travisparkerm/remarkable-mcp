"""
Database models and session management.
SQLite via SQLAlchemy async + aiosqlite.
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import ForeignKey, String, Text, Integer, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DATABASE_DIR = Path(__file__).resolve().parent.parent / "data"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_DIR / 'remarkable_podcast.db'}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
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


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw")
    elevenlabs_voice_id: Mapped[str] = mapped_column(String(255), nullable=True)
    podcast_voice_description: Mapped[str] = mapped_column(Text, nullable=True)
    target_word_count: Mapped[int] = mapped_column(Integer, default=350)

    user: Mapped["User"] = relationship(back_populates="settings")


async def init_db():
    """Create all tables."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
