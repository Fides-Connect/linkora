"""DataChannelBridge — typed DataChannel send helper."""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

from .agent_runtime_fsm import AgentRuntimeState

if TYPE_CHECKING:
    from aiortc import RTCDataChannel

logger = logging.getLogger(__name__)


class DataChannelBridge:
    """Wraps a single DataChannel and provides typed send methods.

    Usage::

        bridge = DataChannelBridge()
        bridge.attach(channel)          # called from set_data_channel()
        bridge.send_chat("hi", is_user=False)
        bridge.send_runtime_state(AgentRuntimeState.LISTENING)
    """

    def __init__(self) -> None:
        self._channel = None

    # ── Channel lifecycle ─────────────────────────────────────────────────────

    def attach(self, channel: RTCDataChannel) -> None:
        """Attach or replace the DataChannel reference."""
        self._channel = channel

    @property
    def is_open(self) -> bool:
        """True when a channel is attached and its readyState is ``"open"``."""
        return self._channel is not None and self._channel.readyState == "open"

    # ── Typed send helpers ────────────────────────────────────────────────────

    def send_chat(
        self,
        text: str,
        is_user: bool,
        is_chunk: bool = False,
    ) -> None:
        """Send a ``{"type": "chat", …}`` message.

        No-op when the channel is not open.
        """
        if not self.is_open:
            return
        try:
            self._channel.send(
                json.dumps(
                    {
                        "type": "chat",
                        "text": text,
                        "isUser": is_user,
                        "isChunk": is_chunk,
                    }
                )
            )
        except Exception as exc:
            logger.error("DataChannelBridge.send_chat error: %s", exc)

    def send_runtime_state(self, state: AgentRuntimeState) -> None:
        """Broadcast a ``{"type": "runtime-state", …}`` message.

        No-op when the channel is not open.
        """
        if not self.is_open:
            return
        try:
            self._channel.send(
                json.dumps(
                    {
                        "type": "runtime-state",
                        "runtimeState": state.value,
                    }
                )
            )
        except Exception as exc:
            logger.error("DataChannelBridge.send_runtime_state error: %s", exc)
