"""Tests for WebSocketBridge."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from ai_assistant.services.ws_bridge import WebSocketBridge
from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_ws():
    """Return a mock WebSocketResponse that is open."""
    ws = Mock()
    ws.closed = False
    sent = []

    async def _send_json(payload):
        sent.append(payload)

    ws.send_json = _send_json
    return ws, sent


def _closed_ws():
    ws = Mock()
    ws.closed = True
    ws.send_json = AsyncMock()
    return ws


# ── is_open ───────────────────────────────────────────────────────────────────

class TestWebSocketBridgeIsOpen:

    def test_true_when_ws_open(self):
        ws, _ = _open_ws()
        assert WebSocketBridge(ws).is_open is True

    def test_false_when_ws_closed(self):
        ws = _closed_ws()
        assert WebSocketBridge(ws).is_open is False

    def test_reflects_ws_state_dynamically(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        assert bridge.is_open is True
        ws.closed = True
        assert bridge.is_open is False


# ── send helpers (enqueue only — sender task not started) ─────────────────────

class TestWebSocketBridgeSendEnqueue:

    def test_send_chat_enqueues_when_open(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.send_chat("hello", is_user=True)
        assert bridge._queue.qsize() == 1
        item = bridge._queue.get_nowait()
        assert item == {"type": "chat", "text": "hello", "isUser": True, "isChunk": False}

    def test_send_chat_chunk_flag(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.send_chat("part", is_user=False, is_chunk=True)
        item = bridge._queue.get_nowait()
        assert item["isChunk"] is True

    def test_send_chat_no_op_when_closed(self):
        bridge = WebSocketBridge(_closed_ws())
        bridge.send_chat("hello", is_user=True)
        assert bridge._queue.empty()

    def test_send_runtime_state_shape(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.send_runtime_state(AgentRuntimeState.LISTENING)
        item = bridge._queue.get_nowait()
        assert item == {"type": "runtime-state", "runtimeState": "listening"}

    def test_send_runtime_state_no_op_when_closed(self):
        bridge = WebSocketBridge(_closed_ws())
        bridge.send_runtime_state(AgentRuntimeState.LISTENING)
        assert bridge._queue.empty()

    def test_send_provider_cards_shape(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        cards = [{"id": "p1", "name": "Alice"}]
        bridge.send_provider_cards(cards)
        item = bridge._queue.get_nowait()
        assert item == {"type": "provider-cards", "cards": cards}

    def test_send_provider_cards_no_op_when_empty(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.send_provider_cards([])
        assert bridge._queue.empty()

    def test_send_provider_cards_no_op_when_closed(self):
        bridge = WebSocketBridge(_closed_ws())
        bridge.send_provider_cards([{"id": "p1"}])
        assert bridge._queue.empty()


# ── sender task — end-to-end delivery ────────────────────────────────────────

class TestWebSocketBridgeSenderTask:

    async def test_sender_delivers_queued_message(self):
        ws, sent = _open_ws()
        bridge = WebSocketBridge(ws)
        await bridge.start_sender()

        bridge.send_chat("hi", is_user=False)

        await bridge.stop_sender()
        assert len(sent) == 1
        assert sent[0]["text"] == "hi"

    async def test_sender_delivers_multiple_messages_in_order(self):
        ws, sent = _open_ws()
        bridge = WebSocketBridge(ws)
        await bridge.start_sender()

        bridge.send_chat("one", is_user=False)
        bridge.send_chat("two", is_user=False)
        bridge.send_runtime_state(AgentRuntimeState.THINKING)

        await bridge.stop_sender()
        assert len(sent) == 3
        assert sent[0]["text"] == "one"
        assert sent[1]["text"] == "two"
        assert sent[2]["type"] == "runtime-state"

    async def test_sender_skips_send_when_ws_closes_mid_run(self):
        ws, sent = _open_ws()
        bridge = WebSocketBridge(ws)
        await bridge.start_sender()

        bridge.send_chat("before close", is_user=False)
        await asyncio.sleep(0)   # let sender drain first message
        ws.closed = True          # simulate WS closing
        bridge.send_chat("after close", is_user=False)

        await bridge.stop_sender()
        # At most 1 message should have been delivered (the one before close).
        assert len(sent) <= 1

    async def test_stop_sender_is_idempotent(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        await bridge.start_sender()
        await bridge.stop_sender()
        await bridge.stop_sender()   # must not raise

    async def test_sender_swallows_send_errors(self):
        ws = Mock()
        ws.closed = False
        errors = []

        async def _bad_send(payload):
            errors.append(payload)
            raise OSError("network gone")

        ws.send_json = _bad_send

        bridge = WebSocketBridge(ws)
        await bridge.start_sender()
        bridge.send_chat("boom", is_user=False)
        await bridge.stop_sender()   # must not raise
        assert len(errors) == 1


# ── replay buffer ─────────────────────────────────────────────────────────────

class TestWebSocketBridgeReplayBuffer:

    def test_start_replay_capture_enables_buffering(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.start_replay_capture()
        assert bridge._buffering is True
        assert bridge._replay_buffer == []

    def test_assistant_chat_buffered_during_suspension(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.start_replay_capture()
        bridge.send_chat("missed reply", is_user=False)
        assert len(bridge._replay_buffer) == 1
        assert bridge._queue.empty()  # not enqueued in live queue

    def test_user_chat_not_buffered(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.start_replay_capture()
        bridge.send_chat("user msg", is_user=True)
        assert bridge._replay_buffer == []

    def test_provider_cards_buffered_during_suspension(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.start_replay_capture()
        bridge.send_provider_cards([{"id": "p1"}])
        assert len(bridge._replay_buffer) == 1

    def test_runtime_state_not_buffered(self):
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.start_replay_capture()
        bridge.send_runtime_state(AgentRuntimeState.LISTENING)
        # runtime-state is ephemeral — not replayable
        assert bridge._replay_buffer == []

    def test_buffer_cap_limits_frames(self):
        from ai_assistant.services.ws_bridge import _MAX_REPLAY_FRAMES
        ws, _ = _open_ws()
        bridge = WebSocketBridge(ws)
        bridge.start_replay_capture()
        for i in range(_MAX_REPLAY_FRAMES + 10):
            bridge.send_chat(f"chunk {i}", is_user=False)
        assert len(bridge._replay_buffer) == _MAX_REPLAY_FRAMES

    async def test_buffer_flushed_into_queue_on_replace_websocket(self):
        ws1, _ = _open_ws()
        bridge = WebSocketBridge(ws1)
        await bridge.start_sender()

        bridge.start_replay_capture()
        bridge.send_chat("missed", is_user=False)
        bridge.send_provider_cards([{"id": "p1"}])

        ws2, sent2 = _open_ws()
        await bridge.replace_websocket(ws2)
        await bridge.stop_sender()

        types = [f["type"] for f in sent2]
        assert "chat" in types
        assert "provider-cards" in types

    async def test_replace_websocket_clears_buffer_and_buffering_flag(self):
        ws1, _ = _open_ws()
        bridge = WebSocketBridge(ws1)
        await bridge.start_sender()

        bridge.start_replay_capture()
        bridge.send_chat("queued", is_user=False)

        ws2, _ = _open_ws()
        await bridge.replace_websocket(ws2)

        assert bridge._buffering is False
        assert bridge._replay_buffer == []
        await bridge.stop_sender()


# ── preamble ordering ─────────────────────────────────────────────────────────

class TestWebSocketBridgePreamble:

    async def test_preamble_frames_precede_replay_frames(self):
        ws1, _ = _open_ws()
        bridge = WebSocketBridge(ws1)
        await bridge.start_sender()

        bridge.start_replay_capture()
        bridge.send_chat("reply 1", is_user=False)
        bridge.send_chat("reply 2", is_user=False)

        ws2, sent2 = _open_ws()
        preamble = [{"type": "session-resumed"}, {"type": "runtime-state", "runtimeState": "listening"}]
        await bridge.replace_websocket(ws2, preamble=preamble)
        await bridge.stop_sender()

        assert sent2[0]["type"] == "session-resumed"
        assert sent2[1]["type"] == "runtime-state"
        assert sent2[2]["type"] == "chat"
        assert sent2[3]["type"] == "chat"

    async def test_replace_websocket_without_preamble_works(self):
        ws1, _ = _open_ws()
        bridge = WebSocketBridge(ws1)
        await bridge.start_sender()

        ws2, sent2 = _open_ws()
        await bridge.replace_websocket(ws2)
        await bridge.stop_sender()
        assert sent2 == []
