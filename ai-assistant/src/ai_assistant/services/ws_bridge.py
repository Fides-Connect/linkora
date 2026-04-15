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
        # Replay buffer: filled while the session is suspended so that frames
        # generated while the client is offline are delivered on reconnect.
        self._replay_buffer: list[dict] = []
        self._buffering: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_replay_capture(self) -> None:
        """Begin buffering replayable outbound frames (called at session suspend).

        Must be called before any ``await`` in the suspend path so that frames
        produced by concurrently-running LLM tasks are captured rather than
        silently discarded.  The buffer is flushed into the new socket's queue
        inside :meth:`replace_websocket`.
        """
        self._buffering = True
        self._replay_buffer = []

    @staticmethod
    def _is_replayable(frame: dict) -> bool:
        """Return True for frames that should be buffered during suspension."""
        t = frame.get("type")
        # Only replay assistant chat messages and provider cards.
        # runtime-state is re-emitted explicitly on resume; tool-status is ephemeral.
        if t == "provider-cards":
            return True
        if t == "chat" and not frame.get("isUser", False):
            return True
        return False

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

    async def replace_websocket(self, ws: web.WebSocketResponse) -> None:
        """Swap the underlying WebSocket for a new one (session resume).

        Stops the current sender (the old WS is already closed), replaces
        the socket reference, gives the bridge a clean outbound queue, then
        starts a fresh sender.  All existing holders of this bridge object
        (AudioProcessor, ResponseDelivery, …) automatically start writing to
        the new socket without any reference updates.
        """
        await self.stop_sender()
        self._ws = ws
        self._queue = asyncio.Queue()
        # Flush any frames buffered while the session was suspended so the
        # client receives the missed content immediately after reconnect.
        for frame in self._replay_buffer:
            self._queue.put_nowait(frame)
        self._replay_buffer = []
        self._buffering = False
        self._sender_task = asyncio.create_task(self._run_sender())

    def send_raw(self, payload: dict) -> None:
        """Enqueue a raw JSON payload frame.

        Used for control frames (e.g. ``session-resumed``) that have no
        dedicated typed helper.  No-op when the WebSocket is closed.
        """
        if not self.is_open:
            return
        try:
            self._queue.put_nowait(payload)
        except Exception as exc:
            logger.error("WebSocketBridge.send_raw enqueue error: %s", exc)

    async def _run_sender(self) -> None:
        """Background coroutine: drain the queue and write frames to the WS."""
        while True:
            item = await self._queue.get()
            if item is _STOP:
                break
            if self._ws.closed:
                # WS already closed.  If we are in buffering mode, preserve
                # replayable frames so they can be delivered on reconnect.
                if self._buffering and self._is_replayable(item):
                    self._replay_buffer.append(item)
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

        When the session is suspended, assistant chat frames are buffered for
        replay on reconnect instead of being silently dropped.
        """
        frame = {"type": "chat", "text": text, "isUser": is_user, "isChunk": is_chunk}
        if not is_user and self._buffering:
            self._replay_buffer.append(frame)
            return
        if not self.is_open:
            return
        try:
            self._queue.put_nowait(frame)
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

        When the session is suspended, provider-card frames are buffered for
        replay on reconnect instead of being silently dropped.
        """
        if not cards:
            return
        frame = {"type": "provider-cards", "cards": cards}
        if self._buffering:
            self._replay_buffer.append(frame)
            return
        if not self.is_open:
            return
        try:
            self._queue.put_nowait(frame)
        except Exception as exc:
            logger.error("WebSocketBridge.send_provider_cards enqueue error: %s", exc)
