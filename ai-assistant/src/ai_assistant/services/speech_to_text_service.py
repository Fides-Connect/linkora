"""
Speech-to-Text Service
Handles all speech recognition functionality.
"""
import asyncio
import logging
from typing import AsyncIterator, Tuple, Optional
from google.cloud import speech_v1 as speech
from google.cloud.speech_v1 import SpeechAsyncClient

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """Service for speech-to-text conversion using Google Cloud Speech API."""
    
    def __init__(self, language_code: str = 'de-DE', credentials=None):
        """
        Initialize Speech-to-Text service.
        
        Args:
            language_code: Language code for speech recognition
            credentials: Google Cloud credentials (optional)
        """
        self.language_code = language_code
        
        if credentials:
            self.client = SpeechAsyncClient(credentials=credentials)
            logger.info(f"STT service initialized with provided credentials")
        else:
            self.client = SpeechAsyncClient()
            logger.info(f"STT service initialized with default credentials")
        
        logger.info(f"STT service configured for language: {language_code}")
    
    async def continuous_stream(self, audio_generator) -> AsyncIterator[Tuple[str, bool, Optional[int]]]:
        """
        Continuously stream audio to STT using async gRPC.
        
        Args:
            audio_generator: Async generator yielding audio chunks
        
        Yields:
            Tuple of (transcript, is_final, speaker_tag) where:
            - transcript: The recognized text
            - is_final: Whether this is a final result
            - speaker_tag: Primary speaker identifier (None if no diarization or no words)
        """
        try:
            config = self._create_recognition_config()
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=False,
            )
            
            request_gen = self._create_request_generator(streaming_config, audio_generator)
            
            logger.info("🎤 Starting async gRPC streaming recognition")
            stream = await self.client.streaming_recognize(requests=request_gen)
            logger.info("✅ gRPC stream created, waiting for STT responses...")

            response_count = 0
            async for response in stream:
                response_count += 1
                if response_count == 1:
                    logger.info(f"📨 First STT response received!")
                logger.debug(f"📨 STT response #{response_count}: {len(response.results)} results")
                for result in response.results:
                    if result.alternatives:
                        alternative = result.alternatives[0]
                        transcript = alternative.transcript
                        is_final = result.is_final
                        
                        # Extract speaker tags from words
                        speaker_tag = None
                        if hasattr(alternative, 'words') and alternative.words:
                            # Calculate primary speaker as most frequent speaker_tag
                            speaker_tags = [word.speaker_tag for word in alternative.words if hasattr(word, 'speaker_tag')]
                            if speaker_tags:
                                speaker_tag = max(set(speaker_tags), key=speaker_tags.count)
                        
                        if is_final:
                            logger.info(f"✅ STT FINAL (Speaker {speaker_tag}): '{transcript}'")
                        else:
                            logger.debug(f"⏳ STT interim (Speaker {speaker_tag}): '{transcript}'")
                        yield (transcript, is_final, speaker_tag)
                    else:
                        logger.debug(f"⚠️  STT result has no alternatives")
            
            logger.info(f"🏁 STT streaming recognition completed (processed {response_count} responses)")
            
        except Exception as e:
            logger.error(f"STT streaming error: {e}", exc_info=True)
            yield ("", False, None)
    
    def _create_recognition_config(self) -> speech.RecognitionConfig:
        """
        Create speech recognition configuration with speaker diarization.
        
        Returns:
            RecognitionConfig object
        """
        # Configure speaker diarization
        diarization_config = speech.SpeakerDiarizationConfig(
            enable_speaker_diarization=True,
            min_speaker_count=2,
            max_speaker_count=4,
        )
        
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=48000,
            language_code=self.language_code,
            audio_channel_count=1,
            enable_automatic_punctuation=True,
            model='phone_call',
            use_enhanced=True,
            diarization_config=diarization_config
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
