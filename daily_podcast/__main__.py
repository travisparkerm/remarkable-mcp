"""
Entry point for `python -m daily_podcast` or `daily-podcast` CLI.
"""

import argparse
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from daily_podcast.config import load_config
from daily_podcast.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Generate a daily podcast from reMarkable notes.")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to look back for notes (default: 1 = today only).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("daily_podcast.log"),
        ],
    )
    logger = logging.getLogger("daily_podcast")

    config = load_config()

    # Parse target date
    target_date = None
    if args.date:
        tz = ZoneInfo(config.timezone)
        target_date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=tz)

    try:
        generated = run_pipeline(config, target_date, days=args.days)
        if generated:
            logger.info("Episode generated successfully.")
        else:
            logger.info("No episode generated (no new notes or already exists).")
    except Exception:
        logger.exception("Pipeline failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
