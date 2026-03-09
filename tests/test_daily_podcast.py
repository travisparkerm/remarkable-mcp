"""Tests for the daily podcast pipeline modules."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from daily_podcast.config import PodcastConfig
from daily_podcast.feed import generate_feed
from daily_podcast.pipeline import run_pipeline


def _make_config(tmpdir: Path) -> PodcastConfig:
    return PodcastConfig(
        episodes_dir=tmpdir,
        feed_title="Test Podcast",
        feed_base_url="https://example.com/podcast",
        timezone="UTC",
    )


def test_feed_generation_with_episodes():
    """Feed generator produces valid RSS XML with episode entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = _make_config(tmpdir)

        # Create a fake episode
        mp3_path = tmpdir / "episode-2025-01-15.mp3"
        mp3_path.write_bytes(b"\x00" * 16000 * 60)  # ~60 seconds at 128kbps

        script_path = tmpdir / "script-2025-01-15.txt"
        script_path.write_text("Today you worked on testing the podcast pipeline.")

        feed_path = generate_feed(config)

        assert feed_path.exists()
        content = feed_path.read_text()
        assert "<title>Test Podcast</title>" in content
        assert "episode-2025-01-15.mp3" in content
        assert "Notes for 2025-01-15" in content
        assert "https://example.com/podcast/episode-2025-01-15.mp3" in content


def test_feed_generation_no_episodes():
    """Feed generator handles empty episodes directory gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(Path(tmpdir))
        feed_path = generate_feed(config)
        # feed.xml path is returned but may not have content if no episodes
        assert feed_path == Path(tmpdir) / "feed.xml"


def test_feed_multiple_episodes_reverse_chronological():
    """Episodes appear in reverse chronological order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = _make_config(tmpdir)

        for date in ["2025-01-13", "2025-01-14", "2025-01-15"]:
            (tmpdir / f"episode-{date}.mp3").write_bytes(b"\x00" * 1000)

        feed_path = generate_feed(config)
        content = feed_path.read_text()

        # 15th should appear before 13th in the feed
        pos_15 = content.index("2025-01-15")
        pos_13 = content.index("2025-01-13")
        assert pos_15 < pos_13


def test_pipeline_idempotency():
    """Running pipeline twice for same date doesn't create duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = _make_config(tmpdir)
        config.anthropic_api_key = "test"
        config.elevenlabs_api_key = "test"
        config.elevenlabs_voice_id = "test"

        # Pre-create episode file
        (tmpdir / "episode-2025-01-15.mp3").write_bytes(b"\x00" * 1000)

        tz = ZoneInfo("UTC")
        target = datetime(2025, 1, 15, tzinfo=tz)
        result = run_pipeline(config, target)
        assert result is False  # Should skip


def test_pipeline_no_notes_skips():
    """Pipeline skips gracefully when no notes are found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config = _make_config(tmpdir)

        tz = ZoneInfo("UTC")
        target = datetime(2025, 1, 15, tzinfo=tz)

        with patch("daily_podcast.pipeline.extract_notes", return_value=""):
            result = run_pipeline(config, target)
            assert result is False
