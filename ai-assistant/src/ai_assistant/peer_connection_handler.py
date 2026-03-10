"""
WebRTC Peer Connection Handler
Manages individual WebRTC connections and media streams.
"""
import asyncio
import json
import logging
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaRelay
from aiortc.sdp import candidate_from_sdp

from .audio_processor import AudioProcessor
from .services.data_channel_message_router import DataChannelMessageRouter
from .services.session_mode import SessionMode

logger = logging.getLogger(__name__)


class PeerConnectionHandler:
    """Handles WebRTC peer connection for a single client."""

    def __init__(
        self,
        connection_id: str,
        websocket,
        user_id: str = None,
        language: str = 'de',
        session_mode: str = 'voice',
        ice_servers: list[dict] | None = None,
        hold_start: bool = False,
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.user_id = user_id
        self.language = language
        # Store as SessionMode enum; backward-compat: == "voice" still works.
        self.session_mode = SessionMode(session_mode)
        self.pc = RTCPeerConnection(
            configuration=self._build_rtc_config(ice_servers)
        )
        self.relay = MediaRelay()
        self.audio_processor = None
        self.track_ready = asyncio.Event()
        self.track_update_ready = asyncio.Event()
        self.track_update_ready.set()  # Initially set - no update pending
        self.data_channel = None
        # One-shot flag: when True, the first voice offer is a hollow pre-warm
        # (no audio track).  We send the SDP answer immediately without waiting
        # for on_track.  Cleared after the hollow answer is sent so the real
        # renegotiation offer (with audio track) is processed normally.
        self._hold_start_active = hold_start
        self._pending_text_inputs: list[str] = []
        self._idle_task: asyncio.Task = None  # 10-minute idle timeout task
        # True once pc.addTrack(output_track) has been called so we never
        # try to add it a second time on a voice re-upgrade.
        self._output_track_added = False
        # Set by the mode-switch→text handler to signal that the next
        # renegotiation offer is a voice→text downgrade (track removal), not
        # a text→voice upgrade.  Allows _handle_renegotiation_offer to answer
        # immediately without waiting for on_track.
        self._voice_to_text_downgrade_pending = False
        self._closed = False      # True once teardown fully completes
        self._close_lock = asyncio.Lock()  # serialises concurrent close() calls

        # DataChannel message dispatch table
        self._dc_router = DataChannelMessageRouter()
        self._dc_router.register("text-input", self._on_dc_text_input)
        self._dc_router.register("mode-switch", self._on_dc_mode_switch)

        logger.info(
            "PeerConnectionHandler created for connection %s with language: %s, mode: %s",
            connection_id, language, session_mode,
        )

        # Set up event handlers
        self._setup_event_handlers()

    # ── Idle timer ────────────────────────────────────────────────────────────

    def _reset_idle_timer(self):
        """Cancel existing idle task and start a fresh 10-minute countdown."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_timeout_task())

    def _wire_runtime_fsm(self, audio_processor: "AudioProcessor") -> None:
        """Wire the AgentRuntimeFSM on_state_change callback to emit DataChannel events.

        After wiring, immediately advances the FSM from BOOTSTRAP through
        DATA_CHANNEL_WAIT to LISTENING so that Flutter receives the initial
        runtime-state events and the FSM is ready to accept "final_transcript".
        """
        try:
            fsm = audio_processor.ai_assistant.response_orchestrator.runtime_fsm
            fsm.on_state_change = lambda _old, new: audio_processor._emit_runtime_state(new)
            # Advance FSM to LISTENING: BOOTSTRAP → DATA_CHANNEL_WAIT → LISTENING
            fsm.transition("data_channel_wait")
            fsm.transition("data_channel_opened")
            logger.info(
                "RuntimeFSM wired and advanced to LISTENING for connection %s",
                self.connection_id,
            )
        except AttributeError as exc:
            logger.warning(
                "Could not wire RuntimeFSM for connection %s: %s",
                self.connection_id, exc,
            )

    async def _idle_timeout_task(self):
        """Close the connection after 10 minutes of inactivity."""
        try:
            await asyncio.sleep(600)  # 10 minutes
            logger.info("Idle timeout reached for connection %s — closing", self.connection_id)
            await self.close()
        except asyncio.CancelledError:
            pass  # Normal cancellation when activity is detected

    # ── ICE / TURN helpers ────────────────────────────────────────────────────

    @staticmethod
    def _build_rtc_config(ice_servers: list[dict] | None) -> RTCConfiguration | None:
        """Convert a list of ICE server dicts into an RTCConfiguration.

        Each dict may contain:
          - ``urls``:       str or list[str]
          - ``username``:   str (optional)
          - ``credential``: str (optional)

        Returns ``None`` (no explicit config) when ``ice_servers`` is empty/None,
        which lets aiortc fall back to its built-in default.
        """
        if not ice_servers:
            return None
        servers = []
        for s in ice_servers:
            urls = s.get("urls", [])
            if isinstance(urls, str):
                urls = [urls]
            for url in urls:
                servers.append(
                    RTCIceServer(
                        urls=url,
                        username=s.get("username"),
                        credential=s.get("credential"),
                    )
                )
        return RTCConfiguration(iceServers=servers) if servers else None

    async def send_ice_config(self, ice_servers: list[dict]) -> None:
        """Send ICE server credentials to the client before the offer/answer exchange.

        The client (Flutter) waits for this message before creating its peer
        connection so that TURN credentials are available from the start.
        """
        await self.websocket.send_json({"type": "ice-config", "iceServers": ice_servers})

    def _flush_pending_text_inputs(self) -> None:
        """Flush queued text-input messages once the processor/channel are ready."""
        if not self._pending_text_inputs:
            return
        if self.audio_processor is None:
            return
        if self.data_channel is None or self.data_channel.readyState != "open":
            return

        pending = self._pending_text_inputs.copy()
        self._pending_text_inputs.clear()
        logger.info(
            "Flushing %d buffered text-input message(s) for connection %s",
            len(pending),
            self.connection_id,
        )
        for text in pending:
            self._dispatch_text_input(text)

    def _dispatch_text_input(self, text: str) -> None:
        """Dispatch a validated text-input to the audio processor."""
        if self.audio_processor is None:
            self._pending_text_inputs.append(text)
            logger.info(
                "Audio processor not ready; buffered text-input for connection %s",
                self.connection_id,
            )
            return

        preview = text[:50] + '…' if len(text) > 50 else text
        logger.debug("Processing text input (%d chars): %s", len(text), preview)
        # Reset idle timer on any user activity
        self._reset_idle_timer()

        asyncio.create_task(self.audio_processor.receive_text_input(text))

    # ── DataChannel message handlers ──────────────────────────────────────────

    def _on_dc_text_input(self, data: dict) -> None:
        """Handle a ``text-input`` DataChannel message."""
        text = data.get('text', '').strip()
        if not text:
            logger.warning("Empty text input received — ignoring")
            return
        if len(text) > 10_000:
            logger.warning(
                "Text input too large (%d chars) from connection %s — rejecting",
                len(text), self.connection_id,
            )
            return
        self._dispatch_text_input(text)

    def _on_dc_mode_switch(self, data: dict) -> None:
        """Handle a ``mode-switch`` DataChannel message."""
        mode = data.get('mode', '')
        if not self.audio_processor:
            logger.warning("mode-switch received but audio processor not ready")
            return
        self._reset_idle_timer()
        if mode == 'text' and not self.audio_processor._is_text_mode:
            logger.info("mode-switch → text: pausing voice pipeline")
            # Signal that the next renegotiation offer removes the audio track
            # (voice→text downgrade) so _handle_renegotiation_offer skips the
            # track-update wait.  Only set when coming from voice mode;
            # pure text sessions never renegotiate on mode-switch.
            self._voice_to_text_downgrade_pending = True
            asyncio.create_task(self.audio_processor.disable_voice_mode())
        elif mode == 'voice' and self.audio_processor._is_text_mode:
            logger.info("mode-switch → voice: resuming voice pipeline")
            asyncio.create_task(self.audio_processor.enable_voice_mode())

    # ── on_track helpers ──────────────────────────────────────────────────────

    async def _on_first_voice_track(self, track) -> None:
        """First audio track on a brand-new voice session."""
        self.audio_processor = AudioProcessor(
            connection_id=self.connection_id,
            input_track=track,
            user_id=self.user_id,
            language=self.language,
        )
        # Wire activity hook so STT transcripts reset the idle timer
        self.audio_processor.on_activity = self._reset_idle_timer
        # Wire FSM state-change → DataChannel runtime-state events
        self._wire_runtime_fsm(self.audio_processor)

        if self.data_channel:
            self.audio_processor.set_data_channel(self.data_channel)
            self._flush_pending_text_inputs()

        self.track_ready.set()
        asyncio.create_task(self.audio_processor.start())
        self._reset_idle_timer()

    async def _on_text_to_voice_upgrade(self, track) -> None:
        """Existing text-only session upgrading to voice."""
        logger.info("Text → voice upgrade detected")
        output_track = await self.audio_processor.enable_voice_mode(track)
        if not self._output_track_added:
            # First time voice mode is activated: add the TTS output track.
            self.pc.addTrack(output_track)
            self._output_track_added = True
        else:
            # The output sender already exists from a previous voice phase;
            # aiortc does not allow adding the same track twice.
            logger.info("Output track sender already present — skipping addTrack")
        self.audio_processor.on_activity = self._reset_idle_timer
        self._reset_idle_timer()
        self._flush_pending_text_inputs()
        self.track_update_ready.set()

    async def _on_track_replacement(self, track) -> None:
        """Track replacement during renegotiation (e.g. Bluetooth change)."""
        logger.info("Track replacement detected (renegotiation)")
        await self.audio_processor.replace_input_track(track)
        self.track_update_ready.set()

    # ── Event handlers ────────────────────────────────────────────────────────

    def _setup_event_handlers(self):

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            """Send ICE candidates to client."""
            if candidate:
                await self._send_message({
                    'type': 'ice-candidate',
                    'candidate': {
                        'candidate': candidate.candidate,
                        'sdpMid': candidate.sdpMid,
                        'sdpMLineIndex': candidate.sdpMLineIndex
                    }
                })

        @self.pc.on("track")
        async def on_track(track):
            """Route incoming media track to the correct handler."""
            logger.info("Received %s track: %s", track.kind, track.id)
            if track.kind != "audio":
                return

            if self.audio_processor is not None and self.audio_processor._is_text_mode:
                await self._on_text_to_voice_upgrade(track)
            elif self.audio_processor is not None:
                await self._on_track_replacement(track)
            else:
                await self._on_first_voice_track(track)

        @self.pc.on("datachannel")
        def on_datachannel(channel):
            """Handle incoming data channel."""
            logger.info("Data channel received: %s", channel.label)
            self.data_channel = channel

            if self.audio_processor:
                self.audio_processor.set_data_channel(channel)
            self._flush_pending_text_inputs()

            @channel.on("message")
            def on_message(message):
                """Dispatch DataChannel messages via the router."""
                try:
                    data = json.loads(message)
                    logger.info("Data channel message received: %s", data.get('type'))
                    self._dc_router.dispatch(data)
                except Exception as exc:
                    logger.error("Error handling data channel message: %s", exc, exc_info=True)

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            """Handle connection state changes."""
            logger.info("Connection state: %s", self.pc.connectionState)
            if self.pc.connectionState == "failed":
                await self.close()

    # ── handle_offer helpers ──────────────────────────────────────────────────

    async def _await_track_update(self, timeout: float, hard: bool) -> None:
        """Wait for :attr:`track_update_ready` to be set.

        Parameters
        ----------
        timeout:
            Seconds to wait.
        hard:
            If ``True`` propagate :exc:`asyncio.TimeoutError`; if ``False``
            log and continue so SDP-only renegotiations don't fail.
        """
        if hard:
            await asyncio.wait_for(self.track_update_ready.wait(), timeout=timeout)
        else:
            try:
                await asyncio.wait_for(self.track_update_ready.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.debug(
                    "Renegotiation for connection %s: no new track within %.1f s "
                    "— SDP-only renegotiation, continuing without track_update_ready",
                    self.connection_id, timeout,
                )

    async def _handle_initial_voice_offer(self) -> None:
        """Complete initial voice offer: wait for track, add output, send answer.

        When ``_hold_start_active`` is True (hollow pre-warm), the client sent
        an offer with no audio track so the full ICE + DC handshake can be
        completed before the user taps the mic.  We send the answer immediately
        without waiting for ``on_track``.  The flag is cleared after so the
        next offer (the real voice offer with audio track sent on mic tap) is
        processed via the normal path, which creates the AudioProcessor and
        plays the cached greeting.
        """
        if self._hold_start_active:
            self._hold_start_active = False  # one-shot
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            await self._send_message({'type': 'answer', 'sdp': self.pc.localDescription.sdp})
            logger.info(
                "Hollow pre-warm: SDP handshake complete for connection %s "
                "(AudioProcessor deferred until real voice offer)",
                self.connection_id,
            )
            return

        await asyncio.wait_for(self.track_ready.wait(), timeout=5.0)
        if self.audio_processor:
            output_track = self.audio_processor.get_output_track()
            logger.info("Adding output track: %s", output_track.id)
            self.pc.addTrack(output_track)
            self._output_track_added = True
        else:
            logger.error("Audio processor not ready after track_ready signal")
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        await self._send_message({'type': 'answer', 'sdp': self.pc.localDescription.sdp})

    async def _handle_initial_text_offer(self) -> None:
        """Create a text-mode AudioProcessor and send answer (no audio track)."""
        if self.audio_processor is None:
            self.audio_processor = AudioProcessor(
                connection_id=self.connection_id,
                input_track=None,
                user_id=self.user_id,
                language=self.language,
            )
            self.audio_processor.on_activity = self._reset_idle_timer
            self._wire_runtime_fsm(self.audio_processor)
            if self.data_channel:
                self.audio_processor.set_data_channel(self.data_channel)
                self._flush_pending_text_inputs()
            asyncio.create_task(self.audio_processor.start())
            self._reset_idle_timer()
            logger.info("Text-mode AudioProcessor created without audio track")
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        await self._send_message({'type': 'answer', 'sdp': self.pc.localDescription.sdp})

    async def _handle_renegotiation_offer(self) -> None:
        """Handle renegotiation: text→voice upgrade (hard wait), voice→text
        downgrade (no wait), or SDP-only track swap (soft wait)."""
        if self._voice_to_text_downgrade_pending:
            # Voice→text downgrade: the client removed its audio sender.
            # on_track will not fire, so answer immediately without waiting.
            self._voice_to_text_downgrade_pending = False
            logger.info("Renegotiation for connection %s: voice→text downgrade, answering immediately",
                        self.connection_id)
        elif self.audio_processor is not None and self.audio_processor._is_text_mode:
            # Hard wait: on_track MUST fire to add the TTS output track before answer.
            await self._await_track_update(timeout=5.0, hard=True)
        else:
            # Soft wait: SDP-only renegotiations (e.g. track swap) continue on timeout.
            await self._await_track_update(timeout=2.0, hard=False)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        await self._send_message({'type': 'answer', 'sdp': self.pc.localDescription.sdp})

    async def handle_offer(self, offer: RTCSessionDescription):
        """Handle WebRTC offer from client — route to the correct helper."""
        try:
            is_renegotiation = self.audio_processor is not None
            logger.info(
                "Handling %s offer%s",
                "renegotiation" if is_renegotiation else "initial",
                " (text→voice upgrade)" if (
                    is_renegotiation and self.audio_processor._is_text_mode
                ) else "",
            )

            # Clear the event before setRemoteDescription so on_track is
            # guaranteed to set it *after* our await below.
            if is_renegotiation:
                self.track_update_ready.clear()

            await self.pc.setRemoteDescription(offer)

            if is_renegotiation:
                await self._handle_renegotiation_offer()
            elif self.session_mode == SessionMode.TEXT:
                await self._handle_initial_text_offer()
            else:
                await self._handle_initial_voice_offer()

        except Exception as exc:
            logger.error("Error handling offer: %s", exc, exc_info=True)

    async def handle_ice_candidate(self, candidate_data: dict):
        """Handle ICE candidate from client."""
        try:
            candidate_str = candidate_data.get('candidate', '')
            if candidate_str:
                candidate = candidate_from_sdp(candidate_str)
                candidate.sdpMid = candidate_data.get('sdpMid')
                candidate.sdpMLineIndex = candidate_data.get('sdpMLineIndex')
                await self.pc.addIceCandidate(candidate)
        except Exception as exc:
            logger.error("Error adding ICE candidate: %s", exc, exc_info=True)

    async def _send_message(self, message: dict):
        """Send message to client via WebSocket."""
        try:
            await self.websocket.send_json(message)
        except Exception as exc:
            logger.error("Error sending message: %s", exc, exc_info=True)

    async def close(self):
        """Close peer connection and cleanup resources.

        Safe to call multiple times — subsequent calls are no-ops.
        Concurrent callers await the in-progress teardown via ``_close_lock``
        rather than returning early, so all callers are guaranteed to unblock
        only after cleanup is complete.  This is relied on by
        close_all_connections() and the handle_websocket() finally block.
        """
        if self._closed:
            return
        async with self._close_lock:
            if self._closed:  # re-check after acquiring lock
                return
            logger.info("Closing connection %s", self.connection_id)

            # _close_lock serialises concurrent calls so only one teardown runs
            # at a time.  _closed is set only after all steps complete — if this
            # coroutine is cancelled mid-way (e.g. asyncio.wait_for timeout
            # during shutdown), _closed stays False and a subsequent sequential
            # call can retry.  CancelledError (BaseException) propagates
            # naturally out of the lock context; only Exception is caught below.

            # Cancel idle timer.
            # Guard against self-cancellation when close() is called from within
            # the idle task itself (e.g. _idle_timeout_task calls close() on expiry).
            # Also await the cancellation to avoid 'Task exception was never retrieved'.
            try:
                idle_task = self._idle_task
                if idle_task and not idle_task.done():
                    current = asyncio.current_task()
                    if idle_task is not current:
                        idle_task.cancel()
                        try:
                            await idle_task
                        except asyncio.CancelledError:
                            pass
            except Exception as exc:
                logger.warning("Error cancelling idle timer for %s: %s", self.connection_id, exc)

            if self.audio_processor:
                # Persist final conversation state before tearing down the processor.
                try:
                    orchestrator = self.audio_processor.ai_assistant.response_orchestrator
                    ai_conv = orchestrator.ai_conversation_service
                    if ai_conv is not None:
                        final_stage = (
                            self.audio_processor.ai_assistant.conversation_service
                            .get_current_stage()
                        )
                        await ai_conv.close_session(final_stage)
                    orchestrator.runtime_fsm.transition("terminate")
                except Exception as exc:
                    logger.warning(
                        "Could not persist conversation on close for %s: %s",
                        self.connection_id, exc,
                    )
                try:
                    await self.audio_processor.stop()
                except Exception as exc:
                    logger.warning("Error stopping audio processor for %s: %s", self.connection_id, exc)

            try:
                await self.pc.close()
                self._closed = True
            except Exception as exc:
                logger.warning("Error closing peer connection for %s: %s", self.connection_id, exc)
