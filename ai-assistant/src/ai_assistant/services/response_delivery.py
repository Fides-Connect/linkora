"""ResponseDelivery — strategy for per-turn response output.

Two concrete strategies handle how each conversation turn is delivered:

- ``VoiceResponseDelivery``: echoes the user's transcript as a DataChannel
  chat bubble, then pipes the LLM stream through TTSPlaybackManager and
  spawns a playback-completion monitor task.

- ``TextResponseDelivery``: no transcript echo (Flutter adds it
  optimistically), no TTS — the stream is consumed as-is (DC chunks are
  already forwarded inside the tracked LLM stream) and then the speaking
  flag is cleared.

Swap the active ``ResponseDelivery`` instance on ``AudioProcessor`` to
change delivery behaviour mid-conversation without any if/else in the
calling code.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Callable
from collections.abc import Awaitable

from .data_channel_bridge import DataChannelBridge
from .session_mode import SessionMode
from .tts_playback_manager import TTSPlaybackManager

logger = logging.getLogger(__name__)


class ResponseDelivery(ABC):
    """Per-turn output strategy — one instance per session, swapped on mode switch."""

    @abstractmethod
    def echo_user_transcript(self, transcript: str) -> None:
        """Send the user's transcript to the client (voice) or skip it (text)."""

    @abstractmethod
    async def stream_response(self, llm_stream: AsyncIterator[str]) -> None:
        """Consume the LLM stream and deliver via the appropriate channel."""


class VoiceResponseDelivery(ResponseDelivery):
    """Voice mode: echo transcript as DC bubble, route LLM stream through TTS."""

    def __init__(
        self,
        *,
        tts_manager: TTSPlaybackManager,
        dc_bridge: DataChannelBridge,
        on_speaking_change: Callable[[bool], None],
        monitor_playback_fn: Callable[[int, float], Awaitable[None]],
    ) -> None:
        self._tts_manager = tts_manager
        self._dc_bridge = dc_bridge
        self._on_speaking_change = on_speaking_change
        self._monitor_playback_fn = monitor_playback_fn

    def echo_user_transcript(self, transcript: str) -> None:
        self._dc_bridge.send_chat(transcript, is_user=True, is_chunk=False)

    async def stream_response(self, llm_stream: AsyncIterator[str]) -> None:
        total_bytes, first_audio_at = await self._tts_manager.process_llm_stream(llm_stream)
        asyncio.create_task(self._monitor_playback_fn(total_bytes or 0, first_audio_at))


class TextResponseDelivery(ResponseDelivery):
    """Text mode: no transcript echo, no TTS — stream already forwarded via DC."""

    def __init__(
        self,
        *,
        on_speaking_change: Callable[[bool], None],
    ) -> None:
        self._on_speaking_change = on_speaking_change

    def echo_user_transcript(self, transcript: str) -> None:
        pass  # Flutter adds it optimistically

    async def stream_response(self, llm_stream: AsyncIterator[str]) -> None:
        async for _ in llm_stream:
            pass
        self._on_speaking_change(False)


class ResponseDeliveryFactory:
    """Creates the correct ResponseDelivery strategy for the given session mode."""

    @staticmethod
    def create(
        mode: SessionMode,
        *,
        tts_manager: TTSPlaybackManager,
        dc_bridge: DataChannelBridge,
        on_speaking_change: Callable[[bool], None],
        monitor_playback_fn: Callable[[int, float], Awaitable[None]],
    ) -> ResponseDelivery:
        if mode == SessionMode.VOICE:
            return VoiceResponseDelivery(
                tts_manager=tts_manager,
                dc_bridge=dc_bridge,
                on_speaking_change=on_speaking_change,
                monitor_playback_fn=monitor_playback_fn,
            )
        return TextResponseDelivery(on_speaking_change=on_speaking_change)
