"""WebSocketBridge — ChatBridge over an aiohttp WebSocketResponse.

Satisfies the ``ChatBridge`` protocol so it can replace ``DataChannelBridge``
wherever a transport-agnostic bridge is accepted (text-mode lite sessions
that connect via ``/ws/chat`` instead of WebRTC DataChannel).

Outbound messages are serialised through an ``asyncio.Queue`` backed by a
background sender task so concurrent ``send_*`` callers never interleave JSON
frames and the caller never ``await``s network I/O.

Usage::

    bridge = WebSocketBridge(ws)
    await bridge.start_sender()

    bridge.send_chat("hi", is_user=False)
    bridge.send_runtime_state(AgentRuntimeState.LISTENING)

    await bridge.stop_sender()   # flush + cancel sender
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from .agent_runtime_fsm import AgentRuntimeState

logger = logging.getLogger(__name__)

# Sentinel value that stops the background sender loop.
_STOP = None


class WebSocketBridge:
    """Wraps an ``aiohttp.WebSocketResponse`` with a typed outbound-message interface.

    This class satisfies ``ChatBridge`` structurally — no explicit inheritance
    is needed.
    """

    def __init__(self, ws: web.WebSocketResponse) -> None:
        self._ws = ws
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._sender_task: asyncio.Task[None] | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start_sender(self) -> None:
        """Start the background sender task.

        Must be called once after the WebSocket upgrade succeeds.
        """
        self._sender_task = asyncio.create_task(self._run_sender())

    async def stop_sender(self) -> None:
        """Flush remaining queued messages then stop the background task.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._sender_task is None or self._sender_task.done():
            return
        self._queue.put_nowait(_STOP)
        if self._sender_task is not None and not self._sender_task.done():
            try:
                await self._sender_task
            except Exception:
                pass
            self._sender_task = None

    async def _run_sender(self) -> None:
        """Background coroutine: drain the queue and write frames to the WS."""
        while True:
            item = await self._queue.get()
            if item is _STOP:
                break
            if self._ws.closed:
                # Connection already closed — discard remaining items.
                continue
            try:
                await self._ws.send_json(item)
            except Exception as exc:
                logger.error("WebSocketBridge send error: %s", exc)

    # ── ChatBridge protocol ────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        """True when the WebSocket has not been closed."""
        return not self._ws.closed

    def send_chat(self, text: str, is_user: bool, is_chunk: bool = False) -> None:
        """Enqueue a ``{"type": "chat", …}`` frame.

        No-op when the WebSocket is closed.
        """
        if not self.is_open:
            return
        try:
            self._queue.put_nowait(
                {
                    "type": "chat",
                    "text": text,
                    "isUser": is_user,
                    "isChunk": is_chunk,
                }
            )
        except Exception as exc:
            logger.error("WebSocketBridge.send_chat enqueue error: %s", exc)

    def send_runtime_state(self, state: AgentRuntimeState) -> None:
        """Enqueue a ``{"type": "runtime-state", …}`` frame.

        No-op when the WebSocket is closed.
        """
        if not self.is_open:
            return
        try:
            self._queue.put_nowait(
                {
                    "type": "runtime-state",
                    "runtimeState": state.value,
                }
            )
        except Exception as exc:
            logger.error("WebSocketBridge.send_runtime_state enqueue error: %s", exc)

    def send_tool_status(self, label: str) -> None:
        """Enqueue a ``{"type": "tool-status", "label": "…"}`` frame.

        No-op when the WebSocket is closed or the label is empty.
        """
        if not self.is_open or not label:
            return
        try:
            self._queue.put_nowait({"type": "tool-status", "label": label})
        except Exception as exc:
            logger.error("WebSocketBridge.send_tool_status enqueue error: %s", exc)

    def send_provider_cards(self, cards: list[dict]) -> None:
        """Enqueue a ``{"type": "provider-cards", …}`` frame.

        No-op when the WebSocket is closed or cards is empty.
        """
        if not self.is_open or not cards:
            return
        try:
            self._queue.put_nowait(
                {
                    "type": "provider-cards",
                    "cards": cards,
                }
            )
        except Exception as exc:
            logger.error("WebSocketBridge.send_provider_cards enqueue error: %s", exc)
