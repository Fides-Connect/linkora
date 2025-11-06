"""
Audio Output Track
Custom MediaStreamTrack for streaming audio output.
"""
import asyncio
import logging
import numpy as np
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
        self.sample_rate = 16000
        self.channels = 1
        self.samples_per_frame = 480  # 30ms at 16kHz
        self._timestamp = 0
        self._start = None
        
    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback."""
        logger.debug(f"Queueing {len(audio_data)} bytes of audio (queue size before: {self.audio_queue.qsize()})")
        await self.audio_queue.put(audio_data)
    
    async def recv(self) -> AudioFrame:
        """Receive audio frame."""
        try:
            logger.debug(f"recv() called - queue size: {self.audio_queue.qsize()}")
            
            # Get audio data from queue
            audio_data = await asyncio.wait_for(
                self.audio_queue.get(),
                timeout=0.1
            )
            
            logger.debug(f"Got {len(audio_data)} bytes from queue")
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            logger.debug(f"Converted to array: {len(audio_array)} samples")
            
            # Ensure we have the right amount of samples
            if len(audio_array) < self.samples_per_frame:
                logger.debug(f"Padding: {len(audio_array)} -> {self.samples_per_frame} samples")
                # Pad with zeros if too short
                audio_array = np.pad(
                    audio_array,
                    (0, self.samples_per_frame - len(audio_array)),
                    mode='constant'
                )
            elif len(audio_array) > self.samples_per_frame:
                logger.debug(f"Splitting: {len(audio_array)} samples, keeping {self.samples_per_frame}, requeueing {len(audio_array) - self.samples_per_frame}")
                # Put excess back in queue
                excess = audio_array[self.samples_per_frame:]
                audio_array = audio_array[:self.samples_per_frame]
                await self.audio_queue.put(excess.tobytes())
            
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
            
            logger.debug(f"Created frame: pts={self._timestamp}, samples={self.samples_per_frame}")
            
            # Update timestamp
            self._timestamp += self.samples_per_frame
            
            return frame
            
        except asyncio.TimeoutError:
            # No audio available, return silence
            logger.debug("Queue timeout - returning silence frame")
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
            
            return frame
