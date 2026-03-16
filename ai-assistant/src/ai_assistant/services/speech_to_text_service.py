"""
Speech-to-Text Service
Handles all speech recognition functionality.
"""
import logging
import time
from typing import AsyncIterator, Tuple
from google.cloud import speech_v1 as speech
from google.cloud.speech_v1 import SpeechAsyncClient
from google.api_core import exceptions as google_exceptions


logger = logging.getLogger(__name__)


class SpeechToTextService:
    """Service for speech-to-text conversion using Google Cloud Speech API."""
    
    def __init__(self, language_code: str = 'de-DE'):
        """
        Initialize Speech-to-Text service.
        
        Args:
            language_code: Language code for speech recognition
        """
        self.language_code = language_code
        self.client = SpeechAsyncClient()
        
        logger.info(f"STT service configured for language: {language_code}")
    
    async def continuous_stream(self, audio_generator) -> AsyncIterator[Tuple[str, bool]]:
        """
        Continuously stream audio to STT using async gRPC.
        
        Args:
            audio_generator: Async generator yielding audio chunks
        
        Yields:
            Tuple of (transcript, is_final) where is_final indicates if result is final
        """
        try:
            config = self._create_recognition_config()
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=True,
            )
            
            request_gen = self._create_request_generator(streaming_config, audio_generator)
            
            logger.info("🎤 Starting async gRPC streaming recognition")
            stream = await self.client.streaming_recognize(requests=request_gen)
            logger.info("✅ gRPC stream created, waiting for STT responses...")

            response_count = 0
            # Idle-silence timer: tracks when the first empty final was received.
            # Reset to None whenever a non-empty transcript arrives (interim or final).
            # If 120 s elapse without any non-empty transcript, close the stream so
            # _continuous_stt opens a fresh gRPC connection (prevents hitting the
            # Google STT hard 305-second stream-duration limit during silence).
            idle_since: float | None = None
            IDLE_TIMEOUT = 120.0

            async for response in stream:
                response_count += 1
                if response_count == 1:
                    logger.info(f"📨 First STT response received!")
                logger.debug(f"📨 STT response #{response_count}: {len(response.results)} results")
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        is_final = result.is_final

                        # ── Idle-silence timer ───────────────────────────
                        if transcript:
                            idle_since = None          # any text resets the timer
                        elif is_final:                 # empty final only
                            if idle_since is None:
                                idle_since = time.monotonic()
                            elif (elapsed := time.monotonic() - idle_since) >= IDLE_TIMEOUT:
                                logger.warning(
                                    "STT idle %.0fs — closing stream for restart",
                                    elapsed,
                                )
                                break

                        # ── Logging ───────────────────────────────────────
                        if is_final:
                            logger.info(f"✅ STT FINAL: '{transcript}'")
                        else:
                            logger.debug(f"⏳ STT interim: '{transcript}'")

                        yield (transcript, is_final)
                    else:
                        logger.debug(f"⚠️  STT result has no alternatives")
                else:
                    # Inner for-loop completed normally — check if the outer break
                    # was triggered (will be handled by the outer for-loop's else).
                    continue
                break  # propagate inner break to the outer async-for

            logger.info(f"🏁 STT streaming recognition completed (processed {response_count} responses)")
        
        except google_exceptions.OutOfRange as grpc_error:
            logger.info(f"STT duration limit reached without audio. Refreshing stream.")
            yield ("", False)
        except Exception as e:
            logger.error(f"STT streaming error: {e}", exc_info=True)
            yield ("", False)
    
    def _create_recognition_config(self) -> speech.RecognitionConfig:
        """
        Create speech recognition configuration.
        
        Returns:
            RecognitionConfig object
        """
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
            language_code=self.language_code,
            audio_channel_count=1,
            enable_automatic_punctuation=True,
            model='telephony',
            use_enhanced=True
        )
    
    async def _create_request_generator(self, streaming_config, audio_generator):
        """
        Generate streaming recognition requests.
        
        Args:
            streaming_config: Streaming configuration
            audio_generator: Async generator for audio chunks
        
        Yields:
            StreamingRecognizeRequest objects
        """
        # First request with config
        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        
        # Stream audio chunks
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
