"""
Audio Processor: Handles the audio processing pipeline using service-oriented architecture.
"""
import asyncio
import logging
import numpy as np
import wave
import os
from datetime import datetime
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

from .audio_track import AudioOutputTrack
from .definitions import AUDIO_RECEIVE_TIMEOUT, AUDIO_STREAM_TIMEOUT
from .services.audio_utils import AudioFrameConverter
from .services.interrupt_handler import InterruptHandler
from .services.sentence_processor import SentenceProcessor

logger = logging.getLogger(__name__)


class DebugRecorder:
    """Handles debug audio recording functionality."""

    def __init__(self, connection_id: str, sample_rate: int = 48000):
        """Initialize debug recorder."""
        self.enabled = os.getenv('DEBUG_RECORD_AUDIO', 'false').lower() == 'true'
        self.frames = []
        self.sample_rate = sample_rate
        self.file_path = None

        if self.enabled:
            debug_dir = 'debug_audio'
            os.makedirs(debug_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.file_path = os.path.join(
                debug_dir,
                f'received_audio_{connection_id}_{timestamp}.wav'
            )
            logger.info(f"Debug audio recording enabled: {self.file_path}")

    def add_frame(self, audio_data: np.ndarray):
        """Add audio frame to recording."""
        if self.enabled:
            self.frames.append(audio_data.copy())

    def save(self):
        """Save recorded audio to file."""
        if not self.enabled or len(self.frames) == 0:
            return

        try:
            logger.info(f"Saving debug recording: {self.file_path}")
            self._log_statistics()

            # Concatenate and save
            all_audio = np.concatenate(self.frames)
            with wave.open(self.file_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(all_audio.tobytes())

            duration = len(all_audio) / self.sample_rate
            logger.info(
                f"Debug recording saved: {self.file_path} "
                f"({duration:.2f}s, {len(all_audio)} samples)"
            )

        except Exception as e:
            logger.error(f"Error saving debug recording: {e}", exc_info=True)

    def _log_statistics(self):
        """Log statistics about recorded frames."""
        frame_count = len(self.frames)
        frame_lengths = [len(f) for f in self.frames]
        logger.info(
            f"Recording {frame_count} frames, lengths: "
            f"min={min(frame_lengths)}, max={max(frame_lengths)}, "
            f"avg={sum(frame_lengths)/len(frame_lengths):.1f}"
        )

        all_audio = np.concatenate(self.frames)
        audio_min, audio_max = all_audio.min(), all_audio.max()
        audio_rms = np.sqrt(np.mean(all_audio.astype(float) ** 2))
        logger.info(f"Audio stats: min={audio_min}, max={audio_max}, RMS={audio_rms:.2f}")

        if audio_rms < 100:
            logger.warning(
                f"WARNING: Low RMS ({audio_rms:.2f}) - might be silence or corrupted"
            )


class AudioStreamManager:
    """Manages audio frame streaming and queuing."""

    def __init__(
        self,
        connection_id: str,
        input_track: MediaStreamTrack,
        audio_queue: asyncio.Queue
    ):
        """Initialize audio stream manager."""
        self.connection_id = connection_id
        self.input_track = input_track
        self.audio_queue = audio_queue
        self.frame_converter = AudioFrameConverter()
        self.debug_recorder = DebugRecorder(connection_id)

    async def stream_audio_frames(self):
        """Main audio frame processing loop."""
        try:
            frame_count = 0
            logger.debug(f"Starting audio stream for {self.connection_id}")

            while True:
                try:
                    frame_count += 1
                    frame = await self._receive_frame(frame_count)

                    if frame is None:
                        break

                    # Convert and queue frame
                    audio_data = self.frame_converter.frame_to_numpy(frame)
                    self.debug_recorder.add_frame(audio_data)

                    audio_bytes = audio_data.tobytes()
                    await self.audio_queue.put(audio_bytes)

                except asyncio.TimeoutError:
                    # Disabled: High-frequency logging during audio gaps
                    logger.debug(f"No audio for {AUDIO_RECEIVE_TIMEOUT}s, continuing...")
                    continue
                except Exception as e:
                    logger.error(f"Error processing frame {frame_count}: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info(f"Audio stream cancelled (processed {frame_count} frames)")
        finally:
            self.debug_recorder.save()

    async def _receive_frame(self, frame_count: int) -> AudioFrame:
        """Receive a single audio frame with timeout."""
        try:
            frame = await asyncio.wait_for(
                self.input_track.recv(),
                timeout=AUDIO_RECEIVE_TIMEOUT
            )
            return frame

        except MediaStreamError:
            logger.info(f"Input track closed (frame {frame_count})")
            return None
        except asyncio.CancelledError:
            logger.info(f"Frame receive cancelled (frame {frame_count})")
            return None


class STTStreamManager:
    """Manages continuous STT streaming."""

    def __init__(
        self,
        ai_assistant,
        audio_queue: asyncio.Queue,
        interrupt_handler: InterruptHandler,
        greeting_complete: asyncio.Event
    ):
        """Initialize STT stream manager."""
        self.ai_assistant = ai_assistant
        self.audio_queue = audio_queue
        self.interrupt_handler = interrupt_handler
        self.greeting_complete = greeting_complete

    async def run_continuous_stt(self, transcript_processor):
        """Run continuous STT and process final transcripts."""
        try:
            logger.info("Starting continuous STT - waiting for greeting...")
            await self.greeting_complete.wait()
            logger.info("Greeting complete, streaming to Google STT")

            audio_gen = self._create_audio_generator()

            async for transcript, is_final in self.ai_assistant.speech_to_text_continuous_stream(
                audio_gen
            ):
                if transcript:
                    await self._handle_transcript(
                        transcript,
                        is_final,
                        transcript_processor
                    )

            logger.info("Continuous STT streaming ended")

        except asyncio.CancelledError:
            logger.info("Continuous STT cancelled")
        except Exception as e:
            logger.error(f"Error in continuous STT: {e}", exc_info=True)

    async def _create_audio_generator(self):
        """Create async generator for audio chunks."""
        chunk_count = 0
        timeout_count = 0

        while True:
            try:
                audio_chunk = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=AUDIO_STREAM_TIMEOUT
                )

                if audio_chunk is None:
                    logger.debug("STT received stop signal")
                    break

                chunk_count += 1
                timeout_count = 0

                yield audio_chunk

            except asyncio.TimeoutError:
                timeout_count += 1
                # High-frequency logging (every 10 timeouts)
                if timeout_count % 30 == 0:
                    logger.debug(f"No audio for {AUDIO_STREAM_TIMEOUT}s, still active")
                continue
            except Exception as e:
                logger.error(f"Error in audio generator: {e}", exc_info=True)
                break

    async def _handle_transcript(
        self,
        transcript: str,
        is_final: bool,
        transcript_processor
    ):
        """Handle transcript from STT."""
        # Check for interrupt
        if self.interrupt_handler.is_speaking() and len(transcript.strip()) > 0:
            logger.info(f"🛑 INTERRUPT detected: '{transcript}'")
            await self.interrupt_handler.trigger_interrupt()
            await asyncio.sleep(0.05)

        if is_final:
            logger.info(f"Final transcript: '{transcript}'")
            if not self.interrupt_handler.is_speaking():
                await transcript_processor(transcript)
            else:
                logger.warning("Skipping - AI still speaking despite interrupt")
        else:
            logger.debug(f"Interim transcript: '{transcript}'")


class AudioProcessor:
    """
    Audio Processor using service-oriented architecture.
    
    Coordinates between:
    - Audio frame streaming
    - STT processing
    - LLM response generation
    - TTS synthesis with sentence streaming
    - Interrupt handling
    """

    def __init__(self, connection_id: str, ai_assistant, input_track: MediaStreamTrack):
        """
        Initialize audio processor.
        
        Args:
            connection_id: Unique connection identifier
            ai_assistant: AIAssistant instance
            input_track: Input audio track from WebRTC
        """
        self.connection_id = connection_id
        self.ai_assistant = ai_assistant
        self.input_track = input_track
        self.output_track = AudioOutputTrack()

        # State management
        self.running = False
        self.processing_task = None
        self.stt_task = None
        self.greeting_complete = asyncio.Event()

        # Audio queue
        self.audio_queue = asyncio.Queue()

        # Initialize services
        self.interrupt_handler = InterruptHandler(self.output_track)
        self.sentence_processor = SentenceProcessor(
            self.ai_assistant.tts_service,
            self.output_track,
            self.interrupt_handler
        )

        # Initialize managers
        self.stream_manager = AudioStreamManager(
            connection_id,
            input_track,
            self.audio_queue
        )
        self.stt_manager = STTStreamManager(
            ai_assistant,
            self.audio_queue,
            self.interrupt_handler,
            self.greeting_complete
        )

    def get_output_track(self) -> MediaStreamTrack:
        """Get the output audio track."""
        return self.output_track

    async def start(self):
        """Start processing audio."""
        self.running = True

        # Start audio frame streaming
        self.processing_task = asyncio.create_task(
            self.stream_manager.stream_audio_frames()
        )

        # Start STT processing
        self.stt_task = asyncio.create_task(
            self.stt_manager.run_continuous_stt(self._process_final_transcript)
        )

        logger.info(f"Audio processor started for {self.connection_id}")

        # Play greeting in parallel
        asyncio.create_task(self._play_greeting())

    async def stop(self):
        """Stop processing audio."""
        logger.info(f"Stopping audio processor for {self.connection_id}")
        self.running = False

        # Cancel tasks first to stop new audio from being queued
        for task in [self.processing_task, self.stt_task]:
            if task and not task.done():
                logger.debug(f"Cancelling task: {task.get_name() if hasattr(task, 'get_name') else 'unnamed'}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Clear any remaining audio chunks from queue when stopping
        queue_size = self.audio_queue.qsize()
        if queue_size > 0:
            logger.debug(f"Clearing {queue_size} buffered audio chunks from queue")
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        # Signal end of stream (in case STT is still waiting)
        await self.audio_queue.put(None)

        logger.info(f"Audio processor stopped for {self.connection_id}")

    async def stop_tts_streaming(self):
        """Stop TTS streaming immediately (called when client disconnects)."""
        logger.info(f"Stopping TTS streaming for {self.connection_id}")
        
        # Trigger interrupt to cancel all ongoing TTS
        if self.interrupt_handler:
            await self.interrupt_handler.trigger_interrupt()
        
        logger.info(f"TTS streaming stopped for {self.connection_id}")

    async def _play_greeting(self):
        """Play the AI greeting."""
        try:
            logger.info("Generating and playing greeting...")
            self.interrupt_handler.set_speaking(True)

            greeting_text, audio_stream = await self.ai_assistant.get_greeting_audio(
                user_id=self.ai_assistant.user_id
            )
            logger.info(f"Playing greeting: '{greeting_text}'")

            async for audio_chunk in audio_stream:
                if audio_chunk:
                    await self.output_track.queue_audio(audio_chunk)

            self.interrupt_handler.set_speaking(False)
            self.greeting_complete.set()
            logger.info("Greeting playback complete")

        except Exception as e:
            logger.error(f"Error playing greeting: {e}", exc_info=True)
            self.interrupt_handler.set_speaking(False)
            self.greeting_complete.set()

    async def _process_final_transcript(self, transcript: str):
        """Process a final transcript through LLM -> TTS pipeline."""
        try:
            logger.info(f"Processing transcript: '{transcript}'")
            start_time = asyncio.get_event_loop().time()

            # Reset interrupt and set speaking
            self.interrupt_handler.clear_interrupt()
            self.interrupt_handler.set_speaking(True)
            self.interrupt_handler.clear_tts_tasks()

            # Generate LLM response and process sentences
            llm_stream = self.ai_assistant.generate_llm_response_stream(transcript)
            full_response, tts_tasks = await self.sentence_processor.process_llm_stream(
                llm_stream
            )

            logger.info(f"LLM complete: '{full_response}'")

            # Monitor TTS completion in background
            if tts_tasks:
                logger.info(f"Started {len(tts_tasks)} TTS tasks")
                asyncio.create_task(self._monitor_tts_completion(tts_tasks))

            # Monitor playback completion
            asyncio.create_task(self.interrupt_handler.monitor_playback_completion())

            total_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Pipeline complete in {total_time:.3f}s")

        except Exception as e:
            logger.error(f"Error processing transcript: {e}", exc_info=True)
        finally:
            self.interrupt_handler.clear_tts_tasks()

    async def _monitor_tts_completion(self, tts_tasks: list):
        """Monitor TTS task completion."""
        await asyncio.gather(*tts_tasks, return_exceptions=True)
        logger.info(f"All {len(tts_tasks)} TTS tasks completed")
