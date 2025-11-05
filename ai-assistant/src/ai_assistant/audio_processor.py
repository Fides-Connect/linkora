"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import numpy as np
from typing import Optional
from aiortc import MediaStreamTrack
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
        self.silence_threshold = 500  # Amplitude threshold for silence detection
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
    
    async def stop(self):
        """Stop processing audio."""
        self.running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Audio processor stopped for connection {self.connection_id}")
    
    async def _process_audio(self):
        """Main audio processing loop."""
        try:
            silence_frames = 0
            speech_frames = 0
            
            while self.running:
                try:
                    # Receive audio frame from input track
                    frame = await asyncio.wait_for(
                        self.input_track.recv(),
                        timeout=5.0
                    )
                    
                    # Convert frame to numpy array
                    audio_data = self._frame_to_numpy(frame)
                    
                    # Detect speech vs silence
                    is_silence = self._is_silence(audio_data)
                    
                    if not is_silence:
                        # Speech detected
                        speech_frames += 1
                        silence_frames = 0
                        self.audio_buffer.append(audio_data)
                    else:
                        # Silence detected
                        if len(self.audio_buffer) > 0:
                            silence_frames += 1
                            self.audio_buffer.append(audio_data)
                            
                            # Check if we have enough silence to process
                            silence_duration = silence_frames / (self.sample_rate / frame.samples)
                            speech_duration = speech_frames / (self.sample_rate / frame.samples)
                            
                            if silence_duration >= self.silence_duration:
                                if speech_duration >= self.min_speech_duration:
                                    # Process the accumulated audio
                                    await self._process_speech_segment()
                                
                                # Reset buffers
                                self.audio_buffer = []
                                silence_frames = 0
                                speech_frames = 0
                    
                except asyncio.TimeoutError:
                    logger.warning("Audio receive timeout")
                    continue
                except Exception as e:
                    logger.error(f"Error receiving frame: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info("Audio processing cancelled")
        except Exception as e:
            logger.error(f"Error in audio processing loop: {e}", exc_info=True)
    
    def _frame_to_numpy(self, frame: AudioFrame) -> np.ndarray:
        """Convert audio frame to numpy array."""
        # Convert to numpy array and ensure it's in the correct format
        array = frame.to_ndarray()
        
        # If stereo, convert to mono
        if len(array.shape) > 1:
            array = array.mean(axis=0)
        
        # Convert to int16 format for Google Cloud
        if array.dtype != np.int16:
            array = (array * 32767).astype(np.int16)
        
        return array
    
    def _is_silence(self, audio_data: np.ndarray) -> bool:
        """Detect if audio data is silence."""
        rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))
        return rms < self.silence_threshold
    
    async def _process_speech_segment(self):
        """Process a complete speech segment through STT -> LLM -> TTS."""
        try:
            logger.info("Processing speech segment")
            
            # Concatenate audio buffer
            audio_data = np.concatenate(self.audio_buffer)
            audio_bytes = audio_data.tobytes()
            
            # Step 1: Speech-to-Text
            logger.info("Performing speech-to-text...")
            transcript = await self.ai_assistant.speech_to_text(audio_bytes)
            
            if not transcript or transcript.strip() == "":
                logger.info("No speech detected in segment")
                return
            
            logger.info(f"Transcript: {transcript}")
            
            # Step 2: LLM Processing
            logger.info("Generating LLM response...")
            llm_response = await self.ai_assistant.generate_llm_response(transcript)
            logger.info(f"LLM Response: {llm_response}")
            
            # Step 3: Text-to-Speech
            logger.info("Converting to speech...")
            async for audio_chunk in self.ai_assistant.text_to_speech_stream(llm_response):
                # Send audio chunks to output track
                await self.output_track.queue_audio(audio_chunk)
            
            logger.info("Speech segment processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing speech segment: {e}", exc_info=True)
