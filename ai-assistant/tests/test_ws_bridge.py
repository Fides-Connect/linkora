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
