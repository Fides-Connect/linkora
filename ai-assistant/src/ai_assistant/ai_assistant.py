"""
AI Assistant
Core logic for speech-to-text, LLM processing, and text-to-speech.
"""
import asyncio
import logging
import os
from typing import AsyncIterator
from google.cloud import speech_v1 as speech
from google.cloud import texttospeech_v1 as tts
import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIAssistant:
    """AI Assistant using Google Cloud services."""
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', 
                 voice_name: str = 'de-DE-Chirp-HD-F'):
        self.language_code = language_code
        self.voice_name = voice_name
        
        # Initialize Google Cloud clients
        # Use default credentials in Cloud Run (via service account)
        # Use explicit credentials locally (via GOOGLE_APPLICATION_CREDENTIALS)
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using credentials from: {credentials_path}")
            self.speech_client = speech.SpeechClient.from_service_account_json(credentials_path)
            self.tts_client = tts.TextToSpeechClient.from_service_account_json(credentials_path)
        else:
            logger.info("Using default credentials (Cloud Run environment)")
            self.speech_client = speech.SpeechClient()
            self.tts_client = tts.TextToSpeechClient()
        
        # Initialize Gemini AI
        genai.configure(api_key=gemini_api_key)
        self.llm_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.chat_session = self.llm_model.start_chat(history=[])
        
        # Configure generation
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.7,
            top_k=40,
            top_p=0.95,
            max_output_tokens=1024
        )
        
        logger.info("AI Assistant initialized")
    
    async def speech_to_text_continuous_stream(self, audio_generator) -> AsyncIterator[tuple[str, bool]]:
        """
        Continuously stream audio to STT and yield (transcript, is_final) tuples.
        This method accepts an async generator that yields audio chunks.
        Returns tuples of (transcript, is_final) where is_final indicates if the result is final.
        """
        import queue
        import threading
        
        try:
            # Configure streaming recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,
                language_code=self.language_code,
                audio_channel_count=1,
                enable_automatic_punctuation=True,
                model='latest_long',  # Optimized for conversations and longer utterances
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,  # Enable interim results to show progress
                single_utterance=False,  # Keep listening continuously
            )
            
            # Use thread-safe queue to bridge async and sync worlds
            request_queue = queue.Queue()
            stop_flag = threading.Event()
            
            # Background thread to populate the sync queue from async generator
            async def populate_queue():
                """Populate queue from async generator."""
                try:
                    # Stream audio chunks only - config is passed separately to streaming_recognize()
                    chunk_count = 0
                    async for audio_chunk in audio_generator:
                        if audio_chunk:
                            request_queue.put(speech.StreamingRecognizeRequest(audio_content=audio_chunk))
                            chunk_count += 1
                            if chunk_count == 1:
                                logger.info(f"Sent first audio chunk to STT ({len(audio_chunk)} bytes)")
                            elif chunk_count % 50 == 0:
                                logger.info(f"Sent {chunk_count} audio chunks to STT")
                    
                except Exception as e:
                    logger.error(f"Error populating request queue: {e}", exc_info=True)
                finally:
                    logger.info(f"populate_queue finished after {chunk_count} chunks")
                    request_queue.put(None)  # Sentinel to signal end
                    stop_flag.set()
            
            def sync_request_generator():
                """Sync generator that pulls from queue."""
                while True:
                    try:
                        # Block waiting for next request, with timeout to check stop flag
                        request = request_queue.get(timeout=0.1)
                        
                        if request is None:  # Sentinel
                            logger.debug("STT request generator received stop signal")
                            break
                        
                        yield request
                        
                    except queue.Empty:
                        # Timeout - check if we should stop
                        if stop_flag.is_set() and request_queue.empty():
                            break
                        continue
            
            # Start queue population task
            populate_task = asyncio.create_task(populate_queue())
            
            # Perform streaming recognition in executor
            loop = asyncio.get_event_loop()
            
            # Queue to pass results from sync thread to async context
            result_queue = asyncio.Queue()
            
            try:
                # Function to run in thread pool - iterates over responses and queues results
                def stream_recognize_and_queue():
                    try:
                        responses = self.speech_client.streaming_recognize(
                            config=streaming_config,
                            requests=sync_request_generator()
                        )
                        
                        for response in responses:
                            for result in response.results:
                                if result.alternatives:
                                    transcript = result.alternatives[0].transcript
                                    is_final = result.is_final
                                    logger.debug(f"STT continuous: '{transcript}' (final={is_final})")
                                    # Put result in queue (use thread-safe put_nowait via call_soon_threadsafe)
                                    loop.call_soon_threadsafe(result_queue.put_nowait, (transcript, is_final))
                    except Exception as e:
                        logger.error(f"Error in streaming recognition thread: {e}", exc_info=True)
                        loop.call_soon_threadsafe(result_queue.put_nowait, None)  # Signal error
                    finally:
                        loop.call_soon_threadsafe(result_queue.put_nowait, None)  # Signal completion
                
                # Start streaming in a thread pool (don't await - it will run in background)
                recognition_future = loop.run_in_executor(None, stream_recognize_and_queue)
                
                # Yield results as they arrive from the queue
                while True:
                    result = await result_queue.get()
                    if result is None:  # Completion or error signal
                        break
                    transcript, is_final = result
                    yield (transcript, is_final)
                
            finally:
                # Clean up
                stop_flag.set()
                populate_task.cancel()
                try:
                    await populate_task
                except asyncio.CancelledError:
                    pass
                
                # Wait for recognition thread to finish (with timeout)
                try:
                    await asyncio.wait_for(recognition_future, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("Recognition thread did not finish within timeout")
                except Exception as e:
                    logger.error(f"Error waiting for recognition thread: {e}")
            
        except Exception as e:
            logger.error(f"Continuous streaming speech-to-text error: {e}", exc_info=True)
            yield ("", False)
    
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
            
            # Yield text chunks as they arrive
            for chunk in response:
                if chunk.text:
                    logger.debug(f"LLM stream chunk: '{chunk.text}'")
                    yield chunk.text
            
        except Exception as e:
            logger.error(f"Streaming LLM generation error: {e}", exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."
    
    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        """Convert text to speech using Google Cloud TTS streaming API."""
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
            
            # Perform synthesis
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            )
            
            # Stream audio in chunks
            chunk_size = 4096
            audio_content = response.audio_content
            
            for i in range(0, len(audio_content), chunk_size):
                chunk = audio_content[i:i + chunk_size]
                yield chunk
                # Small delay to prevent overwhelming the stream
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Text-to-speech error: {e}", exc_info=True)
            # Return empty bytes on error
            yield b''
