"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import numpy as np
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
                    if is_final:
                        logger.info(f"Final transcript: '{transcript}'")
                        # Process complete transcript through LLM
                        await self._process_final_transcript(transcript)
                    else:
                        logger.debug(f"Interim transcript: '{transcript}'")
                        # Could update UI with interim results if needed
            
            logger.info("Continuous STT streaming ended")
            
        except asyncio.CancelledError:
            logger.info("Continuous STT cancelled")
        except Exception as e:
            logger.error(f"Error in continuous STT: {e}", exc_info=True)
    
    async def _process_final_transcript(self, transcript: str):
        """Process a final transcript through LLM -> TTS pipeline."""
        try:
            logger.info(f"Processing final transcript: '{transcript}'")
            start_time = asyncio.get_event_loop().time()
            
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
                    logger.info(f"TTS for sentence {sentence_num}: '{sentence}'")
                    
                    # Create event for this sentence
                    nonlocal next_sentence_to_play, sentence_events
                    my_event = asyncio.Event()
                    sentence_events[sentence_num] = my_event
                    
                    # If we're sentence 1, set our event immediately
                    if sentence_num == 1:
                        my_event.set()
                    
                    # Process TTS to get all audio chunks for this sentence
                    audio_chunks = []
                    async for audio_chunk in self.ai_assistant.text_to_speech_stream(sentence):
                        if audio_chunk:
                            audio_chunks.append(audio_chunk)
                    
                    logger.debug(f"TTS sentence {sentence_num} complete: {len(audio_chunks)} chunks, waiting for turn to play...")
                    
                    # Wait for our turn to play
                    await my_event.wait()
                    
                    # Now queue all our audio chunks atomically (hold playback_lock to prevent interleaving)
                    async with playback_lock:
                        # Add initial silence before first sentence to prevent cutoff
                        if sentence_num == 1:
                            initial_silence = np.zeros(4800, dtype=np.int16)  # 100ms buffer
                            await self.output_track.queue_audio(initial_silence.tobytes())
                            logger.debug("Added 100ms initial silence before first sentence")
                        
                        logger.info(f"Playing sentence {sentence_num} ({len(audio_chunks)} chunks)")
                        
                        # Combine all audio chunks into a single array for processing
                        combined_audio = b''.join(audio_chunks)
                        # Make a writable copy of the array
                        audio_samples = np.frombuffer(combined_audio, dtype=np.int16).copy()
                        
                        # Apply smooth fade-in at start (10ms) and fade-out at end (10ms) to prevent clicks
                        # Using cosine curve for smoother transitions
                        fade_samples = min(480, len(audio_samples) // 2)  # 10ms at 48kHz
                        if fade_samples > 0:
                            # Fade-in at start (except for first sentence which already has silence)
                            if sentence_num > 1:
                                # Cosine fade-in: 0 to 1 (smoother than linear)
                                fade_in = (1.0 - np.cos(np.linspace(0, np.pi, fade_samples))) / 2.0
                                audio_samples[:fade_samples] = (audio_samples[:fade_samples] * fade_in).astype(np.int16)
                            
                            # Cosine fade-out: 1 to 0 (smoother than linear)
                            fade_out = (1.0 + np.cos(np.linspace(0, np.pi, fade_samples))) / 2.0
                            audio_samples[-fade_samples:] = (audio_samples[-fade_samples:] * fade_out).astype(np.int16)
                        
                        # Queue the processed audio
                        await self.output_track.queue_audio(audio_samples.tobytes())
                        
                        # Add silence gap after each sentence (100ms for natural pause)
                        silence_gap = np.zeros(4800, dtype=np.int16)  # 100ms at 48kHz
                        await self.output_track.queue_audio(silence_gap.tobytes())
                        logger.debug(f"Added 100ms silence gap after sentence {sentence_num}")
                        
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
            async for llm_chunk in self.ai_assistant.generate_llm_response_stream(transcript):
                if llm_chunk:
                    logger.debug(f"LLM chunk: '{llm_chunk}'")
                    llm_parts.append(llm_chunk)
                    sentence_buffer += llm_chunk
                    
                    # Check for sentence boundaries (., !, ?)
                    while True:
                        # Find the earliest sentence boundary
                        boundaries = [
                            (sentence_buffer.find('. '), '. '),
                            (sentence_buffer.find('! '), '! '),
                            (sentence_buffer.find('? '), '? '),
                        ]
                        boundaries = [(pos, sep) for pos, sep in boundaries if pos >= 0]
                        
                        if not boundaries:
                            break
                        
                        # Get the earliest boundary
                        boundary_pos, separator = min(boundaries, key=lambda x: x[0])
                        
                        # Extract the sentence
                        sentence = sentence_buffer[:boundary_pos + len(separator)].strip()
                        sentence_buffer = sentence_buffer[boundary_pos + len(separator):]
                        
                        if sentence:
                            sentence_num += 1
                            # Start TTS task immediately (don't await - process in parallel)
                            task = asyncio.create_task(process_sentence_to_audio(sentence, sentence_num))
                            tts_tasks.append(task)
            
            llm_duration = asyncio.get_event_loop().time() - llm_start
            full_llm_response = "".join(llm_parts)
            logger.info(f"LLM complete in {llm_duration:.2f}s: '{full_llm_response}'")
            
            # Stage 2: Process any remaining text in the buffer
            if sentence_buffer.strip():
                sentence_num += 1
                logger.info(f"Processing final text fragment as sentence {sentence_num}")
                task = asyncio.create_task(process_sentence_to_audio(sentence_buffer.strip(), sentence_num))
                tts_tasks.append(task)
            
            # Wait for all TTS tasks to complete
            if tts_tasks:
                logger.info(f"Waiting for {len(tts_tasks)} TTS tasks to complete...")
                await asyncio.gather(*tts_tasks, return_exceptions=True)
            
            total_time = asyncio.get_event_loop().time() - start_time
            logger.info(
                f"Pipeline complete in {total_time:.2f}s "
                f"(LLM: {llm_duration:.2f}s, TTS: {len(tts_tasks)} sentences with ordered playback)"
            )
            
        except Exception as e:
            logger.error(f"Error processing final transcript: {e}", exc_info=True)
