"""Tests for ChatConnectionHandler."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch

from ai_assistant.chat_connection_handler import ChatConnectionHandler


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_ws():
    ws = Mock()
    ws.closed = False
    sent = []

    async def _send_json(payload):
        sent.append(payload)

    async def _close(*args, **kwargs):
        ws.closed = True

    ws.send_json = _send_json
    ws.close = _close
    return ws, sent


def _make_handler(ws=None):
    if ws is None:
        ws, _ = _open_ws()
    return ChatConnectionHandler(
        connection_id="test-conn-1",
        websocket=ws,
        user_id="user-abc",
        language="en",
    )


# ── Input validation ──────────────────────────────────────────────────────────

class TestChatConnectionHandlerInputValidation:

    def test_empty_text_ignored(self, caplog):
        handler = _make_handler()
        handler.handle_text_input("   ")
        assert handler._pending_text_inputs == []

    def test_oversized_input_rejected(self, caplog):
        handler = _make_handler()
        handler.handle_text_input("x" * 10_001)
        assert handler._pending_text_inputs == []

    def test_valid_input_buffered_before_start(self):
        handler = _make_handler()
        handler.handle_text_input("hello world")
        assert handler._pending_text_inputs == ["hello world"]

    def test_max_allowed_input_accepted(self):
        handler = _make_handler()
        handler.handle_text_input("a" * 10_000)
        assert len(handler._pending_text_inputs) == 1


# ── Idle timer ────────────────────────────────────────────────────────────────

class TestChatConnectionHandlerIdleTimer:

    async def test_idle_timer_resets_on_activity(self):
        handler = _make_handler()
        handler._reset_idle_timer()
        first_task = handler._idle_task

        handler._reset_idle_timer()
        second_task = handler._idle_task

        assert first_task is not second_task
        # Give the event loop a tick so the cancel propagates.
        await asyncio.sleep(0)
        assert first_task.cancelled() or first_task.done()
        second_task.cancel()

    async def test_idle_timeout_closes_handler(self):
        handler = _make_handler()
        closed_called = asyncio.Event()

        original_close = handler.close

        async def _mock_close():
            closed_called.set()
            await original_close()

        handler.close = _mock_close

        # Override with a fast-expiring timer for testing
        if handler._idle_task and not handler._idle_task.done():
            handler._idle_task.cancel()

        async def _fast_timeout():
            try:
                await asyncio.sleep(0.01)
                await handler.close()
            except asyncio.CancelledError:
                pass

        handler._idle_task = asyncio.create_task(_fast_timeout())
        await asyncio.wait_for(closed_called.wait(), timeout=1.0)
        assert handler._closed


# ── close() idempotency ───────────────────────────────────────────────────────

class TestChatConnectionHandlerClose:

    async def test_close_is_idempotent(self):
        handler = _make_handler()
        await handler.close()
        await handler.close()   # must not raise

    async def test_close_cancels_idle_task(self):
        handler = _make_handler()
        handler._reset_idle_timer()
        task = handler._idle_task

        await handler.close()
        assert task is None or task.done() or task.cancelled()


# ── start() integration (AudioProcessor mocked) ───────────────────────────────

class TestChatConnectionHandlerStart:

    async def test_start_creates_audio_processor_and_wires_bridge(self):
        ws, sent = _open_ws()
        handler = _make_handler(ws)

        mock_ap = MagicMock()
        mock_ap.start = AsyncMock()
        mock_ap.stop = AsyncMock()
        mock_ap.set_chat_bridge = Mock()
        mock_ap.on_activity = None

        # Stub FSM wiring path
        mock_fsm = Mock()
        mock_ap.ai_assistant.response_orchestrator.runtime_fsm = mock_fsm

        with patch(
            "ai_assistant.chat_connection_handler.AudioProcessor",
            return_value=mock_ap,
        ):
            await handler.start()

        mock_ap.set_chat_bridge.assert_called_once_with(handler.ws_bridge)
        mock_ap.start.assert_called_once()
        assert handler.audio_processor is mock_ap

    async def test_pending_inputs_flushed_on_start(self):
        ws, _ = _open_ws()
        handler = _make_handler(ws)
        handler._pending_text_inputs.append("pre-start message")

        mock_ap = MagicMock()
        mock_ap.start = AsyncMock()
        mock_ap.stop = AsyncMock()
        mock_ap.set_chat_bridge = Mock()
        mock_ap.on_activity = None
        mock_ap.receive_text_input = AsyncMock()

        mock_fsm = Mock()
        mock_ap.ai_assistant.response_orchestrator.runtime_fsm = mock_fsm

        with patch(
            "ai_assistant.chat_connection_handler.AudioProcessor",
            return_value=mock_ap,
        ):
            await handler.start()

        # Pending input should have been dispatched
        assert handler._pending_text_inputs == []

    async def test_dispatch_to_processor_after_start(self):
        ws, _ = _open_ws()
        handler = _make_handler(ws)

        mock_ap = MagicMock()
        mock_ap.start = AsyncMock()
        mock_ap.stop = AsyncMock()
        mock_ap.set_chat_bridge = Mock()
        mock_ap.on_activity = None
        mock_ap.receive_text_input = AsyncMock()

        mock_fsm = Mock()
        mock_ap.ai_assistant.response_orchestrator.runtime_fsm = mock_fsm

        with patch(
            "ai_assistant.chat_connection_handler.AudioProcessor",
            return_value=mock_ap,
        ):
            await handler.start()

        handler.handle_text_input("hello after start")
        await asyncio.sleep(0)  # allow create_task to fire

        mock_ap.receive_text_input.assert_called_once_with("hello after start")


# ── is_closed property ────────────────────────────────────────────────────────

class TestChatConnectionHandlerIsClosed:

    async def test_is_closed_false_before_close(self):
        handler = _make_handler()
        assert handler.is_closed is False

    async def test_is_closed_true_after_close(self):
        handler = _make_handler()
        await handler.close()
        assert handler.is_closed is True

    async def test_is_closed_idempotent(self):
        handler = _make_handler()
        await handler.close()
        await handler.close()
        assert handler.is_closed is True


# ── suspend() ─────────────────────────────────────────────────────────────────

class TestChatConnectionHandlerSuspend:

    async def test_suspend_stops_sender_without_closing_handler(self):
        ws, _ = _open_ws()
        handler = _make_handler(ws)

        mock_ap = MagicMock()
        mock_ap.start = AsyncMock()
        mock_ap.stop = AsyncMock()
        mock_ap.set_chat_bridge = Mock()
        mock_ap.on_activity = None
        mock_fsm = Mock()
        mock_ap.ai_assistant.response_orchestrator.runtime_fsm = mock_fsm

        with patch("ai_assistant.chat_connection_handler.AudioProcessor", return_value=mock_ap):
            await handler.start()

        await handler.suspend()

        # Handler must NOT be marked closed — it can still be resumed.
        assert handler.is_closed is False
        # AudioProcessor must still be present.
        assert handler.audio_processor is not None


# ── resume() ──────────────────────────────────────────────────────────────────

class TestChatConnectionHandlerResume:

    def _make_started_handler(self):
        """Return a handler whose AudioProcessor is mocked."""
        ws, sent = _open_ws()
        handler = _make_handler(ws)

        mock_ap = MagicMock()
        mock_ap.stop = AsyncMock()
        mock_ap.set_chat_bridge = Mock()
        mock_ap.on_activity = None

        mock_fsm = Mock()
        mock_fsm.current_state.value = "listening"
        mock_ap.ai_assistant.response_orchestrator.runtime_fsm = mock_fsm

        handler.audio_processor = mock_ap
        return handler, sent

    async def test_resume_sends_preamble_before_replay(self):
        handler, _ = self._make_started_handler()

        # Simulate a suspended session with a buffered reply.
        handler.ws_bridge.start_replay_capture()
        handler.ws_bridge.send_chat("missed message", is_user=False)

        ws2, sent2 = _open_ws()
        await handler.ws_bridge.start_sender()
        await handler.resume(ws2)
        await handler.ws_bridge.stop_sender()

        types = [f["type"] for f in sent2]
        # session-resumed must come first, then runtime-state, then chat.
        assert types.index("session-resumed") < types.index("chat")
        assert types.index("runtime-state") < types.index("chat")
