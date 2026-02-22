"""
Tests for AudioProcessor text-mode and mode-switching features.

Covers:
- Text-mode initialisation (_is_text_mode, _greeting_sent, _response_task)
- start() behaviour in text vs voice modes
- send_text_greeting() — dedup guard, data-channel polling, timeout fallback
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
from unittest.mock import AsyncMock, Mock, patch, MagicMock

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

    def test_is_text_mode_true_when_no_track(self, text_proc):
        assert text_proc._is_text_mode is True

    def test_is_text_mode_false_when_track_provided(self, voice_proc):
        assert voice_proc._is_text_mode is False

    def test_greeting_sent_initialises_false(self, text_proc):
        assert text_proc._greeting_sent is False

    def test_response_task_initialises_none(self, text_proc):
        assert text_proc._response_task is None

    def test_on_activity_hook_initialises_none(self, text_proc):
        assert text_proc.on_activity is None


# ══════════════════════════════════════════════════════════════════════════════
# start()
# ══════════════════════════════════════════════════════════════════════════════

class TestStart:

    async def test_text_mode_skips_audio_tasks(self, text_proc):
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()) as mock_pa,
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()) as mock_stt,
            patch.object(text_proc, "_play_greeting", new=AsyncMock()) as mock_greet,
        ):
            await text_proc.start()

        # Tasks must NOT be created for the audio pipeline in text mode
        assert text_proc.processing_task is None
        assert text_proc.stt_task is None
        mock_greet.assert_not_called()

    async def test_text_mode_advances_stage_to_triage_immediately(self, text_proc):
        """start() must advance stage to TRIAGE before any async work so that
        a user message arriving before the greeting finishes is processed at
        the correct stage (not GREETING)."""
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()),
            patch.object(text_proc, "_play_greeting", new=AsyncMock()),
        ):
            await text_proc.start()

        assert (
            text_proc.ai_assistant.conversation_service.get_current_stage()
            == ConversationStage.TRIAGE
        )

    async def test_text_mode_sets_running(self, text_proc):
        with (
            patch.object(text_proc, "_process_audio", new=AsyncMock()),
            patch.object(text_proc, "_continuous_stt", new=AsyncMock()),
            patch.object(text_proc, "_play_greeting", new=AsyncMock()),
        ):
            await text_proc.start()

        assert text_proc.running is True

    async def test_voice_mode_creates_audio_tasks(self, voice_proc):
        with (
            patch.object(voice_proc, "_process_audio", new=AsyncMock()),
            patch.object(voice_proc, "_continuous_stt", new=AsyncMock()),
            patch.object(voice_proc, "_play_greeting", new=AsyncMock()),
        ):
            await voice_proc.start()

        assert voice_proc.processing_task is not None
        assert voice_proc.stt_task is not None

    async def test_voice_mode_calls_play_greeting(self, voice_proc):
        play_greeting_called = asyncio.Event()

        async def fake_play_greeting():
            play_greeting_called.set()

        with (
            patch.object(voice_proc, "_process_audio", new=AsyncMock()),
            patch.object(voice_proc, "_continuous_stt", new=AsyncMock()),
            patch.object(voice_proc, "_play_greeting", side_effect=fake_play_greeting),
        ):
            await voice_proc.start()
            await asyncio.wait_for(play_greeting_called.wait(), timeout=1.0)


# ══════════════════════════════════════════════════════════════════════════════
# send_text_greeting()
# ══════════════════════════════════════════════════════════════════════════════

class TestSendTextGreeting:

    async def test_sends_greeting_text_via_data_channel(self, text_proc):
        text_proc.running = True
        text_proc.data_channel = _open_data_channel()
        text_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hallo!", _dummy_audio_gen())
        )
        sent_messages = []
        text_proc.data_channel.send = Mock(side_effect=lambda m: sent_messages.append(m))

        await text_proc.send_text_greeting()

        assert any("Hallo!" in m for m in sent_messages)

    async def test_dedup_guard_prevents_second_call(self, text_proc):
        text_proc.running = True
        text_proc.data_channel = _open_data_channel()
        text_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hi", _dummy_audio_gen())
        )

        # First call should succeed
        await text_proc.send_text_greeting()
        first_call_count = text_proc.ai_assistant.get_greeting_audio.call_count

        # Second call must be a no-op
        await text_proc.send_text_greeting()

        assert text_proc.ai_assistant.get_greeting_audio.call_count == first_call_count

    async def test_sets_greeting_sent_flag(self, text_proc):
        text_proc.running = True
        text_proc.data_channel = _open_data_channel()
        text_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hi", _dummy_audio_gen())
        )

        await text_proc.send_text_greeting()

        assert text_proc._greeting_sent is True

    async def test_does_not_call_tts(self, text_proc):
        """Audio stream returned by get_greeting_audio must never be consumed."""
        text_proc.running = True
        text_proc.data_channel = _open_data_channel()

        consumed = []

        async def audio_gen_tracking():
            consumed.append("chunk")
            yield b"audio"

        text_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hello!", audio_gen_tracking())
        )

        await text_proc.send_text_greeting()

        # send_text_greeting discards the audio stream — nothing consumed
        assert len(consumed) == 0

    async def test_timeout_advances_stage_without_sending(self, text_proc):
        """When data channel never opens, stage must be TRIAGE and no greeting
        should be sent.  The stage is now advanced at the very start of
        send_text_greeting() — before the poll — so it is set even on timeout."""
        text_proc.running = True
        # data_channel is None — channel never opens

        # Replace conversation_service with a mock so set_stage is trackable
        text_proc.ai_assistant.conversation_service = Mock()

        # Patch asyncio.sleep so the 50-iteration loop completes instantly
        with patch("asyncio.sleep", new=AsyncMock()):
            await text_proc.send_text_greeting()

        text_proc.ai_assistant.conversation_service.set_stage.assert_called_with(
            ConversationStage.TRIAGE
        )

    async def test_not_running_returns_immediately(self, text_proc):
        text_proc.running = False
        text_proc.data_channel = _open_data_channel()
        text_proc.ai_assistant.get_greeting_audio = AsyncMock()

        await text_proc.send_text_greeting()

        # Nothing should have been called
        text_proc.ai_assistant.get_greeting_audio.assert_not_called()

    async def test_skips_greeting_when_response_task_already_running(self, text_proc):
        """If the user sends their first message before the data channel finishes
        opening (race condition), _response_task is running and the auto-greeting
        must be suppressed so the user doesn't receive a stale generic greeting
        after their TRIAGE response."""
        text_proc.running = True
        text_proc.data_channel = _open_data_channel()
        text_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hi!", _dummy_audio_gen())
        )

        # Simulate a response task already in flight
        never_done: asyncio.Task = asyncio.create_task(asyncio.sleep(9999))
        text_proc._response_task = never_done
        try:
            await text_proc.send_text_greeting()
            # get_greeting_audio must NOT be called
            text_proc.ai_assistant.get_greeting_audio.assert_not_called()
        finally:
            never_done.cancel()
            try:
                await never_done
            except asyncio.CancelledError:
                pass

    async def test_greeting_called_with_manage_stage_false(self, text_proc):
        """send_text_greeting must call get_greeting_audio with manage_stage=False
        so the stage is never reset from TRIAGE back to GREETING."""
        text_proc.running = True
        text_proc.data_channel = _open_data_channel()
        text_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hello!", _dummy_audio_gen())
        )

        await text_proc.send_text_greeting()

        text_proc.ai_assistant.get_greeting_audio.assert_called_once_with(
            user_id=text_proc.user_id, manage_stage=False
        )


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

        assert text_proc._is_text_mode is False

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
        voice_proc._is_text_mode = True  # simulate paused state
        # Pre-existing running tasks
        old_proc_task = asyncio.create_task(asyncio.sleep(60))
        old_stt_task = asyncio.create_task(asyncio.sleep(60))
        voice_proc.processing_task = old_proc_task
        voice_proc.stt_task = old_stt_task

        await voice_proc.enable_voice_mode()  # no track argument → resume path

        assert voice_proc._is_text_mode is False
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

    async def test_flips_is_text_mode_to_true(self, voice_proc):
        with patch.object(voice_proc, "_trigger_interrupt", new=AsyncMock()):
            await voice_proc.disable_voice_mode()

        assert voice_proc._is_text_mode is True

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
# _play_greeting()
# ══════════════════════════════════════════════════════════════════════════════

class TestPlayGreeting:

    async def test_sets_greeting_sent_immediately(self, voice_proc):
        voice_proc.output_track.queue_audio = AsyncMock()
        voice_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hello!", _dummy_audio_gen())
        )

        await voice_proc._play_greeting()

        assert voice_proc._greeting_sent is True

    async def test_stops_streaming_when_interrupted(self, voice_proc):
        """If interrupt_event is set mid-greeting, audio streaming must stop."""
        queued_chunks = []

        async def slow_audio_gen():
            for i in range(5):
                yield f"chunk{i}".encode()
                await asyncio.sleep(0)  # yield to event loop

        voice_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hi!", slow_audio_gen())
        )

        async def queue_side_effect(chunk):
            queued_chunks.append(chunk)
            # Trigger interrupt after first chunk
            if len(queued_chunks) == 1:
                voice_proc.interrupt_event.set()

        voice_proc.output_track.queue_audio = AsyncMock(
            side_effect=queue_side_effect
        )

        await voice_proc._play_greeting()

        # Must have stopped early — not all 5 chunks queued
        assert len(queued_chunks) < 5

    async def test_clears_is_ai_speaking_on_completion(self, voice_proc):
        voice_proc.output_track.queue_audio = AsyncMock()
        voice_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hi!", _dummy_audio_gen())
        )

        await voice_proc._play_greeting()

        assert voice_proc.is_ai_speaking is False

    async def test_sets_is_ai_speaking_during_playback(self, voice_proc):
        states_during = []

        async def capture(*args):
            states_during.append(voice_proc.is_ai_speaking)

        voice_proc.output_track.queue_audio = AsyncMock(side_effect=capture)
        voice_proc.ai_assistant.get_greeting_audio = AsyncMock(
            return_value=("Hi!", _dummy_audio_gen())
        )

        await voice_proc._play_greeting()

        assert all(s is True for s in states_during), (
            "is_ai_speaking must be True while greeting audio is queued"
        )


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
        interrupt_mock = AsyncMock()

        with (
            patch.object(text_proc, "_trigger_interrupt", new=interrupt_mock),
            patch.object(text_proc, "_process_final_transcript", new=AsyncMock()),
        ):
            await text_proc.process_text_input("next message")

        # _trigger_interrupt must have been called because in_flight was running
        interrupt_mock.assert_called_once()
        in_flight.cancel()  # clean up the dangling task


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
        text_proc._is_text_mode = True
        # generate_llm_response_stream is called synchronously (no await), so
        # Mock (not AsyncMock) is needed — AsyncMock would return a coroutine
        # instead of an async generator, causing a silent TypeError.
        text_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=_empty_llm_stream()
        )

        with patch.object(
            text_proc.tts_manager, "process_llm_stream", new=AsyncMock()
        ) as mock_tts:
            await text_proc._process_final_transcript("hi")

        mock_tts.assert_not_called()

    async def test_text_mode_clears_is_ai_speaking(self, text_proc):
        text_proc._is_text_mode = True

        async def fake_llm():
            yield "chunk"

        text_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=fake_llm()
        )
        text_proc.data_channel = _open_data_channel()
        text_proc.data_channel.send = Mock()

        await text_proc._process_final_transcript("hello")

        assert text_proc.is_ai_speaking is False

    async def test_voice_mode_calls_tts_manager(self, voice_proc):
        voice_proc._is_text_mode = False

        async def fake_llm():
            yield "hello"

        voice_proc.ai_assistant.generate_llm_response_stream = Mock(
            return_value=fake_llm()
        )
        voice_proc.data_channel = _open_data_channel()
        voice_proc.data_channel.send = Mock()

        with patch.object(
            voice_proc.tts_manager, "process_llm_stream", new=AsyncMock()
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
        text_proc.data_channel = _open_data_channel()
        text_proc.data_channel.send = Mock()

        await text_proc._process_final_transcript("test")

        assert calls, "on_activity must be called"

    async def test_cancelled_error_resets_is_ai_speaking(self, text_proc):
        text_proc._is_text_mode = True

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
            # Run _continuous_stt for just long enough to issue the task
            voice_proc.running = True
            stt_task = asyncio.create_task(voice_proc._continuous_stt())

            # Wait for _process_final_transcript to be called
            try:
                await asyncio.wait_for(pft_started.wait(), timeout=1.0)
            finally:
                voice_proc.running = False
                stt_task.cancel()
                try:
                    await stt_task
                except asyncio.CancelledError:
                    pass

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
            stt_task = asyncio.create_task(voice_proc._continuous_stt())
            await asyncio.sleep(0.05)
            voice_proc.running = False
            stt_task.cancel()
            try:
                await stt_task
            except asyncio.CancelledError:
                pass

        assert interrupted, "_trigger_interrupt must be called before new response"


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
        proc.ai_assistant.conversation_service.get_current_stage = Mock(
            return_value=ConversationStage.FINALIZE
        )

        sent_messages = []
        with patch.object(
            proc,
            "_send_chat_message",
            side_effect=lambda text, is_user, **kw: sent_messages.append(text),
        ):
            await proc.process_text_input("Noch jemanden?")

        assert any("such" in m.lower() or "search" in m.lower() or "moment" in m.lower()
                   for m in sent_messages), \
            f"Expected a 'still searching' busy message, got: {sent_messages}"

    async def test_new_message_during_finalize_does_not_cancel_task(self):
        proc = self._make_busy_proc()
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
