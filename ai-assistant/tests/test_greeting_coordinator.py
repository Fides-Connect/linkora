"""Tests for GreetingCoordinator — RED phase.

Covers:
- greeting_sent flag initialises False
- Voice mode: sends chat message, marks sent, idempotent on second call
- Voice mode: manages is_ai_speaking via on_speaking_change callback
- Voice mode: stops streaming on interrupt
- Text mode: sends greeting when DC open and FSM is LISTENING
- Text mode: skips when FSM has advanced beyond LISTENING (race guard)
- Text mode: skips when DC never opens
- Text mode: sets ConversationStage.TRIAGE before polling
- Text mode: calls get_greeting_audio with manage_stage=False
- Text mode: does NOT consume the audio stream (no TTS)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from ai_assistant.services.greeting_coordinator import GreetingCoordinator
from ai_assistant.services.session_mode import SessionMode
from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState
from ai_assistant.services.conversation_service import ConversationStage


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _two_chunks():
    yield b"chunk1"
    yield b"chunk2"


def _make_coordinator(
    fsm_state: AgentRuntimeState = AgentRuntimeState.LISTENING,
    dc_open: bool = True,
) -> tuple:
    """Return (coordinator, ai_mock, dc_mock, output_track_mock, speaking_log, interrupt_event)."""
    ai = Mock()
    ai.get_greeting_audio = AsyncMock(return_value=("Hello!", _two_chunks()))
    ai.conversation_service = Mock()

    dc = Mock()
    dc.is_open = dc_open
    dc.send_chat = Mock()

    fsm = Mock()
    fsm.current_state = fsm_state

    output_track = Mock()
    output_track.queue_audio = AsyncMock()

    speaking_log: list[bool] = []
    interrupt_event = asyncio.Event()

    coord = GreetingCoordinator(
        ai_assistant=ai,
        dc_bridge=dc,
        fsm=fsm,
        output_track=output_track,
        user_id="user-1",
        connection_id="conn-1",
        interrupt_event=interrupt_event,
        on_speaking_change=lambda v: speaking_log.append(v),
    )
    return coord, ai, dc, output_track, speaking_log, interrupt_event


# ══════════════════════════════════════════════════════════════════════════════
# Initialisation
# ══════════════════════════════════════════════════════════════════════════════

class TestGreetingCoordinatorInit:

    def test_greeting_sent_false_initially(self):
        coord, *_ = _make_coordinator()
        assert coord.greeting_sent is False


# ══════════════════════════════════════════════════════════════════════════════
# Voice mode
# ══════════════════════════════════════════════════════════════════════════════

class TestGreetingCoordinatorVoice:

    async def test_sends_chat_message(self):
        coord, ai, dc, *_ = _make_coordinator()
        await coord.send(SessionMode.VOICE)
        dc.send_chat.assert_called_once_with("Hello!", is_user=False, is_chunk=False)

    async def test_marks_greeting_sent(self):
        coord, *_ = _make_coordinator()
        await coord.send(SessionMode.VOICE)
        assert coord.greeting_sent is True

    async def test_second_call_is_noop(self):
        coord, ai, dc, *_ = _make_coordinator()
        await coord.send(SessionMode.VOICE)
        dc.send_chat.reset_mock()
        await coord.send(SessionMode.VOICE)
        dc.send_chat.assert_not_called()

    async def test_speaking_true_during_audio_playback(self):
        coord, ai, dc, output_track, speaking_log, _ = _make_coordinator()
        states_during: list[bool] = []

        async def capture(chunk):
            states_during.append(speaking_log[-1] if speaking_log else None)

        output_track.queue_audio = AsyncMock(side_effect=capture)
        await coord.send(SessionMode.VOICE)
        assert all(s is True for s in states_during), (
            "on_speaking_change(True) must be called before queueing audio"
        )

    async def test_speaking_false_after_completion(self):
        coord, _, _, _, speaking_log, _ = _make_coordinator()
        await coord.send(SessionMode.VOICE)
        assert speaking_log[-1] is False

    async def test_speaking_false_on_exception(self):
        coord, ai, dc, output_track, speaking_log, _ = _make_coordinator()
        ai.get_greeting_audio = AsyncMock(side_effect=RuntimeError("TTS failed"))
        await coord.send(SessionMode.VOICE)  # must not raise
        assert speaking_log[-1] is False

    async def test_stops_streaming_on_interrupt(self):
        coord, ai, dc, output_track, _, interrupt_event = _make_coordinator()
        queued: list = []

        async def queue_and_interrupt(chunk):
            queued.append(chunk)
            if len(queued) == 1:
                interrupt_event.set()

        output_track.queue_audio = AsyncMock(side_effect=queue_and_interrupt)

        async def multi_chunk_audio():
            for i in range(5):
                yield f"chunk{i}".encode()
                await asyncio.sleep(0)

        ai.get_greeting_audio = AsyncMock(return_value=("Hi!", multi_chunk_audio()))
        await coord.send(SessionMode.VOICE)
        assert len(queued) < 5, "Streaming must stop early when interrupted"

    async def test_queues_audio_chunks_via_output_track(self):
        coord, _, _, output_track, _, _ = _make_coordinator()
        await coord.send(SessionMode.VOICE)
        assert output_track.queue_audio.call_count == 2  # two chunks in _two_chunks()


# ══════════════════════════════════════════════════════════════════════════════
# Text mode
# ══════════════════════════════════════════════════════════════════════════════

class TestGreetingCoordinatorText:

    async def test_sends_greeting_when_dc_open_and_listening(self):
        coord, ai, dc, *_ = _make_coordinator(
            fsm_state=AgentRuntimeState.LISTENING, dc_open=True
        )
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        dc.send_chat.assert_called_once_with("Hello!", is_user=False, is_chunk=False)

    async def test_marks_greeting_sent(self):
        coord, ai, dc, *_ = _make_coordinator(fsm_state=AgentRuntimeState.LISTENING)
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        assert coord.greeting_sent is True

    async def test_skips_when_fsm_not_listening(self):
        coord, ai, dc, *_ = _make_coordinator(fsm_state=AgentRuntimeState.THINKING)
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        dc.send_chat.assert_not_called()

    async def test_skips_when_dc_never_opens(self):
        coord, ai, dc, *_ = _make_coordinator()
        coord._wait_for_dc_open = AsyncMock(return_value=False)
        await coord.send(SessionMode.TEXT)
        ai.get_greeting_audio.assert_not_called()
        dc.send_chat.assert_not_called()

    async def test_sets_triage_stage_before_polling(self):
        coord, ai, dc, *_ = _make_coordinator()
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        ai.conversation_service.set_stage.assert_called_with(ConversationStage.TRIAGE)

    async def test_calls_get_greeting_audio_with_manage_stage_false(self):
        coord, ai, dc, *_ = _make_coordinator(fsm_state=AgentRuntimeState.LISTENING)
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        ai.get_greeting_audio.assert_called_once_with(user_id="user-1", manage_stage=False)

    async def test_does_not_consume_audio_stream(self):
        coord, ai, dc, *_ = _make_coordinator(fsm_state=AgentRuntimeState.LISTENING)
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        consumed: list = []

        async def tracking_audio():
            consumed.append(True)
            yield b"audio"

        ai.get_greeting_audio = AsyncMock(return_value=("Hi!", tracking_audio()))
        await coord.send(SessionMode.TEXT)
        assert len(consumed) == 0, "Text mode must discard the audio stream"

    async def test_second_call_is_noop(self):
        coord, ai, dc, *_ = _make_coordinator(fsm_state=AgentRuntimeState.LISTENING)
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        ai.get_greeting_audio.reset_mock()
        await coord.send(SessionMode.TEXT)
        ai.get_greeting_audio.assert_not_called()

    async def test_does_not_set_is_ai_speaking(self):
        """Text mode must never call on_speaking_change — no TTS involved."""
        coord, ai, dc, _, speaking_log, _ = _make_coordinator(
            fsm_state=AgentRuntimeState.LISTENING
        )
        coord._wait_for_dc_open = AsyncMock(return_value=True)
        await coord.send(SessionMode.TEXT)
        assert speaking_log == [], (
            "on_speaking_change must not be called in text mode"
        )
