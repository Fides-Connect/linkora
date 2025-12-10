"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import numpy as np
from typing import Optional
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

from .audio_track import AudioOutputTrack
from .services.audio_frame_converter import AudioFrameConverter
from .services.debug_recorder import DebugRecorder
from .services.transcript_processor import TranscriptProcessor
from .services.tts_playback_manager import TTSPlaybackManager, SentenceParser

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processes audio through the STT -> LLM -> TTS pipeline."""
    
    def __init__(self, connection_id: str, ai_assistant, input_track: MediaStreamTrack, user_id: Optional[str] = None):
        self.connection_id = connection_id
        self.ai_assistant = ai_assistant
        self.input_track = input_track
        self.user_id = user_id
        self.output_track = AudioOutputTrack()
        self.running = False
        self.processing_task = None
        self.stt_task = None
        
        # Audio streaming for continuous STT
        self.audio_queue = asyncio.Queue()
        self.sample_rate = 48000  # WebRTC sends 48kHz
        
        # Services
        self.frame_converter = AudioFrameConverter(self.sample_rate)
        self.debug_recorder = DebugRecorder(connection_id, self.sample_rate)
        self.transcript_processor = TranscriptProcessor(ai_assistant.stt_service)
        self.tts_manager = TTSPlaybackManager(
            ai_assistant.tts_service,
            self._queue_audio_for_playback
        )
        
        # Interrupt handling
        self.is_ai_speaking = False  # True when generating OR playing AI response
        self.interrupt_event = asyncio.Event()
        
    def get_output_track(self) -> MediaStreamTrack:
        """Get the output audio track."""
        return self.output_track
    
    async def start(self):
        """Start processing audio."""
        self.running = True
        logger.debug(f"📥 Creating _process_audio task for connection {self.connection_id}...")
        self.processing_task = asyncio.create_task(self._process_audio())
        self.stt_task = asyncio.create_task(self._continuous_stt())
        logger.info(f"🔊 Continuous STT streaming enabled")
        
        # Play greeting message
        logger.debug(f"👋 Starting greeting playback...")
        asyncio.create_task(self._play_greeting())
    
    async def stop(self):
        """Stop processing audio."""
        logger.debug(f"Stopping audio processor for connection {self.connection_id}")
        self.running = False
        
        # Signal end of audio stream
        await self.audio_queue.put(None)
        
        if self.stt_task:
            self.stt_task.cancel()
            try:
                await self.stt_task
            except asyncio.CancelledError:
                logger.debug("STT task cancelled successfully")
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                logger.debug("Audio processing task cancelled successfully")
        
        # Save debug recording if enabled
        self.debug_recorder.save()
        
        logger.info(f"Audio processor stopped for connection {self.connection_id}")
    
    async def _play_greeting(self):
        """Play the AI greeting message when connection starts."""
        try:
            logger.info("Generating and playing greeting message...")
            
            # Set speaking flag to prevent interruption during greeting
            self.is_ai_speaking = True
            
            # Generate greeting text and audio (pass user_id if available)
            greeting_text, audio_stream = await self.ai_assistant.get_greeting_audio(user_id=self.user_id)
            logger.info(f"Playing greeting: '{greeting_text}'")
            
            # Queue greeting audio for playback
            async for audio_chunk in audio_stream:
                if audio_chunk:
                    await self.output_track.queue_audio(audio_chunk)
            
            # Clear speaking flag after greeting completes
            self.is_ai_speaking = False
            logger.info("Greeting playback complete")
            
        except Exception as e:
            logger.error(f"Error playing greeting: {e}", exc_info=True)
            self.is_ai_speaking = False
    
    async def _process_audio(self):
        """Main audio processing loop - receives frames and queues them for STT."""
        try:
            frame_count = 0
            
            logger.info(f"🔄 Starting audio processing loop for connection {self.connection_id}")
            
            while self.running:
                try:
                    frame_count += 1
                    if frame_count == 1:
                        logger.debug(f"📥 [Frame {frame_count}] Waiting for FIRST audio frame (timeout=5s)...")
                    
                    # Receive audio frame from input track
                    try:
                        frame = await asyncio.wait_for(
                            self.input_track.recv(),
                            timeout=5.0
                        )
                        if frame_count == 1:
                            logger.debug(f"✅ [Frame {frame_count}] First frame received successfully!")
                    except MediaStreamError:
                        logger.warning(f"Input track closed for connection {self.connection_id} (frame {frame_count})")
                        break
                    except asyncio.CancelledError:
                        logger.warning(f"Audio processing cancelled at frame {frame_count}")
                        break
                    
                    # Convert frame to numpy array
                    audio_data = self.frame_converter.frame_to_numpy(frame)
                    
                    # Store frame for debug recording
                    self.debug_recorder.add_frame(audio_data)
                    
                    # Convert to bytes and queue for STT
                    audio_bytes = audio_data.tobytes()
                    await self.audio_queue.put(audio_bytes)
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Audio receive timeout after frame {frame_count}")
                    continue
                except Exception as e:
                    logger.error(f"Error receiving frame {frame_count}: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info(f"Audio processing cancelled (processed {frame_count} frames)")
        except Exception as e:
            logger.error(f"Error in audio processing loop after {frame_count} frames: {e}", exc_info=True)
    
    async def _continuous_stt(self):
        """Continuously stream audio to STT and process final transcripts."""
        try:
            logger.info("🎙️  Starting continuous STT streaming...")
            
            # Keep processing utterances until stopped
            while self.running:
                
                # Create async generator for audio chunks
                async def audio_generator():
                    chunk_count = 0
                    while self.running:
                        try:
                            audio_chunk = await asyncio.wait_for(
                                self.audio_queue.get(),
                                timeout=1.0
                            )
                            if audio_chunk is None:  # Sentinel value to stop
                                logger.debug("STT audio generator received stop signal")
                                break
                            chunk_count += 1
                            if chunk_count == 1:
                                logger.info(f"✅ First audio chunk received by STT generator ({len(audio_chunk)} bytes)")
                            yield audio_chunk
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error(f"Error in audio generator: {e}", exc_info=True)
                            break
                    logger.debug(f"Audio generator finished (chunks={chunk_count})")
                
                # Stream to STT and process results using TranscriptProcessor
                # This will process a single utterance and then return
                audio_generator_instance = audio_generator()
                async for transcript, is_final in self.transcript_processor.process_audio_stream(
                    audio_generator_instance
                ):
                    if transcript:
                        # Check if AI is currently speaking - if so, trigger interrupt
                        if self.is_ai_speaking and len(transcript.strip()) > 0:
                            logger.info(f"🛑 INTERRUPT detected! User speaking while AI responds: '{transcript}'")
                            await self._trigger_interrupt()
                            # Give a moment for the interrupt to take effect
                            await asyncio.sleep(0.05)
                        
                        if is_final:
                            # Process the transcript (interrupt already cleared speaking flag if needed)
                            if not self.is_ai_speaking:
                                await self._process_final_transcript(transcript)
                            else:
                                logger.warning(f"Skipping processing - AI still speaking despite interrupt")
                            # Stop the audio generator to prevent it from consuming more chunks
                            await self.audio_queue.put(None)
                            # Break out of the inner loop to start a new STT stream
                            logger.info("🔄 Final transcript received, starting new STT stream for next utterance")
                            break
                        else:
                            logger.debug(f"Interim transcript: '{transcript}'")
                            # Interim results also trigger interruption if AI is speaking
                
                # Give a brief moment before starting next utterance processing
                await asyncio.sleep(0.1)
            
            logger.info("Continuous STT streaming ended")
            
        except asyncio.CancelledError:
            logger.info("Continuous STT cancelled")
        except Exception as e:
            logger.error(f"Error in continuous STT: {e}", exc_info=True)
    
    async def _trigger_interrupt(self):
        """Trigger an interrupt to stop ongoing AI speech."""
        logger.info("⚡ Triggering interrupt - cancelling ongoing TTS tasks")
        
        # Set the interrupt event
        self.interrupt_event.set()
        
        # Interrupt TTS playback
        self.tts_manager.interrupt()
        
        # Clear the output audio queue to stop playback immediately
        await self.output_track.clear_queue()
        
        # Reset state
        self.is_ai_speaking = False
        
        logger.info("✅ Interrupt complete - AI speech stopped")
    
    async def _process_final_transcript(self, transcript: str):
        """Process a final transcript through LLM -> TTS pipeline."""
        try:
            logger.info(f"Processing final transcript: '{transcript}'")
            start_time = asyncio.get_event_loop().time()
            
            # Reset interrupt event and set speaking flag
            self.interrupt_event.clear()
            self.is_ai_speaking = True
            
            # Performance tracking
            perf_times = {
                'start': start_time,
                'llm_first_token': None,
                'tts_first_audio': None,
            }
            
            # Stage 1: Get LLM stream
            logger.info("Stage 1: Starting streaming LLM...")
            llm_start = asyncio.get_event_loop().time()
            
            # Create LLM stream
            llm_stream = self.ai_assistant.generate_llm_response_stream(transcript)
            
            # Stage 2: Process through TTS manager (handles sentence parsing, TTS, and ordered playback)
            logger.info("Stage 2: Processing LLM stream through TTS manager...")
            
            # Wrap LLM stream to track first token
            async def tracked_llm_stream():
                first_chunk = True
                async for chunk in llm_stream:
                    if first_chunk and chunk:
                        perf_times['llm_first_token'] = asyncio.get_event_loop().time()
                        logger.info(f"⚡ Time to first LLM token: {perf_times['llm_first_token'] - llm_start:.3f}s")
                        first_chunk = False
                    yield chunk
            
            # Process through TTS manager
            await self.tts_manager.process_llm_stream(tracked_llm_stream())
            
            # Monitor playback completion in background
            asyncio.create_task(self._monitor_playback_completion())
            
            total_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Pipeline complete in {total_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error processing final transcript: {e}", exc_info=True)
            self.is_ai_speaking = False
    
    async def _queue_audio_for_playback(self, audio_data: bytes):
        """
        Queue audio for playback with fade effects to prevent crackling.
        
        Args:
            audio_data: Audio data as bytes (int16)
        """
        try:
            # Convert to numpy array (make writable copy)
            audio_samples = np.frombuffer(audio_data, dtype=np.int16).copy()
            
            # Apply smooth fade-in at start and fade-out at end
            # Using cosine curve for smoother transitions
            fade_in_samples = min(480, len(audio_samples) // 2)  # 10ms at 48kHz
            fade_out_samples = min(144, len(audio_samples) // 2)  # 3ms at 48kHz
            
            if fade_in_samples > 0:
                # Cosine fade-in: 0 to 1
                fade_in = (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples))) / 2.0
                audio_samples[:fade_in_samples] = (audio_samples[:fade_in_samples] * fade_in).astype(np.int16)
            
            if fade_out_samples > 0:
                # Cosine fade-out: 1 to 0
                fade_out = (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples))) / 2.0
                audio_samples[-fade_out_samples:] = (audio_samples[-fade_out_samples:] * fade_out).astype(np.int16)
            
            # Queue the processed audio
            await self.output_track.queue_audio(audio_samples.tobytes())
            
        except Exception as e:
            logger.error(f"Error queueing audio for playback: {e}", exc_info=True)
    
    async def _monitor_playback_completion(self):
        """Monitor the audio queue and clear speaking flag when playback is done."""
        try:
            # Wait a bit for audio to start queueing
            await asyncio.sleep(0.1)
            
            # Monitor queue size - when it stays at 0 for a bit, we're done playing
            empty_count = 0
            while self.is_ai_speaking and not self.interrupt_event.is_set():
                queue_size = self.output_track.audio_queue.qsize()
                buffer_size = len(self.output_track._buffer)
                
                if queue_size == 0 and buffer_size == 0:
                    empty_count += 1
                    # If queue and buffer are empty for 5 consecutive checks (100ms), we're done
                    if empty_count >= 5:
                        logger.info("Audio playback completed - clearing speaking flag")
                        self.is_ai_speaking = False
                        break
                else:
                    empty_count = 0
                
                await asyncio.sleep(0.02)  # Check every 20ms
            
        except Exception as e:
            logger.error(f"Error in playback monitor: {e}", exc_info=True)
            self.is_ai_speaking = False
