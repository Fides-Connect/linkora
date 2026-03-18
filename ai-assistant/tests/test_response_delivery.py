"""
Unit tests for ResponseDelivery strategy classes.

Covers:
- VoiceResponseDelivery.echo_user_transcript() → sends user chat bubble via dc_bridge
- VoiceResponseDelivery.stream_response()     → drives tts_manager.process_llm_stream
- TextResponseDelivery.echo_user_transcript() → no-op (Flutter adds optimistically)
- TextResponseDelivery.stream_response()      → consumes stream; calls on_speaking_change(False)
- ResponseDeliveryFactory.create()            → returns correct concrete type
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock

from ai_assistant.services.response_delivery import (
    VoiceResponseDelivery,
    TextResponseDelivery,
    ResponseDeliveryFactory,
)
from ai_assistant.services.session_mode import SessionMode


# ── helpers ──────────────────────────────────────────────────────────────────

async def _stream(*chunks: str):
    """Async generator yielding the given chunks."""
    for chunk in chunks:
        yield chunk


# ── VoiceResponseDelivery ─────────────────────────────────────────────────────

class TestVoiceResponseDeliveryEchoUserTranscript:

    def _make_delivery(self):
        dc_bridge = Mock()
        dc_bridge.send_chat = Mock()
        tts_manager = Mock()
        tts_manager.process_llm_stream = AsyncMock(return_value=(0, 0.0))
        on_speaking_change = Mock()
        monitor_fn = Mock()
        return VoiceResponseDelivery(
            tts_manager=tts_manager,
            dc_bridge=dc_bridge,
            on_speaking_change=on_speaking_change,
            monitor_playback_fn=monitor_fn,
        ), dc_bridge

    def test_sends_user_chat_bubble(self):
        delivery, dc_bridge = self._make_delivery()
        delivery.echo_user_transcript("Hi, I need a plumber")
        dc_bridge.send_chat.assert_called_once_with("Hi, I need a plumber", is_user=True, is_chunk=False)

    def test_sends_is_user_true(self):
        delivery, dc_bridge = self._make_delivery()
        delivery.echo_user_transcript("anything")
        kwargs = dc_bridge.send_chat.call_args[1]
        assert kwargs.get("is_user") is True


class TestVoiceResponseDeliveryStreamResponse:

    def _make_delivery(self):
        dc_bridge = Mock()
        tts_manager = Mock()
        tts_manager.process_llm_stream = AsyncMock(return_value=(0, 0.0))
        on_speaking_change = Mock()
        monitor_fn = AsyncMock()  # must return a coroutine for asyncio.create_task
        return VoiceResponseDelivery(
            tts_manager=tts_manager,
            dc_bridge=dc_bridge,
            on_speaking_change=on_speaking_change,
            monitor_playback_fn=monitor_fn,
        ), tts_manager, monitor_fn

    async def test_calls_tts_manager_process_llm_stream(self):
        delivery, tts_manager, _ = self._make_delivery()
        await delivery.stream_response(_stream("hello", " world"))
        tts_manager.process_llm_stream.assert_called_once()

    async def test_schedules_monitor_task(self):
        delivery, _, monitor_fn = self._make_delivery()
        await delivery.stream_response(_stream("hi"))
        monitor_fn.assert_called_once()


# ── TextResponseDelivery ──────────────────────────────────────────────────────

class TestTextResponseDeliveryEchoUserTranscript:

    def _make_delivery(self):
        on_speaking_change = Mock()
        return TextResponseDelivery(
            on_speaking_change=on_speaking_change,
        )

    def test_is_no_op(self):
        """Flutter adds the user bubble optimistically — backend must not send it."""
        delivery = self._make_delivery()
        # Just verify no exceptions and no side effects — echo is a pure no-op
        delivery.echo_user_transcript("I need an electrician")


class TestTextResponseDeliveryStreamResponse:

    def _make_delivery(self):
        on_speaking_change = Mock()
        delivery = TextResponseDelivery(
            on_speaking_change=on_speaking_change,
        )
        return delivery, on_speaking_change

    async def test_consumes_entire_stream(self):
        delivery, _ = self._make_delivery()
        chunks_seen = []

        async def capturing_stream():
            for c in ("a", "b", "c"):
                chunks_seen.append(c)
                yield c

        await delivery.stream_response(capturing_stream())
        assert chunks_seen == ["a", "b", "c"]

    async def test_calls_on_speaking_change_false_after_stream(self):
        delivery, on_speaking_change = self._make_delivery()
        await delivery.stream_response(_stream("hi"))
        on_speaking_change.assert_called_with(False)

    async def test_does_not_call_tts(self):
        """TextResponseDelivery must never touch a TTS service."""
        # There is no tts_manager attribute on TextResponseDelivery
        delivery, _ = self._make_delivery()
        assert not hasattr(delivery, "tts_manager")

    async def test_empty_stream_still_calls_on_speaking_change(self):
        delivery, on_speaking_change = self._make_delivery()

        async def empty():
            if False:
                yield ""

        await delivery.stream_response(empty())
        on_speaking_change.assert_called_with(False)


# ── ResponseDeliveryFactory ───────────────────────────────────────────────────

class TestResponseDeliveryFactory:

    def _common_kwargs(self):
        return dict(
            tts_manager=Mock(),
            dc_bridge=Mock(),
            on_speaking_change=Mock(),
            monitor_playback_fn=Mock(),
        )

    def test_voice_mode_returns_voice_delivery(self):
        delivery = ResponseDeliveryFactory.create(SessionMode.VOICE, **self._common_kwargs())
        assert isinstance(delivery, VoiceResponseDelivery)

    def test_text_mode_returns_text_delivery(self):
        delivery = ResponseDeliveryFactory.create(SessionMode.TEXT, **self._common_kwargs())
        assert isinstance(delivery, TextResponseDelivery)

    def test_unknown_mode_falls_back_to_text_delivery(self):
        """Factory returns TextResponseDelivery for any non-VOICE mode."""
        delivery = ResponseDeliveryFactory.create("unknown_mode", **self._common_kwargs())
        assert isinstance(delivery, TextResponseDelivery)
