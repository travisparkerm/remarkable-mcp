"""
LLM summarization module.

Takes extracted note text and produces a podcast script via Claude API.
"""

import logging

import anthropic

from daily_podcast.config import PodcastConfig
from daily_podcast.personalities import get_system_prompt

logger = logging.getLogger(__name__)


def generate_podcast_script(
    notes_text: str, config: PodcastConfig, personality: str = ""
) -> str:
    """
    Generate a podcast script from extracted notes using Claude API.

    Args:
        notes_text: Extracted and concatenated notes text.
        config: Pipeline configuration.
        personality: Personality key (e.g. "analyst", "coach"). Falls back to default.

    Returns:
        Podcast script text.

    Raises:
        anthropic.APIError: If the API call fails.
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    system = get_system_prompt(
        personality or "analyst",
        target_word_count=config.podcast_target_length,
    )

    logger.info(
        "Generating podcast script (personality=%s, target: %d words)...",
        personality or "analyst",
        config.podcast_target_length,
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Here are today's handwritten notes:\n\n{notes_text}",
            }
        ],
    )

    script = message.content[0].text
    word_count = len(script.split())
    logger.info("Generated script: %d words.", word_count)
    return script
