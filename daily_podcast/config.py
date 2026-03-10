"""
Configuration management for the daily podcast pipeline.
Loads settings from environment variables / .env file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _env(key: str, default: str = "") -> str:
    """Get env var, stripping inline comments (e.g. 'value  # comment' -> 'value')."""
    val = os.environ.get(key, default)
    # Strip inline comments: everything after ' #' or values that are just comments
    if " #" in val:
        val = val[: val.index(" #")]
    val = val.strip()
    # If the entire value is a comment, treat as empty
    if val.startswith("#"):
        return ""
    return val


def load_env():
    """Load .env files in priority order (.env.local overrides .env)."""
    load_dotenv(".env.local")
    load_dotenv(".env")


def load_config() -> "PodcastConfig":
    """Load configuration from environment variables and .env / .env.local file."""
    load_env()
    return PodcastConfig(
        remarkable_token=_env("REMARKABLE_TOKEN"),
        google_vision_api_key=_env("GOOGLE_VISION_API_KEY"),
        remarkable_root_path=_env("REMARKABLE_ROOT_PATH"),
        anthropic_api_key=_env("ANTHROPIC_API_KEY"),
        podcast_voice=_env("PODCAST_VOICE")
        or "conversational, reflective, like a personal evening recap",
        podcast_target_length=int(_env("PODCAST_TARGET_LENGTH") or "350"),
        elevenlabs_api_key=_env("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=_env("ELEVENLABS_VOICE_ID"),
        elevenlabs_model_id=_env("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2",
        feed_title=_env("FEED_TITLE") or "My Daily Notes",
        feed_base_url=_env("FEED_BASE_URL"),
        timezone=_env("TIMEZONE") or "Europe/Warsaw",
        episodes_dir=Path(_env("EPISODES_DIR") or "./episodes"),
    )


@dataclass
class PodcastConfig:
    # reMarkable
    remarkable_token: str = ""
    google_vision_api_key: str = ""
    remarkable_root_path: str = ""

    # LLM
    anthropic_api_key: str = ""
    podcast_voice: str = "conversational, reflective, like a personal evening recap"
    podcast_target_length: int = 350

    # TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # Feed
    feed_title: str = "My Daily Notes"
    feed_base_url: str = ""

    # Settings
    timezone: str = "Europe/Warsaw"
    episodes_dir: Path = field(default_factory=lambda: Path("./episodes"))
