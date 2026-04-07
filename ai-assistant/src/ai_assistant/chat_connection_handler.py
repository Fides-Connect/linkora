"""ChatConnectionHandler — per-connection handler for lite-mode ``/ws/chat`` sessions.

Unlike ``PeerConnectionHandler``, there is no WebRTC lifecycle here: the
WebSocket IS the transport.  Chat messages flow directly over WebSocket
frames using the same JSON protocol that the DataChannel carries in the full
WebRTC path.

Lifecycle::

    handler = ChatConnectionHandler(connection_id=..., websocket=ws, ...)
    await handler.start()            # wires bridge + boots AudioProcessor
    handler.handle_text_input(text)  # called for each incoming text-input frame
    await handler.close()            # tears down processor + bridge

All heavy I/O (LLM, greeting, provider search) runs inside ``AudioProcessor``
and is entirely unchanged from the WebRTC path.
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from .audio_processor import AudioProcessor
from .services.agent_profile import FULL_PROFILE, AgentProfile
from .services.ws_bridge import WebSocketBridge

logger = logging.getLogger(__name__)


class ChatConnectionHandler:
    """Manages a single ``/ws/chat`` WebSocket connection (lite mode)."""

    def __init__(
        self,
        *,
        connection_id: str,
        websocket: web.WebSocketResponse,
        user_id: str | None = None,
        language: str = "en",
        language_fallback_from: str = "",
        profile: AgentProfile | None = None,
    ) -> None:
        self.connection_id = connection_id
        self.websocket = websocket
        self.user_id = user_id
        self.language = language
        self.language_fallback_from = language_fallback_from
        self._profile: AgentProfile = profile if profile is not None else FULL_PROFILE

        self.ws_bridge = WebSocketBridge(websocket)
        self.audio_processor: AudioProcessor | None = None

        # Messages that arrive before AudioProcessor is ready are buffered.
        self._pending_text_inputs: list[str] = []
        self._idle_task: asyncio.Task[None] | None = None
        self._closed = False

        logger.info(
            "ChatConnectionHandler created: %s (user=%s, language=%s)",
            connection_id,
            user_id,
            language,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Wire the WebSocketBridge and boot the AudioProcessor.

        Creates a text-mode (input_track=None) AudioProcessor, replaces its
        DataChannelBridge with the WebSocketBridge, wires the AgentRuntimeFSM,
        and calls ``AudioProcessor.start()`` which fires the greeting.
        """
        await self.ws_bridge.start_sender()

        self.audio_processor = AudioProcessor(
            connection_id=self.connection_id,
            input_track=None,
            user_id=self.user_id,
            language=self.language,
            language_fallback_from=self.language_fallback_from,
        )

        # Replace the default DataChannelBridge with the WebSocket bridge.
        # Must be done BEFORE start() so the session starter and delivery
        # strategy reference the bridge.
        self.audio_processor.set_chat_bridge(self.ws_bridge)

        # Wire activity hook so incoming messages reset the idle timer.
        self.audio_processor.on_activity = self._reset_idle_timer

        # Wire the AgentRuntimeFSM: state changes → WebSocket runtime-state frames.
        self._wire_runtime_fsm(self.audio_processor)

        # Flush any messages that arrived before start() was called.
        self._flush_pending_text_inputs()

        await self.audio_processor.start()
        self._reset_idle_timer()
        logger.info("ChatConnectionHandler started: %s", self.connection_id)

    async def close(self) -> None:
        """Tear down the connection (idempotent)."""
        if self._closed:
            return
        self._closed = True

        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass

        if self.audio_processor is not None:
            await self.audio_processor.stop()
            self.audio_processor = None

        await self.ws_bridge.stop_sender()

        if not self.websocket.closed:
            try:
                await self.websocket.close()
            except Exception as exc:
                logger.debug("Error closing WS for %s: %s", self.connection_id, exc)

        logger.info("ChatConnectionHandler closed: %s", self.connection_id)

    # ── Inbound message handling ───────────────────────────────────────────────

    def handle_text_input(self, text: str) -> None:
        """Validate and dispatch an incoming text-input message.

        Called by ``SignalingServer.handle_chat_websocket`` for every
        ``{"type": "text-input", "text": "…"}`` frame.
        """
        text = text.strip()
        if not text:
            logger.warning("Empty text input from %s — ignoring", self.connection_id)
            return
        if len(text) > 10_000:
            logger.warning(
                "Text input too large (%d chars) from %s — rejecting",
                len(text),
                self.connection_id,
            )
            return
        self._dispatch_text_input(text)

    def _dispatch_text_input(self, text: str) -> None:
        if self.audio_processor is None:
            self._pending_text_inputs.append(text)
            logger.debug(
                "AudioProcessor not ready; buffered text input for %s",
                self.connection_id,
            )
            return
        self._reset_idle_timer()
        asyncio.create_task(self.audio_processor.receive_text_input(text))

    def _flush_pending_text_inputs(self) -> None:
        if not self._pending_text_inputs or self.audio_processor is None:
            return
        pending = self._pending_text_inputs.copy()
        self._pending_text_inputs.clear()
        logger.info(
            "Flushing %d buffered text input(s) for %s",
            len(pending),
            self.connection_id,
        )
        for text in pending:
            self._dispatch_text_input(text)

    # ── AgentRuntimeFSM wiring ────────────────────────────────────────────────

    def _wire_runtime_fsm(self, audio_processor: AudioProcessor) -> None:
        """Wire FSM state-change events → WebSocket runtime-state frames.

        Mirrors ``PeerConnectionHandler._wire_runtime_fsm``.
        """
        try:
            fsm = audio_processor.ai_assistant.response_orchestrator.runtime_fsm
            fsm.on_state_change = lambda _old, new: audio_processor._emit_runtime_state(new)
            # Advance: BOOTSTRAP → DATA_CHANNEL_WAIT → LISTENING
            fsm.transition("data_channel_wait")
            fsm.transition("data_channel_opened")
            logger.info(
                "RuntimeFSM wired and advanced to LISTENING for %s",
                self.connection_id,
            )
        except AttributeError as exc:
            logger.warning(
                "Could not wire RuntimeFSM for %s: %s",
                self.connection_id,
                exc,
            )

    # ── Idle timer ────────────────────────────────────────────────────────────

    def _reset_idle_timer(self) -> None:
        """Cancel existing idle task and start a fresh 10-minute countdown."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_timeout_task())

    async def _idle_timeout_task(self) -> None:
        try:
            await asyncio.sleep(600)  # 10 minutes
            logger.info("Idle timeout for connection %s — closing", self.connection_id)
            await self.close()
        except asyncio.CancelledError:
            pass
