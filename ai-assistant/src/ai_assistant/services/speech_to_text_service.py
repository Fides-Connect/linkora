"""
Speech-to-Text Service
Handles audio streaming to Google Cloud Speech API.
"""
import asyncio
import logging
from typing import AsyncIterator, Callable

from google.cloud import speech_v1 as speech
from google.cloud.speech_v1 import SpeechAsyncClient

from ..definitions import (
    STT_SAMPLE_RATE_HZ,
    STT_AUDIO_CHANNEL_COUNT,
    STT_ENABLE_AUTOMATIC_PUNCTUATION,
    STT_MODEL,
    STT_USE_ENHANCED,
    STT_INTERIM_RESULTS,
    STT_SINGLE_UTTERANCE,
)

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """Service for streaming speech-to-text using Google Cloud Speech API."""

    def __init__(self, speech_client: SpeechAsyncClient, language_code: str = 'de-DE'):
        """
        Initialize STT service.
        
        Args:
            speech_client: Async Google Cloud Speech client
            language_code: Language code for recognition (default: de-DE)
        """
        self.speech_client = speech_client
        self.language_code = language_code

    async def stream_recognize(
        self,
        audio_generator: Callable,
    ) -> AsyncIterator[tuple[str, bool]]:
        """
        Stream audio to STT and yield (transcript, is_final) tuples.
        
        Args:
            audio_generator: Async generator that yields audio chunks
            
        Yields:
            Tuple of (transcript, is_final) where is_final indicates completion
        """
        try:
            config = self._create_recognition_config()
            streaming_config = self._create_streaming_config(config)

            # Perform async gRPC streaming recognition
            logger.info("Starting async gRPC streaming recognition")
            stream = await self.speech_client.streaming_recognize(
                requests=self._create_request_generator(streaming_config, audio_generator)
            )

            # Process responses asynchronously
            response_count = 0
            async for response in stream:
                response_count += 1
                logger.info(f"📥 STT response #{response_count} received")
                async for transcript, is_final in self._process_response(response):
                    yield transcript, is_final

            logger.info(f"Async gRPC streaming recognition completed ({response_count} responses)")

        except Exception as e:
            logger.error(f"Streaming speech-to-text error: {e}", exc_info=True)
            yield "", False

    def _create_recognition_config(self) -> speech.RecognitionConfig:
        """Create recognition configuration."""
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=STT_SAMPLE_RATE_HZ,
            language_code=self.language_code,
            audio_channel_count=STT_AUDIO_CHANNEL_COUNT,
            enable_automatic_punctuation=STT_ENABLE_AUTOMATIC_PUNCTUATION,
            model=STT_MODEL,
            use_enhanced=STT_USE_ENHANCED
        )

    def _create_streaming_config(
        self,
        config: speech.RecognitionConfig
    ) -> speech.StreamingRecognitionConfig:
        """Create streaming configuration."""
        return speech.StreamingRecognitionConfig(
            config=config,
            interim_results=STT_INTERIM_RESULTS,
            single_utterance=STT_SINGLE_UTTERANCE,
        )

    async def _create_request_generator(
        self,
        streaming_config: speech.StreamingRecognitionConfig,
        audio_generator: Callable
    ):
        """Generate streaming recognition requests."""
        # First request with config
        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)

        # Then stream audio chunks
        chunk_count = 0
        async for audio_chunk in audio_generator:
            if audio_chunk:
                chunk_count += 1
                if chunk_count == 1:
                    logger.info(f"Sent first audio chunk to STT ({len(audio_chunk)} bytes)")
                elif chunk_count % 50 == 0:
                    logger.debug(f"Sent {chunk_count} audio chunks to STT")
                yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)

        logger.info(f"Audio generator finished after {chunk_count} chunks")

    async def _process_response(self, response) -> AsyncIterator[tuple[str, bool]]:
        """Process STT response and yield transcripts."""
        logger.debug(f"📝 Processing STT response: {len(response.results)} results")
        for result in response.results:
            if result.alternatives:
                transcript = result.alternatives[0].transcript
                is_final = result.is_final
                # Only log final transcripts at INFO level, interim at DEBUG
                if is_final:
                    logger.info(f"STT: '{transcript}' (final={is_final})")
                else:
                    logger.debug(f"STT: '{transcript}' (final={is_final})")
                yield transcript, is_final
            else:
                logger.warning("STT result has no alternatives")
