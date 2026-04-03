"""
Unit tests for SessionStarter strategy classes.

Covers:
- VoiceSessionStarter.initialize():
  - fetches user data and seeds conversation context
  - generates greeting text via conversation_service
  - sends a DataChannel chat bubble
  - streams TTS chunks to output_track
  - halts TTS streaming when interrupt_event is set
  - advances GREETING → TRIAGE via handle_signal_transition_async
  - sets initialized_event when done
  - sets initialized_event even on error (ensures waiters are never blocked)
- TextSessionStarter.initialize():
  - fetches user data and seeds context
  - advances GREETING → TRIAGE via handle_signal_transition (sync)
  - never calls TTS
  - sets initialized_event immediately
- SessionStarterFactory.create():
  - returns VoiceSessionStarter for VOICE mode
  - returns TextSessionStarter for TEXT mode
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from ai_assistant.services.session_starter import (
    VoiceSessionStarter,
    TextSessionStarter,
    SessionStarterFactory,
    _fetch_user_data,
)
from ai_assistant.services.session_mode import SessionMode


# ── helpers ───────────────────────────────────────────────────────────────────

def _voice_starter(
    *,
    user_name: str = "Max",
    has_open_request: bool = False,
    greeting_text: str = "Hallo Max!",
    tts_chunks: list[bytes] | None = None,
    interrupt_event: asyncio.Event | None = None,
):
    """Build a VoiceSessionStarter with all deps mocked."""
    tts_chunks = tts_chunks or [b"chunk1", b"chunk2"]

    data_provider = Mock()
    data_provider.get_user_by_id = AsyncMock(return_value={
        "name": user_name,
        "has_open_request": has_open_request,
    })

    conversation_service = Mock()
    conversation_service.context = {}
    conversation_service.generate_greeting_text = AsyncMock(return_value=greeting_text)

    orchestrator = Mock()
    orchestrator.handle_signal_transition_async = AsyncMock()
    orchestrator.handle_signal_transition = Mock()

    llm_service = Mock()
    session_history = Mock()
    session_history.add_message = Mock()
    llm_service.get_session_history = Mock(return_value=session_history)

    async def _tts_gen(*args, **kwargs):
        for c in tts_chunks:
            yield c

    tts_service = Mock()
    tts_service.synthesize_stream = Mock(return_value=_tts_gen())

    dc_bridge = Mock()
    dc_bridge.send_chat = Mock()

    output_track = Mock()
    output_track.queue_audio = AsyncMock()

    on_speaking_change = Mock()

    starter = VoiceSessionStarter(
        conversation_service=conversation_service,
        response_orchestrator=orchestrator,
        data_provider=data_provider,
        tts_service=tts_service,
        llm_service=llm_service,
        dc_bridge=dc_bridge,
        output_track=output_track,
        user_id="user-123",
        connection_id="conn-1",
        interrupt_event=interrupt_event or asyncio.Event(),
        on_speaking_change=on_speaking_change,
    )
    return starter, {
        "conversation_service": conversation_service,
        "orchestrator": orchestrator,
        "dc_bridge": dc_bridge,
        "output_track": output_track,
        "on_speaking_change": on_speaking_change,
        "llm_service": llm_service,
        "tts_service": tts_service,
        "data_provider": data_provider,
    }


def _text_starter(
    *,
    user_name: str = "Anna",
    has_open_request: bool = False,
    greeting_text: str = "Hallo Anna!",
):
    """Build a TextSessionStarter with all deps mocked."""
    data_provider = Mock()
    data_provider.get_user_by_id = AsyncMock(return_value={
        "name": user_name,
        "has_open_request": has_open_request,
    })

    conversation_service = Mock()
    conversation_service.context = {}
    conversation_service.generate_greeting_text = AsyncMock(return_value=greeting_text)

    orchestrator = Mock()
    orchestrator.handle_signal_transition = Mock()

    llm_service = Mock()
    session_history = Mock()
    session_history.add_message = Mock()
    llm_service.get_session_history = Mock(return_value=session_history)

    dc_bridge = Mock()
    dc_bridge.send_chat = Mock()

    starter = TextSessionStarter(
        conversation_service=conversation_service,
        response_orchestrator=orchestrator,
        data_provider=data_provider,
        llm_service=llm_service,
        dc_bridge=dc_bridge,
        user_id="user-456",
        connection_id="conn-2",
    )
    return starter, {
        "conversation_service": conversation_service,
        "orchestrator": orchestrator,
        "data_provider": data_provider,
        "llm_service": llm_service,
        "dc_bridge": dc_bridge,
    }


# ══════════════════════════════════════════════════════════════════════════════
# _fetch_user_data helper
# ══════════════════════════════════════════════════════════════════════════════

class TestFetchUserData:

    async def test_returns_first_name_and_open_request(self):
        provider = Mock()
        provider.get_user_by_id = AsyncMock(return_value={
            "name": "Max Mustermann",
            "has_open_request": True,
        })
        name, has_req = await _fetch_user_data(provider, "u1")
        assert name == "Max"
        assert has_req is True

    async def test_empty_user_id_returns_defaults(self):
        provider = Mock()
        name, has_req = await _fetch_user_data(provider, None)
        assert name == ""
        assert has_req is False
        provider.get_user_by_id.assert_not_called()

    async def test_error_returns_defaults(self):
        provider = Mock()
        provider.get_user_by_id = AsyncMock(side_effect=RuntimeError("DB down"))
        name, has_req = await _fetch_user_data(provider, "u1")
        assert name == ""
        assert has_req is False

    async def test_firestore_name_used_when_weaviate_name_empty(self):
        """Firestore is authoritative: its name is used when Weaviate has none."""
        provider = Mock()
        provider.get_user_by_id = AsyncMock(return_value={
            "name": "",
            "has_open_request": True,
        })
        fs = Mock()
        fs.get_user = AsyncMock(return_value={"name": "Lena Huber"})
        name, has_req = await _fetch_user_data(provider, "u1", firestore_service=fs)
        assert name == "Lena"
        assert has_req is True

    async def test_firestore_name_overrides_weaviate_name(self):
        """Firestore wins even when Weaviate already has a name."""
        provider = Mock()
        provider.get_user_by_id = AsyncMock(return_value={
            "name": "Old Name",
            "has_open_request": False,
        })
        fs = Mock()
        fs.get_user = AsyncMock(return_value={"name": "Max Mustermann"})
        name, has_req = await _fetch_user_data(provider, "u1", firestore_service=fs)
        assert name == "Max"

    async def test_firestore_error_falls_back_to_weaviate_name(self):
        """A Firestore error must not discard the Weaviate name."""
        provider = Mock()
        provider.get_user_by_id = AsyncMock(return_value={
            "name": "Anna",
            "has_open_request": False,
        })
        fs = Mock()
        fs.get_user = AsyncMock(side_effect=RuntimeError("Firestore down"))
        name, has_req = await _fetch_user_data(provider, "u1", firestore_service=fs)
        assert name == "Anna"


# ══════════════════════════════════════════════════════════════════════════════
# VoiceSessionStarter
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceSessionStarterInitialize:

    async def test_initialized_event_set_on_completion(self):
        starter, _ = _voice_starter()
        assert not starter.initialized_event.is_set()
        await starter.initialize()
        assert starter.initialized_event.is_set()

    async def test_seeds_conversation_context(self):
        starter, deps = _voice_starter(user_name="Max", has_open_request=True)
        await starter.initialize()
        assert deps["conversation_service"].context["user_name"] == "Max"
        assert deps["conversation_service"].context["has_open_request"] is True

    async def test_calls_generate_greeting_text(self):
        starter, deps = _voice_starter()
        await starter.initialize()
        deps["conversation_service"].generate_greeting_text.assert_called_once_with(
            user_name="Max", has_open_request=False
        )

    async def test_sends_greeting_dc_bubble(self):
        starter, deps = _voice_starter(greeting_text="Hello there!")
        await starter.initialize()
        deps["dc_bridge"].send_chat.assert_called_once_with(
            "Hello there!", is_user=False, is_chunk=False
        )

    async def test_streams_tts_to_output_track(self):
        starter, deps = _voice_starter(tts_chunks=[b"a", b"b", b"c"])
        await starter.initialize()
        assert deps["output_track"].queue_audio.call_count == 3

    async def test_clears_first_message_flag_after_greeting(self):
        starter, deps = _voice_starter()
        await starter.initialize()
        assert deps["conversation_service"].context.get("is_first_message") is False
        deps["orchestrator"].handle_signal_transition_async.assert_not_called()

    async def test_calls_on_speaking_change_true_then_false(self):
        starter, deps = _voice_starter()
        calls = []
        deps["on_speaking_change"].side_effect = lambda v: calls.append(v)
        await starter.initialize()
        assert calls[0] is True
        assert calls[-1] is False

    async def test_interrupt_stops_tts_streaming_early(self):
        interrupt_event = asyncio.Event()
        chunks_queued = []

        async def counting_queue(chunk):
            chunks_queued.append(chunk)
            if len(chunks_queued) == 1:
                interrupt_event.set()

        starter, deps = _voice_starter(
            tts_chunks=[b"c1", b"c2", b"c3", b"c4", b"c5"],
            interrupt_event=interrupt_event,
        )
        deps["output_track"].queue_audio = AsyncMock(side_effect=counting_queue)

        await starter.initialize()

        # Should have stopped after the first chunk triggered the interrupt
        assert len(chunks_queued) <= 2, (
            "TTS streaming must stop when interrupt_event is set"
        )

    async def test_initialized_event_set_even_on_error(self):
        starter, deps = _voice_starter()
        deps["conversation_service"].generate_greeting_text = AsyncMock(
            side_effect=RuntimeError("LLM exploded")
        )
        await starter.initialize()  # must not raise
        assert starter.initialized_event.is_set()

    async def test_first_message_cleared_on_error(self):
        starter, deps = _voice_starter()
        deps["conversation_service"].generate_greeting_text = AsyncMock(
            side_effect=RuntimeError("LLM error")
        )
        await starter.initialize()
        # Flag is cleared even on error; no stage transition is needed
        assert deps["conversation_service"].context.get("is_first_message") is False
        deps["orchestrator"].handle_signal_transition.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# TextSessionStarter
# ══════════════════════════════════════════════════════════════════════════════

class TestTextSessionStarterInitialize:

    async def test_initialized_event_set_immediately(self):
        starter, _ = _text_starter()
        assert not starter.initialized_event.is_set()
        await starter.initialize()
        assert starter.initialized_event.is_set()

    async def test_seeds_conversation_context(self):
        starter, deps = _text_starter(user_name="Anna", has_open_request=False)
        await starter.initialize()
        assert deps["conversation_service"].context["user_name"] == "Anna"
        assert deps["conversation_service"].context["has_open_request"] is False

    async def test_calls_generate_greeting_text(self):
        starter, deps = _text_starter(user_name="Anna", has_open_request=False)
        await starter.initialize()
        deps["conversation_service"].generate_greeting_text.assert_called_once_with(
            user_name="Anna", has_open_request=False
        )

    async def test_sends_greeting_dc_bubble(self):
        """Text mode must push a greeting bubble so it appears in the UI
        immediately when the Assistant page opens."""
        starter, deps = _text_starter(greeting_text="Hallo Anna!")
        await starter.initialize()
        deps["dc_bridge"].send_chat.assert_called_once_with(
            "Hallo Anna!", is_user=False, is_chunk=False
        )

    async def test_adds_greeting_to_llm_history(self):
        from langchain_core.messages import AIMessage

        starter, deps = _text_starter(greeting_text="Hi there!")
        await starter.initialize()
        history = deps["llm_service"].get_session_history.return_value
        history.add_message.assert_called_once()
        added_msg = history.add_message.call_args[0][0]
        assert isinstance(added_msg, AIMessage)
        assert added_msg.content == "Hi there!"

    async def test_clears_first_message_flag_after_greeting(self):
        starter, deps = _text_starter()
        await starter.initialize()
        assert deps["conversation_service"].context.get("is_first_message") is False
        deps["orchestrator"].handle_signal_transition.assert_not_called()

    async def test_does_not_call_tts(self):
        """TextSessionStarter must never touch TTS — no audio at session start."""
        starter, _ = _text_starter()
        assert not hasattr(starter, "_tts")
        await starter.initialize()

    async def test_initialized_event_set_even_on_error(self):
        starter, deps = _text_starter()
        deps["data_provider"].get_user_by_id = AsyncMock(
            side_effect=RuntimeError("DB error")
        )
        await starter.initialize()
        assert starter.initialized_event.is_set()

    async def test_first_message_cleared_on_error(self):
        starter, deps = _text_starter()
        deps["conversation_service"].generate_greeting_text = AsyncMock(
            side_effect=RuntimeError("LLM exploded")
        )
        await starter.initialize()  # must not raise
        assert starter.initialized_event.is_set()
        assert deps["conversation_service"].context.get("is_first_message") is False
        deps["orchestrator"].handle_signal_transition.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# TextSessionStarter — buffered message (early user input)
# ══════════════════════════════════════════════════════════════════════════════

class TestTextSessionStarterWithBufferedMessage:
    """When a user message arrives before the session is ready, the greeting
    bubble must be skipped and the stage must advance directly to TRIAGE."""

    def _buffered_starter(self, buffered_message: str = "I need a plumber"):
        """Build a TextSessionStarter with a buffered_message set."""
        data_provider = Mock()
        data_provider.get_user_by_id = AsyncMock(return_value={"name": "Anna", "has_open_request": False})
        conversation_service = Mock()
        conversation_service.context = {}
        conversation_service.generate_greeting_text = AsyncMock(return_value="Hallo!")
        orchestrator = Mock()
        orchestrator.handle_signal_transition = Mock()
        llm_service = Mock()
        dc_bridge = Mock()
        dc_bridge.send_chat = Mock()
        starter = TextSessionStarter(
            conversation_service=conversation_service,
            response_orchestrator=orchestrator,
            data_provider=data_provider,
            llm_service=llm_service,
            dc_bridge=dc_bridge,
            user_id="user-456",
            connection_id="conn-2",
            buffered_message=buffered_message,
        )
        return starter, conversation_service, orchestrator, dc_bridge

    async def test_skips_greeting_bubble_when_buffered_message_set(self):
        starter, conv, orch, dc = self._buffered_starter()
        await starter.initialize()
        dc.send_chat.assert_not_called()

    async def test_skips_generate_greeting_text_when_buffered_message_set(self):
        starter, conv, orch, dc = self._buffered_starter()
        await starter.initialize()
        conv.generate_greeting_text.assert_not_called()

    async def test_preserves_first_message_flag_when_buffered(self):
        """When a buffered message is set, is_first_message must stay True so
        the TRIAGE LLM call greets the user and handles their intent together."""
        starter, conv, orch, dc = self._buffered_starter()
        await starter.initialize()
        # Flag left True — orchestrator will clear it after first LLM chunk
        assert conv.context.get("is_first_message") is not False
        orch.handle_signal_transition.assert_not_called()

    async def test_initialized_event_set_when_buffered_message_set(self):
        starter, conv, orch, dc = self._buffered_starter()
        await starter.initialize()
        assert starter.initialized_event.is_set()

    async def test_seeds_context_even_when_buffered_message_set(self):
        starter, conv, orch, dc = self._buffered_starter()
        await starter.initialize()
        assert "user_name" in conv.context
        assert "has_open_request" in conv.context


# ══════════════════════════════════════════════════════════════════════════════
# TextSessionStarter — late DataChannel message (initialization race)
# ══════════════════════════════════════════════════════════════════════════════

class TestTextSessionStarterLateMessage:
    """When a user's text message arrives via DataChannel AFTER the WebRTC
    handshake (but before the 300 ms window closes), the system must skip the
    autonomous greeting and go straight to TRIAGE, allowing the LLM to respond
    to the user's intent directly.  This covers the log-observed race where
    generate_greeting_text was called at T+0 ms and the client message arrived
    at T+254 ms."""

    def _late_starter(self, first_message_event: asyncio.Event):
        """Build a TextSessionStarter wired with a first_message_event."""
        data_provider = Mock()
        data_provider.get_user_by_id = AsyncMock(return_value={"name": "Max", "has_open_request": False})
        conversation_service = Mock()
        conversation_service.context = {}
        conversation_service.generate_greeting_text = AsyncMock(return_value="Hello Max!")
        orchestrator = Mock()
        orchestrator.handle_signal_transition = Mock()
        llm_service = Mock()
        llm_service.get_session_history = Mock(return_value=Mock(add_message=Mock()))
        dc_bridge = Mock()
        dc_bridge.send_chat = Mock()
        starter = TextSessionStarter(
            conversation_service=conversation_service,
            response_orchestrator=orchestrator,
            data_provider=data_provider,
            llm_service=llm_service,
            dc_bridge=dc_bridge,
            user_id="user-99",
            connection_id="conn-late",
            first_message_event=first_message_event,
        )
        return starter, conversation_service, orchestrator, dc_bridge

    async def test_skips_greeting_when_message_arrives_within_300ms(self):
        """If a message is signalled before the 300 ms window expires, the
        autonomous greeting must be skipped; is_first_message stays True so TRIAGE
        greets the user and handles their intent in a single LLM call."""
        event = asyncio.Event()

        async def _fire_soon():
            await asyncio.sleep(0.05)  # well within 300 ms
            event.set()

        asyncio.create_task(_fire_soon())
        starter, conv, orch, dc = self._late_starter(event)
        await starter.initialize()

        conv.generate_greeting_text.assert_not_called()
        orch.handle_signal_transition.assert_not_called()

    async def test_no_dc_bubble_when_late_message_detected(self):
        """No standalone greeting bubble must be sent when the late-message
        path is taken."""
        event = asyncio.Event()

        async def _fire_soon():
            await asyncio.sleep(0.05)
            event.set()

        asyncio.create_task(_fire_soon())
        starter, conv, orch, dc = self._late_starter(event)
        await starter.initialize()

        dc.send_chat.assert_not_called()

    async def test_initialized_event_set_after_late_message_skip(self):
        """initialized_event must always be set, even on the late-message path."""
        event = asyncio.Event()

        async def _fire_soon():
            await asyncio.sleep(0.05)
            event.set()

        asyncio.create_task(_fire_soon())
        starter, conv, orch, dc = self._late_starter(event)
        await starter.initialize()

        assert starter.initialized_event.is_set()

    async def test_generates_greeting_when_no_message_within_300ms(self):
        """If no message arrives within 300 ms, the autonomous greeting must
        be generated and sent normally."""
        event = asyncio.Event()  # never set during this test
        starter, conv, orch, dc = self._late_starter(event)
        await starter.initialize()

        conv.generate_greeting_text.assert_called_once()
        dc.send_chat.assert_called_once()
        orch.handle_signal_transition.assert_not_called()
        assert conv.context.get("is_first_message") is False


# ══════════════════════════════════════════════════════════════════════════════
# SessionStarterFactory
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionStarterFactory:

    def _common_kwargs(self):
        return dict(
            conversation_service=Mock(),
            response_orchestrator=Mock(),
            data_provider=Mock(),
            tts_service=Mock(),
            llm_service=Mock(),
            dc_bridge=Mock(),
            output_track=Mock(),
            user_id="u1",
            connection_id="c1",
            interrupt_event=asyncio.Event(),
            on_speaking_change=Mock(),
        )

    def test_voice_mode_returns_voice_starter(self):
        starter = SessionStarterFactory.create(SessionMode.VOICE, **self._common_kwargs())
        assert isinstance(starter, VoiceSessionStarter)

    def test_text_mode_returns_text_starter(self):
        starter = SessionStarterFactory.create(SessionMode.TEXT, **self._common_kwargs())
        assert isinstance(starter, TextSessionStarter)

    def test_created_starter_has_unset_initialized_event(self):
        starter = SessionStarterFactory.create(SessionMode.TEXT, **self._common_kwargs())
        assert not starter.initialized_event.is_set()


# ══════════════════════════════════════════════════════════════════════════════
# GAP-2: Session resumption hydration
# ══════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timezone, timedelta
from ai_assistant.services.conversation_service import ConversationStage


def _make_summary(
    final_stage=ConversationStage.TRIAGE,
    topic_title="Plumber needed",
    request_summary="User wants a plumber",
    minutes_ago=10,
):
    ended_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "final_stage": final_stage,
        "topic_title": topic_title,
        "request_summary": request_summary,
        "ended_at": ended_at,
    }


def _voice_starter_with_ai_conv(summary=None):
    """Build a VoiceSessionStarter with an ai_conversation_service mock."""
    ai_conv = Mock()
    ai_conv.get_recent_session_summary = AsyncMock(return_value=summary)

    data_provider = Mock()
    data_provider.get_user_by_id = AsyncMock(return_value={"name": "Max", "has_open_request": False})

    conversation_service = Mock()
    conversation_service.context = {}
    conversation_service.generate_greeting_text = AsyncMock(return_value="Hallo!")
    conversation_service.restore_from_summary = Mock()

    orchestrator = Mock()
    orchestrator.handle_signal_transition_async = AsyncMock()
    orchestrator.handle_signal_transition = Mock()

    llm = Mock()
    llm.get_session_history = Mock(return_value=Mock(add_message=Mock()))

    async def _tts(*a, **kw):
        yield b"audio"

    tts = Mock()
    tts.synthesize_stream = Mock(return_value=_tts())

    dc = Mock()
    dc.send_chat = Mock()
    output_track = Mock()
    output_track.queue_audio = AsyncMock()

    starter = VoiceSessionStarter(
        conversation_service=conversation_service,
        response_orchestrator=orchestrator,
        data_provider=data_provider,
        tts_service=tts,
        llm_service=llm,
        dc_bridge=dc,
        output_track=output_track,
        user_id="user-123",
        connection_id="conn-1",
        interrupt_event=asyncio.Event(),
        on_speaking_change=Mock(),
        ai_conversation_service=ai_conv,
    )
    return starter, conversation_service, ai_conv


def _text_starter_with_ai_conv(summary=None):
    """Build a TextSessionStarter with an ai_conversation_service mock."""
    ai_conv = Mock()
    ai_conv.get_recent_session_summary = AsyncMock(return_value=summary)

    data_provider = Mock()
    data_provider.get_user_by_id = AsyncMock(return_value={"name": "Anna", "has_open_request": False})

    conversation_service = Mock()
    conversation_service.context = {}
    conversation_service.generate_greeting_text = AsyncMock(return_value="Hallo!")
    conversation_service.restore_from_summary = Mock()

    orchestrator = Mock()
    orchestrator.handle_signal_transition = Mock()

    llm = Mock()
    llm.get_session_history = Mock(return_value=Mock(add_message=Mock()))

    dc = Mock()
    dc.send_chat = Mock()

    starter = TextSessionStarter(
        conversation_service=conversation_service,
        response_orchestrator=orchestrator,
        data_provider=data_provider,
        llm_service=llm,
        dc_bridge=dc,
        user_id="user-456",
        connection_id="conn-2",
        ai_conversation_service=ai_conv,
    )
    return starter, conversation_service, ai_conv


class TestVoiceSessionStarterResumption:
    """GAP-2: session resumption hydration for VoiceSessionStarter."""

    async def test_no_summary_does_not_set_resume_context(self):
        starter, conv, _ = _voice_starter_with_ai_conv(summary=None)
        await starter.initialize()
        assert "session_resume_context" not in conv.context

    async def test_recent_triage_session_injects_resume_context(self):
        summary = _make_summary(final_stage=ConversationStage.TRIAGE, minutes_ago=5)
        starter, conv, _ = _voice_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        ctx = conv.context.get("session_resume_context", "")
        assert "triage" in ctx.lower()
        assert "5 minutes ago" in ctx

    async def test_recent_triage_session_calls_restore_from_summary(self):
        summary = _make_summary(final_stage=ConversationStage.TRIAGE)
        starter, conv, _ = _voice_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        conv.restore_from_summary.assert_called_once_with(summary)

    async def test_recent_confirmation_session_calls_restore_from_summary(self):
        summary = _make_summary(final_stage=ConversationStage.CONFIRMATION)
        starter, conv, _ = _voice_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        conv.restore_from_summary.assert_called_once_with(summary)

    async def test_terminal_stage_injects_context_but_no_restore(self):
        summary = _make_summary(final_stage=ConversationStage.COMPLETED)
        starter, conv, _ = _voice_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        assert "session_resume_context" in conv.context
        conv.restore_from_summary.assert_not_called()

    async def test_no_ai_conv_service_skips_hydration(self):
        """When no ai_conversation_service is injected, hydration is silently skipped."""
        data_provider = Mock()
        data_provider.get_user_by_id = AsyncMock(return_value={"name": "Max", "has_open_request": False})
        conv = Mock()
        conv.context = {}
        conv.generate_greeting_text = AsyncMock(return_value="Hi!")
        conv.restore_from_summary = Mock()
        orchestrator = Mock()
        orchestrator.handle_signal_transition_async = AsyncMock()
        orchestrator.handle_signal_transition = Mock()
        llm = Mock()
        llm.get_session_history = Mock(return_value=Mock(add_message=Mock()))

        async def _tts(*a, **kw):
            yield b"x"

        tts = Mock()
        tts.synthesize_stream = Mock(return_value=_tts())
        dc = Mock()
        dc.send_chat = Mock()

        starter = VoiceSessionStarter(
            conversation_service=conv,
            response_orchestrator=orchestrator,
            data_provider=data_provider,
            tts_service=tts,
            llm_service=llm,
            dc_bridge=dc,
            output_track=Mock(queue_audio=AsyncMock()),
            user_id="u1",
            connection_id="c1",
            interrupt_event=asyncio.Event(),
            on_speaking_change=Mock(),
            # ai_conversation_service not passed
        )
        await starter.initialize()
        conv.restore_from_summary.assert_not_called()
        assert "session_resume_context" not in conv.context

    async def test_summary_topic_title_included_in_context(self):
        summary = _make_summary(
            final_stage=ConversationStage.TRIAGE,
            topic_title="Electrician for kitchen",
        )
        starter, conv, _ = _voice_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        ctx = conv.context.get("session_resume_context", "")
        assert "Electrician for kitchen" in ctx

    async def test_ended_at_none_produces_context_without_minutes(self):
        summary = _make_summary(final_stage=ConversationStage.TRIAGE)
        summary["ended_at"] = None
        starter, conv, _ = _voice_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        ctx = conv.context.get("session_resume_context", "")
        assert "triage" in ctx.lower()
        assert "minutes ago" not in ctx


class TestTextSessionStarterResumption:
    """GAP-2: session resumption hydration for TextSessionStarter."""

    async def test_no_summary_does_not_set_resume_context(self):
        starter, conv, _ = _text_starter_with_ai_conv(summary=None)
        await starter.initialize()
        assert "session_resume_context" not in conv.context

    async def test_recent_triage_session_injects_resume_context(self):
        summary = _make_summary(final_stage=ConversationStage.TRIAGE, minutes_ago=15)
        starter, conv, _ = _text_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        ctx = conv.context.get("session_resume_context", "")
        assert "triage" in ctx.lower()
        assert "15 minutes ago" in ctx

    async def test_mid_flow_calls_restore_from_summary(self):
        for stage in (ConversationStage.TRIAGE, ConversationStage.CLARIFY, ConversationStage.CONFIRMATION):
            summary = _make_summary(final_stage=stage)
            starter, conv, _ = _text_starter_with_ai_conv(summary=summary)
            await starter.initialize()
            conv.restore_from_summary.assert_called_once_with(summary)

    async def test_terminal_stage_no_restore(self):
        summary = _make_summary(final_stage=ConversationStage.FINALIZE)
        starter, conv, _ = _text_starter_with_ai_conv(summary=summary)
        await starter.initialize()
        conv.restore_from_summary.assert_not_called()
        assert "session_resume_context" in conv.context

    async def test_resume_context_present_before_greeting_llm_call(self):
        """session_resume_context must be set in context before generate_greeting_text is called."""
        captured_ctx = {}

        async def _capture_greeting(**kw):
            captured_ctx.update(conv.context)
            return "Hello!"

        summary = _make_summary(final_stage=ConversationStage.TRIAGE)
        starter, conv, _ = _text_starter_with_ai_conv(summary=summary)
        conv.generate_greeting_text = AsyncMock(side_effect=_capture_greeting)
        await starter.initialize()
        assert "session_resume_context" in captured_ctx


# ══════════════════════════════════════════════════════════════════════════════
# Tests: VoiceSessionStarter — is_ai_speaking deferred until playback drains
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceStarterSpeakingFlagTiming:
    """is_ai_speaking must stay True until monitor_playback_fn completes.

    Clearing the speaking flag immediately after TTS streaming finishes (but
    before buffered audio has played) lets _stt_session misclassify the
    still-playing greeting audio as user speech.  The monitor_playback_fn
    defers the flag-clear until the output-track queue is empty.
    """

    async def test_speaking_false_deferred_while_monitor_blocks(self):
        """With a blocking monitor_playback_fn, on_speaking_change(False) must
        NOT fire when initialized_event is set — only after the monitor yields."""
        monitor_finished = asyncio.Event()

        async def slow_monitor():
            await monitor_finished.wait()

        starter, deps = _voice_starter()
        starter._monitor_playback_fn = slow_monitor
        calls: list = []
        deps["on_speaking_change"].side_effect = lambda v: calls.append(v)

        task = asyncio.create_task(starter.initialize())
        await asyncio.wait_for(starter.initialized_event.wait(), timeout=2.0)

        # Yield control so the monitor task can be scheduled (but it will block)
        await asyncio.sleep(0)

        assert False not in calls, (
            f"on_speaking_change(False) fired before monitor completed; calls={calls}"
        )

        # Unblock monitor so the task and test both complete cleanly
        monitor_finished.set()
        await asyncio.sleep(0)
        await task

    async def test_speaking_false_immediate_when_interrupted(self):
        """When interrupt_event is set, on_speaking_change(False) fires in the
        finally block rather than being delegated to the monitor."""
        interrupt_event = asyncio.Event()
        interrupt_event.set()  # simulate an interrupt before TTS finishes

        async def dummy_monitor():
            pass

        starter, deps = _voice_starter(interrupt_event=interrupt_event)
        starter._monitor_playback_fn = dummy_monitor
        calls: list = []
        deps["on_speaking_change"].side_effect = lambda v: calls.append(v)

        await starter.initialize()

        assert True in calls, "on_speaking_change(True) must have been called first"
        assert calls[-1] is False, (
            "on_speaking_change(False) must fire immediately when interrupted"
        )

    async def test_speaking_false_immediate_when_no_monitor(self):
        """Without a monitor_playback_fn (backward-compatible path) the finally
        block clears the flag immediately, as before the deferred-clear feature."""
        starter, deps = _voice_starter()
        # _monitor_playback_fn defaults to None — no change needed
        calls: list = []
        deps["on_speaking_change"].side_effect = lambda v: calls.append(v)

        await starter.initialize()

        assert True in calls, "on_speaking_change(True) must have been called first"
        assert calls[-1] is False, (
            "on_speaking_change(False) must fire immediately when no monitor provided"
        )
