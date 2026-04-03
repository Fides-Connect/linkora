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
from collections.abc import Coroutine
from datetime import datetime, UTC
from typing import TYPE_CHECKING
from collections.abc import Callable

from ai_assistant.services.ai_conversation_service import AIConversationService
from langchain_core.messages import AIMessage

from .conversation_service import ConversationStage
from .data_channel_bridge import DataChannelBridge
from .greeting_cache import get_greeting_cache
from .session_mode import SessionMode

if TYPE_CHECKING:
    from ..audio_track import AudioOutputTrack
    from ..data_provider import DataProvider
    from ..firestore_service import FirestoreService
    from .conversation_service import ConversationService
    from .llm_service import LLMService
    from .response_orchestrator import ResponseOrchestrator
    from .text_to_speech_service import TextToSpeechService

logger = logging.getLogger(__name__)


async def _fetch_user_data(
    data_provider: DataProvider,
    user_id: str | None,
    *,
    firestore_service: FirestoreService | None = None,
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
        conversation_service: ConversationService,
        response_orchestrator: ResponseOrchestrator,
        data_provider: DataProvider,
        tts_service: TextToSpeechService,
        llm_service: LLMService,
        dc_bridge: DataChannelBridge,
        output_track: AudioOutputTrack,
        user_id: str | None,
        connection_id: str,
        interrupt_event: asyncio.Event,
        on_speaking_change: Callable[[bool], None],
        firestore_service: FirestoreService | None = None,
        ai_conversation_service: AIConversationService | None = None,
        monitor_playback_fn: Callable[[], Coroutine] | None = None,
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
        self._ai_conv_service = ai_conversation_service
        self._monitor_playback_fn = monitor_playback_fn

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

            # GAP-2: Session resumption hydration (§9.2)
            if self._ai_conv_service is not None and self._user_id:
                _summary = await self._ai_conv_service.get_recent_session_summary(self._user_id)
                if _summary:
                    _ended = _summary.get("ended_at")
                    _now = datetime.now(UTC)
                    if _ended:
                        if _ended.tzinfo is None:
                            _ended = _ended.replace(tzinfo=UTC)
                        _mins = int((_now - _ended).total_seconds() / 60)
                        _ctx = (
                            f"[System Context: The user's previous session ended {_mins} minutes ago "
                            f"in stage {_summary['final_stage'].value}. "
                            f"Last discussed request: \"{_summary.get('topic_title', '')}\".]"
                        )
                    else:
                        _ctx = (
                            f"[System Context: Previous session in stage {_summary['final_stage'].value}. "
                            f"Last discussed request: \"{_summary.get('topic_title', '')}\".]"
                        )
                    self._conv.context["session_resume_context"] = _ctx
                    _MID_FLOW = {ConversationStage.TRIAGE, ConversationStage.CLARIFY, ConversationStage.CONFIRMATION}
                    if _summary["final_stage"] in _MID_FLOW:
                        self._conv.restore_from_summary(_summary)
                        logger.info(
                            "Voice session resumed to %s for user %s",
                            _summary["final_stage"].value, self._user_id,
                        )

            # Check the greeting cache first — the REST warmup endpoint may
            # have already generated text + TTS audio while the user was on
            # the assistant tab, saving ~1.5–2.5 s of LLM + TTS latency.
            language = getattr(self._conv, "language", "de")
            cache_entry = (
                get_greeting_cache().get(self._user_id, language)
                if self._user_id
                else None
            )

            if cache_entry:
                logger.info(
                    "Cache hit — using pre-generated greeting for %s (skipping LLM+TTS)",
                    self._connection_id,
                )
                greeting_text = cache_entry.text
                audio_bytes: bytes | None = cache_entry.audio_bytes
            else:
                logger.info(
                    "Cache miss — generating greeting on the fly for %s",
                    self._connection_id,
                )
                greeting_text = await self._conv.generate_greeting_text(
                    user_name=user_name,
                    has_open_request=has_open_request,
                )
                audio_bytes = None  # will synthesise via streaming below

            # Add greeting to LLM history so subsequent turns are coherent.
            history = self._llm.get_session_history(self._connection_id)
            history.add_message(AIMessage(content=greeting_text))

            # Push greeting bubble to Flutter.
            self._dc.send_chat(greeting_text, is_user=False, is_chunk=False)

            # Greeting delivered — clear the first-message flag so subsequent
            # TRIAGE turns don't re-greet.  TRIAGE is already the initial stage.
            self._conv.context["is_first_message"] = False
            self.initialized_event.set()

            # Play audio.
            if audio_bytes:  # treat empty bytes as a cache miss — fall through to TTS
                # Fast path: replay pre-synthesised bytes from the cache.
                for i in range(0, len(audio_bytes), 2048):
                    if self._interrupt_event.is_set():
                        logger.info(
                            "Voice greeting interrupted for %s", self._connection_id
                        )
                        break
                    await self._output_track.queue_audio(audio_bytes[i : i + 2048])
            else:
                # Normal path: stream TTS synthesis on the fly.
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

        except Exception as exc:
            logger.error(
                "VoiceSessionStarter.initialize error for %s: %s",
                self._connection_id,
                exc,
                exc_info=True,
            )
            # Clear first-message flag so the next user turn doesn't attempt to
            # re-greet.  Stage stays at TRIAGE (already the initial stage).
            self._conv.context["is_first_message"] = False
        finally:
            # Keep is_ai_speaking=True until the audio queue actually drains.
            # Clearing it here while audio is still buffered in the output
            # track would let _stt_session treat the still-playing greeting as
            # user speech and route it to the LLM.
            if self._interrupt_event.is_set() or self._monitor_playback_fn is None:
                # Interrupted or no monitor available — clear immediately.
                self._on_speaking_change(False)
            else:
                # Delegate flag-clearing to the playback monitor so it fires
                # only after the output track's audio queue is empty.
                asyncio.create_task(self._monitor_playback_fn())
            self.initialized_event.set()


class TextSessionStarter(SessionStarter):
    """Text-mode initializer: greeting bubble → seed history → TRIAGE ready.

    For non-buffered sessions: generates a personalised greeting text, pushes it
    as a DataChannel chat bubble, seeds LLM history for coherent follow-up turns,
    then clears the is_first_message flag so subsequent TRIAGE turns don't re-greet.

    For buffered sessions (a user message arrived before the session was ready):
    skips the standalone greeting.  is_first_message stays True so the first
    generate_response_stream() call greets the user and processes their intent
    simultaneously in a single TRIAGE turn.

    TTS is skipped (text-only session).
    """

    def __init__(
        self,
        *,
        conversation_service: ConversationService,
        response_orchestrator: ResponseOrchestrator,
        data_provider: DataProvider,
        llm_service: LLMService,
        dc_bridge: DataChannelBridge,
        user_id: str | None,
        connection_id: str,
        firestore_service: FirestoreService | None = None,
        ai_conversation_service: AIConversationService | None = None,
        buffered_message: str | None = None,
        first_message_event: asyncio.Event | None = None,
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
        self._ai_conv_service = ai_conversation_service
        self._buffered_message = buffered_message
        self._first_message_event = first_message_event

    async def initialize(self) -> None:
        try:
            user_name, has_open_request = await _fetch_user_data(
                self._data_provider,
                self._user_id,
                firestore_service=self._firestore_service,
            )
            self._conv.context["user_name"] = user_name
            self._conv.context["has_open_request"] = has_open_request

            # GAP-2: Session resumption hydration (§9.2)
            if self._ai_conv_service is not None and self._user_id is not None:
                _summary = await self._ai_conv_service.get_recent_session_summary(self._user_id)
                if _summary:
                    _ended = _summary.get("ended_at")
                    _now = datetime.now(UTC)
                    if _ended:
                        if _ended.tzinfo is None:
                            _ended = _ended.replace(tzinfo=UTC)
                        _mins = int((_now - _ended).total_seconds() / 60)
                        _ctx = (
                            f"[System Context: The user's previous session ended {_mins} minutes ago "
                            f"in stage {_summary['final_stage'].value}. "
                            f"Last discussed request: \"{_summary.get('topic_title', '')}\".]"
                        )
                    else:
                        _ctx = (
                            f"[System Context: Previous session in stage {_summary['final_stage'].value}. "
                            f"Last discussed request: \"{_summary.get('topic_title', '')}\".]"
                        )
                    self._conv.context["session_resume_context"] = _ctx
                    _MID_FLOW = {ConversationStage.TRIAGE, ConversationStage.CLARIFY, ConversationStage.CONFIRMATION}
                    if _summary["final_stage"] in _MID_FLOW:
                        self._conv.restore_from_summary(_summary)
                        logger.info(
                            "Text session resumed to %s for user %s",
                            _summary["final_stage"].value, self._user_id,
                        )

            if self._buffered_message:
                # A first user message arrived before the session was ready.
                # Skip the standalone greeting so the LLM greets the user AND
                # handles their intent together in the first TRIAGE turn.
                # is_first_message stays True — ResponseOrchestrator will clear it
                # after the first successful LLM chunk.
                logger.info(
                    "TextSessionStarter: skipped standalone greeting (buffered message) for %s",
                    self._connection_id,
                )
                return

            # Wait up to 300 ms for a DataChannel message that arrives after the
            # WebRTC handshake but before initialize() has committed to sending a
            # standalone greeting.  This closes the race between the LLM call and
            # a buffered client message delivered when the DataChannel first opens.
            if self._first_message_event is not None:
                try:
                    await asyncio.wait_for(
                        self._first_message_event.wait(), timeout=0.3
                    )
                    # A real message arrived in the window — skip the autonomous
                    # greeting; is_first_message stays True so TRIAGE greets the
                    # user while responding to their intent in one turn.
                    logger.info(
                        "TextSessionStarter: skipped standalone greeting (late DC message) for %s",
                        self._connection_id,
                    )
                    return
                except TimeoutError:
                    pass  # No early message — proceed with autonomous greeting.

            greeting_text = await self._conv.generate_greeting_text(
                user_name=user_name,
                has_open_request=has_open_request,
            )

            # Push greeting bubble to Flutter (no TTS in text mode).
            self._dc.send_chat(greeting_text, is_user=False, is_chunk=False)

            # Seed LLM history so TRIAGE prompt sees a prior assistant message
            # and knows the greeting was already delivered.
            history = self._llm.get_session_history(self._connection_id)
            history.add_message(AIMessage(content=greeting_text))

            # Greeting delivered — clear the first-message flag so subsequent
            # TRIAGE turns don't re-greet.  TRIAGE is already the initial stage.
            self._conv.context["is_first_message"] = False
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
            # Clear first-message flag so the next user turn doesn't attempt
            # to re-greet.  Stage stays at TRIAGE (already the initial stage).
            self._conv.context["is_first_message"] = False
        finally:
            self.initialized_event.set()


class SessionStarterFactory:
    """Creates the correct SessionStarter for the given session mode."""

    @staticmethod
    def create(
        mode: SessionMode,
        *,
        conversation_service: ConversationService,
        response_orchestrator: ResponseOrchestrator,
        data_provider: DataProvider,
        tts_service: TextToSpeechService | None = None,
        llm_service: LLMService | None = None,
        dc_bridge: DataChannelBridge | None = None,
        output_track: AudioOutputTrack | None = None,
        user_id: str | None = None,
        connection_id: str = "",
        interrupt_event: asyncio.Event | None = None,
        on_speaking_change: Callable[[bool], None] | None = None,
        firestore_service: FirestoreService | None = None,
        ai_conversation_service: AIConversationService | None = None,
        buffered_message: str | None = None,
        first_message_event: asyncio.Event | None = None,
        monitor_playback_fn: Callable[[], Coroutine] | None = None,
    ) -> SessionStarter:
        if mode == SessionMode.VOICE:
            if llm_service is None or dc_bridge is None or output_track is None or tts_service is None:
                raise ValueError("Voice session starter requires llm_service, dc_bridge, output_track, and tts_service")
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
                ai_conversation_service=ai_conversation_service,
                monitor_playback_fn=monitor_playback_fn,
            )
        if llm_service is None or dc_bridge is None:
            raise ValueError("Text session starter requires llm_service and dc_bridge")
        return TextSessionStarter(
            conversation_service=conversation_service,
            response_orchestrator=response_orchestrator,
            data_provider=data_provider,
            llm_service=llm_service,
            dc_bridge=dc_bridge,
            user_id=user_id,
            connection_id=connection_id,
            firestore_service=firestore_service,
            ai_conversation_service=ai_conversation_service,
            buffered_message=buffered_message,
            first_message_event=first_message_event,
        )
