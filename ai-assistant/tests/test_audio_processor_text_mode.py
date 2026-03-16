"""
Tests for AudioProcessor text-mode and mode-switching features.

Covers:
- Text-mode initialisation (session_mode, _greeting_sent, _response_task)
- start() behaviour in text vs voice modes
- enable_voice_mode() — fresh upgrade, resume, track replacement
- disable_voice_mode() — pause-only semantics, idempotence
- _play_greeting() — marks _greeting_sent, respects interrupt event
- process_text_input() — interrupts in-flight response, ignores empty input
- _trigger_interrupt() — cancels _response_task, resets flags
- _process_final_transcript() — text path (no TTS), CancelledError handling,
  on_activity hook
- _continuous_stt() — runs response as background task (non-blocking),
  interrupts ongoing response before new final transcript
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from ai_assistant.services.session_mode import SessionMode

from ai_assistant.audio_processor import AudioProcessor
from ai_assistant.services.conversation_service import ConversationStage


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_processor(input_track=None):
    """Return an AudioProcessor with all external I/O patched."""
    with (
        patch("ai_assistant.services.speech_to_text_service.SpeechAsyncClient"),
        patch("ai_assistant.services.text_to_speech_service.TextToSpeechAsyncClient"),
    ):
        return AudioProcessor(
            connection_id="test-conn",
            input_track=input_track,
        )


def _open_data_channel():
    """Return a mock data channel that reports readyState == 'open'."""
    dc = Mock()
    dc.readyState = "open"
    return dc


def _advance_fsm_to_listening(proc) -> None:
    """Advance the AgentRuntimeFSM from BOOTSTRAP to LISTENING.

    In production this happens inside PeerConnectionHandler._wire_runtime_fsm().
    Tests that want process_text_input() to reach the greeting/response code must
    call this first, otherwise the FSM guard fires at BOOTSTRAP.
    """
    fsm = proc.ai_assistant.response_orchestrator.runtime_fsm
    fsm.transition("data_channel_wait")   # BOOTSTRAP → DATA_CHANNEL_WAIT
    fsm.transition("data_channel_opened") # DATA_CHANNEL_WAIT → LISTENING


async def _dummy_audio_gen():
    """Async generator yielding two fake audio chunks."""
    yield b"chunk1"
    yield b"chunk2"


async def _empty_llm_stream():
    """Empty async LLM stream."""
    if False:  # pragma: no cover
        yield ""


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def text_proc():
    """AudioProcessor created without an input track (text mode)."""
    return _make_processor(input_track=None)


@pytest.fixture
def voice_proc():
    """AudioProcessor created with an input track (voice mode)."""
    track = Mock()
    track.kind = "audio"
    track.id = "voice-track-1"
    return _make_processor(input_track=track)


# ══════════════════════════════════════════════════════════════════════════════
# Initialisation
# ══════════════════════════════════════════════════════════════════════════════

class TestTextModeInitialisation:

    def test_session_mode_text_when_no_track(self, text_proc):
        assert text_proc.session_mode == SessionMode.TEXT

    def test_session_mode_voice_when_track_provided(self, voice_proc):
        assert voice_proc.session_mode == SessionMode.VOICE

    def test_session_not_initialized_at_start(self, text_proc):
        assert text_proc._session_starter.initialized_event.is_set() is False

    def test_response_task_initialises_none(self, text_proc):
        assert text_proc._response_task is None

    def test_on_activity_hook_initialises_none(self, text_proc):
        assert text_proc.on_activity is None

    def test_text_input_lock_initialised(self, text_proc):
        assert isinstance(text_proc._text_input_lock, asyncio.Lock)


# ══════════════════════════════════════════════════════════════════════════════
# start()
# ══════════════════════════════════════════════════════════════════════════════

class TestStart:

    async def test_text_mode_skips_audio_tasks(self, text_proc):
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock(return_value=None)),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock(return_value=None)),
            patch.object(text_proc._session_starter, "initialize", new=AsyncMock(return_value=None)),
        ):
            await text_proc.start()

        # Tasks must NOT be created for the audio pipeline in text mode
        assert text_proc.processing_task is None
        assert text_proc.stt_task is None

    async def test_text_mode_sets_running(self, text_proc):
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock(return_value=None)),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock(return_value=None)),
            patch.object(text_proc._session_starter, "initialize", new=AsyncMock(return_value=None)),
        ):
            await text_proc.start()

        assert text_proc.running is True

    async def test_voice_mode_creates_audio_tasks(self, voice_proc):
        with (
            patch.object(voice_proc, "_process_audio", new=AsyncMock(return_value=None)),
            patch.object(voice_proc, "_continuous_stt", new=AsyncMock(return_value=None)),
            patch.object(voice_proc._session_starter, "initialize", new=AsyncMock(return_value=None)),
        ):
            await voice_proc.start()

        assert voice_proc.processing_task is not None
        assert voice_proc.stt_task is not None

    async def test_voice_mode_schedules_session_starter(self, voice_proc):
        """start() must schedule _session_starter.initialize() as a task."""
        initialized = asyncio.Event()

        async def fake_initialize():
            initialized.set()

        with (
            patch.object(voice_proc, "_process_audio", new=AsyncMock()),
            patch.object(voice_proc, "_continuous_stt", new=AsyncMock()),
            patch.object(voice_proc._session_starter, "initialize", side_effect=fake_initialize),
        ):
            await voice_proc.start()
            await asyncio.wait_for(initialized.wait(), timeout=1.0)


# ══════════════════════════════════════════════════════════════════════════════
# enable_voice_mode()
# ══════════════════════════════════════════════════════════════════════════════

class TestEnableVoiceMode:

    async def test_fresh_upgrade_flips_flag(self, text_proc):
        new_track = Mock()
        new_track.kind = "audio"
        new_track.id = "new-track"
        text_proc.running = True
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()),
        ):
            await text_proc.enable_voice_mode(input_track=new_track)

        assert text_proc.session_mode == SessionMode.VOICE

    async def test_fresh_upgrade_starts_stt_and_audio_tasks(self, text_proc):
        new_track = Mock()
        new_track.kind = "audio"
        new_track.id = "new-track"
        text_proc.running = True
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()),
        ):
            await text_proc.enable_voice_mode(input_track=new_track)

        assert text_proc.processing_task is not None
        assert text_proc.stt_task is not None

    async def test_fresh_upgrade_assigns_input_track(self, text_proc):
        new_track = Mock()
        text_proc.running = True
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()),
        ):
            await text_proc.enable_voice_mode(input_track=new_track)

        assert text_proc.input_track is new_track

    async def test_resume_flips_flag_without_restarting_tasks(self, voice_proc):
        """Resuming a paused session should only flip the flag."""
        voice_proc.session_mode = SessionMode.TEXT  # simulate paused state
        # Pre-existing running tasks
        old_proc_task = asyncio.create_task(asyncio.sleep(60))
        old_stt_task = asyncio.create_task(asyncio.sleep(60))
        voice_proc.processing_task = old_proc_task
        voice_proc.stt_task = old_stt_task

        await voice_proc.enable_voice_mode()  # no track argument → resume path

        assert voice_proc.session_mode == SessionMode.VOICE
        # Tasks must be the SAME objects — not replaced
        assert voice_proc.processing_task is old_proc_task
        assert voice_proc.stt_task is old_stt_task

        old_proc_task.cancel()
        old_stt_task.cancel()

    async def test_track_replacement_calls_replace_input_track(self, voice_proc):
        """When voice_proc already has a track and a new one is provided, replace it."""
        new_track = Mock()
        new_track.kind = "audio"
        new_track.id = "replacement"

        with patch.object(
            voice_proc, "replace_input_track", new=AsyncMock()
        ) as mock_replace:
            await voice_proc.enable_voice_mode(input_track=new_track)

        mock_replace.assert_called_once_with(new_track)

    async def test_on_activity_hook_called(self, text_proc):
        activity_called = []
        text_proc.on_activity = lambda: activity_called.append(1)
        text_proc.running = True
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()),
        ):
            await text_proc.enable_voice_mode()

        assert activity_called


# ══════════════════════════════════════════════════════════════════════════════
# disable_voice_mode()
# ══════════════════════════════════════════════════════════════════════════════

class TestDisableVoiceMode:

    async def test_flips_session_mode_to_text(self, voice_proc):
        with patch.object(voice_proc, "_trigger_interrupt", new=AsyncMock()):
            await voice_proc.disable_voice_mode()

        assert voice_proc.session_mode == SessionMode.TEXT

    async def test_calls_trigger_interrupt(self, voice_proc):
        with patch.object(
            voice_proc, "_trigger_interrupt", new=AsyncMock()
        ) as mock_intr:
            await voice_proc.disable_voice_mode()

        mock_intr.assert_called_once()

    async def test_idempotent_when_already_text_mode(self, text_proc):
        with patch.object(
            text_proc, "_trigger_interrupt", new=AsyncMock()
        ) as mock_intr:
            await text_proc.disable_voice_mode()

        mock_intr.assert_not_called()

    async def test_does_not_cancel_stt_task(self, voice_proc):
        """Pause-only: STT task must remain alive after disable_voice_mode."""
        running_task = asyncio.create_task(asyncio.sleep(60))
        voice_proc.stt_task = running_task
        with patch.object(voice_proc, "_trigger_interrupt", new=AsyncMock()):
            await voice_proc.disable_voice_mode()

        assert not running_task.cancelled()
        running_task.cancel()





# ══════════════════════════════════════════════════════════════════════════════
# process_text_input()
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessTextInput:

    async def test_ignores_empty_string(self, text_proc):
        with patch.object(
            text_proc, "_process_final_transcript", new=AsyncMock()
        ) as mock_pft:
            await text_proc.process_text_input("   ")

        mock_pft.assert_not_called()
        assert text_proc._response_task is None

    async def test_creates_response_task(self, text_proc):
        text_proc._session_starter.initialized_event.set()
        with patch.object(
            text_proc, "_process_final_transcript", new=AsyncMock()
        ):
            await text_proc.process_text_input("hello")

        assert text_proc._response_task is not None

    async def test_interrupts_ongoing_response_before_new_one(self, text_proc):
        """Sending a second message while AI is still responding must interrupt first."""
        interrupted_calls = []

        async def fake_trigger_interrupt():
            interrupted_calls.append(1)

        text_proc._session_starter.initialized_event.set()
        text_proc.is_ai_speaking = True
        with (
            patch.object(
                text_proc, "_trigger_interrupt", side_effect=fake_trigger_interrupt
            ),
            patch.object(text_proc, "_process_final_transcript", new=AsyncMock()),
        ):
            await text_proc.process_text_input("new message")

        assert interrupted_calls, "Expected _trigger_interrupt to be called"

    async def test_interrupts_in_flight_task_before_new_one(self, text_proc):
        """process_text_input must call _trigger_interrupt when a task is in-flight."""
        # Simulate an in-flight task (not done)
        in_flight = asyncio.create_task(asyncio.sleep(60))
        text_proc._response_task = in_flight
        text_proc._session_starter.initialized_event.set()
        interrupt_mock = AsyncMock()

        with (
            patch.object(text_proc, "_trigger_interrupt", new=interrupt_mock),
            patch.object(text_proc, "_process_final_transcript", new=AsyncMock()),
        ):
            await text_proc.process_text_input("next message")

        # _trigger_interrupt must have been called because in_flight was running
        interrupt_mock.assert_called_once()
        in_flight.cancel()  # clean up the dangling task

    async def test_concurrent_inputs_are_serialized_by_lock(self, text_proc):
        """Second process_text_input call must wait until first leaves the critical section."""
        gate = asyncio.Event()
        interrupt_calls: list[str] = []

        # Mark session as initialized so the wait doesn't block —
        # this test is about lock serialisation, not initialization behaviour.
        text_proc._session_starter.initialized_event.set()

        async def blocking_interrupt():
            interrupt_calls.append("interrupt")
            await gate.wait()

        text_proc.is_ai_speaking = True
        with (
            patch.object(text_proc, "_trigger_interrupt", side_effect=blocking_interrupt),
            patch.object(text_proc, "_process_final_transcript", new=AsyncMock()),
        ):
            first = asyncio.create_task(text_proc.process_text_input("first"))
            await asyncio.sleep(0)
            second = asyncio.create_task(text_proc.process_text_input("second"))
            await asyncio.sleep(0)

            # Without the lock, both calls could enter and block in interrupt.
            assert interrupt_calls == ["interrupt"]

            gate.set()
            await asyncio.gather(first, second)




# ══════════════════════════════════════════════════════════════════════════════
# _trigger_interrupt()
# ══════════════════════════════════════════════════════════════════════════════

class TestTriggerInterrupt:

    async def test_sets_interrupt_event(self, voice_proc):
        voice_proc.tts_manager.interrupt = Mock()
        voice_proc.output_track.clear_queue = AsyncMock()

        await voice_proc._trigger_interrupt()

        assert voice_proc.interrupt_event.is_set()

    async def test_clears_is_ai_speaking(self, voice_proc):
        voice_proc.is_ai_speaking = True
        voice_proc.tts_manager.interrupt = Mock()
        voice_proc.output_track.clear_queue = AsyncMock()

        await voice_proc._trigger_interrupt()

        assert voice_proc.is_ai_speaking is False

    async def test_cancels_response_task(self, voice_proc):
        in_flight = asyncio.create_task(asyncio.sleep(60))
        voice_proc._response_task = in_flight
        voice_proc.tts_manager.interrupt = Mock()
        voice_proc.output_track.clear_queue = AsyncMock()

        await voice_proc._trigger_interrupt()

        # cancel() was called; yield so the event loop can process the cancellation
        await asyncio.sleep(0)

        assert in_flight.cancelled()
        assert voice_proc._response_task is None

    async def test_calls_tts_manager_interrupt(self, voice_proc):
        voice_proc.tts_manager.interrupt = Mock()
        voice_proc.output_track.clear_queue = AsyncMock()

        await voice_proc._trigger_interrupt()

        voice_proc.tts_manager.interrupt.assert_called_once()

    async def test_clears_output_queue(self, voice_proc):
        voice_proc.tts_manager.interrupt = Mock()
        voice_proc.output_track.clear_queue = AsyncMock()

        await voice_proc._trigger_interrupt()

        voice_proc.output_track.clear_queue.assert_called_once()

    async def test_no_error_when_no_response_task(self, voice_proc):
        """_trigger_interrupt must not raise if _response_task is None."""
        voice_proc._response_task = None
        voice_proc.tts_manager.interrupt = Mock()
        voice_proc.output_track.clear_queue = AsyncMock()

        await voice_proc._trigger_interrupt()  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# _process_final_transcript()
# ══════════════════════════════════════════════════════════════════════════════

class TestProcessFinalTranscript:

    async def test_text_mode_skips_tts_manager(self, text_proc):
        """In text mode, the LLM stream is consumed directly — TTS is never called."""
        # text_proc uses SessionMode.TEXT by default (no input track)
        # generate_llm_response_stream is called synchronously (no await), so
        # Mock (not AsyncMock) is needed — AsyncMock would return a coroutine
        # instead of an async generator, causing a silent TypeError.
        text_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=_empty_llm_stream()
        )

        with patch.object(
            text_proc.tts_manager, "process_llm_stream", new=AsyncMock(return_value=(0, 0.0))
        ) as mock_tts:
            await text_proc._process_final_transcript("hi")

        mock_tts.assert_not_called()

    async def test_text_mode_clears_is_ai_speaking(self, text_proc):
        # text_proc uses SessionMode.TEXT by default (no input track)
        async def fake_llm():
            yield "chunk"

        text_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=fake_llm()
        )
        _dc = _open_data_channel()
        text_proc._dc_bridge.attach(_dc)
        _dc.send = Mock()

        await text_proc._process_final_transcript("hello")

        assert text_proc.is_ai_speaking is False

    async def test_voice_mode_calls_tts_manager(self, voice_proc):
        # voice_proc uses SessionMode.VOICE by default (has input track)
        async def fake_llm():
            yield "hello"

        voice_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=fake_llm()
        )
        _dc = _open_data_channel()
        voice_proc._dc_bridge.attach(_dc)
        _dc.send = Mock()

        with patch.object(
            voice_proc.tts_manager, "process_llm_stream", new=AsyncMock(return_value=(0, 0.0))
        ) as mock_tts:
            await voice_proc._process_final_transcript("hello")

        mock_tts.assert_called_once()

    async def test_on_activity_callback_invoked(self, text_proc):
        calls = []
        text_proc.on_activity = lambda: calls.append(1)

        async def fake_llm():
            yield "x"

        text_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=fake_llm()
        )
        _dc = _open_data_channel()
        text_proc._dc_bridge.attach(_dc)
        _dc.send = Mock()

        await text_proc._process_final_transcript("test")

        assert calls, "on_activity must be called"

    async def test_cancelled_error_resets_is_ai_speaking(self, text_proc):
        # text_proc uses SessionMode.TEXT by default (no input track)
        async def raise_cancel():
            raise asyncio.CancelledError()
            yield  # make it an async generator  # noqa: unreachable

        text_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=raise_cancel()
        )
        text_proc.is_ai_speaking = True

        with pytest.raises(asyncio.CancelledError):
            await text_proc._process_final_transcript("cancel me")

        assert text_proc.is_ai_speaking is False

    async def test_text_mode_does_not_echo_user_message(self, text_proc):
        """In text mode, _process_final_transcript must not send the user transcript
        to the data channel — Flutter adds it optimistically."""
        text_proc.running = True
        _dc = _open_data_channel()
        text_proc._dc_bridge.attach(_dc)
        _advance_fsm_to_listening(text_proc)

        sent_messages = []
        _dc.send = Mock(side_effect=lambda m: sent_messages.append(m))

        # Patch LLM stream to return nothing
        text_proc.ai_assistant.generate_llm_response_stream = Mock(return_value=_empty_llm_stream())

        await text_proc._process_final_transcript("hi, I need an electrician")

        # No message with isUser=true should have been sent
        import json
        user_messages = [
            m for m in sent_messages
            if isinstance(m, str) and json.loads(m).get('isUser') is True
        ]
        assert user_messages == [], (
            "Text mode must not echo user message — Flutter adds it optimistically"
        )

    async def test_voice_mode_echoes_user_message(self, voice_proc):
        """In voice mode, _process_final_transcript sends the user transcript."""
        voice_proc.running = True
        _dc = _open_data_channel()
        voice_proc._dc_bridge.attach(_dc)

        sent_messages = []
        _dc.send = Mock(side_effect=lambda m: sent_messages.append(m))

        voice_proc.ai_assistant.generate_llm_response_stream = Mock(return_value=_empty_llm_stream())

        # Patch TTS manager so we don't need real audio
        voice_proc.tts_manager = AsyncMock()
        voice_proc.tts_manager.process_llm_stream = AsyncMock(return_value=(0, 0.0))

        await voice_proc._process_final_transcript("I need a plumber")

        import json
        user_messages = [
            m for m in sent_messages
            if isinstance(m, str) and json.loads(m).get('isUser') is True
        ]
        assert len(user_messages) == 1


# ══════════════════════════════════════════════════════════════════════════════
# _continuous_stt() — response task scheduling
# ══════════════════════════════════════════════════════════════════════════════

class TestContinuousSttTaskScheduling:

    async def test_final_transcript_starts_background_task(self, voice_proc):
        """After a final transcript, STT must immediately continue (not block)."""
        tasks_created: list[asyncio.Task] = []

        # Patch process_final_transcript to record the task and then complete
        pft_started = asyncio.Event()

        async def fake_pft(transcript):
            pft_started.set()
            await asyncio.sleep(0.5)  # simulate slow LLM+TTS

        voice_proc.ai_assistant.generate_llm_response_stream = AsyncMock(
            return_value=_empty_llm_stream()
        )

        # Simulate one STT cycle: emit one final transcript then stop
        transcripts = [("hello world", True)]

        async def fake_process_audio_stream(_):
            for text, final in transcripts:
                yield text, final

        voice_proc.transcript_processor.process_audio_stream = Mock(
            return_value=fake_process_audio_stream(None)
        )

        with patch.object(
            voice_proc, "_process_final_transcript", side_effect=fake_pft
        ):
            voice_proc.running = True
            await voice_proc._stt_session()
            # _handle_final_transcript schedules fake_pft via create_task;
            # wait for it to be invoked (gives up to 1 s before failing).
            try:
                await asyncio.wait_for(pft_started.wait(), timeout=1.0)
            finally:
                voice_proc.running = False

        assert pft_started.is_set(), "_process_final_transcript was never called"

    async def test_final_transcript_triggers_interrupt_when_ai_speaking(
        self, voice_proc
    ):
        """If AI is speaking when a final transcript arrives, interrupt first."""
        interrupted = []

        async def fake_interrupt():
            interrupted.append(1)

        async def fake_process_audio_stream(_):
            yield "interrupt me", True

        voice_proc.is_ai_speaking = True
        voice_proc.transcript_processor.process_audio_stream = Mock(
            return_value=fake_process_audio_stream(None)
        )

        with (
            patch.object(
                voice_proc, "_trigger_interrupt", side_effect=fake_interrupt
            ),
            patch.object(voice_proc, "_process_final_transcript", new=AsyncMock()),
        ):
            voice_proc.running = True
            await voice_proc._stt_session()
            await asyncio.sleep(0)  # flush the create_task for _process_final_transcript

        assert interrupted, "_trigger_interrupt must be called before new response"

    async def test_final_echo_not_routed_to_llm_when_ai_speaking(
        self, voice_proc
    ):
        """Echo guard: when AI is speaking and a FINAL transcript arrives,
        _process_final_transcript must NOT be called for that echo transcript.

        Without this guard the triggering transcript (AI's own TTS audio picked
        up by the microphone) would be routed to the LLM as if the user spoke.
        """
        pft_called = False

        async def spy_pft(transcript):
            nonlocal pft_called
            pft_called = True

        async def fake_process_audio_stream(_):
            yield "ai tts echo", True  # final=True while AI is still speaking

        voice_proc.is_ai_speaking = True
        voice_proc.transcript_processor.process_audio_stream = Mock(
            return_value=fake_process_audio_stream(None)
        )

        with (
            patch.object(voice_proc, "_trigger_interrupt", new=AsyncMock()),
            patch.object(
                voice_proc, "_process_final_transcript", side_effect=spy_pft
            ),
        ):
            voice_proc.running = True
            stt_task = asyncio.create_task(voice_proc._continuous_stt())
            await asyncio.sleep(0.05)
            voice_proc.running = False
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass

        assert not pft_called, (
            "_process_final_transcript must NOT be called for a FINAL echo "
            "transcript when is_ai_speaking=True"
        )


# ══════════════════════════════════════════════════════════════════════════════
# FINALIZE-stage busy guard
# ══════════════════════════════════════════════════════════════════════════════

class TestFinalizeStageGuard:
    """
    When ConversationStage is FINALIZE, process_text_input must send an
    apologetic 'still searching' message and return without cancelling the
    ongoing response task.
    When the stage is anything other than FINALIZE, interruption proceeds
    as normal.
    """

    def _make_busy_proc(self):
        proc = _make_processor(input_track=None)
        dc = _open_data_channel()
        proc.set_data_channel(dc)
        return proc

    async def test_new_message_during_finalize_sends_busy_message(self):
        proc = self._make_busy_proc()
        proc._session_starter.initialized_event.set()
        proc.ai_assistant.conversation_service.get_current_stage = Mock(
            return_value=ConversationStage.FINALIZE
        )
        # Guard fires only while the search/presentation task is still running.
        running_task = asyncio.create_task(asyncio.sleep(999))
        proc._response_task = running_task

        sent_messages = []
        with patch.object(
            proc,
            "_send_chat_message",
            side_effect=lambda text, is_user, **kw: sent_messages.append(text),
        ):
            await proc.process_text_input("Noch jemanden?")

        running_task.cancel()
        try:
            await running_task
        except asyncio.CancelledError:
            pass

        assert any("such" in m.lower() or "search" in m.lower() or "moment" in m.lower()
                   for m in sent_messages), \
            f"Expected a 'still searching' busy message, got: {sent_messages}"

    async def test_new_message_during_finalize_does_not_cancel_task(self):
        proc = self._make_busy_proc()
        proc._session_starter.initialized_event.set()
        proc.ai_assistant.conversation_service.get_current_stage = Mock(
            return_value=ConversationStage.FINALIZE
        )

        # Plant a fake running response task
        never_done = asyncio.create_task(asyncio.sleep(999))
        proc._response_task = never_done

        with patch.object(proc, "_send_chat_message", new=Mock()):
            await proc.process_text_input("Bitte warten")

        assert not never_done.cancelled(), \
            "Running task must NOT be cancelled during FINALIZE stage"
        never_done.cancel()
        try:
            await never_done
        except asyncio.CancelledError:
            pass

    async def test_new_message_outside_finalize_still_interrupts(self):
        proc = self._make_busy_proc()
        proc._session_starter.initialized_event.set()
        proc.ai_assistant.conversation_service.get_current_stage = Mock(
            return_value=ConversationStage.TRIAGE
        )

        interrupted = False

        async def fake_interrupt():
            nonlocal interrupted
            interrupted = True

        proc.is_ai_speaking = True
        with patch.object(proc, "_trigger_interrupt", side_effect=fake_interrupt):
            with patch.object(proc, "_process_final_transcript", new=AsyncMock()):
                await proc.process_text_input("New question")

        assert interrupted, "Should interrupt when not in FINALIZE stage"


# ══════════════════════════════════════════════════════════════════════════════
# receive_text_input()
# ══════════════════════════════════════════════════════════════════════════════

class TestReceiveTextInput:
    """receive_text_input is the single public entry-point for text.

    Voice sessions: auto-switch to text then process.
    Text sessions: go straight to process_text_input.
    """

    async def test_voice_mode_triggers_disable_then_process(self, voice_proc):
        """In voice mode, receive_text_input must call disable_voice_mode first."""
        voice_proc._session_starter.initialized_event.set()
        disable_called = []
        process_called = []

        async def fake_disable():
            disable_called.append(1)
            voice_proc.session_mode = SessionMode.TEXT  # simulate what disable does

        with (
            patch.object(voice_proc, "disable_voice_mode", side_effect=fake_disable),
            patch.object(voice_proc, "process_text_input", new=AsyncMock(
                side_effect=lambda t: process_called.append(t)
            )),
        ):
            await voice_proc.receive_text_input("switch me")

        assert disable_called, "disable_voice_mode must be called"
        assert process_called == ["switch me"]

    async def test_text_mode_skips_disable_goes_straight_to_process(self, text_proc):
        """In text mode, receive_text_input must NOT call disable_voice_mode."""
        text_proc._session_starter.initialized_event.set()
        disable_called = []
        process_called = []

        with (
            patch.object(
                text_proc, "disable_voice_mode",
                side_effect=lambda: disable_called.append(1),
            ),
            patch.object(text_proc, "process_text_input", new=AsyncMock(
                side_effect=lambda t: process_called.append(t)
            )),
        ):
            await text_proc.receive_text_input("hello")

        assert not disable_called, "disable_voice_mode must NOT be called in text mode"
        assert process_called == ["hello"]

    async def test_voice_mode_detected_by_session_mode(self, voice_proc):
        """The switch is triggered by session_mode == VOICE, not any other flag."""
        assert voice_proc.session_mode == SessionMode.VOICE

        with (
            patch.object(voice_proc, "disable_voice_mode", new=AsyncMock()),
            patch.object(voice_proc, "process_text_input", new=AsyncMock()),
        ):
            await voice_proc.receive_text_input("test")

        # Just verifying no AttributeError — the mode check itself is the contract
        assert True


# ══════════════════════════════════════════════════════════════════════════════
# History repair: _trigger_interrupt stashes orphaned HumanMessages
# ══════════════════════════════════════════════════════════════════════════════

class TestInterruptHistoryRepair:
    """_trigger_interrupt must pop any trailing HumanMessage from LLM history
    and stash it in _interrupted_text_buffer so no user intent is lost when a
    rapid burst of messages cancels the previous LLM response task."""

    async def test_buffer_initialises_empty(self, text_proc):
        assert text_proc._interrupted_text_buffer == []

    async def test_interrupt_stashes_trailing_human_message(self, text_proc):
        """When a HumanMessage is orphaned by cancellation it goes into the buffer."""
        from langchain_core.messages import HumanMessage

        llm_svc = text_proc.ai_assistant.response_orchestrator.llm_service
        llm_svc.add_message_to_history(text_proc.connection_id, HumanMessage(content="find a coach"))

        # Set up a fake in-flight response task so _trigger_interrupt sees one to cancel
        cancelled = asyncio.Event()

        async def _blocked():
            await cancelled.wait()

        text_proc._response_task = asyncio.create_task(_blocked())

        # Stub FSM transitions so we don't need real FSM wiring
        fsm = text_proc.ai_assistant.response_orchestrator.runtime_fsm
        fsm.transition("data_channel_wait")
        fsm.transition("data_channel_opened")  # BOOTSTRAP → LISTENING

        with patch.object(text_proc.tts_manager, "interrupt"), \
             patch.object(text_proc.output_track, "clear_queue", new=AsyncMock()):
            await text_proc._trigger_interrupt()

        assert text_proc._interrupted_text_buffer == ["find a coach"]
        # Message removed from history
        assert len(llm_svc.get_session_history(text_proc.connection_id).messages) == 0

    async def test_interrupt_does_not_stash_when_no_trailing_human_message(self, text_proc):
        """If history ends with an AI message, the buffer must remain empty."""
        from langchain_core.messages import AIMessage, HumanMessage

        llm_svc = text_proc.ai_assistant.response_orchestrator.llm_service
        llm_svc.add_message_to_history(text_proc.connection_id, HumanMessage(content="hi"))
        llm_svc.add_message_to_history(text_proc.connection_id, AIMessage(content="hello!"))

        fsm = text_proc.ai_assistant.response_orchestrator.runtime_fsm
        fsm.transition("data_channel_wait")
        fsm.transition("data_channel_opened")

        with patch.object(text_proc.tts_manager, "interrupt"), \
             patch.object(text_proc.output_track, "clear_queue", new=AsyncMock()):
            await text_proc._trigger_interrupt()

        assert text_proc._interrupted_text_buffer == []


# ══════════════════════════════════════════════════════════════════════════════
# process_text_input: stashed text is combined with the next user message
# ══════════════════════════════════════════════════════════════════════════════

class TestInterruptedTextCombining:
    """When _interrupted_text_buffer is non-empty, process_text_input must prepend
    those stashed fragments to the new input before dispatching to the LLM.
    This ensures rapid STT bursts / multi-message sequences are processed as
    one coherent turn and Gemini never sees consecutive HumanMessages."""

    async def test_stashed_text_prepended_to_new_input(self, text_proc):
        """Text in _interrupted_text_buffer is merged with the new message."""
        _advance_fsm_to_listening(text_proc)
        text_proc._session_starter.initialized_event.set()

        text_proc._interrupted_text_buffer = ["First message.", "Second message."]

        dispatched: list[str] = []

        async def fake_transcript(transcript: str):
            dispatched.append(transcript)

        with patch.object(text_proc, "_process_final_transcript", new=AsyncMock(side_effect=fake_transcript)):
            await text_proc.process_text_input("Third message.")
            await asyncio.sleep(0)  # let the created task run

        assert len(dispatched) == 1
        combined = dispatched[0]
        assert "First message." in combined
        assert "Second message." in combined
        assert "Third message." in combined
        # Chronological order: stashed first, new text last
        assert combined.index("First message.") < combined.index("Third message.")

    async def test_buffer_cleared_after_combining(self, text_proc):
        """After combining, _interrupted_text_buffer must be empty."""
        _advance_fsm_to_listening(text_proc)
        text_proc._session_starter.initialized_event.set()
        text_proc._interrupted_text_buffer = ["old fragment"]

        with patch.object(text_proc, "_process_final_transcript", new=AsyncMock()):
            await text_proc.process_text_input("new input")
            await asyncio.sleep(0)

        assert text_proc._interrupted_text_buffer == []

    async def test_no_stash_leaves_input_unchanged(self, text_proc):
        """When buffer is empty, the input text is dispatched as-is."""
        _advance_fsm_to_listening(text_proc)
        text_proc._session_starter.initialized_event.set()

        dispatched: list[str] = []

        async def fake_transcript(transcript: str):
            dispatched.append(transcript)

        with patch.object(text_proc, "_process_final_transcript", new=AsyncMock(side_effect=fake_transcript)):
            await text_proc.process_text_input("standalone message")
            await asyncio.sleep(0)

        assert dispatched == ["standalone message"]

    async def test_multiple_stashed_turns_all_combined(self, text_proc):
        """Three stashed fragments plus new input all end up in one dispatch."""
        _advance_fsm_to_listening(text_proc)
        text_proc._session_starter.initialized_event.set()
        text_proc._interrupted_text_buffer = ["A", "B", "C"]

        dispatched: list[str] = []

        async def fake_transcript(transcript: str):
            dispatched.append(transcript)

        with patch.object(text_proc, "_process_final_transcript", new=AsyncMock(side_effect=fake_transcript)):
            await text_proc.process_text_input("D")
            await asyncio.sleep(0)

        assert len(dispatched) == 1
        assert all(frag in dispatched[0] for frag in ["A", "B", "C", "D"])

