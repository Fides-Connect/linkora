"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import numpy as np
import time
import re
from difflib import SequenceMatcher
from typing import Optional, List, Dict
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
        
        # Speaker diarization and echo filtering
        self.ai_speaker_tag: Optional[int] = None  # Identified speaker tag for AI voice
        self.last_ai_output: str = ""  # Recent LLM text output for echo detection
        self.sliding_window_similarity_threshold = 0.7  # Minimum similarity (70%) for fuzzy matching
        
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
            
            # Store greeting text in buffer for echo detection
            self.last_ai_output = greeting_text
            logger.info(f"📝 Stored greeting in buffer for echo detection")
            
            # Queue greeting audio for playback
            async for audio_chunk in audio_stream:
                if audio_chunk:
                    await self.output_track.queue_audio(audio_chunk)

            # Monitor playback completion in background
            asyncio.create_task(self._monitor_playback_completion())
            
            # Clear speaking flag after greeting completes
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
                async for transcript, is_final, speaker_tag in self.transcript_processor.process_audio_stream(
                    audio_generator_instance
                ):
                    if transcript:
                        # AI voice detection using sliding window
                        # Pass is_final to check buffer even if AI stopped speaking (final transcript delay)
                        is_ai_voice = self._is_ai_voice_sliding_window(transcript, is_final=is_final)
                        
                        if is_ai_voice:
                            logger.info(f"🔇 Filtering AI voice (sliding window match) from speaker {speaker_tag}: '{transcript}'")
                            continue  # Skip processing this transcript
                        
                        # If not AI voice and AI is speaking, it's a human interrupt
                        if self.is_ai_speaking:
                            logger.info(f"🛑 HUMAN INTERRUPT detected via sliding window: '{transcript}'")
                            await self._trigger_interrupt()
                            await asyncio.sleep(0.05)
                        
                        # Log user speech with speaker tag
                        if speaker_tag is not None:
                            logger.info(f"👤 User speech from speaker {speaker_tag}: '{transcript}'")
                        
                        if is_final:
                            # Stop the audio generator to prevent it from consuming more chunks
                            await self.audio_queue.put(None)
                            
                            # If AI is still marked as speaking but we got a final user transcript,
                            # force clear the flag (playback monitor may have failed)
                            if self.is_ai_speaking:
                                logger.warning(f"⚠️  Final transcript received but is_ai_speaking=True - force clearing flag")
                                logger.warning(f"   Queue size: {self.output_track.audio_queue.qsize()}, Buffer: {len(self.output_track._buffer)} bytes")
                                self.is_ai_speaking = False
                            
                            # Process the transcript if it's not empty
                            if transcript.strip():
                                await self._process_final_transcript(transcript)
                            else:
                                logger.warning(f"⚠️  Received empty final transcript - skipping processing")
                            
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
    
    def _is_ai_voice_sliding_window(self, transcript: str, is_final: bool = False) -> bool:
        """
        Detect if transcript is AI's own voice using sliding window approach.
        
        Maintains a sliding window of last 4 words from accumulated STT results.
        Checks if these 4 consecutive words appear in order in the current AI output.
        Only active while AI is speaking - once AI stops, all input is treated as human.
        Exception: Final transcripts are checked even if AI stopped (due to processing delay).
        
        Args:
            transcript: The current STT transcript (interim or final)
            is_final: Whether this is a final transcript (checked even if AI stopped)
            
        Returns:
            True if the last 4 words match AI output (it's AI voice), False otherwise (human)
        """
        # Only check for AI voice while AI is actively speaking
        if not self.is_ai_speaking:
            logger.debug("📊 AI is not speaking - skipping sliding window check")
            return False
        
        # Need AI output buffer to compare against
        if not self.last_ai_output:
            logger.debug("📊 No AI output buffer - cannot perform sliding window check")
            return False
        
        # Normalize transcript: remove punctuation, lowercase, split into words
        transcript_normalized = re.sub(r'[^\w\s]', '', transcript.lower().strip())
        words = transcript_normalized.split()

        # Need at least 1 word to update sliding window
        if not words:
            logger.debug("📊 Transcript has no words - skipping sliding window check")
            return False
        
        # Update sliding window: Since interim results are cumulative (each contains previous + new words),
        # we replace the window with the last 4 words from the current transcript
        # This prevents duplicating words across multiple interim results
        stt_word_window = words[-4:] if len(words) >= 4 else words
        logger.debug(f"📊 Updated sliding window: {stt_word_window} (from {len(words)} words)")
        
        # Need at least 4 words to check
        if len(stt_word_window) < 4:
            logger.debug(f"📊 Sliding window has only {len(stt_word_window)} words: {stt_word_window}")
            return True  # Not enough data yet, assume AI voice to avoid false interrupts
        
        # Get last 4 words as phrase
        last_4_words = ' '.join(stt_word_window)
        logger.debug(f"🔍 Sliding window (last 4 words): '{last_4_words}'")
        
        # Normalize: remove punctuation, lowercase, collapse all whitespace to single spaces
        ai_normalized = re.sub(r'[^\w\s]', '', self.last_ai_output.lower().strip())
        ai_normalized = re.sub(r'\s+', ' ', ai_normalized)  # Collapse multiple spaces/newlines to single space
        
        # Find best matching subsequence using fuzzy matching
        # Split AI output into words and check all 4-word windows
        ai_words = ai_normalized.split()
        best_similarity = 0.0
        
        # Check each 4-word window in the AI output
        for i in range(len(ai_words) - 3):
            ai_window = ' '.join(ai_words[i:i+4])
            similarity = SequenceMatcher(None, last_4_words, ai_window).ratio()
            if similarity > best_similarity:
                best_similarity = similarity
        
        logger.info(f"📊 Sliding window similarity: {best_similarity:.2%} (threshold: {self.sliding_window_similarity_threshold:.0%})")
        
        # Check if similarity exceeds threshold
        if best_similarity >= self.sliding_window_similarity_threshold:
            logger.info(f"✅ Sliding window MATCH - AI voice detected")
            logger.info(f"   Window: '{last_4_words}'")
            logger.info(f"   AI output: '{self.last_ai_output[:100]}...'")
            return True
        else:
            logger.info(f"❌  NO MATCH - Human voice detected!")
            logger.info(f"   Window: '{last_4_words}'")
            logger.info(f"   AI output: '{self.last_ai_output[:100]}...'")
            return False
        
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
            
            # Wrap LLM stream to track first token and collect AI output text
            ai_response_text = []
            async def tracked_llm_stream():
                first_chunk = True
                async for chunk in llm_stream:
                    if first_chunk and chunk:
                        perf_times['llm_first_token'] = asyncio.get_event_loop().time()
                        logger.info(f"⚡ Time to first LLM token: {perf_times['llm_first_token'] - llm_start:.3f}s")
                        first_chunk = False
                    if chunk:
                        ai_response_text.append(chunk)
                        # Update or add the current response in buffer
                        self.last_ai_output = ''.join(ai_response_text)
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
                    # If queue and buffer are empty for 8 consecutive checks (2s), we're done
                    if empty_count >= 8:
                        logger.info("🔊 Audio playback completed - clearing speaking flag")
                        self.is_ai_speaking = False
                        break
                else:
                    empty_count = 0
                
                await asyncio.sleep(0.250)  # Check every 250ms
            
        except Exception as e:
            logger.error(f"Error in playback monitor: {e}", exc_info=True)
            self.is_ai_speaking = False
