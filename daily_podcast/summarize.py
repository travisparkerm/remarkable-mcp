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
) -> tuple[str, str]:
    """
    Generate a podcast script from extracted notes using Claude API.

    Args:
        notes_text: Extracted and concatenated notes text.
        config: Pipeline configuration.
        personality: Personality key (e.g. "analyst", "coach"). Falls back to default.

    Returns:
        Tuple of (title, script_text). Title is a short 4-7 word
        content-based episode title.

    Raises:
        anthropic.APIError: If the API call fails.
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    system = get_system_prompt(
        personality or "analyst",
        target_word_count=config.podcast_target_length,
    )

    # Ask for a title on the first line so we can parse it out
    system += (
        "\n\nIMPORTANT: Your very first line must be a short, evocative episode title "
        "(4-7 words) that captures the essence of the content. Do NOT include the show "
        "name or date — just a descriptive title. Write it on its own line, then leave "
        "a blank line before the script begins."
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

    full_text = message.content[0].text.strip()

    # Parse title from first line
    lines = full_text.split("\n", 1)
    title = lines[0].strip()
    script = lines[1].strip() if len(lines) > 1 else full_text

    word_count = len(script.split())
    logger.info("Generated script: %d words, title: %s", word_count, title)
    return title, script
