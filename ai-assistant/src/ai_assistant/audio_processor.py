"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import json
import os
import numpy as np
from typing import AsyncGenerator, Optional
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

from .ai_assistant import AIAssistant
from .audio_track import AudioOutputTrack
from .firestore_service import FirestoreService
from .services.audio_frame_converter import AudioFrameConverter
from .services.data_channel_bridge import DataChannelBridge
from .services.debug_recorder import DebugRecorder
from .services.response_delivery import ResponseDelivery, ResponseDeliveryFactory
from .services.session_starter import SessionStarter, SessionStarterFactory
from .services.session_mode import SessionMode
from .services.transcript_processor import TranscriptProcessor
from .services.tts_playback_manager import TTSPlaybackManager, SentenceParser
from .services.conversation_service import ConversationStage
from .services.agent_runtime_fsm import AgentRuntimeState
from .services.ai_conversation_service import AIConversationService

# Module-level FirestoreService instance (lazy-init on first use)
_firestore_service = FirestoreService()

logger = logging.getLogger(__name__)

# FSM states that mean the AI is actively generating or playing a response.
_ACTIVE_RESPONSE_STATES = frozenset(
    {
        AgentRuntimeState.THINKING,
        AgentRuntimeState.LLM_STREAMING,
        AgentRuntimeState.TOOL_EXECUTING,
        AgentRuntimeState.SPEAKING,
    }
)


