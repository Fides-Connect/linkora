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

    async def test_advances_stage_to_triage(self):
        starter, deps = _voice_starter()
        await starter.initialize()
        deps["orchestrator"].handle_signal_transition_async.assert_called_once_with("triage")

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

    async def test_stage_advanced_even_on_error(self):
        starter, deps = _voice_starter()
        deps["conversation_service"].generate_greeting_text = AsyncMock(
            side_effect=RuntimeError("LLM error")
        )
        await starter.initialize()
        # Fallback sync transition is used on error
        deps["orchestrator"].handle_signal_transition.assert_called_with("triage")


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

    async def test_advances_stage_to_triage(self):
        starter, deps = _text_starter()
        await starter.initialize()
        deps["orchestrator"].handle_signal_transition.assert_called_once_with("triage")

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

    async def test_stage_advanced_even_when_greeting_fails(self):
        starter, deps = _text_starter()
        deps["conversation_service"].generate_greeting_text = AsyncMock(
            side_effect=RuntimeError("LLM exploded")
        )
        await starter.initialize()  # must not raise
        assert starter.initialized_event.is_set()
        deps["orchestrator"].handle_signal_transition.assert_called_with("triage")


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
