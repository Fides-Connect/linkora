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
        self.sample_rate = 48000  # Match WebRTC native rate
        self.channels = 1  
        self.samples_per_frame = 960  # 20ms at 48kHz
        self._timestamp = 0
        self._start = None
        self._next_frame_time = None
        self._buffer = np.array([], dtype=np.int16)
        
        # Comfort noise parameters
        self._comfort_noise_amplitude = 20  # Very low amplitude for subtle background noise
        self._last_frame_was_silence = False
        
    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback."""
        logger.debug(f"Queueing {len(audio_data)} bytes of audio, queue size before: {self.audio_queue.qsize()}")
        await self.audio_queue.put(audio_data)
    
    async def clear_queue(self):
        """Clear all pending audio from the queue and buffer."""
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # Clear the buffer
        self._buffer = np.array([], dtype=np.int16)
        logger.info("Audio queue and buffer cleared for interrupt")
    
    def _generate_comfort_noise(self, num_samples: int) -> np.ndarray:
        """Generate comfort noise to keep the audio stream alive.
        
        Uses pink noise (1/f noise) which is more natural sounding than white noise.
        Pink noise has more energy at lower frequencies, similar to natural ambient sound.
        """
        # Generate white noise
        white_noise = np.random.normal(0, 1, num_samples)
        
        # Apply simple pink noise filter (1/f characteristic)
        # Using a simple IIR filter approximation
        pink_noise = np.zeros(num_samples)
        b0, b1, b2 = 0.99886, 0.0555179, -0.0750759
        pink_noise[0] = white_noise[0]
        pink_noise[1] = b0 * white_noise[1] + b1 * white_noise[0]
        for i in range(2, num_samples):
            pink_noise[i] = b0 * white_noise[i] + b1 * white_noise[i-1] + b2 * white_noise[i-2]
        
        # Normalize and scale to desired amplitude
        pink_noise = pink_noise / np.max(np.abs(pink_noise)) * self._comfort_noise_amplitude
        
        return pink_noise.astype(np.int16)
    
    async def recv(self) -> AudioFrame:
        """Receive audio frame.
        
        This method ALWAYS returns an audio frame, either with real audio data
        or comfort noise to keep the WebRTC connection alive.
        """
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
            
            # Try to get audio from queue (non-blocking with short timeout)
            has_new_audio = False
            try:
                audio_data = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=0.001  # Very short timeout - don't wait long
                )
                logger.debug(f"Got {len(audio_data)} bytes from queue")
                
                # Convert bytes to numpy array and append to buffer
                new_samples = np.frombuffer(audio_data, dtype=np.int16)
                self._buffer = np.concatenate([self._buffer, new_samples])
                logger.debug(f"Buffer now has {len(self._buffer)} samples")
                has_new_audio = True
                
            except asyncio.TimeoutError:
                # No audio available - we'll send comfort noise
                pass
            
            # Check if we have enough samples for a frame
            if len(self._buffer) >= self.samples_per_frame:
                # Extract exactly one frame worth of samples
                audio_array = self._buffer[:self.samples_per_frame]
                # Keep the rest in the buffer for next frame
                self._buffer = self._buffer[self.samples_per_frame:]
                logger.debug(f"Extracted {len(audio_array)} samples, {len(self._buffer)} samples remain in buffer")
                self._last_frame_was_silence = False
                
            elif len(self._buffer) > 0:
                # Not enough for a full frame, but we have some - pad with comfort noise
                logger.debug(f"Padding: {len(self._buffer)} -> {self.samples_per_frame} samples")
                padding_size = self.samples_per_frame - len(self._buffer)
                comfort_noise = self._generate_comfort_noise(padding_size)
                audio_array = np.concatenate([self._buffer, comfort_noise])
                self._buffer = np.array([], dtype=np.int16)
                self._last_frame_was_silence = False
                
            else:
                # No audio available, generate comfort noise
                if not self._last_frame_was_silence:
                    logger.debug("No audio in buffer - generating comfort noise")
                    self._last_frame_was_silence = True
                audio_array = self._generate_comfort_noise(self.samples_per_frame)
            
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
            # Return comfort noise on error to keep stream alive
            comfort_noise = self._generate_comfort_noise(self.samples_per_frame)
            
            frame = AudioFrame(
                format='s16',
                layout='mono',
                samples=self.samples_per_frame
            )
            frame.planes[0].update(comfort_noise.tobytes())
            frame.sample_rate = self.sample_rate
            frame.pts = self._timestamp
            frame.time_base = Fraction(1, self.sample_rate)
            
            self._timestamp += self.samples_per_frame
            if self._next_frame_time:
                self._next_frame_time += self.samples_per_frame / self.sample_rate
            
            return frame
