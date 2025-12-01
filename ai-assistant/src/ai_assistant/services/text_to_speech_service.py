"""
Text-to-Speech Service
Handles text-to-speech conversion using Google Cloud TTS API.
"""
import asyncio
import logging
from typing import AsyncIterator

from google.cloud import texttospeech_v1 as tts
from google.cloud.texttospeech_v1 import TextToSpeechAsyncClient

from ..definitions import (
    TTS_SAMPLE_RATE_HZ,
    TTS_CHUNK_SIZE,
)

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """Service for text-to-speech conversion using Google Cloud TTS API."""

    def __init__(
        self,
        tts_client: TextToSpeechAsyncClient,
        language_code: str = 'de-DE',
        voice_name: str = 'de-DE-Chirp3-HD-Sulafat',
        max_concurrency: int = 5
    ):
        """
        Initialize TTS service.
        
        Args:
            tts_client: Async Google Cloud TTS client
            language_code: Language code for voice (default: de-DE)
            voice_name: Voice name to use for synthesis
            max_concurrency: Maximum concurrent TTS API requests
        """
        self.tts_client = tts_client
        self.language_code = language_code
        self.voice_name = voice_name
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def synthesize_speech(self, text: str) -> AsyncIterator[bytes]:
        """
        Convert text to speech and stream audio chunks.
        
        Args:
            text: Text to convert to speech
            
        Yields:
            Audio chunks as bytes
        """
        try:
            synthesis_input = tts.SynthesisInput(text=text)
            voice = self._create_voice_params()
            audio_config = self._create_audio_config()

            # Perform async synthesis with rate limiting
            logger.debug(f"Starting TTS synthesis: '{text[:50]}...'")
            async with self.semaphore:
                response = await self.tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )

            # Stream audio in chunks
            audio_content = response.audio_content
            logger.debug(f"TTS complete: {len(audio_content)} bytes, streaming in chunks")

            for chunk in self._chunk_audio(audio_content):
                yield chunk

        except Exception as e:
            logger.error(f"Text-to-speech error: {e}", exc_info=True)
            yield b''

    def _create_voice_params(self) -> tts.VoiceSelectionParams:
        """Create voice selection parameters."""
        return tts.VoiceSelectionParams(
            language_code=self.language_code,
            name=self.voice_name,
        )

    def _create_audio_config(self) -> tts.AudioConfig:
        """Create audio configuration."""
        return tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=TTS_SAMPLE_RATE_HZ,
        )

    def _chunk_audio(self, audio_content: bytes) -> AsyncIterator[bytes]:
        """Split audio content into chunks."""
        chunk_size = TTS_CHUNK_SIZE
        for i in range(0, len(audio_content), chunk_size):
            yield audio_content[i:i + chunk_size]
