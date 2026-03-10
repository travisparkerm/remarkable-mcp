"""Tests for the daily podcast pipeline modules."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from daily_podcast.config import PodcastConfig
from daily_podcast.extract import (
    _parse_date_header,
    _parse_scope,
    _path_matches_scope,
    filter_content_by_date,
    TIME_WINDOW_DAYS,
)
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

        mp3_path = tmpdir / "episode-2025-01-15.mp3"
        mp3_path.write_bytes(b"\x00" * 16000 * 60)

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

        (tmpdir / "episode-2025-01-15.mp3").write_bytes(b"\x00" * 1000)

        tz = ZoneInfo("UTC")
        target = datetime(2025, 1, 15, tzinfo=tz)
        result = run_pipeline(config, target)
        assert result is False


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


# --- Date header parsing tests ---


class TestParseDateHeader:
    def test_long_month_day_year(self):
        assert _parse_date_header("March 9, 2026") == datetime(2026, 3, 9)

    def test_short_month_day_year(self):
        assert _parse_date_header("Mar 9, 2026") == datetime(2026, 3, 9)

    def test_month_day_year_no_comma(self):
        assert _parse_date_header("March 9 2026") == datetime(2026, 3, 9)

    def test_day_month_year(self):
        assert _parse_date_header("9 March 2026") == datetime(2026, 3, 9)

    def test_iso_format(self):
        assert _parse_date_header("2026-03-09") == datetime(2026, 3, 9)

    def test_us_slash_format(self):
        assert _parse_date_header("3/9/2026") == datetime(2026, 3, 9)

    def test_us_dash_format(self):
        assert _parse_date_header("3-9-2026") == datetime(2026, 3, 9)

    def test_not_a_date(self):
        assert _parse_date_header("Some random text") is None

    def test_empty_line(self):
        assert _parse_date_header("") is None

    def test_whitespace_stripped(self):
        assert _parse_date_header("  March 9, 2026  ") == datetime(2026, 3, 9)

    def test_two_digit_year_month_name(self):
        assert _parse_date_header("Mar 9, 26") == datetime(2026, 3, 9)

    def test_two_digit_year_slash(self):
        assert _parse_date_header("3/9/26") == datetime(2026, 3, 9)

    def test_two_digit_year_day_month(self):
        assert _parse_date_header("9 March 26") == datetime(2026, 3, 9)

    def test_two_digit_year_dash(self):
        assert _parse_date_header("3-9-26") == datetime(2026, 3, 9)

    def test_inline_date_after_dashes(self):
        assert _parse_date_header("Morning Prayer ------------ Mar 20, 26") == datetime(2026, 3, 20)

    def test_inline_date_after_em_dash(self):
        assert _parse_date_header("Journal Entry — March 9, 2026") == datetime(2026, 3, 9)

    def test_inline_date_after_en_dash(self):
        assert _parse_date_header("Notes – 3/9/26") == datetime(2026, 3, 9)

    def test_inline_date_long_prefix(self):
        assert _parse_date_header("MORNING PRAYER ------------ Mar 10, 26") == datetime(2026, 3, 10)

    def test_no_separator_no_match_long_line(self):
        assert _parse_date_header("Some random text with no date at all here") is None


class TestFilterContentByDate:
    def test_filters_to_matching_date(self):
        text = (
            "March 8, 2026\n"
            "Old notes from yesterday\n"
            "March 9, 2026\n"
            "Today's notes about project X\n"
            "More details here\n"
            "March 10, 2026\n"
            "Tomorrow's notes"
        )
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 9),
            day_end=datetime(2026, 3, 10),
        )
        assert "Today's notes about project X" in result
        assert "More details here" in result
        assert "Old notes from yesterday" not in result
        assert "Tomorrow's notes" not in result

    def test_no_date_headers_returns_full_text(self):
        text = "Just some notes\nwithout any date headers"
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 9),
            day_end=datetime(2026, 3, 10),
        )
        assert result == text

    def test_no_date_headers_long_text_returns_tail(self):
        """Long docs without date headers are truncated to the tail."""
        text = "A" * 5000 + "\nrecent content here"
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 9),
            day_end=datetime(2026, 3, 10),
            tail_chars=100,
        )
        assert "recent content here" in result
        assert result.startswith("...")
        assert len(result) < 200

    def test_preamble_before_first_date_is_kept(self):
        text = (
            "Notebook Title\n"
            "March 9, 2026\n"
            "Today's notes"
        )
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 9),
            day_end=datetime(2026, 3, 10),
        )
        assert "Notebook Title" in result
        assert "Today's notes" in result

    def test_no_matching_dates_returns_empty(self):
        text = (
            "March 1, 2026\n"
            "Old stuff\n"
            "March 2, 2026\n"
            "Also old"
        )
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 9),
            day_end=datetime(2026, 3, 10),
        )
        # Only preamble (empty) would remain
        assert result.strip() == ""

    def test_inline_date_headers(self):
        """Date headers with separators (e.g. journal entries) are recognized."""
        text = (
            "2026 PRAYER JOURNAL\n"
            "Morning Prayer ------------ Jan 2, 26\n"
            "currently in lyon, france\n"
            "Morning Prayer ------------ Mar 10, 26\n"
            "working on podcast project today\n"
            "grateful for progress\n"
        )
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 10),
            day_end=datetime(2026, 3, 11),
        )
        assert "working on podcast project today" in result
        assert "grateful for progress" in result
        assert "currently in lyon, france" not in result

    def test_multi_day_range(self):
        text = (
            "March 7, 2026\nDay 7\n"
            "March 8, 2026\nDay 8\n"
            "March 9, 2026\nDay 9\n"
        )
        result = filter_content_by_date(
            text,
            day_start=datetime(2026, 3, 8),
            day_end=datetime(2026, 3, 10),
        )
        assert "Day 8" in result
        assert "Day 9" in result
        assert "Day 7" not in result


# --- Scope parsing tests ---


class TestParseScope:
    def test_root(self):
        assert _parse_scope("/") == ["/"]

    def test_empty(self):
        assert _parse_scope("") == ["/"]

    def test_single_path(self):
        assert _parse_scope("/1 - Work/") == ["/1 - Work"]

    def test_json_list(self):
        result = _parse_scope('["/1 - Work/", "/2 - Home/"]')
        assert result == ["/1 - Work", "/2 - Home"]

    def test_json_single(self):
        result = _parse_scope('["/1 - Work/"]')
        assert result == ["/1 - Work"]


class TestPathMatchesScope:
    def test_root_matches_all(self):
        assert _path_matches_scope("/anything/here", ["/"])

    def test_exact_match(self):
        assert _path_matches_scope("/1 - Work/notes", ["/1 - Work"])

    def test_no_match(self):
        assert not _path_matches_scope("/2 - Home/journal", ["/1 - Work"])

    def test_multi_scope(self):
        assert _path_matches_scope(
            "/2 - Home/journal", ["/1 - Work", "/2 - Home"]
        )


class TestTimeWindowDays:
    def test_values(self):
        assert TIME_WINDOW_DAYS["1d"] == 1
        assert TIME_WINDOW_DAYS["7d"] == 7
        assert TIME_WINDOW_DAYS["30d"] == 30
        assert TIME_WINDOW_DAYS["all"] is None
