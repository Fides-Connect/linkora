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
        self.sample_rate = 16000  # Google Cloud requires 16kHz
        self.silence_threshold = 23400  # Amplitude threshold for silence detection
        self.silence_duration = 1.5  # Seconds of silence to trigger processing
        self.min_speech_duration = 0.5  # Minimum speech duration in seconds
        
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
        logger.info(f"Audio processor stopped for connection {self.connection_id}")
    
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
                    
                    # Detect speech vs silence
                    #is_silence = self._is_silence(audio_data)
                    is_silence = frame_count > 10 and frame_count < 50
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
        
        # Convert to numpy array and ensure it's in the correct format
        array = frame.to_ndarray()
        logger.debug(f"Frame.to_ndarray() result: shape={array.shape}, dtype={array.dtype}")
        
        # If stereo, convert to mono
        if len(array.shape) > 1:
            logger.debug(f"Converting stereo to mono (original shape: {array.shape})")
            array = array.mean(axis=0)
        
        # Convert to int16 format for Google Cloud
        if array.dtype != np.int16:
            logger.debug(f"Converting from {array.dtype} to int16")
            array = (array * 32767).astype(np.int16)
        
        logger.debug(f"Final numpy array: shape={array.shape}, dtype={array.dtype}, min={array.min()}, max={array.max()}")
        return array
    
    def _is_silence(self, audio_data: np.ndarray) -> bool:
        """Detect if audio data is silence."""
        rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))
        return rms < self.silence_threshold
    
    async def _process_speech_segment(self):
        """Process a complete speech segment through STT -> LLM -> TTS."""
        try:
            logger.info(f"Processing speech segment ({len(self.audio_buffer)} frames)")
            logger.debug(f"Buffer details: total_frames={len(self.audio_buffer)}")
            
            # Concatenate audio buffer
            audio_data = np.concatenate(self.audio_buffer)
            audio_bytes = audio_data.tobytes()
            
            logger.debug(f"Concatenated audio: samples={len(audio_data)}, bytes={len(audio_bytes)}, duration={len(audio_data)/self.sample_rate:.2f}s")
            
            # Step 1: Speech-to-Text
            logger.info("Step 1/3: Performing speech-to-text...")
            logger.debug(f"Sending {len(audio_bytes)} bytes to STT")
            transcript = await self.ai_assistant.speech_to_text(audio_bytes)
            transcript = "Hallo! Wie geht es dir?"
            
            if not transcript or transcript.strip() == "":
                logger.info("No speech detected in segment (empty transcript)")
                return
            
            logger.info(f"Transcript received: '{transcript}' (length: {len(transcript)} chars)")
            
            # Step 2: LLM Processing
            logger.info("Step 2/3: Generating LLM response...")
            logger.debug(f"Sending transcript to LLM: '{transcript}'")
            llm_response = await self.ai_assistant.generate_llm_response(transcript)
            logger.info(f"LLM Response received: '{llm_response}' (length: {len(llm_response)} chars)")
            
            # Step 3: Text-to-Speech
            logger.info("Step 3/3: Converting to speech...")
            logger.debug(f"Sending to TTS: '{llm_response}'")
            
            chunk_count = 0
            async for audio_chunk in self.ai_assistant.text_to_speech_stream(llm_response):
                chunk_count += 1
                chunk_size = len(audio_chunk)
                logger.debug(f"TTS chunk {chunk_count}: {chunk_size} bytes")
                # Send audio chunks to output track
                await self.output_track.queue_audio(audio_chunk)
            
            logger.info(f"Speech segment processed successfully ({chunk_count} audio chunks)")
            
        except Exception as e:
            logger.error(f"Error processing speech segment: {e}", exc_info=True)
