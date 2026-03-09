"""SessionStarter — one-shot session initialization strategy.

Two concrete strategies:

- ``VoiceSessionStarter``: fetches user data → generates personalised
  greeting text via LLM → adds it to conversation history → sends a DC
  chat bubble → streams TTS audio to the output track (interrupt-aware)
  → advances the stage GREETING → TRIAGE via ResponseOrchestrator.

- ``TextSessionStarter``: fetches user data → generates personalised
  greeting text via LLM → adds it to conversation history → sends a DC
  chat bubble (no TTS) → advances the stage GREETING → TRIAGE.

Both set ``initialized_event`` when done so
``AudioProcessor.process_text_input`` can safely await readiness before
processing the very first message, avoiding a race between session
initialization and the user's first input.

Create via ``SessionStarterFactory.create(mode, **deps)`` — no branching
at call sites.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional

from langchain_core.messages import AIMessage

from .data_channel_bridge import DataChannelBridge
from .session_mode import SessionMode

logger = logging.getLogger(__name__)


async def _fetch_user_data(
    data_provider,
    user_id: Optional[str],
    *,
    firestore_service=None,
) -> tuple[str, bool]:
    """Return (first_name, has_open_request) from the data provider.

    Weaviate (data_provider) is queried for has_open_request. For the user
    name, Firestore (firestore_service) is tried first — it is the canonical
    user-profile store — with Weaviate as fallback. Falls back to ("", False)
    on any error or when user_id is absent.
    """
    if not user_id:
        return "", False
    try:
        first_name = ""
        has_open_request = False

        # --- Weaviate: has_open_request + Weaviate name (fallback) ---
        try:
            weaviate_user = await data_provider.get_user_by_id(user_id)
            if weaviate_user:
                weaviate_name = weaviate_user.get("name", "")
                first_name = weaviate_name.split()[0] if weaviate_name else ""
                has_open_request = weaviate_user.get("has_open_request", False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Weaviate user lookup failed for %s: %s", user_id, exc)

        # --- Firestore: authoritative source for the user's display name ---
        if firestore_service is not None:
            try:
                fs_user = await firestore_service.get_user(user_id)
                if fs_user:
                    fs_name = fs_user.get("name", "") or ""
                    fs_first = fs_name.split()[0] if fs_name else ""
                    if fs_first:
                        first_name = fs_first
            except Exception as exc:  # noqa: BLE001
                logger.warning("Firestore user lookup failed for %s: %s", user_id, exc)

        return first_name, has_open_request
    except Exception as exc:
        logger.error(
            "Failed to fetch user data for user_id=%s: %s",
            user_id,
            exc,
            exc_info=True,
        )
    return "", False


class SessionStarter(ABC):
    """One-shot session initializer.

    Subclasses implement ``initialize()``; on completion (normal or error)
    they must set ``initialized_event`` so waiters are unblocked.
    """

    def __init__(self) -> None:
        self.initialized_event: asyncio.Event = asyncio.Event()

    @abstractmethod
    async def initialize(self) -> None:
        """Run the session initialization sequence once."""


class VoiceSessionStarter(SessionStarter):
    """Voice-mode initializer: greeting text → TTS → GREETING→TRIAGE."""

    def __init__(
        self,
        *,
        conversation_service,
        response_orchestrator,
        data_provider,
        tts_service,
        llm_service,
        dc_bridge: DataChannelBridge,
        output_track,
        user_id: Optional[str],
        connection_id: str,
        interrupt_event: asyncio.Event,
        on_speaking_change: Callable[[bool], None],
        firestore_service=None,
    ) -> None:
        super().__init__()
        self._conv = conversation_service
        self._orchestrator = response_orchestrator
        self._data_provider = data_provider
        self._tts = tts_service
        self._llm = llm_service
        self._dc = dc_bridge
        self._output_track = output_track
        self._user_id = user_id
        self._connection_id = connection_id
        self._interrupt_event = interrupt_event
        self._on_speaking_change = on_speaking_change
        self._firestore_service = firestore_service

    async def initialize(self) -> None:
        self._on_speaking_change(True)
        try:
            user_name, has_open_request = await _fetch_user_data(
                self._data_provider,
                self._user_id,
                firestore_service=self._firestore_service,
            )
            # Seed context so TRIAGE prompt can reference the user's name.
            self._conv.context["user_name"] = user_name
            self._conv.context["has_open_request"] = has_open_request

            greeting_text = await self._conv.generate_greeting_text(
                user_name=user_name,
                has_open_request=has_open_request,
            )

            # Add greeting to LLM history so subsequent turns are coherent.
            history = self._llm.get_session_history(self._connection_id)
            history.add_message(AIMessage(content=greeting_text))

            # Push greeting bubble to Flutter.
            self._dc.send_chat(greeting_text, is_user=False, is_chunk=False)

            # Stream TTS audio to output track, honouring interrupt.
            async for chunk in self._tts.synthesize_stream(
                greeting_text, chunk_size=2048
            ):
                if chunk:
                    if self._interrupt_event.is_set():
                        logger.info(
                            "Voice greeting interrupted for %s",
                            self._connection_id,
                        )
                        break
                    await self._output_track.queue_audio(chunk)

            # Advance stage GREETING → TRIAGE.
            await self._orchestrator.handle_signal_transition_async("triage")

        except Exception as exc:
            logger.error(
                "VoiceSessionStarter.initialize error for %s: %s",
                self._connection_id,
                exc,
                exc_info=True,
            )
            # Ensure stage reaches TRIAGE even on error.
            self._orchestrator.handle_signal_transition("triage")
        finally:
            self._on_speaking_change(False)
            self.initialized_event.set()


class TextSessionStarter(SessionStarter):
    """Text-mode initializer: greeting bubble → seed history → GREETING→TRIAGE.

    Generates the same personalised greeting text as VoiceSessionStarter,
    pushes it as a DataChannel chat bubble so it appears in the Flutter UI
    immediately on session open, adds it to LLM history for coherent follow-up
    turns, then advances the conversation stage from GREETING to TRIAGE.
    TTS is skipped (text-only session).
    """

    def __init__(
        self,
        *,
        conversation_service,
        response_orchestrator,
        data_provider,
        llm_service,
        dc_bridge: DataChannelBridge,
        user_id: Optional[str],
        connection_id: str,
        firestore_service=None,
        buffered_message: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._conv = conversation_service
        self._orchestrator = response_orchestrator
        self._data_provider = data_provider
        self._llm = llm_service
        self._dc = dc_bridge
        self._user_id = user_id
        self._connection_id = connection_id
        self._firestore_service = firestore_service
        self._buffered_message = buffered_message

    async def initialize(self) -> None:
        try:
            user_name, has_open_request = await _fetch_user_data(
                self._data_provider,
                self._user_id,
                firestore_service=self._firestore_service,
            )
            self._conv.context["user_name"] = user_name
            self._conv.context["has_open_request"] = has_open_request

            if self._buffered_message:
                # A first user message arrived before the session was ready.
                # Skip the standalone greeting so the LLM responds to the
                # user's intent directly instead of producing two separate turns.
                # The caller is responsible for injecting the buffered message
                # as a system-tagged input after initialize() completes.
                self._orchestrator.handle_signal_transition("triage")
                logger.info(
                    "TextSessionStarter: skipped greeting (buffered message) for %s",
                    self._connection_id,
                )
                return

            greeting_text = await self._conv.generate_greeting_text(
                user_name=user_name,
                has_open_request=has_open_request,
            )

            # Push greeting bubble to Flutter (no TTS in text mode).
            self._dc.send_chat(greeting_text, is_user=False, is_chunk=False)

            # Seed LLM history so TRIAGE prompt sees a prior assistant message
            # and skips its first-turn greeting rule.
            history = self._llm.get_session_history(self._connection_id)
            history.add_message(AIMessage(content=greeting_text))

            # Advance stage GREETING → TRIAGE.
            self._orchestrator.handle_signal_transition("triage")
            logger.info(
                "TextSessionStarter: TRIAGE ready for %s (user=%r)",
                self._connection_id,
                user_name,
            )
        except Exception as exc:
            logger.error(
                "TextSessionStarter.initialize error for %s: %s",
                self._connection_id,
                exc,
                exc_info=True,
            )
            self._orchestrator.handle_signal_transition("triage")
        finally:
            self.initialized_event.set()


class SessionStarterFactory:
    """Creates the correct SessionStarter for the given session mode."""

    @staticmethod
    def create(
        mode: SessionMode,
        *,
        conversation_service,
        response_orchestrator,
        data_provider,
        tts_service=None,
        llm_service=None,
        dc_bridge: Optional[DataChannelBridge] = None,
        output_track=None,
        user_id: Optional[str] = None,
        connection_id: str = "",
        interrupt_event: Optional[asyncio.Event] = None,
        on_speaking_change: Optional[Callable[[bool], None]] = None,
        firestore_service=None,
        buffered_message: Optional[str] = None,
    ) -> SessionStarter:
        if mode == SessionMode.VOICE:
            return VoiceSessionStarter(
                conversation_service=conversation_service,
                response_orchestrator=response_orchestrator,
                data_provider=data_provider,
                tts_service=tts_service,
                llm_service=llm_service,
                dc_bridge=dc_bridge,
                output_track=output_track,
                user_id=user_id,
                connection_id=connection_id,
                interrupt_event=interrupt_event or asyncio.Event(),
                on_speaking_change=on_speaking_change or (lambda _: None),
                firestore_service=firestore_service,
            )
        return TextSessionStarter(
            conversation_service=conversation_service,
            response_orchestrator=response_orchestrator,
            data_provider=data_provider,
            llm_service=llm_service,
            dc_bridge=dc_bridge,
            user_id=user_id,
            connection_id=connection_id,
            firestore_service=firestore_service,
            buffered_message=buffered_message,
        )
