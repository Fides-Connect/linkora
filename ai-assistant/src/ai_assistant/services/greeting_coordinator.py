"""GreetingCoordinator — one-shot greeting for voice and text sessions.

Owns the ``greeting_sent`` flag and all greeting logic, eliminating the
``_play_greeting`` and ``send_text_greeting`` duplication in
``AudioProcessor``.
"""
import asyncio
import logging
from typing import Callable, Optional

from .session_mode import SessionMode
from .agent_runtime_fsm import AgentRuntimeState

logger = logging.getLogger(__name__)


class GreetingCoordinator:
    """Unifies voice and text greeting under a single ``send(mode)`` interface.

    Injected dependencies
    ---------------------
    ai_assistant:
        Exposes ``get_greeting_audio(user_id, manage_stage)`` and
        ``conversation_service``.
    dc_bridge:
        ``DataChannelBridge`` — used to send chat messages.
    fsm:
        ``AgentRuntimeFSM`` — inspected to detect whether the user already
        sent their first message (text mode only).
    output_track:
        ``AudioOutputTrack`` — audio is queued here (voice mode only).
    user_id:
        Forwarded to ``get_greeting_audio``.
    connection_id:
        Used for log messages.
    interrupt_event:
        ``asyncio.Event`` — set by ``_trigger_interrupt`` when the user speaks
        over the greeting.  Checked inside the audio-chunk loop.
    on_speaking_change:
        Callback ``(bool) -> None`` wired to set/clear ``is_ai_speaking`` on
        the owning ``AudioProcessor``.
    """

    def __init__(
        self,
        *,
        ai_assistant,
        dc_bridge,
        fsm,
        output_track,
        user_id: Optional[str],
        connection_id: str,
        interrupt_event: asyncio.Event,
        on_speaking_change: Callable[[bool], None],
    ) -> None:
        self._ai = ai_assistant
        self._dc = dc_bridge
        self._fsm = fsm
        self._output_track = output_track
        self._user_id = user_id
        self._connection_id = connection_id
        self._interrupt_event = interrupt_event
        self._on_speaking_change = on_speaking_change
        self.greeting_sent: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def send(self, mode: SessionMode) -> None:
        """Send the greeting once; subsequent calls are idempotent no-ops."""
        if self.greeting_sent:
            logger.info(
                "Greeting already sent for %s — ignoring duplicate call",
                self._connection_id,
            )
            return
        self.greeting_sent = True

        if mode == SessionMode.VOICE:
            await self._send_voice_greeting()
        else:
            await self._send_text_greeting()

    # ── Voice mode ────────────────────────────────────────────────────────────

    async def _send_voice_greeting(self) -> None:
        """Generate audio greeting, stream it to the output track."""
        self._on_speaking_change(True)
        try:
            greeting_text, audio_stream = await self._ai.get_greeting_audio(
                user_id=self._user_id
            )
            logger.info("Voice greeting: %s", greeting_text)
            self._dc.send_chat(greeting_text, is_user=False, is_chunk=False)

            async for chunk in audio_stream:
                if chunk:
                    if self._interrupt_event.is_set():
                        logger.info(
                            "Voice greeting interrupted for %s", self._connection_id
                        )
                        break
                    await self._output_track.queue_audio(chunk)
        except Exception as exc:
            logger.error(
                "Error in voice greeting for %s: %s",
                self._connection_id,
                exc,
                exc_info=True,
            )
        finally:
            self._on_speaking_change(False)

    # ── Text mode ─────────────────────────────────────────────────────────────

    async def _send_text_greeting(self) -> None:
        """Set stage → TRIAGE via the orchestrator, poll for DataChannel, then send greeting text."""
        # Advance stage via the orchestrator (single source of truth for transitions)
        # so GREETING → TRIAGE is consistent with all other stage transitions.
        # No LLM stream is active here so handle_signal_transition (sync) is sufficient.
        self._ai.response_orchestrator.handle_signal_transition("triage")

        if not await self._wait_for_dc_open():
            return

        # Yield so any concurrently-scheduled process_text_input() can execute
        # its synchronous FSM transition (LISTENING → THINKING) first.
        await asyncio.sleep(0)

        if self._fsm.current_state != AgentRuntimeState.LISTENING:
            logger.info(
                "Text mode: FSM is '%s' for %s — user already sent first message; "
                "skipping auto-greeting",
                self._fsm.current_state.value,
                self._connection_id,
            )
            return

        try:
            # manage_stage=False: populate context (user_name, open_request)
            # without resetting the stage back to GREETING.
            # The audio stream is discarded — TTS is not called in text mode.
            greeting_text, _ = await self._ai.get_greeting_audio(
                user_id=self._user_id, manage_stage=False
            )
            logger.info("Text greeting for %s: %s", self._connection_id, greeting_text)
            self._dc.send_chat(greeting_text, is_user=False, is_chunk=False)
        except Exception as exc:
            logger.error(
                "Error in text greeting for %s: %s",
                self._connection_id,
                exc,
                exc_info=True,
            )

    async def _wait_for_dc_open(self, timeout: float = 5.0) -> bool:
        """Poll until the DataChannel bridge reports ``is_open``.

        Returns ``True`` if the channel opens within *timeout* seconds,
        ``False`` otherwise.
        """
        steps = int(timeout / 0.1)
        for _ in range(steps):
            if self._dc.is_open:
                return True
            await asyncio.sleep(0.1)
        logger.warning(
            "DataChannel not open after %ss for %s — skipping text greeting "
            "(stage already at TRIAGE)",
            timeout,
            self._connection_id,
        )
        return False
