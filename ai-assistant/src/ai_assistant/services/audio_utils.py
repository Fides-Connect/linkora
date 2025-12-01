"""
Audio Frame Utilities
Helper functions for audio frame processing and conversion.
"""
import logging
import numpy as np
from av import AudioFrame

logger = logging.getLogger(__name__)


class AudioFrameConverter:
    """Handles audio frame format conversions."""

    @staticmethod
    def frame_to_numpy(frame: AudioFrame) -> np.ndarray:
        """
        Convert audio frame to numpy array with proper format handling.
        
        Args:
            frame: AudioFrame to convert
            
        Returns:
            Numpy array of int16 audio samples
        """
        logger.debug(f"Converting frame: format={frame.format}, samples={frame.samples}")

        # Convert to numpy array
        array = frame.to_ndarray()
        logger.debug(f"Frame array: shape={array.shape}, dtype={array.dtype}")

        # Handle stereo to mono conversion
        array = AudioFrameConverter._handle_stereo_to_mono(array)

        # Ensure int16 format
        array = AudioFrameConverter._ensure_int16_format(array)

        # Validate output
        return AudioFrameConverter._validate_audio_array(array)

    @staticmethod
    def _handle_stereo_to_mono(array: np.ndarray) -> np.ndarray:
        """Convert stereo audio to mono if needed."""
        if len(array.shape) <= 1:
            return array

        if array.shape[0] == 1:
            # Shape is (1, N*2) - interleaved stereo
            logger.debug(f"Reshaping interleaved stereo: {array.shape} -> (-1, 2)")
            array = array.reshape(-1, 2)

        # Convert to mono by averaging channels
        logger.debug(f"Converting stereo to mono (shape: {array.shape})")
        array = array.mean(axis=1).astype(array.dtype)
        logger.debug(f"After mono conversion: shape={array.shape}")

        return array

    @staticmethod
    def _ensure_int16_format(array: np.ndarray) -> np.ndarray:
        """Ensure array is in int16 format."""
        if array.dtype == np.int16:
            return array

        logger.warning(f"Converting from {array.dtype} to int16")
        array_min, array_max = array.min(), array.max()
        logger.debug(f"Array range: min={array_min}, max={array_max}")

        if array.dtype in (np.float32, np.float64):
            array = AudioFrameConverter._convert_float_to_int16(array, array_min, array_max)
        else:
            array = array.astype(np.int16)

        return array

    @staticmethod
    def _convert_float_to_int16(
        array: np.ndarray,
        array_min: float,
        array_max: float
    ) -> np.ndarray:
        """Convert float audio to int16."""
        if -1.0 <= array_min and array_max <= 1.0:
            logger.debug("Float audio in normalized range [-1.0, 1.0]")
            return (array * 32767).astype(np.int16)
        else:
            logger.warning(f"Float audio out of expected range: [{array_min}, {array_max}]")
            array = array / max(abs(array_min), abs(array_max))
            return (array * 32767).astype(np.int16)

    @staticmethod
    def _validate_audio_array(array: np.ndarray) -> np.ndarray:
        """Validate and log audio array properties."""
        if len(array) == 0:
            logger.error("Conversion resulted in empty array!")
            return np.zeros(480, dtype=np.int16)

        final_min, final_max = array.min(), array.max()
        rms = np.sqrt(np.mean(array.astype(float) ** 2))
        logger.debug(
            f"Final array: shape={array.shape}, dtype={array.dtype}, "
            f"min={final_min}, max={final_max}, RMS={rms:.2f}"
        )

        if rms < 10:
            logger.debug(f"Audio has very low RMS ({rms:.2f}) - might be silence")

        return array


class AudioFadeProcessor:
    """Applies fade effects to audio to prevent clicks and pops."""

    @staticmethod
    def apply_fades(
        audio_samples: np.ndarray,
        is_first_sentence: bool = False
    ) -> np.ndarray:
        """
        Apply smooth fade-in and fade-out to audio samples.
        
        Args:
            audio_samples: Audio samples as int16 numpy array
            is_first_sentence: Whether this is the first sentence (longer fade-in)
            
        Returns:
            Audio samples with fades applied
        """
        # Make a writable copy
        audio = audio_samples.copy()

        # Calculate fade lengths
        fade_in_samples = AudioFadeProcessor._get_fade_in_length(
            len(audio),
            is_first_sentence
        )
        fade_out_samples = min(144, len(audio) // 2)  # 3ms at 48kHz

        # Apply fades
        audio = AudioFadeProcessor._apply_fade_in(audio, fade_in_samples)
        audio = AudioFadeProcessor._apply_fade_out(audio, fade_out_samples)

        return audio

    @staticmethod
    def _get_fade_in_length(audio_length: int, is_first_sentence: bool) -> int:
        """Calculate appropriate fade-in length."""
        # First sentence gets longer fade-in (10ms) to eliminate phone speaker crackling
        base_length = 480 if is_first_sentence else 144  # 10ms or 3ms at 48kHz
        return min(base_length, audio_length // 2)

    @staticmethod
    def _apply_fade_in(audio: np.ndarray, fade_samples: int) -> np.ndarray:
        """Apply cosine fade-in to audio."""
        if fade_samples <= 0:
            return audio

        # Cosine fade-in: 0 to 1 (smoother than linear)
        fade_curve = (1.0 - np.cos(np.linspace(0, np.pi, fade_samples))) / 2.0
        audio[:fade_samples] = (audio[:fade_samples] * fade_curve).astype(np.int16)

        return audio

    @staticmethod
    def _apply_fade_out(audio: np.ndarray, fade_samples: int) -> np.ndarray:
        """Apply cosine fade-out to audio."""
        if fade_samples <= 0:
            return audio

        # Cosine fade-out: 1 to 0 (smoother than linear)
        fade_curve = (1.0 + np.cos(np.linspace(0, np.pi, fade_samples))) / 2.0
        audio[-fade_samples:] = (audio[-fade_samples:] * fade_curve).astype(np.int16)

        return audio
