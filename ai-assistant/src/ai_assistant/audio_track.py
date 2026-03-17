"""
Audio Output Track
Custom MediaStreamTrack for streaming audio output.
"""
import asyncio
import collections
import logging
import numpy as np
import time
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
        self.sample_rate = 24000  # 24kHz: half the TTS payload vs 48kHz; aiortc resamples to 48kHz for RTP
        self.channels = 1  
        self.samples_per_frame = 480  # 20ms at 24kHz
        self._timestamp = 0
        self._start = None
        self._next_frame_time = None
        # Ring-buffer implemented as a deque of raw int16 bytes chunks.
        # Avoids O(N) np.concatenate allocations at 50 Hz.
        self._buffer: collections.deque[bytes] = collections.deque()
        self._buffer_samples = 0  # total int16 samples across all chunks

        # Comfort noise parameters
        self._comfort_noise_amplitude = 20  # Very low amplitude for subtle background noise
        self._last_frame_was_silence = False

    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for playback."""
        logger.debug("Queueing %s bytes of audio, queue size before: %s", len(audio_data), self.audio_queue.qsize())
        await self.audio_queue.put(audio_data)

    async def clear_queue(self):
        """Clear all pending audio from the queue and buffer."""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._buffer.clear()
        self._buffer_samples = 0
        logger.info("Audio queue and buffer cleared for interrupt")

    def _drain_queue_into_buffer(self) -> None:
        """Move all currently available queue items into the sample buffer (non-blocking)."""
        while True:
            try:
                audio_data: bytes = self.audio_queue.get_nowait()
                self._buffer.append(audio_data)
                self._buffer_samples += len(audio_data) // 2  # int16 = 2 bytes
                logger.debug(f"Got {len(audio_data)} bytes from queue, buffer={self._buffer_samples} samples")
            except asyncio.QueueEmpty:
                break

    def _read_samples_from_buffer(self, n: int) -> np.ndarray:
        """Consume exactly *n* int16 samples from the deque buffer."""
        # Fast path — single chunk covers the entire request
        if self._buffer and len(self._buffer[0]) // 2 >= n:
            chunk = self._buffer[0]
            arr = np.frombuffer(chunk[:n * 2], dtype=np.int16).copy()
            remainder = chunk[n * 2:]
            if remainder:
                self._buffer[0] = remainder
            else:
                self._buffer.popleft()
            self._buffer_samples -= n
            return arr

        # General path — gather from multiple chunks
        out = np.empty(n, dtype=np.int16)
        written = 0
        while written < n and self._buffer:
            chunk = self._buffer[0]
            chunk_samples = len(chunk) // 2
            need = n - written
            if chunk_samples <= need:
                out[written:written + chunk_samples] = np.frombuffer(chunk, dtype=np.int16)
                written += chunk_samples
                self._buffer_samples -= chunk_samples
                self._buffer.popleft()
            else:
                out[written:] = np.frombuffer(chunk[:need * 2], dtype=np.int16)
                self._buffer[0] = chunk[need * 2:]
                self._buffer_samples -= need
                written = n
        return out[:written]
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

            logger.debug(f"recv() called - queue size: {self.audio_queue.qsize()}, buffer size: {self._buffer_samples} samples")

            # Drain all currently available queue items into the deque buffer.
            self._drain_queue_into_buffer()

            # If the buffer is short, wait out the remaining frame budget before
            # padding — a late-arriving TTS chunk can still fill the frame cleanly
            # rather than mixing real audio with comfort noise at sentence starts.
            if self._buffer_samples < self.samples_per_frame:
                remaining = self._next_frame_time - time.time()
                if remaining > 0.001:  # only worth waiting if > 1 ms remains
                    await asyncio.sleep(remaining)
                    self._drain_queue_into_buffer()

            if self._buffer_samples >= self.samples_per_frame:
                audio_array = self._read_samples_from_buffer(self.samples_per_frame)
                logger.debug(f"Extracted {self.samples_per_frame} samples, {self._buffer_samples} remain")
                self._last_frame_was_silence = False

            elif self._buffer_samples > 0:
                # Still short after waiting — pad the tail with comfort noise.
                partial = self._read_samples_from_buffer(self._buffer_samples)
                padding_size = self.samples_per_frame - len(partial)
                logger.debug(f"Padding: {len(partial)} -> {self.samples_per_frame} samples")
                comfort_noise = self._generate_comfort_noise(padding_size)
                audio_array = np.concatenate([partial, comfort_noise])
                self._last_frame_was_silence = False

            else:
                # Silence — generate comfort noise
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

            logger.debug("Created frame: pts=%s, samples=%s, sample_rate=%s", self._timestamp, self.samples_per_frame, self.sample_rate)

            # Update timestamp and next frame time
            self._timestamp += self.samples_per_frame
            self._next_frame_time += frame_duration

            return frame

        except Exception as e:
            logger.error("Error in recv(): %s", e, exc_info=True)
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
