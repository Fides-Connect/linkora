"""
AI Assistant
Core logic for speech-to-text, LLM processing, and text-to-speech.
"""
import asyncio
import logging
import os
from typing import AsyncIterator
from google.cloud import speech_v1 as speech
from google.cloud.speech_v1 import SpeechAsyncClient
from google.cloud import texttospeech_v1 as tts
from google.cloud.texttospeech_v1 import TextToSpeechAsyncClient
import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIAssistant:
    """AI Assistant using Google Cloud services with gRPC streaming."""
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', 
                 voice_name: str = 'de-DE-Chirp3-HD-Sulafat'):
        self.language_code = language_code
        self.voice_name = voice_name
        
        # Initialize Google Cloud clients with async gRPC
        # Use default credentials in Cloud Run (via service account)
        # Use explicit credentials locally (via GOOGLE_APPLICATION_CREDENTIALS)
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using credentials from: {credentials_path}")
            # For async clients, we'll use the sync client's credentials
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.speech_client = SpeechAsyncClient(credentials=credentials)
            self.tts_client = TextToSpeechAsyncClient(credentials=credentials)
        else:
            logger.info("Using default credentials (Cloud Run environment)")
            self.speech_client = SpeechAsyncClient()
            self.tts_client = TextToSpeechAsyncClient()
        
        # Initialize Gemini AI
        genai.configure(api_key=gemini_api_key)
        self.llm_model = genai.GenerativeModel('gemini-2.0-flash')
        self.chat_session = self.llm_model.start_chat(history=[])
        
        # Configure generation - AGGRESSIVE optimization for ultra-low latency
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.9,  # Higher for faster, more varied sampling
            top_k=8,  # Much lower for fastest token selection
            top_p=0.9,
            max_output_tokens=512
        )
        
        logger.info("AI Assistant initialized with gRPC streaming")
        # Semaphore to limit concurrent Google API TTS requests for rate limiting
        # Default to 5 but allow override via environment variable for testing
        max_concurrency = int(os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5'))
        self.google_tts_api_semaphore = asyncio.Semaphore(max_concurrency)
    
    async def speech_to_text_continuous_stream(self, audio_generator) -> AsyncIterator[tuple[str, object]]:
        """
        Continuously stream audio to STT using async gRPC and yield (transcript, event) tuples.
        This method accepts an async generator that yields audio chunks.
        Returns tuples of (transcript, event) where:
        - transcript: recognized text (interim or final)
        - event: speech_event_type (e.g., SPEECH_ACTIVITY_END) or None
        
        Uses native async gRPC streaming for optimal latency with voice activity detection.
        Processing is triggered by SPEECH_ACTIVITY_END event
        """
        try:
            # Configure streaming recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,
                language_code=self.language_code,
                audio_channel_count=1,
                enable_automatic_punctuation=True,
                model='command_and_search',
                use_enhanced=True
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,  # Enable interim results for continuous updates
                single_utterance=False,  # Keep listening continuously
                enable_voice_activity_events=True
            )
            
            # Create async generator for gRPC requests
            async def request_generator():
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
                            logger.info(f"Sent {chunk_count} audio chunks to STT")
                        yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
                
                logger.info(f"Audio generator finished after {chunk_count} chunks")
            
            # Perform async gRPC streaming recognition
            logger.info("Starting async gRPC streaming recognition")
            stream = await self.speech_client.streaming_recognize(requests=request_generator())

            # Process responses asynchronously
            async for response in stream:
                # Detect any speech/voice-activity event on the response
                event = None
                try:
                    if hasattr(response, "speech_event_type") and response.speech_event_type:
                        event = response.speech_event_type
                        # Log the event with its name
                        event_name = speech.StreamingRecognizeResponse.SpeechEventType(event).name
                        logger.info(f"🎤 STT speech event: {event_name} (value={event})")
                except Exception as e:
                    logger.debug(f"Could not extract speech event: {e}")
                    event = None

                # Check if there are any results
                has_results = False
                for result in response.results:
                    if result.alternatives:
                        has_results = True
                        transcript = result.alternatives[0].transcript
                        logger.debug(f"STT continuous: '{transcript}' (event={event})")
                        # Yield transcript and the speech event
                        yield (transcript, event)
                
                # If there are no results but there's an event, yield it with empty transcript
                if not has_results and event is not None:
                    logger.debug(f"STT event without transcript (event={event})")
                    yield ("", event)
            
            logger.info("Async gRPC streaming recognition completed")
            
        except Exception as e:
            logger.error(f"Continuous streaming speech-to-text error: {e}", exc_info=True)
            yield ("", None)
    
    async def generate_llm_response_stream(self, prompt: str) -> AsyncIterator[str]:
        """Generate streaming response using Gemini LLM for low latency."""
        try:
            # Send message with streaming enabled
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.chat_session.send_message(
                    prompt,
                    generation_config=self.generation_config,
                    stream=True
                )
            )
            
            # Helper function to safely get next item from iterator
            # Returns (chunk, is_done) tuple to avoid StopIteration in executor
            def get_next_chunk(iterator):
                try:
                    return (next(iterator), False)
                except StopIteration:
                    return (None, True)
            
            # Convert the synchronous iterator to async by running each next() in executor
            # This allows proper streaming without blocking the event loop
            response_iter = iter(response)
            while True:
                # Get next chunk in executor to avoid blocking
                chunk, is_done = await loop.run_in_executor(None, get_next_chunk, response_iter)
                
                if is_done:
                    break
                    
                if chunk and chunk.text:
                    logger.debug(f"LLM stream chunk: '{chunk.text}'")
                    yield chunk.text
            
        except Exception as e:
            logger.error(f"Streaming LLM generation error: {e}", exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."
    
    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        """Convert text to speech using Google Cloud TTS async gRPC API."""
        try:
            # Configure TTS request
            synthesis_input = tts.SynthesisInput(text=text)
            
            voice = tts.VoiceSelectionParams(
                language_code=self.language_code,
                name=self.voice_name,
            )
            
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,  # Match WebRTC's native rate - no resampling needed!
            )
            
            # Perform async synthesis using gRPC under semaphore control
            logger.debug(f"Starting async TTS synthesis for text: '{text[:50]}...' (acquiring semaphore)")
            async with self.google_tts_api_semaphore:
                logger.debug("Semaphore acquired for TTS synthesis")
                response = await self.tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            
            # Stream audio in chunks (larger chunks = fewer iterations = lower overhead)
            chunk_size = 2048
            audio_content = response.audio_content
            
            logger.debug(f"TTS synthesis complete, streaming {len(audio_content)} bytes in chunks of {chunk_size}")
            
            for i in range(0, len(audio_content), chunk_size):
                chunk = audio_content[i:i + chunk_size]
                yield chunk
                # No artificial delay - stream as fast as possible for lowest latency
                
        except Exception as e:
            logger.error(f"Text-to-speech error: {e}", exc_info=True)
            # Return empty bytes on error
            yield b''
