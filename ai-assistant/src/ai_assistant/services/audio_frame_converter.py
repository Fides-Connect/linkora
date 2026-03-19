"""
Audio Frame Conversion Service
Handles conversion of audio frames to numpy arrays and format transformations.
"""
import logging
import numpy as np
from av import AudioFrame

logger = logging.getLogger(__name__)


class AudioFrameConverter:
    """Converts audio frames between different formats."""

    def __init__(self, sample_rate: int = 48000) -> None:
        """
        Initialize audio frame converter.

        Args:
            sample_rate: Target sample rate in Hz
        """
        self.sample_rate = sample_rate

    def frame_to_numpy(self, frame: AudioFrame) -> np.ndarray:
        """
        Convert audio frame to numpy array.

        Args:
            frame: Audio frame to convert

        Returns:
            Numpy array with audio samples in int16 format
        """
        logger.debug("Converting frame: format=%s, layout=%s", frame.format, frame.layout)

        # Convert to numpy array
        array = frame.to_ndarray()
        logger.debug("Frame.to_ndarray() result: shape=%s, dtype=%s", array.shape, array.dtype)

        # Convert to mono if needed
        array = self._convert_to_mono(array)

        # Convert to int16 format
        array = self._convert_to_int16(array)

        # Validate output
        if len(array) == 0:
            logger.error("Conversion resulted in empty array!")
            return np.zeros(480, dtype=np.int16)

        self._log_audio_stats(array)

        return array

    def _convert_to_mono(self, array: np.ndarray) -> np.ndarray:
        """Convert stereo audio to mono."""
        if len(array.shape) <= 1:
            return array

        if array.shape[0] == 1:
            # Interleaved stereo - reshape to separate channels
            logger.debug("Reshaping interleaved stereo: %s -> (-1, 2)", array.shape)
            array = array.reshape(-1, 2)

        # Average channels to create mono
        logger.debug("Converting stereo to mono (shape: %s)", array.shape)
        array = array.mean(axis=1).astype(array.dtype)
        logger.debug("After mono conversion: shape=%s, dtype=%s", array.shape, array.dtype)

        return array

    def _convert_to_int16(self, array: np.ndarray) -> np.ndarray:
        """Convert audio array to int16 format."""
        if array.dtype == np.int16:
            return array

        logger.warning("Converting from %s to int16", array.dtype)

        if array.dtype in (np.float32, np.float64):
            return self._convert_float_to_int16(array)
        else:
            return array.astype(np.int16)

    def _convert_float_to_int16(self, array: np.ndarray) -> np.ndarray:
        """Convert floating-point audio to int16."""
        array_min, array_max = array.min(), array.max()
        logger.debug("Float range: [%s, %s]", array_min, array_max)

        if -1.0 <= array_min and array_max <= 1.0:
            # Normalized range
            logger.debug("Float audio in normalized range [-1.0, 1.0]")
            return (array * 32767).astype(np.int16)
        else:
            # Out of range - normalize first
            logger.warning("Float audio out of expected range: [%s, %s]", array_min, array_max)
            array = array / max(abs(array_min), abs(array_max))
            return (array * 32767).astype(np.int16)

    def _log_audio_stats(self, array: np.ndarray) -> None:
        """Log statistics about the audio array."""
        final_min, final_max = array.min(), array.max()
        rms = np.sqrt(np.mean(array.astype(float) ** 2))

        logger.debug("Audio stats: shape=%s, dtype=%s, min=%s, max=%s, RMS=%.2f", array.shape, array.dtype, final_min, final_max, rms)

        if rms < 10:
            logger.debug("Very low RMS (%.2f) - might be silence", rms)
