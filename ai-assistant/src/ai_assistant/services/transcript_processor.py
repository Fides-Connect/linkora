"""
Transcript Processing Service
Handles continuous speech-to-text processing and transcript accumulation.
"""
import asyncio
import logging
from collections.abc import AsyncIterator

from google.api_core.exceptions import GoogleAPIError

from ..services.speech_to_text_service import SpeechToTextService

logger = logging.getLogger(__name__)


class TranscriptProcessor:
    """Processes audio stream through STT and manages transcription state."""

    def __init__(self, stt_service: SpeechToTextService) -> None:
        """
        Initialize transcript processor.

        Args:
            stt_service: Speech-to-text service instance
        """
        self.stt_service = stt_service
        self._processing = False
        self._current_transcript = ""

    async def process_audio_stream(
        self,
        audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[tuple[str, bool]]:
        """
        Process audio stream through STT and yield transcription results.

        Args:
            audio_stream: Async iterator of audio data bytes

        Yields:
            Tuple of (transcript_text, is_final)

        Raises:
            GoogleAPIError: If STT API fails
        """
        self._processing = True
        self._current_transcript = ""

        logger.info("🎙️  Transcript processor started, waiting for STT results...")

        try:
            result_count = 0
            async for transcript, is_final in self.stt_service.continuous_stream(audio_stream):
                result_count += 1
                if result_count == 1:
                    logger.info("✅ First transcript result received from STT!")

                if transcript:
                    if is_final:
                        self._current_transcript = transcript
                        logger.debug("Final transcript: %s", transcript)
                        yield transcript, True
                    else:
                        logger.debug("Interim transcript: %s", transcript)
                        yield transcript, False

        except GoogleAPIError as e:
            logger.error("STT API error: %s", e, exc_info=True)
            raise
        except Exception as e:
            logger.error("Unexpected error in transcript processing: %s", e, exc_info=True)
            raise
        finally:
            self._processing = False

    def is_processing(self) -> bool:
        """Check if currently processing transcription."""
        return self._processing

    def get_current_transcript(self) -> str:
        """Get the current transcript text."""
        return self._current_transcript

    def reset(self) -> None:
        """Reset processor state."""
        self._processing = False
        self._current_transcript = ""


class TranscriptAccumulator:
    """Accumulates transcript chunks into complete text."""

    def __init__(self) -> None:
        """Initialize transcript accumulator."""
        self._accumulated = ""
        self._lock = asyncio.Lock()

    async def add(self, text: str, separator: str = " ") -> None:
        """
        Add text to accumulated transcript.

        Args:
            text: Text to add
            separator: Separator between chunks
        """
        async with self._lock:
            if self._accumulated:
                self._accumulated += separator
            self._accumulated += text

    async def get(self) -> str:
        """Get current accumulated transcript."""
        async with self._lock:
            return self._accumulated

    async def clear(self) -> None:
        """Clear accumulated transcript."""
        async with self._lock:
            self._accumulated = ""

    async def replace(self, text: str) -> None:
        """
        Replace accumulated transcript with new text.

        Args:
            text: New text
        """
        async with self._lock:
            self._accumulated = text
