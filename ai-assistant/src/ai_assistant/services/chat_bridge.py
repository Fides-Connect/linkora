"""ChatBridge — transport-agnostic outbound message protocol.

Both ``DataChannelBridge`` (WebRTC DataChannel) and ``WebSocketBridge``
(direct WebSocket) satisfy this protocol structurally, so all downstream
components (AudioProcessor, SessionStarter, ResponseDelivery) accept either
transport without code changes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .agent_runtime_fsm import AgentRuntimeState


@runtime_checkable
class ChatBridge(Protocol):
    """Structural protocol for outbound message transports.

    Any class that provides ``is_open``, ``send_chat``, ``send_runtime_state``,
    ``send_provider_cards``, and ``send_tool_status`` with matching signatures
    satisfies this protocol without inheriting from it.
    """

    @property
    def is_open(self) -> bool:
        """True when the transport is ready to accept outbound messages."""
        ...

    def send_chat(self, text: str, is_user: bool, is_chunk: bool = False) -> None:
        """Send a ``{"type": "chat", …}`` message frame."""
        ...

    def send_runtime_state(self, state: AgentRuntimeState) -> None:
        """Broadcast the current agent runtime state."""
        ...

    def send_provider_cards(self, cards: list[dict]) -> None:
        """Send provider card data to the client."""
        ...

    def send_tool_status(self, label: str) -> None:
        """Send a ``{"type": "tool-status", …}`` message frame."""
        ...
