"""
LLM summarization module.

Takes extracted note text and produces a podcast script via Claude API.
"""

import logging

import anthropic

from daily_podcast.config import PodcastConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a personal podcast host creating a short daily audio recap of handwritten notes.

Your job is to synthesize the day's notes into a natural, conversational podcast script
that sounds like a thoughtful evening reflection — not a robotic readback.

Guidelines:
- Tone: {voice}
- Target length: {target_length} words (roughly 2 minutes spoken)
- Structure: brief intro → key themes/ideas → action items or follow-ups → brief editorial reflection
- Synthesize and connect ideas across separate notes — don't just list them
- Call out any action items or to-dos you find
- Add light editorial commentary (e.g., "You spent a lot of time on X today — seems like that's becoming a priority")
- Handle messy/incomplete OCR gracefully — skip gibberish, work with what's intelligible
- If notes are very short or sparse, make the script proportionally shorter (don't pad)
- Write the script as spoken text only — no stage directions, no [brackets], no headings
- Address the listener as "you" (it's their personal notes)
- Start directly with content (e.g., "Hey, so today was interesting..." not "Welcome to episode 47...")
"""


def generate_podcast_script(notes_text: str, config: PodcastConfig) -> str:
    """
    Generate a podcast script from extracted notes using Claude API.

    Args:
        notes_text: Extracted and concatenated notes text.
        config: Pipeline configuration.

    Returns:
        Podcast script text (300-400 words).

    Raises:
        anthropic.APIError: If the API call fails.
    """
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    system = SYSTEM_PROMPT.format(
        voice=config.podcast_voice,
        target_length=config.podcast_target_length,
    )

    logger.info("Generating podcast script (target: %d words)...", config.podcast_target_length)

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
