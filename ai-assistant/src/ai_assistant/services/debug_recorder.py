"""
Debug Recording Service
Handles audio recording for debugging purposes.
"""
import logging
import os
import wave
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class DebugRecorder:
    """Records audio frames for debugging."""

    def __init__(self, connection_id: str, sample_rate: int = 48000, enabled: bool | None = None) -> None:
        """
        Initialize debug recorder.

        Args:
            connection_id: Connection identifier
            sample_rate: Audio sample rate
            enabled: Whether recording is enabled (None = read from env)
        """
        self.connection_id = connection_id
        self.sample_rate = sample_rate
        self.frames: list[np.ndarray] = []

        if enabled is None:
            enabled = os.getenv('DEBUG_RECORD_AUDIO', 'false').lower() == 'true'

        self.enabled = enabled
        self.wav_path: str | None = None

        if self.enabled:
            self._setup_recording()

    def _setup_recording(self) -> None:
        """Set up recording directory and file path."""
        debug_dir = 'debug_audio'
        os.makedirs(debug_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.wav_path = os.path.join(
            debug_dir,
            f'received_audio_{self.connection_id}_{timestamp}.wav'
        )
        logger.info("Debug recording enabled: %s", self.wav_path)

    def add_frame(self, audio_data: np.ndarray) -> None:
        """
        Add an audio frame to the recording.

        Args:
            audio_data: Audio data as numpy array
        """
        if self.enabled:
            self.frames.append(audio_data.copy())

    def save(self) -> None:
        """Save recorded audio to WAV file."""
        if not self.enabled or len(self.frames) == 0:
            if self.enabled:
                logger.warning("No frames to save!")
            return

        try:
            self._log_recording_stats()
            all_audio = np.concatenate(self.frames)
            self._log_audio_stats(all_audio)
            self._write_wav_file(all_audio)

            duration = len(all_audio) / self.sample_rate
            logger.info("Debug recording saved: %s (%.2fs, %s samples)", self.wav_path, duration, len(all_audio))

        except Exception as e:
            logger.error("Error saving debug recording: %s", e, exc_info=True)

    def _log_recording_stats(self) -> None:
        """Log statistics about recorded frames."""
        frame_count = len(self.frames)
        frame_lengths = [len(f) for f in self.frames]

        logger.info(
            "Recording %s frames, lengths: min=%s, max=%s, avg=%.1f",
            frame_count, min(frame_lengths), max(frame_lengths),
            sum(frame_lengths) / len(frame_lengths),
        )

    def _log_audio_stats(self, audio: np.ndarray) -> None:
        """Log statistics about audio data."""
        audio_min, audio_max = audio.min(), audio.max()
        audio_rms = np.sqrt(np.mean(audio.astype(float) ** 2))

        logger.info("Audio statistics: min=%s, max=%s, RMS=%.2f", audio_min, audio_max, audio_rms)

        if audio_rms < 100:
            logger.warning("WARNING: Audio has very low RMS (%.2f) - recording might be silence or corrupted", audio_rms)

    def _write_wav_file(self, audio: np.ndarray) -> None:
        """Write audio data to WAV file."""
        if self.wav_path is None:
            return
        with wave.open(self.wav_path, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio.tobytes())
