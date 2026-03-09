"""
Text-to-speech module.

Converts podcast scripts to MP3 audio via ElevenLabs API.
"""

import logging
from pathlib import Path

from elevenlabs import ElevenLabs

from daily_podcast.config import PodcastConfig

logger = logging.getLogger(__name__)


def generate_audio(script: str, output_path: Path, config: PodcastConfig) -> Path:
    """
    Convert a podcast script to an MP3 file using ElevenLabs.

    Args:
        script: The podcast script text.
        output_path: Path to write the MP3 file.
        config: Pipeline configuration.

    Returns:
        Path to the generated MP3 file.

    Raises:
        Exception: If TTS generation fails.
    """
    client = ElevenLabs(api_key=config.elevenlabs_api_key)

    logger.info("Generating audio with voice %s...", config.elevenlabs_voice_id)

    audio_generator = client.text_to_speech.convert(
        voice_id=config.elevenlabs_voice_id,
        text=script,
        model_id=config.elevenlabs_model_id,
        output_format="mp3_44100_128",
    )

    # ElevenLabs returns an iterator of bytes chunks
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    file_size = output_path.stat().st_size
    logger.info("Audio saved: %s (%d bytes)", output_path, file_size)
    return output_path
