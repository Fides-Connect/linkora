"""
RED tests for PeerConnectionHandler refactoring.

Tests verify:
1. DataChannelMessageRouter wired in __init__
2. _on_dc_text_input / _on_dc_mode_switch extracted methods
3. handle_offer decomposed into _handle_initial_voice_offer,
   _handle_initial_text_offer, _handle_renegotiation_offer, _await_track_update
4. on_track flattened into _on_first_voice_track, _on_text_to_voice_upgrade,
   _on_track_replacement
5. session_mode stored as SessionMode enum
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from ai_assistant.peer_connection_handler import PeerConnectionHandler
from ai_assistant.services.data_channel_message_router import DataChannelMessageRouter
from ai_assistant.services.session_mode import SessionMode


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


def _make_handler(ws, mode: str = "voice") -> PeerConnectionHandler:
    with patch("ai_assistant.peer_connection_handler.RTCPeerConnection"):
        return PeerConnectionHandler(
            connection_id="test-pch",
            websocket=ws,
            user_id="u1",
            language="de",
            session_mode=mode,
        )


# ══════════════════════════════════════════════════════════════════════════════
# 1. DataChannelMessageRouter wiring
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelRouterWiring:
    """_dc_router is a DataChannelMessageRouter wired in __init__."""

    def test_dc_router_attribute_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert hasattr(handler, "_dc_router")

    def test_dc_router_is_correct_type(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert isinstance(handler._dc_router, DataChannelMessageRouter)

    def test_text_input_handler_registered(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert "text-input" in handler._dc_router._handlers

    def test_mode_switch_handler_registered(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert "mode-switch" in handler._dc_router._handlers


# ══════════════════════════════════════════════════════════════════════════════
# 2. Extracted DataChannel message handlers
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelMessageHandlers:
    """_on_dc_text_input and _on_dc_mode_switch are standalone methods."""

    def test_on_dc_text_input_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_on_dc_text_input", None))

    def test_on_dc_mode_switch_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_on_dc_mode_switch", None))

    def test_on_dc_text_input_dispatches(self, mock_ws):
        """_on_dc_text_input("hello") calls _dispatch_text_input."""
        handler = _make_handler(mock_ws)
        handler._dispatch_text_input = Mock()
        handler._on_dc_text_input({"type": "text-input", "text": "hello"})
        handler._dispatch_text_input.assert_called_once_with("hello")

    def test_on_dc_text_input_ignores_empty(self, mock_ws):
        handler = _make_handler(mock_ws)
        handler._dispatch_text_input = Mock()
        handler._on_dc_text_input({"type": "text-input", "text": "   "})
        handler._dispatch_text_input.assert_not_called()

    def test_on_dc_text_input_rejects_oversized(self, mock_ws):
        handler = _make_handler(mock_ws)
        handler._dispatch_text_input = Mock()
        handler._on_dc_text_input({"type": "text-input", "text": "x" * 10_001})
        handler._dispatch_text_input.assert_not_called()

    async def test_on_dc_mode_switch_to_text(self, mock_ws):
        handler = _make_handler(mock_ws)
        ap = AsyncMock()
        ap.session_mode = SessionMode.VOICE
        handler.audio_processor = ap
        handler._reset_idle_timer = Mock()

        handler._on_dc_mode_switch({"type": "mode-switch", "mode": "text"})

        # Should schedule a task — just assert the AP method will be called
        # (the task runs on the next event-loop tick)
        await asyncio.sleep(0)
        ap.disable_voice_mode.assert_called_once()

    async def test_on_dc_mode_switch_to_voice(self, mock_ws):
        handler = _make_handler(mock_ws)
        ap = AsyncMock()
        ap.session_mode = SessionMode.TEXT
        handler.audio_processor = ap
        handler._reset_idle_timer = Mock()

        handler._on_dc_mode_switch({"type": "mode-switch", "mode": "voice"})

        await asyncio.sleep(0)
        ap.enable_voice_mode.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 3. handle_offer decomposition
# ══════════════════════════════════════════════════════════════════════════════

class TestHandleOfferDecomposition:
    """handle_offer delegates to private helpers."""

    def test_handle_initial_voice_offer_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_handle_initial_voice_offer", None))

    def test_handle_initial_text_offer_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_handle_initial_text_offer", None))

    def test_handle_renegotiation_offer_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_handle_renegotiation_offer", None))

    def test_await_track_update_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_await_track_update", None))

    async def test_handle_offer_routes_to_text_helper(self, mock_ws):
        """Initial text offer routes to _handle_initial_text_offer."""
        handler = _make_handler(mock_ws, mode="text")
        offer = MagicMock()
        handler._handle_initial_text_offer = AsyncMock()

        with patch.object(handler.pc, "setRemoteDescription", AsyncMock()):
            await handler.handle_offer(offer)

        handler._handle_initial_text_offer.assert_awaited_once()

    async def test_handle_offer_routes_to_renegotiation_helper(self, mock_ws):
        """Renegotiation offer (audio_processor already set) routes to _handle_renegotiation_offer."""
        handler = _make_handler(mock_ws, mode="voice")
        ap = AsyncMock()
        ap.session_mode = SessionMode.VOICE
        handler.audio_processor = ap

        offer = MagicMock()
        handler._handle_renegotiation_offer = AsyncMock()
        handler._handle_initial_voice_offer = AsyncMock()

        with patch.object(handler.pc, "setRemoteDescription", AsyncMock()):
            await handler.handle_offer(offer)

        handler._handle_renegotiation_offer.assert_awaited_once()
        handler._handle_initial_voice_offer.assert_not_awaited()


# ══════════════════════════════════════════════════════════════════════════════
# 4. on_track flattening
# ══════════════════════════════════════════════════════════════════════════════

class TestOnTrackFlattening:
    """on_track delegates to _on_first_voice_track / _on_text_to_voice_upgrade / _on_track_replacement."""

    def test_on_first_voice_track_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_on_first_voice_track", None))

    def test_on_text_to_voice_upgrade_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_on_text_to_voice_upgrade", None))

    def test_on_track_replacement_method_exists(self, mock_ws):
        handler = _make_handler(mock_ws)
        assert callable(getattr(handler, "_on_track_replacement", None))


# ══════════════════════════════════════════════════════════════════════════════
# 5. SessionMode enum stored on handler
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionModeEnum:
    """session_mode is stored as a SessionMode enum instance."""

    def test_voice_mode_stored_as_enum(self, mock_ws):
        handler = _make_handler(mock_ws, mode="voice")
        assert handler.session_mode == SessionMode.VOICE

    def test_text_mode_stored_as_enum(self, mock_ws):
        handler = _make_handler(mock_ws, mode="text")
        assert handler.session_mode == SessionMode.TEXT

    def test_session_mode_is_session_mode_type(self, mock_ws):
        handler = _make_handler(mock_ws, mode="voice")
        assert isinstance(handler.session_mode, SessionMode)

    def test_session_mode_still_compares_equal_to_string(self, mock_ws):
        """SessionMode(str, Enum) backward compat: == 'voice' must still work."""
        handler = _make_handler(mock_ws, mode="voice")
        assert handler.session_mode == "voice"
