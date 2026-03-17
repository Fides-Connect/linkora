"""
Text-to-Speech Service
Handles all text-to-speech synthesis functionality.
"""
import asyncio
import logging
from collections.abc import AsyncIterator
from google.cloud import texttospeech_v1 as tts
from google.cloud.texttospeech_v1 import TextToSpeechAsyncClient

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """Service for text-to-speech conversion using Google Cloud TTS API."""

    def __init__(self, language_code: str = 'de-DE',
                 voice_name: str = 'de-DE-Chirp3-HD-Sulafat',
                 max_concurrent_requests: int = 5) -> None:
        """
        Initialize Text-to-Speech service.

        Args:
            language_code: Language code for TTS
            voice_name: Voice name to use for synthesis
            max_concurrent_requests: Maximum concurrent API requests
        """
        self.language_code = language_code
        self.voice_name = voice_name
        self.client = TextToSpeechAsyncClient()

        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        logger.info("TTS service configured: language=%s, voice=%s, max_concurrent=%s", language_code, voice_name, max_concurrent_requests)

    async def synthesize_stream(self, text: str, chunk_size: int = 2048) -> AsyncIterator[bytes]:
        """
        Convert text to speech and stream audio chunks.

        Args:
            text: Text to synthesize
            chunk_size: Size of audio chunks to yield

        Yields:
            Audio data chunks as bytes
        """
        try:
            synthesis_input = tts.SynthesisInput(text=text)
            voice = tts.VoiceSelectionParams(
                language_code=self.language_code,
                name=self.voice_name,
            )
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                sample_rate_hertz=24000,
            )

            logger.debug("Starting TTS synthesis for text: '%s...' (acquiring semaphore)", text[:50])
            async with self.semaphore:
                response = await self.client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config,
                )

            audio_content = response.audio_content
            logger.debug("TTS synthesis complete, streaming %s bytes in chunks of %s", len(audio_content), chunk_size)

            for i in range(0, len(audio_content), chunk_size):
                chunk = audio_content[i:i + chunk_size]
                yield chunk

        except Exception as e:
            logger.error("TTS synthesis error: %s", e, exc_info=True)
            yield b''

    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to speech and return all audio data.

        Args:
            text: Text to synthesize

        Returns:
            Complete audio data as bytes
        """
        chunks = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)
        return b''.join(chunks)
