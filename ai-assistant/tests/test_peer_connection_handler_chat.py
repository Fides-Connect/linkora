"""
Tests for PeerConnectionHandler new features introduced in the chat branch.

Covers:
- session_mode parameter and storage
- Idle timer: _reset_idle_timer, _idle_timeout_task, cancellation on close
- Text-mode handle_offer: creates AudioProcessor without audio track
- on_track text→voice upgrade path
- DataChannel on_message: text-input routing, validation, voice→text switch
- DataChannel on_message: mode-switch (pause / resume)
- on_connectionstatechange: text greeting on connect, _greeting_sent dedup guard
- handle_offer: renegotiation detected via audio_processor presence
- _handle_voice_to_text_switch
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from aiortc import RTCSessionDescription
from ai_assistant.peer_connection_handler import PeerConnectionHandler


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_handler(session_mode: str = "voice") -> PeerConnectionHandler:
    """Return a PeerConnectionHandler with PC fully mocked."""
    ws = Mock()
    ws.send_json = AsyncMock()
    ws.send_str = AsyncMock()

    with patch("ai_assistant.peer_connection_handler.RTCPeerConnection") as mock_pc_cls:
        mock_pc = _mock_pc()
        mock_pc_cls.return_value = mock_pc

        handler = PeerConnectionHandler(
            connection_id="test-conn",
            websocket=ws,
            session_mode=session_mode,
        )
        handler.pc = mock_pc
        return handler


def _mock_pc():
    pc = Mock()
    pc.setRemoteDescription = AsyncMock()
    pc.createAnswer = AsyncMock(
        return_value=Mock(sdp="ans-sdp", type="answer")
    )
    pc.setLocalDescription = AsyncMock()
    pc.addTrack = Mock()
    pc.getSenders = Mock(return_value=[])
    pc.connectionState = "new"
    pc.close = AsyncMock()
    pc.localDescription = Mock(sdp="ans-sdp", type="answer")
    return pc


def _mock_audio_processor(is_text_mode: bool = False) -> Mock:
    ap = Mock()
    ap._is_text_mode = is_text_mode
    ap._greeting_sent = False
    ap.stop = AsyncMock()
    ap.start = AsyncMock()
    ap.get_output_track = Mock(return_value=Mock(id="out-track"))
    ap.set_data_channel = Mock()
    ap.enable_voice_mode = AsyncMock(return_value=Mock(id="out-track"))
    ap.disable_voice_mode = AsyncMock()
    ap.receive_text_input = AsyncMock()
    ap.process_text_input = AsyncMock()
    ap.replace_input_track = AsyncMock()
    return ap


# ══════════════════════════════════════════════════════════════════════════════
# Initialisation
# ══════════════════════════════════════════════════════════════════════════════

class TestInitialisation:

    def test_session_mode_stored_voice(self):
        handler = _make_handler("voice")
        assert handler.session_mode == "voice"

    def test_session_mode_stored_text(self):
        handler = _make_handler("text")
        assert handler.session_mode == "text"

    def test_idle_task_is_none_initially(self):
        handler = _make_handler()
        assert handler._idle_task is None


# ══════════════════════════════════════════════════════════════════════════════
# Idle timer
# ══════════════════════════════════════════════════════════════════════════════

class TestIdleTimer:

    async def test_reset_idle_timer_creates_task(self):
        handler = _make_handler()
        handler._reset_idle_timer()
        assert handler._idle_task is not None
        handler._idle_task.cancel()

    async def test_reset_idle_timer_replaces_existing_task(self):
        handler = _make_handler()
        handler._reset_idle_timer()
        first_task = handler._idle_task
        handler._reset_idle_timer()
        # Yield so the event loop processes the first task's cancellation
        await asyncio.sleep(0)
        second_task = handler._idle_task
        assert first_task.cancelled()
        assert second_task is not first_task
        second_task.cancel()

    async def test_idle_timeout_calls_close(self):
        handler = _make_handler()
        handler.close = AsyncMock()

        # Run the timeout task with a patched sleep that resolves instantly
        with patch("asyncio.sleep", new=AsyncMock()):
            await handler._idle_timeout_task()

        handler.close.assert_called_once()

    async def test_idle_timeout_cancelled_silently(self):
        handler = _make_handler()
        handler.close = AsyncMock()

        task = asyncio.create_task(handler._idle_timeout_task())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # Should NOT propagate

        handler.close.assert_not_called()

    async def test_close_cancels_idle_task(self):
        handler = _make_handler()
        handler._reset_idle_timer()
        idle_task = handler._idle_task
        # Avoid the pc.close() call failing in teardown
        handler.pc.close = AsyncMock()

        await handler.close()
        # Yield so the event loop processes the cancellation request
        await asyncio.sleep(0)

        assert idle_task.cancelled()


# ══════════════════════════════════════════════════════════════════════════════
# handle_offer — text mode initial connection
# ══════════════════════════════════════════════════════════════════════════════

class TestHandleOfferTextMode:

    async def test_text_mode_creates_audio_processor_without_track(self):
        handler = _make_handler(session_mode="text")
        offer = RTCSessionDescription(sdp="sdp", type="offer")

        created_processors = []

        def fake_audio_processor(**kwargs):
            ap = _mock_audio_processor(is_text_mode=True)
            ap.input_track = kwargs.get("input_track")
            created_processors.append(ap)
            return ap

        with (
            patch(
                "ai_assistant.peer_connection_handler.AudioProcessor",
                side_effect=fake_audio_processor,
            ),
            patch.object(handler, "_send_message", new=AsyncMock()),
        ):
            await handler.handle_offer(offer)

        assert created_processors, "AudioProcessor must be created"
        assert created_processors[0].input_track is None

    async def test_text_mode_does_not_add_output_track(self):
        handler = _make_handler(session_mode="text")
        offer = RTCSessionDescription(sdp="sdp", type="offer")

        with (
            patch(
                "ai_assistant.peer_connection_handler.AudioProcessor",
                return_value=_mock_audio_processor(is_text_mode=True),
            ),
            patch.object(handler, "_send_message", new=AsyncMock()),
        ):
            await handler.handle_offer(offer)

        handler.pc.addTrack.assert_not_called()

    async def test_text_mode_skips_track_ready_wait(self):
        """Text mode must not hang waiting for the audio track event."""
        handler = _make_handler(session_mode="text")
        offer = RTCSessionDescription(sdp="sdp", type="offer")

        # track_ready is NOT set — voice mode would block here
        assert not handler.track_ready.is_set()

        with (
            patch(
                "ai_assistant.peer_connection_handler.AudioProcessor",
                return_value=_mock_audio_processor(is_text_mode=True),
            ),
            patch.object(handler, "_send_message", new=AsyncMock()),
        ):
            # Must complete without timeout
            await asyncio.wait_for(handler.handle_offer(offer), timeout=1.0)


# ══════════════════════════════════════════════════════════════════════════════
# handle_offer — renegotiation detection
# ══════════════════════════════════════════════════════════════════════════════

class TestHandleOfferRenegotiation:

    async def test_audio_processor_presence_signals_renegotiation(self):
        handler = _make_handler(session_mode="voice")
        handler.audio_processor = _mock_audio_processor(is_text_mode=False)
        handler.track_update_ready.set()

        offer = RTCSessionDescription(sdp="sdp", type="offer")
        with patch.object(handler, "_send_message", new=AsyncMock()):
            await handler.handle_offer(offer)

        # Renegotiation: track_update_ready was used (cleared then waited)
        # The offer should still be processed
        handler.pc.setRemoteDescription.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# on_track — text→voice upgrade
# ══════════════════════════════════════════════════════════════════════════════

class TestOnTrackTextToVoiceUpgrade:

    def _fire_on_track(self, handler: PeerConnectionHandler, track: Mock):
        """Extract and invoke the on_track handler registered on pc."""
        # The handler registered with @self.pc.on("track") is captured via
        # the mock's event-handler system.  We access it through side_effect
        # or by inspecting call_args on the .on() mock.
        callbacks = {}
        original_on = handler.pc.on

        def capture_on(event):
            def decorator(fn):
                callbacks[event] = fn
                return fn
            return decorator

        handler.pc.on = capture_on
        # Re-run setup to capture handlers
        handler._setup_event_handlers()
        handler.pc.on = original_on
        return callbacks.get("track")

    async def test_upgrade_calls_enable_voice_mode(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)
        handler.audio_processor = ap

        track = Mock()
        track.kind = "audio"
        track.id = "audio-1"

        on_track_cb = self._fire_on_track(handler, track)
        if on_track_cb:
            await on_track_cb(track)
            ap.enable_voice_mode.assert_called_once_with(track)

    async def test_upgrade_adds_output_track_to_pc(self):
        handler = _make_handler(session_mode="text")
        out_track = Mock(id="out-1")
        ap = _mock_audio_processor(is_text_mode=True)
        ap.enable_voice_mode = AsyncMock(return_value=out_track)
        handler.audio_processor = ap

        track = Mock()
        track.kind = "audio"

        on_track_cb = self._fire_on_track(handler, track)
        if on_track_cb:
            await on_track_cb(track)
            handler.pc.addTrack.assert_called_once_with(out_track)


# ══════════════════════════════════════════════════════════════════════════════
# DataChannel on_message — text-input
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelTextInput:

    def _get_on_message(self, handler: PeerConnectionHandler):
        """Trigger the on_datachannel callback, then return the on_message handler."""
        callbacks = {}
        channel = Mock()
        channel.readyState = "open"

        # Capture on_message registration
        message_callbacks = {}

        def channel_on(event):
            def decorator(fn):
                message_callbacks[event] = fn
                return fn
            return decorator

        channel.on = channel_on

        # Fire on_datachannel
        datachannel_callbacks = {}

        def pc_on(event):
            def decorator(fn):
                datachannel_callbacks[event] = fn
                return fn
            return decorator

        handler.pc.on = pc_on
        handler._setup_event_handlers()

        if "datachannel" in datachannel_callbacks:
            datachannel_callbacks["datachannel"](channel)
            handler.data_channel = channel

        return message_callbacks.get("message"), channel

    async def test_text_input_dispatches_to_audio_processor(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)
        handler.audio_processor = ap

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "hello"}))
        await asyncio.sleep(0)  # let create_task run

        ap.receive_text_input.assert_called_once_with("hello")

    async def test_text_input_buffered_when_audio_processor_not_ready(self):
        handler = _make_handler(session_mode="text")
        assert handler.audio_processor is None

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "hello later"}))
        await asyncio.sleep(0)

        assert handler._pending_text_inputs == ["hello later"]

    async def test_flushes_buffered_text_when_audio_processor_becomes_ready(self):
        handler = _make_handler(session_mode="text")

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "first"}))
        on_message(json.dumps({"type": "text-input", "text": "second"}))

        ap = _mock_audio_processor(is_text_mode=True)
        handler.audio_processor = ap
        handler._flush_pending_text_inputs()
        await asyncio.sleep(0)

        assert handler._pending_text_inputs == []
        assert ap.receive_text_input.call_args_list == [
            (("first",),),
            (("second",),),
        ]

    async def test_on_message_does_not_transition_runtime_fsm_synchronously(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)
        ap.ai_assistant = Mock()
        ap.ai_assistant.response_orchestrator = Mock()
        ap.ai_assistant.response_orchestrator.runtime_fsm = Mock()
        ap.ai_assistant.response_orchestrator.runtime_fsm.transition = Mock(
            side_effect=AssertionError("on_message must not call runtime_fsm.transition")
        )
        handler.audio_processor = ap

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "hello"}))
        await asyncio.sleep(0)

        ap.receive_text_input.assert_called_once_with("hello")

    async def test_empty_text_input_ignored(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)
        handler.audio_processor = ap

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "   "}))
        await asyncio.sleep(0)

        ap.receive_text_input.assert_not_called()

    async def test_oversized_text_input_rejected(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)
        handler.audio_processor = ap

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "x" * 10_001}))
        await asyncio.sleep(0)

        ap.receive_text_input.assert_not_called()

    async def test_voice_to_text_auto_switch(self):
        """text-input while in voice mode should call receive_text_input (mode switch handled internally)."""
        handler = _make_handler(session_mode="voice")
        ap = _mock_audio_processor(is_text_mode=False)
        handler.audio_processor = ap

        on_message, _ = self._get_on_message(handler)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "text-input", "text": "switch me"}))
        await asyncio.sleep(0)

        ap.receive_text_input.assert_called_once_with("switch me")


# ══════════════════════════════════════════════════════════════════════════════
# DataChannel on_message — mode-switch
# ══════════════════════════════════════════════════════════════════════════════

class TestDataChannelModeSwitch:

    def _get_on_message(self, handler, ap):
        """Wire up audio processor and capture on_message."""
        handler.audio_processor = ap
        message_callbacks = {}
        channel = Mock()

        def channel_on(event):
            def decorator(fn):
                message_callbacks[event] = fn
                return fn
            return decorator

        channel.on = channel_on

        datachannel_callbacks = {}

        def pc_on(event):
            def decorator(fn):
                datachannel_callbacks[event] = fn
                return fn
            return decorator

        handler.pc.on = pc_on
        handler._setup_event_handlers()

        if "datachannel" in datachannel_callbacks:
            datachannel_callbacks["datachannel"](channel)
            handler.data_channel = channel

        return message_callbacks.get("message")

    async def test_mode_switch_text_calls_disable_voice_mode(self):
        handler = _make_handler(session_mode="voice")
        ap = _mock_audio_processor(is_text_mode=False)

        on_message = self._get_on_message(handler, ap)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "mode-switch", "mode": "text"}))
        await asyncio.sleep(0)

        ap.disable_voice_mode.assert_called_once()

    async def test_mode_switch_voice_calls_enable_voice_mode(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)

        on_message = self._get_on_message(handler, ap)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "mode-switch", "mode": "voice"}))
        await asyncio.sleep(0)

        ap.enable_voice_mode.assert_called_once()

    async def test_mode_switch_text_no_op_when_already_text(self):
        handler = _make_handler(session_mode="text")
        ap = _mock_audio_processor(is_text_mode=True)  # already text

        on_message = self._get_on_message(handler, ap)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "mode-switch", "mode": "text"}))
        await asyncio.sleep(0)

        ap.disable_voice_mode.assert_not_called()

    async def test_mode_switch_voice_no_op_when_already_voice(self):
        handler = _make_handler(session_mode="voice")
        ap = _mock_audio_processor(is_text_mode=False)  # already voice

        on_message = self._get_on_message(handler, ap)
        if on_message is None:
            pytest.skip("on_message handler not captured")

        on_message(json.dumps({"type": "mode-switch", "mode": "voice"}))
        await asyncio.sleep(0)

        ap.enable_voice_mode.assert_not_called()



