"""
Audio Processor
Handles the audio processing pipeline: STT -> LLM -> TTS
"""
import asyncio
import logging
import json
import os
import numpy as np
from typing import Optional
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

from .ai_assistant import AIAssistant
from .audio_track import AudioOutputTrack
from .services.audio_frame_converter import AudioFrameConverter
from .services.debug_recorder import DebugRecorder
from .services.transcript_processor import TranscriptProcessor
from .services.tts_playback_manager import TTSPlaybackManager, SentenceParser
from .services.conversation_service import ConversationStage
from .services.agent_runtime_fsm import AgentRuntimeState
from .services.ai_conversation_service import AIConversationService

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processes audio through the STT -> LLM -> TTS pipeline."""
    
    def __init__(self, connection_id: str, input_track: Optional[MediaStreamTrack] = None, user_id: Optional[str] = None, language: str = 'de'):
        self.connection_id = connection_id
        self.input_track = input_track
        self.user_id = user_id
        self.language = language
        self.output_track = AudioOutputTrack()
        self.running = False
        self.processing_task = None
        self.stt_task = None
        
        # Activity hook: called on every _process_final_transcript invocation
        # Used by PeerConnectionHandler to reset the idle timer.
        self.on_activity = None

        # Composability hook: when set, _continuous_stt calls this instead of
        # _process_final_transcript directly.  PeerConnectionHandler wires this
        # to the ResponseOrchestrator in Phase 8.
        self.on_transcript_final = None
        
        # Create language-specific AI assistant for this connection
        self.ai_assistant = self._create_language_specific_assistant(language)
        
        logger.info(f"AudioProcessor created for connection {connection_id} with language: {language}")
        
        # Audio streaming for continuous STT
        self.audio_queue = asyncio.Queue()
        self.sample_rate = 48000  # WebRTC sends 48kHz
        
        # Services
        self.frame_converter = AudioFrameConverter(self.sample_rate)
        self.debug_recorder = DebugRecorder(connection_id, self.sample_rate)
        self.transcript_processor = TranscriptProcessor(self.ai_assistant.stt_service)
        self.tts_manager = TTSPlaybackManager(
            self.ai_assistant.tts_service,
            self._queue_audio_for_playback
        )
        
        # Interrupt handling
        self.is_ai_speaking = False  # True when generating OR playing AI response
        self.interrupt_event = asyncio.Event()
        self.data_channel = None

        # True when session has no audio pipeline (text-only)
        self._is_text_mode = (input_track is None)

        # True once greeting has been sent (text or voice); prevents duplicate
        # greetings when connectionstatechange fires on renegotiation.
        self._greeting_sent = False

        # Tracks the current LLM+TTS response task so it can be cancelled on
        # interrupt.  Set by _continuous_stt and process_text_input.
        self._response_task: Optional[asyncio.Task] = None

    def _create_language_specific_assistant(self, language: str):
        """Create a language-specific AI assistant instance."""
        logger.info(f"Creating language-specific AI assistant for language: {language}")
        
        # Create new AI assistant with language-specific configuration
        assistant = AIAssistant(
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            language=language,
            llm_model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
            session_id=self.connection_id
        )

        # Wire AIConversationService so every session is persisted to Firestore.
        # firestore_service is None here (injected later by PeerConnectionHandler
        # if credentials are available); AIConversationService handles None safely.
        ai_conv_service = AIConversationService(firestore_service=None)
        assistant.response_orchestrator.ai_conversation_service = ai_conv_service
        
        logger.info(f"AI Assistant created with language '{language}': {assistant.language_code}, {assistant.voice_name}")
        
        return assistant

    def set_data_channel(self, channel):
        """Set the data channel for sending text messages."""
        self.data_channel = channel
        logger.info("Data channel set in AudioProcessor")

    def _send_chat_message(self, text: str, is_user: bool, is_chunk: bool = False):
        """Send chat message to client via data channel."""
        if self.data_channel and self.data_channel.readyState == "open":
            try:
                message = json.dumps({
                    "type": "chat",
                    "text": text,
                    "isUser": is_user,
                    "isChunk": is_chunk
                })
                self.data_channel.send(message)
            except Exception as e:
                logger.error(f"Error sending chat message: {e}")

    def _emit_runtime_state(self, state: AgentRuntimeState):
        """Broadcast the current AgentRuntimeState to the Flutter client.

        Sends a DataChannel JSON message of the form:
            {"type": "runtime-state", "runtimeState": "<state.value>"}
        Does nothing if the data channel is not open yet.
        """
        if self.data_channel and self.data_channel.readyState == "open":
            try:
                message = json.dumps({
                    "type": "runtime-state",
                    "runtimeState": state.value,
                })
                self.data_channel.send(message)
            except Exception as e:
                logger.error("Error emitting runtime state %s: %s", state, e)
        
    def get_output_track(self) -> MediaStreamTrack:
        """Get the output audio track."""
        return self.output_track
    
    async def start(self):
        """Start processing audio."""
        self.running = True
        if self.input_track is not None:
            self.processing_task = asyncio.create_task(self._process_audio())
            self.stt_task = asyncio.create_task(self._continuous_stt())
        else:
            logger.info(f"Text-only mode — skipping audio processing tasks for connection {self.connection_id}")
        logger.info(f"Audio processor started for connection {self.connection_id}")

        if not self._is_text_mode:
            # Voice mode: play greeting audio; greeting also advances stage to TRIAGE.
            asyncio.create_task(self._play_greeting())
        # Text mode: send_text_greeting() is called from on_connectionstatechange
        # once the data channel is confirmed open.
    
    async def replace_input_track(self, new_track: MediaStreamTrack):
        """Replace the input track during renegotiation (e.g., when Bluetooth device changes)."""
        logger.info(f"Replacing input track: {self.input_track.id if self.input_track else 'None'} -> {new_track.id}")
        
        try:
            # Cancel existing processing task
            if self.processing_task and not self.processing_task.done():
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling the task
            
            # Cancel existing STT task to ensure clean state
            if self.stt_task and not self.stt_task.done():
                self.stt_task.cancel()
                try:
                    await self.stt_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling the task
            
            # Don't clear the queue - let STT drain buffered audio naturally
            # This prevents audio loss during device transitions
            
            # Update to new track
            self.input_track = new_track
            
            # Restart both tasks if processor is still running
            if self.running:
                self.processing_task = asyncio.create_task(self._process_audio())
                self.stt_task = asyncio.create_task(self._continuous_stt())
                logger.info("Audio processing restarted with new input track")
            
        except Exception as e:
            logger.error(f"Error replacing input track: {e}", exc_info=True)
    
    async def send_text_greeting(self):
        """Generate and send a text-only greeting for text-mode sessions.

        Polls until the data channel is open then generates the greeting
        text (advancing the stage to TRIAGE) without producing TTS audio.
        """
        if self._greeting_sent:
            # Renegotiation caused connectionstatechange to fire again — skip.
            logger.info("Text greeting already sent — ignoring duplicate call")
            return
        self._greeting_sent = True

        if not self.running:
            return
        # Wait up to 5 s for the data channel to open
        for _ in range(50):
            if self.data_channel and self.data_channel.readyState == 'open':
                break
            await asyncio.sleep(0.1)
        else:
            logger.warning(
                f"Data channel not open after 5 s for connection {self.connection_id} "
                "— advancing stage without sending greeting"
            )
            self.ai_assistant.conversation_service.set_stage(ConversationStage.TRIAGE)
            return

        try:
            # get_greeting_audio: returns (text, lazy_audio_stream).
            # We discard the audio stream — TTS synthesis is lazy and never called.
            greeting_text, _ = await self.ai_assistant.get_greeting_audio(
                user_id=self.user_id
            )
            logger.info(f"Text greeting: {greeting_text}")
            self._send_chat_message(greeting_text, is_user=False, is_chunk=False)
        except Exception as e:
            logger.error(f"Error sending text greeting: {e}", exc_info=True)
            self.ai_assistant.conversation_service.set_stage(ConversationStage.TRIAGE)

    async def enable_voice_mode(self, input_track: Optional[MediaStreamTrack] = None) -> 'AudioOutputTrack':
        """Resume or start voice mode.

        Two cases:
        - input_track provided and self.input_track is None: fresh text→voice
          upgrade (pure text session).  Starts STT and audio-frame tasks.
        - input_track is None (or tasks already running): resuming a previously
          paused voice session.  Only flips the mode flag — tasks keep running.
        """
        logger.info(f"Enabling voice mode for connection {self.connection_id}")
        self._is_text_mode = False

        if input_track is not None and self.input_track is None:
            # Pure-text session upgrading to voice: wire up new track, start tasks
            self.input_track = input_track
            if self.running:
                self.processing_task = asyncio.create_task(self._process_audio())
                self.stt_task = asyncio.create_task(self._continuous_stt())
            logger.info("Voice tasks started for text→voice upgrade")
        elif input_track is not None and self.input_track is not None:
            # Track replacement (e.g. Bluetooth change during resume)
            await self.replace_input_track(input_track)
        else:
            logger.info("Voice mode resumed — existing STT/audio tasks kept as-is")

        self._reset_idle_timer_if_available()
        return self.output_track

    def _reset_idle_timer_if_available(self):
        """Reset idle timer if the hook is wired."""
        if self.on_activity:
            self.on_activity()

    async def disable_voice_mode(self):
        """Pause TTS output and mark session as text-only.

        Keeps the STT / audio-frame tasks alive so switching back to voice
        is instant — no WebRTC renegotiation or task restart required.
        """
        if self._is_text_mode:
            return  # Already paused
        logger.info(f"Pausing voice mode for connection {self.connection_id}")
        self._is_text_mode = True
        # Stop any TTS that is currently playing / being generated
        await self._trigger_interrupt()
        logger.info("Voice mode paused — STT/audio tasks remain alive for fast resume")

    async def stop(self):
        """Stop processing audio."""
        self.running = False
        
        # Signal end of audio stream
        await self.audio_queue.put(None)
        
        if self.stt_task:
            self.stt_task.cancel()
            try:
                await self.stt_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the task
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the task
        
        # Save debug recording if enabled
        self.debug_recorder.save()
        
        logger.info(f"Audio processor stopped for connection {self.connection_id}")
    
    async def _play_greeting(self):
        """Play the AI greeting message when connection starts."""
        # Mark as sent immediately to prevent any duplicate greeting trigger
        # from connectionstatechange firing again during renegotiation.
        self._greeting_sent = True
        try:
            # Set speaking flag to prevent interruption during greeting
            self.is_ai_speaking = True
            
            # Generate greeting text and audio (pass user_id if available)
            greeting_text, audio_stream = await self.ai_assistant.get_greeting_audio(user_id=self.user_id)
            logger.info(f"Greeting: {greeting_text}")
            
            # Send greeting text to client via data channel
            self._send_chat_message(greeting_text, is_user=False, is_chunk=False)
            
            # Queue greeting audio for playback; stop early if interrupted
            async for audio_chunk in audio_stream:
                if audio_chunk:
                    if self.interrupt_event.is_set():
                        logger.info("Greeting interrupted by user speech")
                        break
                    await self.output_track.queue_audio(audio_chunk)
            
            # Clear speaking flag after greeting completes
            self.is_ai_speaking = False
            
        except Exception as e:
            logger.error(f"Error playing greeting: {e}", exc_info=True)
            self.is_ai_speaking = False
    
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
    
    async def _continuous_stt(self):
        """Continuously stream audio to STT and process final transcripts."""
        try:
            while self.running:
                async def audio_generator():
                    chunk_count = 0
                    while self.running:
                        try:
                            audio_chunk = await asyncio.wait_for(
                                self.audio_queue.get(),
                                timeout=1.0
                            )
                            if audio_chunk is None:
                                break
                            chunk_count += 1
                            yield audio_chunk
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error(f"Audio generator error: {e}", exc_info=True)
                            break
                
                audio_generator_instance = audio_generator()
                async for transcript, is_final in self.transcript_processor.process_audio_stream(
                    audio_generator_instance
                ):
                    if transcript and self.is_ai_speaking and len(transcript.strip()) > 0:
                        logger.info(f"Interrupt detected: '{transcript}'")
                        await self._trigger_interrupt()
                        await asyncio.sleep(0.05)
                    
                    if is_final:
                        await self.audio_queue.put(None)
                        # Interrupt any ongoing AI response before processing
                        # the new transcript (handles the case where partial
                        # speech wasn't enough to fire the interrupt but the
                        # final transcript arrived while AI was still speaking).
                        if self.is_ai_speaking:
                            await self._trigger_interrupt()
                        if transcript and transcript.strip():
                            # Start response as a background task so STT can
                            # immediately resume listening for the next interrupt.
                            # Use on_transcript_final hook if wired (e.g. to
                            # ResponseOrchestrator in Phase 8), otherwise fall
                            # back to _process_final_transcript.
                            handler = (
                                self.on_transcript_final
                                if self.on_transcript_final is not None
                                else self._process_final_transcript
                            )
                            self._response_task = asyncio.create_task(
                                handler(transcript)
                            )
                        break
                
                await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            logger.info("Continuous STT cancelled")
        except Exception as e:
            logger.error(f"Error in continuous STT: {e}", exc_info=True)
    
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
    
    async def process_text_input(self, text: str):
        """Public entry point for text-mode input from the data channel.

        Validates the input, interrupts any ongoing response, and starts a new
        response task.  Use this instead of calling _process_final_transcript
        directly.

        Special case: when the conversation is in FINALIZE stage (actively
        searching for providers), interrupting would lose the search results.
        Instead, send a bilingual 'please wait' message and return early.
        """
        text = text.strip()
        if not text:
            logger.warning("process_text_input called with empty text — ignoring")
            return

        # Guard: do not interrupt provider search in progress
        if (
            self.ai_assistant.conversation_service.get_current_stage()
            == ConversationStage.FINALIZE
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

        # Interrupt any in-progress response before generating the new one so
        # the user gets a fresh reply without the old stream still running.
        if self.is_ai_speaking or (self._response_task and not self._response_task.done()):
            await self._trigger_interrupt()
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

            # Advance the runtime FSM: LISTENING → THINKING
            fsm = self.ai_assistant.response_orchestrator.runtime_fsm
            fsm.transition("final_transcript")
            
            # Send user transcript to client
            self._send_chat_message(transcript, is_user=True)
            
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
                    if chunk:
                        # Send AI chunk to client
                        self._send_chat_message(chunk, is_user=False, is_chunk=True)
                        
                    if first_chunk and chunk:
                        perf_times['llm_first_token'] = asyncio.get_event_loop().time()
                        logger.info(f"⚡ Time to first LLM token: {perf_times['llm_first_token'] - llm_start:.3f}s")
                        first_chunk = False
                    yield chunk
            
            if self._is_text_mode:
                # Text mode: consume the LLM stream (chunks already sent via
                # data channel inside tracked_llm_stream) without TTS.
                async for _ in tracked_llm_stream():
                    pass
                self.is_ai_speaking = False
            else:
                # Voice mode: process through TTS manager
                await self.tts_manager.process_llm_stream(tracked_llm_stream())
                # Monitor playback completion in background; it will clear
                # is_ai_speaking once the audio queue drains.
                asyncio.create_task(self._monitor_playback_completion())

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
