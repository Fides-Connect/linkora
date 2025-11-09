"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import numpy as np
import re
import wave
import os
from datetime import datetime
from typing import Optional
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

from .audio_track import AudioOutputTrack

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processes audio through the STT -> LLM -> TTS pipeline."""
    
    def __init__(self, connection_id: str, ai_assistant, input_track: MediaStreamTrack):
        self.connection_id = connection_id
        self.ai_assistant = ai_assistant
        self.input_track = input_track
        self.output_track = AudioOutputTrack()
        self.running = False
        self.processing_task = None
        self.stt_task = None
        
        # Audio streaming for continuous STT
        self.audio_queue = asyncio.Queue()
        self.sample_rate = 48000  # WebRTC sends 48kHz - match it exactly
        
        # Transcript accumulation
        self.current_transcript = ""
        
        # Interrupt handling
        self.is_ai_speaking = False  # True when generating OR playing AI response
        self.interrupt_event = asyncio.Event()
        self.current_tts_tasks = []
        self.playback_start_time = None  # Track when playback started
        
        # Debug: WAV file recording
        self.debug_recording = os.getenv('DEBUG_RECORD_AUDIO', 'false').lower() == 'true'
        self.debug_wav_file = None
        self.debug_all_frames = []  # Store all frames for complete recording
        if self.debug_recording:
            # Create debug directory if it doesn't exist
            debug_dir = 'debug_audio'
            os.makedirs(debug_dir, exist_ok=True)
            # Create unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.debug_wav_path = os.path.join(debug_dir, f'received_audio_{connection_id}_{timestamp}.wav')
            logger.info(f"Debug audio recording enabled: {self.debug_wav_path}")
        
    def get_output_track(self) -> MediaStreamTrack:
        """Get the output audio track."""
        return self.output_track
    
    async def start(self):
        """Start processing audio."""
        self.running = True
        self.processing_task = asyncio.create_task(self._process_audio())
        self.stt_task = asyncio.create_task(self._continuous_stt())
        logger.info(f"Audio processor started for connection {self.connection_id}")
        logger.debug("Continuous STT streaming enabled")
    
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
                pass
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                logger.debug("Audio processing task cancelled successfully")
                pass
        
        # Save debug recording if enabled
        if self.debug_recording and len(self.debug_all_frames) > 0:
            self._save_debug_recording()
        
        logger.info(f"Audio processor stopped for connection {self.connection_id}")
    
    def _save_debug_recording(self):
        """Save all received audio frames to a WAV file."""
        try:
            logger.info(f"Saving debug recording: {self.debug_wav_path}")
            
            if len(self.debug_all_frames) == 0:
                logger.warning("No frames to save!")
                return
            
            # Log statistics about the frames
            frame_count = len(self.debug_all_frames)
            frame_lengths = [len(f) for f in self.debug_all_frames]
            logger.info(f"Recording {frame_count} frames, lengths: min={min(frame_lengths)}, max={max(frame_lengths)}, avg={sum(frame_lengths)/len(frame_lengths):.1f}")
            
            # Concatenate all frames
            all_audio = np.concatenate(self.debug_all_frames)
            
            # Log audio statistics
            audio_min, audio_max = all_audio.min(), all_audio.max()
            audio_rms = np.sqrt(np.mean(all_audio.astype(float) ** 2))
            logger.info(f"Audio statistics: min={audio_min}, max={audio_max}, RMS={audio_rms:.2f}")
            
            if audio_rms < 100:
                logger.warning(f"WARNING: Audio has very low RMS ({audio_rms:.2f}) - recording might be silence or corrupted")
            
            # Write to WAV file
            with wave.open(self.debug_wav_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(all_audio.tobytes())
            
            duration = len(all_audio) / self.sample_rate
            logger.info(f"Debug recording saved: {self.debug_wav_path} ({duration:.2f}s, {len(all_audio)} samples)")
            
        except Exception as e:
            logger.error(f"Error saving debug recording: {e}", exc_info=True)
    
    async def _process_audio(self):
        """Main audio processing loop - receives frames and queues them for STT."""
        try:
            frame_count = 0
            
            logger.debug(f"Starting audio processing loop for connection {self.connection_id}")
            
            while self.running:
                try:
                    frame_count += 1
                    logger.debug(f"[Frame {frame_count}] Waiting for incoming audio frame (timeout=5s)")
                    
                    # Receive audio frame from input track
                    try:
                        frame = await asyncio.wait_for(
                            self.input_track.recv(),
                            timeout=5.0
                        )
                    except MediaStreamError:
                        logger.info(f"Input track closed for connection {self.connection_id} (frame {frame_count})")
                        break
                    except asyncio.CancelledError:
                        logger.info(f"Audio processing cancelled at frame {frame_count}")
                        break
                    
                    # Log frame details
                    logger.debug(
                        f"[Frame {frame_count}] Received frame: pts={getattr(frame, 'pts', 'N/A')}, "
                        f"samples={getattr(frame, 'samples', 'N/A')}, "
                        f"sample_rate={getattr(frame, 'sample_rate', 'N/A')}, "
                        f"format={getattr(frame, 'format', 'N/A')}"
                    )
                    
                    # Convert frame to numpy array
                    audio_data = self._frame_to_numpy(frame)
                    logger.debug(f"[Frame {frame_count}] Converted to numpy: shape={audio_data.shape}, dtype={audio_data.dtype}")
                    
                    # Store frame for debug recording
                    if self.debug_recording:
                        self.debug_all_frames.append(audio_data.copy())
                    
                    # Queue audio data for continuous STT streaming
                    rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))
                    logger.debug(f"[Frame {frame_count}] Audio level: RMS={rms:.2f}")
                    
                    # Convert to bytes and queue for STT
                    audio_bytes = audio_data.tobytes()
                    await self.audio_queue.put(audio_bytes)
                    
                    # Log every 50 frames at INFO level to track progress
                    if frame_count % 50 == 0:
                        logger.info(f"[Frame {frame_count}] Queued {len(audio_bytes)} bytes for STT (RMS={rms:.2f})")
                    logger.debug(f"[Frame {frame_count}] Queued {len(audio_bytes)} bytes for STT")
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Audio receive timeout after frame {frame_count}")
                    continue
                except Exception as e:
                    logger.error(f"Error receiving frame {frame_count}: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info(f"Audio processing cancelled (processed {frame_count} frames)")
        except Exception as e:
            logger.error(f"Error in audio processing loop after {frame_count} frames: {e}", exc_info=True)
    
    def _frame_to_numpy(self, frame: AudioFrame) -> np.ndarray:
        """Convert audio frame to numpy array."""
        logger.debug(f"Converting frame to numpy: format={frame.format}, layout={frame.layout}")
        
        # Log raw frame properties
        logger.debug(f"Frame properties: sample_rate={frame.sample_rate}, samples={frame.samples}, format={frame.format.name}")
        
        # Convert to numpy array
        array = frame.to_ndarray()
        logger.debug(f"Frame.to_ndarray() result: shape={array.shape}, dtype={array.dtype}")
        
        # Handle stereo to mono conversion
        if len(array.shape) > 1:
            if array.shape[0] == 1:
                # Shape is (1, N*2) - single channel with interleaved stereo
                # Reshape to (N, 2) to properly separate left/right channels
                logger.debug(f"Reshaping interleaved stereo: {array.shape} -> (-1, 2)")
                array = array.reshape(-1, 2)
            
            # Now convert to mono by averaging channels
            logger.debug(f"Converting stereo to mono (shape: {array.shape})")
            array = array.mean(axis=1).astype(array.dtype)  # Keep original dtype!
            logger.debug(f"After mono conversion: shape={array.shape}, dtype={array.dtype}")
        
        # NO RESAMPLING - just handle different sample rates in STT config
        # The resampling 48->16->48 is causing quality issues
        
        # Ensure int16 format
        if array.dtype != np.int16:
            logger.warning(f"Converting from {array.dtype} to int16")
            # Check the range of values
            array_min, array_max = array.min(), array.max()
            logger.debug(f"Array range before conversion: min={array_min}, max={array_max}")
            
            if array.dtype in (np.float32, np.float64):
                # Normalize float audio (-1.0 to 1.0 range)
                if -1.0 <= array_min and array_max <= 1.0:
                    logger.debug("Float audio in normalized range [-1.0, 1.0]")
                    array = (array * 32767).astype(np.int16)
                else:
                    logger.warning(f"Float audio out of expected range: [{array_min}, {array_max}]")
                    array = array / max(abs(array_min), abs(array_max))
                    array = (array * 32767).astype(np.int16)
            else:
                array = array.astype(np.int16)
        
        # Validate the output
        if len(array) == 0:
            logger.error("Conversion resulted in empty array!")
            return np.zeros(480, dtype=np.int16)
        
        final_min, final_max = array.min(), array.max()
        rms = np.sqrt(np.mean(array.astype(float) ** 2))
        logger.debug(f"Final numpy array: shape={array.shape}, dtype={array.dtype}, min={final_min}, max={final_max}, RMS={rms:.2f}")
        
        # Warn if audio seems to be all silence
        if rms < 10:
            logger.debug(f"Audio frame has very low RMS ({rms:.2f}) - might be silence or incorrect conversion")
        
        return array
    
    async def _continuous_stt(self):
        """Continuously stream audio to STT and process final transcripts."""
        try:
            logger.info("Starting continuous STT streaming...")
            
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
                        if chunk_count % 50 == 0:
                            logger.info(f"STT audio generator: yielding chunk {chunk_count} ({len(audio_chunk)} bytes)")
                        yield audio_chunk
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Error in audio generator: {e}", exc_info=True)
                        break
            
            # Stream to STT and process results
            async for transcript, is_final in self.ai_assistant.speech_to_text_continuous_stream(
                audio_generator()
            ):
                if transcript:
                    # Check if AI is currently speaking - if so, trigger interrupt
                    if self.is_ai_speaking and len(transcript.strip()) > 0:
                        logger.info(f"🛑 INTERRUPT detected! User speaking while AI responds: '{transcript}'")
                        await self._trigger_interrupt()
                        # Give a moment for the interrupt to take effect
                        await asyncio.sleep(0.05)
                    
                    if is_final:
                        logger.info(f"Final transcript: '{transcript}'")
                        # Process the transcript (interrupt already cleared speaking flag if needed)
                        if not self.is_ai_speaking:
                            await self._process_final_transcript(transcript)
                        else:
                            logger.warning(f"Skipping processing - AI still speaking despite interrupt")
                    else:
                        logger.debug(f"Interim transcript: '{transcript}'")
                        # Interim results also trigger interruption if AI is speaking
            
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
        
        # Cancel all ongoing TTS tasks
        for task in self.current_tts_tasks:
            if not task.done():
                task.cancel()
        
        # Clear the output audio queue to stop playback immediately
        await self.output_track.clear_queue()
        
        # Reset state
        self.is_ai_speaking = False
        self.current_tts_tasks = []
        
        logger.info("✅ Interrupt complete - AI speech stopped")
    
    async def _process_final_transcript(self, transcript: str):
        """Process a final transcript through LLM -> TTS pipeline."""
        try:
            logger.info(f"Processing final transcript: '{transcript}'")
            start_time = asyncio.get_event_loop().time()
            
            # Reset interrupt event and set speaking flag
            self.interrupt_event.clear()
            self.is_ai_speaking = True
            self.current_tts_tasks = []
            
            # Performance tracking
            perf_times = {
                'start': start_time,
                'llm_first_token': None,
                'llm_complete': None,
                'tts_first_chunk': None,
                'tts_complete': None
            }
            
            # Stage 1: LLM Processing (Streaming)
            logger.info("Stage 1: Starting streaming LLM...")
            llm_start = asyncio.get_event_loop().time()
            
            llm_parts = []
            sentence_buffer = ""
            
            # Mechanism to ensure sentences are played in order
            next_sentence_to_play = 1
            sentence_events = {}  # Dict mapping sentence_num to asyncio.Event
            playback_lock = asyncio.Lock()
            
            async def process_sentence_to_audio(sentence: str, sentence_num: int):
                """Process a complete sentence through TTS and queue audio in order."""
                try:
                    # Check for interrupt before processing
                    if self.interrupt_event.is_set():
                        logger.info(f"Sentence {sentence_num} skipped due to interrupt")
                        return
                    
                    logger.info(f"TTS for sentence {sentence_num}: '{sentence}'")
                    tts_start = asyncio.get_event_loop().time()
                    
                    # Create event for this sentence
                    nonlocal next_sentence_to_play, sentence_events
                    my_event = asyncio.Event()
                    sentence_events[sentence_num] = my_event
                    
                    # If we're sentence 1, set our event immediately
                    if sentence_num == 1:
                        my_event.set()
                    
                    # Process TTS to get all audio chunks for this sentence
                    audio_chunks = []
                    first_chunk = True
                    async for audio_chunk in self.ai_assistant.text_to_speech_stream(sentence):
                        # Check for interrupt during TTS processing
                        if self.interrupt_event.is_set():
                            logger.info(f"TTS for sentence {sentence_num} interrupted during processing")
                            return
                        
                        if audio_chunk:
                            if first_chunk and sentence_num == 1:
                                # Track time to first TTS audio chunk (only for first sentence)
                                perf_times['tts_first_chunk'] = asyncio.get_event_loop().time()
                                first_chunk = False
                            audio_chunks.append(audio_chunk)
                    
                    tts_duration = asyncio.get_event_loop().time() - tts_start
                    logger.debug(f"TTS sentence {sentence_num} complete in {tts_duration:.3f}s: {len(audio_chunks)} chunks, waiting for turn to play...")
                    
                    # Check for interrupt before waiting for turn
                    if self.interrupt_event.is_set():
                        logger.info(f"Sentence {sentence_num} interrupted before playback")
                        return
                    
                    # Wait for our turn to play
                    await my_event.wait()
                    
                    # Check for interrupt one more time before queueing audio
                    if self.interrupt_event.is_set():
                        logger.info(f"Sentence {sentence_num} interrupted right before playback")
                        return
                    
                    # Now queue all our audio chunks atomically (hold playback_lock to prevent interleaving)
                    async with playback_lock:
                        logger.info(f"Playing sentence {sentence_num} ({len(audio_chunks)} chunks)")
                        
                        # Combine all audio chunks into a single array for processing
                        combined_audio = b''.join(audio_chunks)
                        # Make a writable copy of the array
                        audio_samples = np.frombuffer(combined_audio, dtype=np.int16).copy()
                        
                        # Apply smooth fade-in at start and fade-out at end to prevent clicks/crackling
                        # Using cosine curve for smoother transitions
                        # First sentence gets longer fade-in (10ms) to eliminate crackling on phone speakers
                        fade_in_samples = min(480 if sentence_num == 1 else 144, len(audio_samples) // 2)  # 10ms or 3ms at 48kHz
                        fade_out_samples = min(144, len(audio_samples) // 2)  # 3ms at 48kHz
                        
                        if fade_in_samples > 0:
                            # Cosine fade-in: 0 to 1 (smoother than linear, eliminates crackling)
                            fade_in = (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples))) / 2.0
                            audio_samples[:fade_in_samples] = (audio_samples[:fade_in_samples] * fade_in).astype(np.int16)
                        
                        if fade_out_samples > 0:
                            # Cosine fade-out: 1 to 0 (smoother than linear)
                            fade_out = (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples))) / 2.0
                            audio_samples[-fade_out_samples:] = (audio_samples[-fade_out_samples:] * fade_out).astype(np.int16)
                        
                        # Queue the processed audio
                        await self.output_track.queue_audio(audio_samples.tobytes())
                        
                        logger.debug(f"Sentence {sentence_num} playback complete")
                        
                        # Signal next sentence can play BEFORE releasing the lock
                        # This ensures next sentence can't start queueing until we're completely done
                        next_sentence = sentence_num + 1
                        if next_sentence in sentence_events:
                            sentence_events[next_sentence].set()
                    
                except Exception as e:
                    logger.error(f"Error in TTS for sentence {sentence_num}: {e}", exc_info=True)
                    # On error, still signal next sentence to prevent deadlock
                    # Acquire lock to ensure proper ordering even in error case
                    async with playback_lock:
                        next_sentence = sentence_num + 1
                        if next_sentence in sentence_events:
                            sentence_events[next_sentence].set()
            
            sentence_num = 0
            tts_tasks = []
            
            # Stream LLM response and process sentences in parallel (with ordered playback)
            first_llm_chunk = True
            async for llm_chunk in self.ai_assistant.generate_llm_response_stream(transcript):
                if llm_chunk:
                    if first_llm_chunk:
                        # Track time to first LLM token
                        perf_times['llm_first_token'] = asyncio.get_event_loop().time()
                        logger.info(f"LLM first token received in {perf_times['llm_first_token'] - llm_start:.3f}s")
                        first_llm_chunk = False
                    
                    logger.debug(f"LLM chunk: '{llm_chunk}'")
                    llm_parts.append(llm_chunk)
                    sentence_buffer += llm_chunk
                    
                    # Check for sentence boundaries - trigger on punctuation (with or without space/newline)
                    # Process multiple sentences if they exist in the buffer
                    while True:
                        # Find sentence-ending punctuation (. ! ?) followed by space, newline, or end of text
                        # Also handle mid-sentence splits for long text
                        
                        # Match sentence endings: . ! ? followed by whitespace or end of string
                        # Also match : followed by newline (for intro lines like "here is a story:")
                        sentence_end_pattern = r'([.!?][\s\n]+|:\n)'
                        match = re.search(sentence_end_pattern, sentence_buffer)
                        
                        if match:
                            end_pos = match.end()
                            sentence = sentence_buffer[:end_pos].strip()
                            
                            # Only split if we have meaningful content (at least 3 words)
                            word_count = len(sentence.split())
                            if word_count >= 3:
                                sentence_buffer = sentence_buffer[end_pos:]
                                
                                if sentence:
                                    sentence_num += 1
                                    logger.debug(f"Sentence {sentence_num} extracted ({word_count} words): '{sentence[:50]}...'")
                                    # Start TTS task immediately (don't await - process in parallel)
                                    task = asyncio.create_task(process_sentence_to_audio(sentence, sentence_num))
                                    tts_tasks.append(task)
                                    self.current_tts_tasks.append(task)  # Track for interruption
                            else:
                                # Not enough words yet, wait for more text
                                break
                        else:
                            # No sentence boundary found - check if buffer is getting too long
                            # If we have 20+ words, split at a comma or dash to start streaming earlier
                            word_count = len(sentence_buffer.split())
                            if word_count >= 20:
                                # Find a good break point (comma, dash, semicolon)
                                break_pattern = r'([,;—–-]\s+)'
                                break_match = re.search(break_pattern, sentence_buffer)
                                if break_match:
                                    end_pos = break_match.end()
                                    sentence = sentence_buffer[:end_pos].strip()
                                    sentence_buffer = sentence_buffer[end_pos:]
                                    
                                    if sentence:
                                        sentence_num += 1
                                        logger.debug(f"Sentence {sentence_num} extracted at break ({word_count} words): '{sentence[:50]}...'")
                                        task = asyncio.create_task(process_sentence_to_audio(sentence, sentence_num))
                                        tts_tasks.append(task)
                                        self.current_tts_tasks.append(task)  # Track for interruption
                                else:
                                    # No good break point, wait for punctuation
                                    break
                            else:
                                # Not enough text yet, wait for more
                                break
            
            llm_duration = asyncio.get_event_loop().time() - llm_start
            perf_times['llm_complete'] = asyncio.get_event_loop().time()
            full_llm_response = "".join(llm_parts)
            logger.info(f"LLM complete in {llm_duration:.3f}s: '{full_llm_response}'")
            
            # Stage 2: Process any remaining text in the buffer
            if sentence_buffer.strip():
                sentence_num += 1
                logger.info(f"Processing final text fragment as sentence {sentence_num}")
                task = asyncio.create_task(process_sentence_to_audio(sentence_buffer.strip(), sentence_num))
                tts_tasks.append(task)
                self.current_tts_tasks.append(task)  # Track for interruption
            
            # Wait for all TTS tasks to complete
            if tts_tasks:
                logger.info(f"Waiting for {len(tts_tasks)} TTS tasks to complete...")
                await asyncio.gather(*tts_tasks, return_exceptions=True)
                perf_times['tts_complete'] = asyncio.get_event_loop().time()
            
            # Keep speaking flag true while audio is still in the queue/playing
            # We'll clear it in a background task that monitors the queue
            asyncio.create_task(self._monitor_playback_completion())
            
            total_time = asyncio.get_event_loop().time() - start_time
            
            # Log detailed performance metrics
            if perf_times['llm_first_token']:
                time_to_first_token = perf_times['llm_first_token'] - start_time
                logger.info(f"⚡ Time to first LLM token: {time_to_first_token:.3f}s")
            
            if perf_times['tts_first_chunk']:
                time_to_first_audio = perf_times['tts_first_chunk'] - start_time
                logger.info(f"🔊 Time to first audio chunk: {time_to_first_audio:.3f}s")
            
            logger.info(
                f"✅ Pipeline complete in {total_time:.3f}s "
                f"(LLM: {llm_duration:.3f}s, TTS: {len(tts_tasks)} sentences with ordered playback)"
            )
            
        except Exception as e:
            logger.error(f"Error processing final transcript: {e}", exc_info=True)
        finally:
            # Don't clear speaking flag here - let the playback monitor do it
            # This allows interruption during audio playback, not just during TTS generation
            self.current_tts_tasks = []
    
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
