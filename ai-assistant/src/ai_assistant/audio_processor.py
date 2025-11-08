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
        
        # Audio buffer for STT
        self.audio_buffer = []
        self.sample_rate = 48000  # WebRTC sends 48kHz - match it exactly
        self.silence_threshold = 500  # Amplitude threshold for silence detection
        self.silence_duration = 1.5  # Seconds of silence to trigger processing
        self.min_speech_duration = 0.5  # Minimum speech duration in seconds
        
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
        logger.info(f"Audio processor started for connection {self.connection_id}")
        logger.debug(f"VAD settings - silence_threshold={self.silence_threshold}, silence_duration={self.silence_duration}s")
    
    async def stop(self):
        """Stop processing audio."""
        logger.debug(f"Stopping audio processor for connection {self.connection_id}")
        self.running = False
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
        """Main audio processing loop."""
        try:
            silence_frames = 0
            speech_frames = 0
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
                    
                    # Detect speech vs silence
                    is_silence = self._is_silence(audio_data)
                    rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))
                    logger.debug(f"[Frame {frame_count}] Audio level: RMS={rms:.2f}, is_silence={is_silence}")
                    
                    if not is_silence:
                        # Speech detected
                        speech_frames += 1
                        silence_frames = 0
                        self.audio_buffer.append(audio_data)
                        logger.debug(f"[Frame {frame_count}] Speech detected! Total speech frames: {speech_frames}, buffer size: {len(self.audio_buffer)}")
                    else:
                        # Silence detected
                        if len(self.audio_buffer) > 0:
                            silence_frames += 1
                            self.audio_buffer.append(audio_data)
                            
                            # Check if we have enough silence to process
                            silence_duration = silence_frames / (self.sample_rate / frame.samples)
                            speech_duration = speech_frames / (self.sample_rate / frame.samples)
                            
                            logger.debug(
                                f"[Frame {frame_count}] Silence in buffer: {silence_frames} frames, "
                                f"duration={silence_duration:.2f}s, speech_duration={speech_duration:.2f}s"
                            )
                            
                            if silence_duration >= self.silence_duration:
                                if speech_duration >= self.min_speech_duration:
                                    logger.info(
                                        f"[Frame {frame_count}] Processing speech segment: "
                                        f"speech={speech_duration:.2f}s, silence={silence_duration:.2f}s, "
                                        f"buffer_frames={len(self.audio_buffer)}"
                                    )
                                    # Process the accumulated audio
                                    await self._process_speech_segment()
                                else:
                                    logger.debug(
                                        f"[Frame {frame_count}] Discarding short speech segment: "
                                        f"duration={speech_duration:.2f}s < {self.min_speech_duration}s"
                                    )
                                
                                # Reset buffers
                                self.audio_buffer = []
                                silence_frames = 0
                                speech_frames = 0
                                logger.debug(f"[Frame {frame_count}] Buffer reset")
                        else:
                            logger.debug(f"[Frame {frame_count}] Silence detected (no buffer)")
                    
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
            logger.warning(f"Audio frame has very low RMS ({rms:.2f}) - might be silence or incorrect conversion")
        
        return array
    
    def _is_silence(self, audio_data: np.ndarray) -> bool:
        """Detect if audio data is silence."""
        rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))
        return rms < self.silence_threshold
    
    async def _process_speech_segment(self):
        """Process a complete speech segment through STT -> LLM -> TTS with full streaming for minimal latency.
        
        Pipeline design for maximum parallelism:
        1. STT streams transcript chunks as they're recognized
        2. Once STT completes, immediately start LLM streaming
        3. As LLM produces text chunks, buffer them and synthesize in batches
        4. Stream audio back to user as soon as TTS produces chunks
        """
        try:
            logger.info(f"Processing speech segment ({len(self.audio_buffer)} frames)")
            logger.debug(f"Buffer details: total_frames={len(self.audio_buffer)}")
            
            # Concatenate audio buffer
            audio_data = np.concatenate(self.audio_buffer)
            audio_bytes = audio_data.tobytes()
            
            logger.debug(f"Concatenated audio: samples={len(audio_data)}, bytes={len(audio_bytes)}, duration={len(audio_data)/self.sample_rate:.2f}s")
            
            start_time = asyncio.get_event_loop().time()
            
            # Stage 1: Speech-to-Text (Streaming)
            logger.info("Stage 1: Starting streaming STT...")
            stt_start = asyncio.get_event_loop().time()
            
            transcript_parts = []
            async for transcript_chunk in self.ai_assistant.speech_to_text_stream(audio_bytes):
                if transcript_chunk and transcript_chunk.strip():
                    logger.info(f"STT chunk: '{transcript_chunk}'")
                    transcript_parts.append(transcript_chunk)
            
            full_transcript = " ".join(transcript_parts).strip()
            stt_duration = asyncio.get_event_loop().time() - stt_start
            
            if not full_transcript:
                logger.info("No speech detected in segment (empty transcript)")
                return
            
            logger.info(f"STT complete in {stt_duration:.2f}s: '{full_transcript}'")
            
            # Stage 2: LLM Processing (Streaming)
            logger.info("Stage 2: Starting streaming LLM...")
            llm_start = asyncio.get_event_loop().time()
            
            llm_parts = []
            sentence_buffer = ""
            tts_tasks = []
            
            async def process_sentence_to_audio(sentence: str, sentence_num: int):
                """Process a complete sentence through TTS and queue audio."""
                try:
                    logger.info(f"TTS for sentence {sentence_num}: '{sentence}'")
                    chunk_count = 0
                    async for audio_chunk in self.ai_assistant.text_to_speech_stream(sentence):
                        if audio_chunk:
                            chunk_count += 1
                            await self.output_track.queue_audio(audio_chunk)
                    logger.debug(f"TTS sentence {sentence_num} complete: {chunk_count} chunks")
                except Exception as e:
                    logger.error(f"Error in TTS for sentence {sentence_num}: {e}", exc_info=True)
            
            sentence_num = 0
            
            # Stream LLM response and process sentences in parallel
            async for llm_chunk in self.ai_assistant.generate_llm_response_stream(full_transcript):
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
                            # Start TTS for this sentence in parallel
                            task = asyncio.create_task(process_sentence_to_audio(sentence, sentence_num))
                            tts_tasks.append(task)
            
            llm_duration = asyncio.get_event_loop().time() - llm_start
            full_llm_response = "".join(llm_parts)
            logger.info(f"LLM complete in {llm_duration:.2f}s: '{full_llm_response}'")
            
            # Stage 3: Process any remaining text in the buffer
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
                f"(STT: {stt_duration:.2f}s, LLM: {llm_duration:.2f}s, "
                f"TTS: {sentence_num} sentences processed in parallel)"
            )
            
        except Exception as e:
            logger.error(f"Error in speech segment processing pipeline: {e}", exc_info=True)