class AudioProcessor:
    """Processes audio through the STT -> LLM -> TTS pipeline."""

    def __init__(
        self,
        connection_id: str,
        input_track: Optional[MediaStreamTrack] = None,
        user_id: Optional[str] = None,
        language: str = "de",
    ):
        self.connection_id = connection_id
        self.input_track = input_track
        self.user_id = user_id
        self.language = language
        self.output_track = AudioOutputTrack()
        self.running = False
        self.processing_task = None
        self.stt_task = None

        # Session mode — derived from whether an audio track is provided.
        # The ``_is_text_mode`` property below provides backward compat.
        self.session_mode: SessionMode = (
            SessionMode.TEXT if input_track is None else SessionMode.VOICE
        )

        # Activity hook: called on every _process_final_transcript invocation.
        # Used by PeerConnectionHandler to reset the idle timer.
        self.on_activity = None

        # Composability hook: when set, _continuous_stt calls this instead of
        # _process_final_transcript directly.
        self.on_transcript_final = None

        # Create language-specific AI assistant for this connection
        self.ai_assistant = self._create_language_specific_assistant(language)

        logger.info(
            "AudioProcessor created for connection %s with language: %s",
            connection_id,
            language,
        )

        # Audio streaming for continuous STT
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self.sample_rate = 48000  # WebRTC sends 48kHz

        # ── Phase-1 services ──────────────────────────────────────────────────
        self._dc_bridge = DataChannelBridge()

        # ── Legacy services ───────────────────────────────────────────────────
        self.frame_converter = AudioFrameConverter(self.sample_rate)
        self.debug_recorder = DebugRecorder(connection_id, self.sample_rate)
        self.transcript_processor = TranscriptProcessor(self.ai_assistant.stt_service)
        self.tts_manager = TTSPlaybackManager(
            self.ai_assistant.tts_service,
            self._queue_audio_for_playback,
        )

        # Interrupt handling
        self.is_ai_speaking = False  # True when generating OR playing AI response
        self.interrupt_event = asyncio.Event()
        # data_channel exposed as property so assignment auto-wires _dc_bridge.
        self._data_channel = None

        # Tracks the current LLM+TTS response task so it can be cancelled on
        # interrupt.
        self._response_task: Optional[asyncio.Task] = None

        # Serializes text-input handling from the DataChannel to avoid races
        # between concurrent process_text_input() calls.
        self._text_input_lock = asyncio.Lock()

        # ── Response delivery strategy & session starter ─────────────────────
        # Swapped on mode switch via _make_delivery() / _make_session_starter().
        self._delivery: ResponseDelivery = self._make_delivery(self.session_mode)
        self._session_starter: SessionStarter = self._make_session_starter(self.session_mode)

    # ── Backward-compat properties ────────────────────────────────────────────

    @property
    def _is_text_mode(self) -> bool:
        """Read-only compat view of session_mode."""
        return self.session_mode == SessionMode.TEXT

    @property
    def data_channel(self):
        """The active DataChannel (or ``None``).  Setting it also wires ``_dc_bridge``."""
        return self._data_channel

    @data_channel.setter
    def data_channel(self, channel) -> None:
        self._data_channel = channel
        self._dc_bridge.attach(channel)

    # ── Factory ───────────────────────────────────────────────────────────────

    def _create_language_specific_assistant(self, language: str):
        """Create a language-specific AI assistant instance."""
        logger.info("Creating language-specific AI assistant for language: %s", language)

        assistant = AIAssistant(
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            language=language,
            llm_model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
            session_id=self.connection_id
        )

        # Wire AIConversationService so every session is persisted to Firestore.
        ai_conv_service = AIConversationService(firestore_service=_firestore_service)
        assistant.response_orchestrator.ai_conversation_service = ai_conv_service

        logger.info(
            "AI Assistant created with language '%s': %s, %s",
            language, assistant.language_code, assistant.voice_name,
        )
        return assistant

    # ── DataChannel wiring ────────────────────────────────────────────────────

    def set_data_channel(self, channel) -> None:
        """Attach the DataChannel for outbound messages."""
        self.data_channel = channel  # property setter also wires _dc_bridge
        logger.info("Data channel set in AudioProcessor")

    # ── Strategy factories ────────────────────────────────────────────────────

    def _make_delivery(self, mode: SessionMode) -> ResponseDelivery:
        """Create a ResponseDelivery strategy for the given mode."""
        return ResponseDeliveryFactory.create(
            mode,
            tts_manager=self.tts_manager,
            dc_bridge=self._dc_bridge,
            on_speaking_change=lambda speaking: setattr(self, "is_ai_speaking", speaking),
            monitor_playback_fn=self._monitor_playback_completion,
        )

    def _make_session_starter(self, mode: SessionMode) -> SessionStarter:
        """Create a SessionStarter strategy for the given mode."""
        return SessionStarterFactory.create(
            mode,
            conversation_service=self.ai_assistant.conversation_service,
            response_orchestrator=self.ai_assistant.response_orchestrator,
            data_provider=self.ai_assistant.data_provider,
            tts_service=self.ai_assistant.tts_service,
            llm_service=self.ai_assistant.llm_service,
            dc_bridge=self._dc_bridge,
            output_track=self.output_track,
            user_id=self.user_id,
            connection_id=self.connection_id,
            interrupt_event=self.interrupt_event,
            on_speaking_change=lambda speaking: setattr(self, "is_ai_speaking", speaking),
        )

    # ── DataChannel send helpers (thin wrappers over DataChannelBridge) ───────

    def _send_chat_message(self, text: str, is_user: bool, is_chunk: bool = False) -> None:
        """Send a chat message to the client via DataChannel."""
        self._dc_bridge.send_chat(text, is_user=is_user, is_chunk=is_chunk)

    def _emit_runtime_state(self, state: AgentRuntimeState) -> None:
        """Broadcast the current AgentRuntimeState to the Flutter client."""
        self._dc_bridge.send_runtime_state(state)

    def get_output_track(self) -> MediaStreamTrack:
        """Get the output audio track."""
        return self.output_track

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start processing audio."""
        self.running = True
        if self.input_track is not None:
            self.processing_task = asyncio.create_task(self._process_audio())
            self.stt_task = asyncio.create_task(self._continuous_stt())
        else:
            logger.info(
                "Text-only mode — skipping audio tasks for connection %s",
                self.connection_id,
            )
        asyncio.create_task(self._session_starter.initialize())
        logger.info("Audio processor started for connection %s", self.connection_id)

    async def replace_input_track(self, new_track: MediaStreamTrack) -> None:
        """Replace input track during renegotiation (e.g. Bluetooth change)."""
        logger.info(
            "Replacing input track: %s -> %s",
            self.input_track.id if self.input_track else "None",
            new_track.id,
        )
        try:
            for task_attr in ("processing_task", "stt_task"):
                task = getattr(self, task_attr)
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            self.input_track = new_track

            if self.running:
                self.processing_task = asyncio.create_task(self._process_audio())
                self.stt_task = asyncio.create_task(self._continuous_stt())
                logger.info("Audio processing restarted with new input track")

        except Exception as exc:
            logger.error("Error replacing input track: %s", exc, exc_info=True)

    async def stop(self) -> None:
        """Stop processing audio."""
        self.running = False
        await self.audio_queue.put(None)

        for task_attr in ("stt_task", "processing_task"):
            task = getattr(self, task_attr)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.debug_recorder.save()
        logger.info("Audio processor stopped for connection %s", self.connection_id)

    # ── Voice mode toggle ─────────────────────────────────────────────────────

    async def enable_voice_mode(self, input_track: Optional[MediaStreamTrack] = None) -> 'AudioOutputTrack':
        """Resume or start voice mode."""
        logger.info("Enabling voice mode for connection %s", self.connection_id)
        self.session_mode = SessionMode.VOICE
        self._delivery = self._make_delivery(SessionMode.VOICE)

        if input_track is not None and self.input_track is None:
            self.input_track = input_track
            if self.running:
                self.processing_task = asyncio.create_task(self._process_audio())
                self.stt_task = asyncio.create_task(self._continuous_stt())
            logger.info("Voice tasks started for text→voice upgrade")
        elif input_track is not None and self.input_track is not None:
            await self.replace_input_track(input_track)
        else:
            logger.info("Voice mode resumed — existing tasks kept as-is")

        self._reset_idle_timer_if_available()
        return self.output_track

    def _reset_idle_timer_if_available(self) -> None:
        if self.on_activity:
            self.on_activity()

    async def disable_voice_mode(self) -> None:
        """Pause TTS output and mark session as text-only.

        Keeps STT / audio-frame tasks alive for fast resume.
        """
        if self.session_mode == SessionMode.TEXT:
            return
        logger.info("Pausing voice mode for connection %s", self.connection_id)
        self.session_mode = SessionMode.TEXT
        await self._trigger_interrupt()
        self._delivery = self._make_delivery(SessionMode.TEXT)
        logger.info("Voice mode paused — STT/audio tasks remain alive")

    async def receive_text_input(self, text: str) -> None:
        """Single public entry point for all incoming text.

        Automatically handles voice → text mode switch when the current
        session is in voice mode, then delegates to process_text_input.
        Callers (e.g. PeerConnectionHandler) never need mode-check logic.
        """
        if self.session_mode == SessionMode.VOICE:
            logger.info("Voice → text switch triggered by receive_text_input")
            await self.disable_voice_mode()
        await self.process_text_input(text)

    # ── Audio processing ───────────────────────────────────────────────────────

    async def _process_audio(self):
        """Main audio processing loop - receives frames and queues them for STT."""
        try:
            frame_count = 0
            
            while self.running:
                try:
                    frame_count += 1
                    
                    try:
                        frame = await asyncio.wait_for(
                            self.input_track.recv(),
                            timeout=5.0
                        )
                    except MediaStreamError:
                        logger.warning(f"Input track closed (frame {frame_count})")
                        break
                    except asyncio.CancelledError:
                        break
                    
                    audio_data = self.frame_converter.frame_to_numpy(frame)
                    self.debug_recorder.add_frame(audio_data)
                    audio_bytes = audio_data.tobytes()
                    await self.audio_queue.put(audio_bytes)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error receiving frame: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info(f"Audio processing cancelled (frames={frame_count})")
        except Exception as e:
            logger.error(f"Error in audio processing: {e}", exc_info=True)
    
    # ── STT pipeline (decomposed) ──────────────────────────────────────────────

    async def _make_audio_chunks(self) -> AsyncGenerator[bytes, None]:
        """Async generator that yields raw PCM bytes from the audio queue.

        Terminates when the queue delivers ``None`` (sentinel from :meth:`stop`
        or :meth:`_continuous_stt`) or when :attr:`running` becomes ``False``.
        """
        while self.running:
            try:
                chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                if chunk is None:
                    break
                yield chunk
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.error("Audio generator error: %s", exc, exc_info=True)
                break

    async def _handle_final_transcript(self, transcript: str) -> None:
        """Guard and dispatch a confirmed-final STT transcript.

        Handles:
        - FINALIZE busy guard (provider search in progress)
        - Interrupt-while-speaking before dispatch
        - ``on_transcript_final`` hook or ``_process_final_transcript`` fallback
        """
        if not transcript.strip():
            return

        if (
            self.ai_assistant.conversation_service.get_current_stage()
            == ConversationStage.FINALIZE
            and self._response_task is not None
            and not self._response_task.done()
        ):
            busy_msg = (
                "Ich suche noch nach passenden Anbietern – bitte noch einen Moment Geduld! "
                "I'm still searching for providers – just a moment more, thank you!"
            )
            self._send_chat_message(busy_msg, is_user=False)
            logger.info(
                "_handle_final_transcript: FINALIZE stage — voice input ignored "
                "during provider search"
            )
            return

        if self.is_ai_speaking:
            await self._trigger_interrupt()

        handler = (
            self.on_transcript_final
            if self.on_transcript_final is not None
            else self._process_final_transcript
        )
        self._response_task = asyncio.create_task(handler(transcript))

    async def _stt_session(self) -> None:
        """Run one STT streaming session from :meth:`_make_audio_chunks`.

        Fires partial-transcript interrupt checks inline, delegates final
        transcripts to :meth:`_handle_final_transcript`, then refills the
        queue sentinel so the next session starts cleanly.
        """
        async for transcript, is_final in self.transcript_processor.process_audio_stream(
            self._make_audio_chunks()
        ):
            if transcript and self.is_ai_speaking and len(transcript.strip()) > 0:
                logger.info("Interrupt detected: '%s'", transcript)
                await self._trigger_interrupt()
                await asyncio.sleep(0.05)

            if is_final:
                # Reset the queue so the *next* _stt_session starts from an
                # empty FIFO rather than a stale sentinel.
                await self.audio_queue.put(None)
                await self._handle_final_transcript(transcript)
                break

    async def _continuous_stt(self) -> None:
        """Outer loop — restarts :meth:`_stt_session` after each final transcript."""
        try:
            while self.running:
                await self._stt_session()
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Continuous STT cancelled")
        except Exception as exc:
            logger.error("Error in continuous STT: %s", exc, exc_info=True)

    async def _trigger_interrupt(self):
        """Trigger an interrupt to stop ongoing AI speech."""
        logger.info("Triggering interrupt")
        # Stop TTS and clear audio output immediately so the user hears silence.
        self.tts_manager.interrupt()
        await self.output_track.clear_queue()
        self.is_ai_speaking = False
        self.interrupt_event.set()
        # Cancel the ongoing LLM/TTS response task (fire-and-forget; the task
        # will clean up via its CancelledError handler).
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
            self._response_task = None
        # Bring the FSM back to LISTENING so the next final_transcript event
        # is accepted. Without this the FSM stays stranded in LLM_STREAMING or
        # THINKING and the second user message is silently dropped.
        fsm = self.ai_assistant.response_orchestrator.runtime_fsm
        fsm.transition("interrupt")
        fsm.transition("interrupt_handled")
    
    async def process_text_input(self, text: str):
        """Process a text message through the LLM pipeline.

        Awaits session initialization (handles race on very first message),
        guards against provider search in progress, interrupts any in-flight
        response, then dispatches to _process_final_transcript.
        """
        async with self._text_input_lock:
            text = text.strip()
            if not text:
                logger.warning("process_text_input called with empty text — ignoring")
                return

            # Await session initialization so the first message has user context.
            # Fast-path: skip wait_for entirely when already set — asyncio.wait_for
            # creates an internal Task even for immediately-resolved awaitables,
            # which costs extra event-loop ticks in Python ≤ 3.11 and breaks
            # concurrency tests that rely on exact yield counts.
            if not self._session_starter.initialized_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._session_starter.initialized_event.wait(), timeout=2.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Session initialization timeout for %s — proceeding without user context",
                        self.connection_id,
                    )

            # Guard: block text input while the provider search + initial
            # presentation task is still running.  Once the task completes,
            # the user's accept/decline replies must flow normally.
            if (
                self.ai_assistant.conversation_service.get_current_stage()
                == ConversationStage.FINALIZE
                and self._response_task is not None
                and not self._response_task.done()
            ):
                busy_msg = (
                    "Ich suche noch nach passenden Anbietern – bitte noch einen Moment Geduld! "
                    "I'm still searching for providers – just a moment more, thank you!"
                )
                self._send_chat_message(busy_msg, is_user=False)
                logger.info(
                    "process_text_input: FINALIZE stage — returning busy message, "
                    "not interrupting provider search"
                )
                return

            # Interrupt any in-progress response before generating the new one.
            if self.is_ai_speaking or (self._response_task and not self._response_task.done()):
                await self._trigger_interrupt()

            # Advance FSM LISTENING → THINKING if not already done.
            from .services.agent_runtime_fsm import AgentRuntimeState
            fsm = self.ai_assistant.response_orchestrator.runtime_fsm
            if fsm.current_state == AgentRuntimeState.LISTENING:
                fsm.transition("final_transcript")

            self._response_task = asyncio.create_task(
                self._process_final_transcript(text)
            )

    async def _process_final_transcript(self, transcript: str):
        """Process a final transcript through LLM -> TTS pipeline."""
        try:
            logger.info(f"Processing final transcript: '{transcript}'")
            
            # Notify the connection handler of activity (resets idle timer)
            if self.on_activity:
                self.on_activity()

            # Open AI conversation session on the first turn (idempotent after that)
            ai_conv = self.ai_assistant.response_orchestrator.ai_conversation_service
            if ai_conv is not None and self.user_id:
                await ai_conv.open_session(
                    user_id=self.user_id,
                    session_id=self.connection_id,
                )

            # Echo transcript to client — delivery strategy decides whether to send it.
            self._delivery.echo_user_transcript(transcript)
            
            start_time = asyncio.get_event_loop().time()
            
            # Reset interrupt event and set speaking flag
            self.interrupt_event.clear()
            self.is_ai_speaking = True
            
            # Performance tracking
            perf_times = {
                'start': start_time,
                 'llm_first_token': None,
                'tts_first_audio': None,
            }
            
            # Get LLM stream
            llm_start = asyncio.get_event_loop().time()
            
            # Create LLM stream
            llm_stream = self.ai_assistant.generate_llm_response_stream(
                transcript, user_id=self.user_id
            )
            
            # Wrap LLM stream to track first token
            async def tracked_llm_stream():
                first_chunk = True
                async for chunk in llm_stream:
                    # The orchestrator emits a sentinel dict before each
                    # autonomous sub-stream (finalize presentation, provider
                    # pitch).  Consume it silently and reset first_chunk so
                    # the next text chunk opens a new Flutter bubble.
                    if isinstance(chunk, dict) and chunk.get("type") == "new_bubble":
                        first_chunk = True
                        continue

                    if chunk:
                        # First chunk of each turn → is_chunk=False → new bubble.
                        # Remaining chunks → is_chunk=True → append.
                        self._send_chat_message(chunk, is_user=False, is_chunk=not first_chunk)

                    if first_chunk and chunk:
                        perf_times['llm_first_token'] = asyncio.get_event_loop().time()
                        logger.info(f"⚡ Time to first LLM token: {perf_times['llm_first_token'] - llm_start:.3f}s")
                        first_chunk = False
                    yield chunk
            
            # Delegate output to the active delivery strategy.
            await self._delivery.stream_response(tracked_llm_stream())

            total_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Pipeline complete in {total_time:.3f}s")

        except asyncio.CancelledError:
            # User interrupted — reset state and let the task exit cleanly.
            logger.info(f"Response generation interrupted for: '{transcript}'")
            self.is_ai_speaking = False
            raise
        except Exception as e:
            logger.error(f"Error processing final transcript: {e}", exc_info=True)
            self.is_ai_speaking = False
    
    async def _queue_audio_for_playback(self, audio_data: bytes):
        """
        Queue audio for playback with fade effects to prevent crackling.
        
        Args:
            audio_data: Audio data as bytes (int16)
        """
        try:
            # Convert to numpy array (make writable copy)
            audio_samples = np.frombuffer(audio_data, dtype=np.int16).copy()
            
            # Apply smooth fade-in at start and fade-out at end
            # Using cosine curve for smoother transitions
            fade_in_samples = min(480, len(audio_samples) // 2)  # 10ms at 48kHz
            fade_out_samples = min(144, len(audio_samples) // 2)  # 3ms at 48kHz
            
            if fade_in_samples > 0:
                # Cosine fade-in: 0 to 1
                fade_in = (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples))) / 2.0
                audio_samples[:fade_in_samples] = (audio_samples[:fade_in_samples] * fade_in).astype(np.int16)
            
            if fade_out_samples > 0:
                # Cosine fade-out: 1 to 0
                fade_out = (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples))) / 2.0
                audio_samples[-fade_out_samples:] = (audio_samples[-fade_out_samples:] * fade_out).astype(np.int16)
            
            # Queue the processed audio
            await self.output_track.queue_audio(audio_samples.tobytes())
            
        except Exception as e:
            logger.error(f"Error queueing audio for playback: {e}", exc_info=True)
    
    async def _monitor_playback_completion(self):
        """Monitor the audio queue and clear speaking flag when playback is done."""
        try:
            # Wait a bit for audio to start queueing
            await asyncio.sleep(0.1)
            
            # Monitor queue size - when it stays at 0 for a bit, we're done playing
            empty_count = 0
            while self.is_ai_speaking and not self.interrupt_event.is_set():
                queue_size = self.output_track.audio_queue.qsize()
                buffer_size = len(self.output_track._buffer)
                
                if queue_size == 0 and buffer_size == 0:
                    empty_count += 1
                    # If queue and buffer are empty for 5 consecutive checks (100ms), we're done
                    if empty_count >= 5:
                        self.is_ai_speaking = False
                        break
                else:
                    empty_count = 0
                
                await asyncio.sleep(0.02)  # Check every 20ms
            
        except Exception as e:
            logger.error(f"Error in playback monitor: {e}", exc_info=True)
            self.is_ai_speaking = False
