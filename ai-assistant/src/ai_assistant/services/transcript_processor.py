"""
Transcript Processing Service
Handles continuous speech-to-text processing and transcript accumulation.
"""
import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from google.api_core.exceptions import GoogleAPIError

from ..services.speech_to_text_service import SpeechToTextService

logger = logging.getLogger(__name__)


class TranscriptProcessor:
    """Processes audio stream through STT and manages transcription state."""
    
    def __init__(self, stt_service: SpeechToTextService):
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
    ) -> AsyncIterator[tuple[str, bool, float]]:
        """
        Process audio stream through STT and yield transcription results.
        
        Args:
            audio_stream: Async iterator of audio data bytes
            
        Yields:
            Tuple of (transcript_text, is_final, stability_or_confidence)
            
        Raises:
            GoogleAPIError: If STT API fails
        """
        self._processing = True
        self._current_transcript = ""
        
        logger.info("🎙️  Transcript processor started, waiting for STT results...")
        
        try:
            result_count = 0
            async for transcript, is_final, score in self.stt_service.continuous_stream(audio_stream):
                result_count += 1
                if result_count == 1:
                    logger.info(f"✅ First transcript result received from STT!")
                
                if transcript:
                    if is_final:
                        self._current_transcript = transcript
                        logger.info(f"Final transcript: {transcript}")
                        yield transcript, True, score
                    else:
                        logger.debug(f"Interim transcript: {transcript}")
                        yield transcript, False, score
                        
        except GoogleAPIError as e:
            logger.error(f"STT API error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error in transcript processing: {e}", exc_info=True)
            raise
        finally:
            self._processing = False
    
    def is_processing(self) -> bool:
        """Check if currently processing transcription."""
        return self._processing
    
    def get_current_transcript(self) -> str:
        """Get the current transcript text."""
        return self._current_transcript
    
    def reset(self):
        """Reset processor state."""
        self._processing = False
        self._current_transcript = ""


class TranscriptAccumulator:
    """Accumulates transcript chunks into complete text."""
    
    def __init__(self):
        """Initialize transcript accumulator."""
        self._accumulated = ""
        self._lock = asyncio.Lock()
    
    async def add(self, text: str, separator: str = " "):
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
    
    async def clear(self):
        """Clear accumulated transcript."""
        async with self._lock:
            self._accumulated = ""
    
    async def replace(self, text: str):
        """
        Replace accumulated transcript with new text.
        
        Args:
            text: New text
        """
        async with self._lock:
            self._accumulated = text
