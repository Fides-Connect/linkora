"""
Audio Output Track
Custom MediaStreamTrack for streaming audio output.
"""
import asyncio
import logging
import numpy as np
import time
from typing import Optional
from aiortc import MediaStreamTrack
from av import AudioFrame
from fractions import Fraction

logger = logging.getLogger(__name__)


class AudioOutputTrack(MediaStreamTrack):
    """Custom audio track for outputting synthesized speech."""
    
    kind = "audio"
    
    def __init__(self):
        super().__init__()
        self.audio_queue = asyncio.Queue()
        self.sample_rate = 48000  # 48kHz to match WebRTC standard
        self.channels = 1
        self.samples_per_frame = 960  # 20ms at 48kHz
        self._timestamp = 0
        self._start = None
        self._next_frame_time = None
        self._buffer = np.array([], dtype=np.int16)  # Buffer for partial frames
        
    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback, resampling from 24kHz to 48kHz if needed."""
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Resample from 24kHz to 48kHz (2x upsampling)
        # Simple linear interpolation for 2x upsampling
        upsampled = np.repeat(audio_array, 2)  # Simple repeat method
        
        logger.debug(f"Queueing {len(audio_data)} bytes of audio (resampled to {len(upsampled)*2} bytes), queue size before: {self.audio_queue.qsize()}")
        await self.audio_queue.put(upsampled.tobytes())
    
    async def recv(self) -> AudioFrame:
        """Receive audio frame."""
        try:
            # Initialize timing on first frame
            if self._start is None:
                self._start = time.time()
                self._next_frame_time = self._start
            
            # Calculate when this frame should be sent
            frame_duration = self.samples_per_frame / self.sample_rate
            current_time = time.time()
            
            # Wait if we're ahead of schedule
            if current_time < self._next_frame_time:
                await asyncio.sleep(self._next_frame_time - current_time)
            
            logger.debug(f"recv() called - queue size: {self.audio_queue.qsize()}, buffer size: {len(self._buffer)} samples")
            
            # Fill buffer until we have enough samples for a frame
            while len(self._buffer) < self.samples_per_frame:
                try:
                    audio_data = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=0.05
                    )
                    logger.debug(f"Got {len(audio_data)} bytes from queue")
                    
                    # Convert bytes to numpy array and append to buffer
                    new_samples = np.frombuffer(audio_data, dtype=np.int16)
                    self._buffer = np.concatenate([self._buffer, new_samples])
                    logger.debug(f"Buffer now has {len(self._buffer)} samples")
                    
                except asyncio.TimeoutError:
                    logger.debug("Queue timeout - checking if we have enough samples")
                    break
            
            # Check if we have enough samples for a frame
            if len(self._buffer) >= self.samples_per_frame:
                # Extract exactly one frame worth of samples
                audio_array = self._buffer[:self.samples_per_frame]
                # Keep the rest in the buffer for next frame
                self._buffer = self._buffer[self.samples_per_frame:]
                logger.debug(f"Extracted {len(audio_array)} samples, {len(self._buffer)} samples remain in buffer")
                
            elif len(self._buffer) > 0:
                # Not enough for a full frame, but we have some - pad with silence
                logger.debug(f"Padding: {len(self._buffer)} -> {self.samples_per_frame} samples")
                audio_array = np.pad(
                    self._buffer,
                    (0, self.samples_per_frame - len(self._buffer)),
                    mode='constant'
                )
                self._buffer = np.array([], dtype=np.int16)
                
            else:
                # No audio available, return silence
                logger.debug("No audio in buffer - returning silence frame")
                audio_array = np.zeros(self.samples_per_frame, dtype=np.int16)
            
            # Create audio frame
            frame = AudioFrame(
                format='s16',
                layout='mono',
                samples=self.samples_per_frame
            )
            
            # Set audio data
            frame.planes[0].update(audio_array.tobytes())
            frame.sample_rate = self.sample_rate
            frame.pts = self._timestamp
            frame.time_base = Fraction(1, self.sample_rate)
            
            logger.debug(f"Created frame: pts={self._timestamp}, samples={self.samples_per_frame}, sample_rate={self.sample_rate}")
            
            # Update timestamp and next frame time
            self._timestamp += self.samples_per_frame
            self._next_frame_time += frame_duration
            
            return frame
            
        except Exception as e:
            logger.error(f"Error in recv(): {e}", exc_info=True)
            # Return silence on error
            silence = np.zeros(self.samples_per_frame, dtype=np.int16)
            
            frame = AudioFrame(
                format='s16',
                layout='mono',
                samples=self.samples_per_frame
            )
            frame.planes[0].update(silence.tobytes())
            frame.sample_rate = self.sample_rate
            frame.pts = self._timestamp
            frame.time_base = Fraction(1, self.sample_rate)
            
            self._timestamp += self.samples_per_frame
            if self._next_frame_time:
                self._next_frame_time += self.samples_per_frame / self.sample_rate
            
            return frame
