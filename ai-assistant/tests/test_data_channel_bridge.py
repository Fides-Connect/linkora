"""Tests for DataChannelBridge — RED phase."""
import json
import pytest
from unittest.mock import Mock

from ai_assistant.services.data_channel_bridge import DataChannelBridge
from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_dc():
    dc = Mock()
    dc.readyState = "open"
    sent = []
    dc.send = Mock(side_effect=lambda m: sent.append(m))
    return dc, sent


def _closed_dc():
    dc = Mock()
    dc.readyState = "closed"
    dc.send = Mock()
    return dc


# ══════════════════════════════════════════════════════════════════════════════
# is_open
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelBridgeIsOpen:

    def test_false_before_attach(self):
        assert not DataChannelBridge().is_open

    def test_true_when_open_channel_attached(self):
        dc, _ = _open_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc)
        assert bridge.is_open

    def test_false_when_closed_channel_attached(self):
        bridge = DataChannelBridge()
        bridge.attach(_closed_dc())
        assert not bridge.is_open

    def test_reattach_replaces_old_channel(self):
        dc1, sent1 = _open_dc()
        dc2, sent2 = _open_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc1)
        bridge.attach(dc2)
        bridge.send_chat("test", is_user=False)
        assert len(sent1) == 0
        assert len(sent2) == 1


# ══════════════════════════════════════════════════════════════════════════════
# send_chat
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelBridgeSendChat:

    def test_user_message_shape(self):
        dc, sent = _open_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_chat("hello", is_user=True)
        assert len(sent) == 1
        msg = json.loads(sent[0])
        assert msg["type"] == "chat"
        assert msg["text"] == "hello"
        assert msg["isUser"] is True
        assert msg["isChunk"] is False

    def test_ai_chunk_shape(self):
        dc, sent = _open_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_chat("partial", is_user=False, is_chunk=True)
        msg = json.loads(sent[0])
        assert msg["isUser"] is False
        assert msg["isChunk"] is True

    def test_no_channel_does_not_raise(self):
        DataChannelBridge().send_chat("hello", is_user=True)

    def test_closed_channel_does_not_send(self):
        dc = _closed_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_chat("hello", is_user=True)
        dc.send.assert_not_called()

    def test_send_error_is_swallowed(self):
        dc = Mock()
        dc.readyState = "open"
        dc.send = Mock(side_effect=Exception("network error"))
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_chat("test", is_user=False)  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# send_runtime_state
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelBridgeSendRuntimeState:

    def test_message_shape(self):
        dc, sent = _open_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_runtime_state(AgentRuntimeState.LISTENING)
        assert len(sent) == 1
        msg = json.loads(sent[0])
        assert msg["type"] == "runtime-state"
        assert msg["runtimeState"] == "listening"

    def test_no_channel_does_not_raise(self):
        DataChannelBridge().send_runtime_state(AgentRuntimeState.THINKING)

    def test_closed_channel_does_not_send(self):
        dc = _closed_dc()
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_runtime_state(AgentRuntimeState.THINKING)
        dc.send.assert_not_called()

    def test_send_error_is_swallowed(self):
        dc = Mock()
        dc.readyState = "open"
        dc.send = Mock(side_effect=Exception("error"))
        bridge = DataChannelBridge()
        bridge.attach(dc)
        bridge.send_runtime_state(AgentRuntimeState.LISTENING)  # must not raise
