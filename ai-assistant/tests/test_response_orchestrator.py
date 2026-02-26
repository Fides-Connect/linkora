"""
Unit tests for ResponseOrchestrator — agentic brain.
Tests stage ownership, signal_transition handling, tool dispatch,
FSM ownership, and provider search triggered by signal_transition.
"""
import pytest
from unittest.mock import Mock, AsyncMock

from ai_assistant.services.conversation_service import ConversationStage
from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState, AgentRuntimeFSM
from ai_assistant.services.agent_tools import (
    AgentToolRegistry, ToolCapability, ToolPermissionError,
)
from ai_assistant.services.response_orchestrator import ResponseOrchestrator


@pytest.fixture
def mock_llm_service():
    service = Mock()

    async def mock_generate_stream(*args, **kwargs):
        yield "Test "
        yield "response"

    service.generate_stream = mock_generate_stream
    return service


@pytest.fixture
def mock_conversation_service():
    service = Mock()
    service.get_current_stage = Mock(return_value=ConversationStage.TRIAGE)
    service.accumulate_problem_description = AsyncMock()
    service.search_providers_for_request = AsyncMock()
    service.record_ai_response = Mock()
    service.set_stage = Mock()
    service.create_prompt_for_stage = Mock(return_value="prompt")
    service.context = {
        "user_problem": [],
        "providers_found": [],
        "current_provider_index": 0,
    }
    return service


@pytest.fixture
def mock_tool_registry():
    registry = Mock(spec=AgentToolRegistry)
    registry.execute = AsyncMock(return_value={"result": "ok"})
    registry.all_schemas.return_value = []
    return registry


@pytest.fixture
def orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry):
    return ResponseOrchestrator(
        llm_service=mock_llm_service,
        conversation_service=mock_conversation_service,
        tool_registry=mock_tool_registry,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FSM ownership
# ─────────────────────────────────────────────────────────────────────────────

class TestOrchestratorOwnsFSMs:

    def test_runtime_fsm_is_agent_runtime_fsm(self, orchestrator):
        assert isinstance(orchestrator.runtime_fsm, AgentRuntimeFSM)

    def test_runtime_fsm_starts_at_bootstrap(self, orchestrator):
        assert orchestrator.runtime_fsm.current_state == AgentRuntimeState.BOOTSTRAP


# ─────────────────────────────────────────────────────────────────────────────
# handle_signal_transition (sync)
# ─────────────────────────────────────────────────────────────────────────────

class TestHandleSignalTransition:

    def test_legal_target_calls_set_stage(self, orchestrator, mock_conversation_service):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        orchestrator.handle_signal_transition("finalize")
        mock_conversation_service.set_stage.assert_called_once_with(ConversationStage.FINALIZE)

    def test_legal_target_returns_true(self, orchestrator, mock_conversation_service):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        assert orchestrator.handle_signal_transition("clarify") is True

    def test_unknown_string_does_not_call_set_stage(self, orchestrator, mock_conversation_service):
        orchestrator.handle_signal_transition("bogus_stage")
        mock_conversation_service.set_stage.assert_not_called()

    def test_unknown_string_returns_false(self, orchestrator):
        assert orchestrator.handle_signal_transition("completely_unknown") is False

    def test_illegal_jump_does_not_call_set_stage(self, orchestrator, mock_conversation_service):
        # TRIAGE → COMPLETED is not a legal transition
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        orchestrator.handle_signal_transition("completed")
        mock_conversation_service.set_stage.assert_not_called()

    def test_illegal_jump_returns_false(self, orchestrator, mock_conversation_service):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.GREETING
        assert orchestrator.handle_signal_transition("completed") is False

    async def test_finalize_target_also_triggers_provider_search(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        await orchestrator.handle_signal_transition_async("finalize")
        mock_conversation_service.search_providers_for_request.assert_called_once()

    async def test_non_finalize_target_does_not_trigger_search(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        await orchestrator.handle_signal_transition_async("clarify")
        mock_conversation_service.search_providers_for_request.assert_not_called()

    async def test_finalize_target_forwards_session_id_to_search(
        self, orchestrator, mock_conversation_service
    ):
        """session_id is forwarded to search_providers_for_request on FINALIZE."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        await orchestrator.handle_signal_transition_async("finalize", session_id="sess-42")
        mock_conversation_service.search_providers_for_request.assert_called_once_with("sess-42")


# ─────────────────────────────────────────────────────────────────────────────
# dispatch_tool
# ─────────────────────────────────────────────────────────────────────────────

class TestToolDispatch:

    async def test_happy_path_calls_registry_execute(
        self, orchestrator, mock_tool_registry
    ):
        ctx = {
            "user_id": "u1",
            "user_capabilities": [ToolCapability("providers", "read")],
        }
        chunks = []
        async for chunk in orchestrator.dispatch_tool("search_providers", {"query": "plumber"}, ctx):
            chunks.append(chunk)

        mock_tool_registry.execute.assert_called_once_with(
            "search_providers", {"query": "plumber"}, ctx
        )

    async def test_permission_denied_yields_error_dict(
        self, orchestrator, mock_tool_registry
    ):
        mock_tool_registry.execute.side_effect = ToolPermissionError(
            "search_providers", ToolCapability("providers", "read")
        )
        ctx = {"user_id": "u1", "user_capabilities": []}
        chunks = []
        async for chunk in orchestrator.dispatch_tool("search_providers", {}, ctx):
            chunks.append(chunk)

        assert any(
            isinstance(c, dict) and c.get("error") == "permission_denied"
            for c in chunks
        )

    async def test_unknown_tool_yields_error_dict(
        self, orchestrator, mock_tool_registry
    ):
        mock_tool_registry.execute.side_effect = KeyError("no_such_tool")
        ctx = {"user_id": "u1", "user_capabilities": []}
        chunks = []
        async for chunk in orchestrator.dispatch_tool("no_such_tool", {}, ctx):
            chunks.append(chunk)

        assert any(
            isinstance(c, dict) and c.get("error") == "unknown_tool"
            for c in chunks
        )


# ─────────────────────────────────────────────────────────────────────────────
# Provider search triggered by signal_transition("finalize") in stream
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderSearchViaSignalTransition:

    async def test_search_not_called_without_signal_transition(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        # LLM stream produces only text — no function-call chunks
        async for _ in orchestrator.generate_response_stream("hi", "sess"):
            pass
        mock_conversation_service.search_providers_for_request.assert_not_called()

    async def test_search_called_when_signal_transition_finalize_received(
        self, orchestrator, mock_conversation_service, mock_llm_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE

        async def stream_with_transition(*args, **kwargs):
            yield "Searching now..."
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "finalize"}}

        mock_llm_service.generate_stream = stream_with_transition
        async for _ in orchestrator.generate_response_stream("ready", "sess"):
            pass

        mock_conversation_service.set_stage.assert_called_with(ConversationStage.FINALIZE)
        mock_conversation_service.search_providers_for_request.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Timing: accumulate + no-double-search guards
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderSearchTiming:

    async def test_no_search_during_triage_without_signal(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        async for _ in orchestrator.generate_response_stream(
            "Ich brauche einen Elektriker", "test-session"
        ):
            pass
        mock_conversation_service.search_providers_for_request.assert_not_called()

    async def test_accumulate_called_in_triage(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        async for _ in orchestrator.generate_response_stream("some input", "test-session"):
            pass
        mock_conversation_service.accumulate_problem_description.assert_called_once_with(
            "some input"
        )

    async def test_no_accumulate_in_greeting(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.GREETING
        async for _ in orchestrator.generate_response_stream("Hallo", "test-session"):
            pass
        mock_conversation_service.accumulate_problem_description.assert_not_called()

    async def test_no_accumulate_in_finalize(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE
        async for _ in orchestrator.generate_response_stream("Ja bitte", "test-session"):
            pass
        mock_conversation_service.accumulate_problem_description.assert_not_called()


# ───────────────────────────────────────────────────────────────────────────────
# record_ai_response called after every stream
# ───────────────────────────────────────────────────────────────────────────────

class TestRecordAiResponseInOrchestrator:
    """record_ai_response must be called after every generate_response_stream."""

    async def test_record_ai_response_called_with_assembled_text(
        self, orchestrator, mock_conversation_service
    ):
        """Assembled LLM text is forwarded to conversation context after stream."""
        async for _ in orchestrator.generate_response_stream("hi", "sess"):
            pass
        # Default mock yields "Test " + "response"
        mock_conversation_service.record_ai_response.assert_called_once_with("Test response")

    async def test_record_ai_response_called_even_when_only_tool_calls(
        self, orchestrator, mock_conversation_service, mock_llm_service
    ):
        """record_ai_response is called with empty string when stream has no text chunks."""
        async def tool_only_stream(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "clarify"}}

        mock_llm_service.generate_stream = tool_only_stream
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        async for _ in orchestrator.generate_response_stream("hi", "sess"):
            pass
        mock_conversation_service.record_ai_response.assert_called_once_with("")


# ─────────────────────────────────────────────────────────────────────────────
# Tool-call text filter
# ─────────────────────────────────────────────────────────────────────────────

class TestToolCallTextFilter:
    """signal_transition(...) and any identifier(...) patterns must be stripped."""

    async def test_signal_transition_text_is_stripped(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Plain-text signal_transition(...) emitted by LLM must not reach the caller."""
        async def leaky_stream(*args, **kwargs):
            yield "Ich leite weiter. "
            yield "signal_transition(finalize)"

        mock_llm_service.generate_stream = leaky_stream
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("hi", "sess"):
            chunks.append(chunk)
        combined = "".join(chunks)
        assert "signal_transition" not in combined

    async def test_generic_tool_call_text_is_stripped(
        self, mock_llm_service, mock_conversation_service
    ):
        """Known tool names leaked as plain text must be stripped."""
        async def leaky_stream(*args, **kwargs):
            yield "Calling search_providers(query='plumber') now."

        mock_llm_service.generate_stream = leaky_stream
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("hi", "sess"):
            chunks.append(chunk)
        combined = "".join(chunks)
        assert "search_providers" not in combined

    async def test_normal_text_with_parens_is_not_stripped(
        self, mock_llm_service, mock_conversation_service
    ):
        """Normal prose containing parentheses must NOT be stripped."""
        async def natural_stream(*args, **kwargs):
            yield "I'll help you find(locate) the best providers in your area."

        mock_llm_service.generate_stream = natural_stream
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("hi", "sess"):
            chunks.append(chunk)
        combined = "".join(chunks)
        # "find" is not a known tool name so its parenthesized form must survive
        assert "find" in combined

    async def test_clean_text_passes_through(
        self, mock_llm_service, mock_conversation_service
    ):
        """Text with no tool-call patterns must be forwarded unchanged."""
        async def clean_stream(*args, **kwargs):
            yield "Hallo, ich helfe dir gerne!"

        mock_llm_service.generate_stream = clean_stream
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("hi", "sess"):
            chunks.append(chunk)
        assert "Hallo, ich helfe dir gerne!" in "".join(chunks)

    async def test_chunk_that_becomes_empty_after_strip_is_not_yielded(
        self, mock_llm_service, mock_conversation_service
    ):
        """A chunk that is purely a tool-call pattern must not be yielded at all."""
        async def pure_tool_stream(*args, **kwargs):
            yield "signal_transition(triage)"

        mock_llm_service.generate_stream = pure_tool_stream
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("hi", "sess"):
            chunks.append(chunk)
        # Nothing should be yielded
        assert chunks == [] or all(c.strip() == "" for c in chunks)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL_TRANSITION_SCHEMA tool registration
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalTransitionToolRegistration:
    """register_functions must be called with SIGNAL_TRANSITION_SCHEMA per stream."""

    async def test_register_functions_called_each_stream(
        self, mock_conversation_service
    ):
        from ai_assistant.services.llm_service import SIGNAL_TRANSITION_SCHEMA

        llm = Mock()
        llm.register_functions = Mock()

        async def noop_stream(*args, **kwargs):
            if False:
                yield ""

        llm.generate_stream = noop_stream

        orch = ResponseOrchestrator(
            llm_service=llm,
            conversation_service=mock_conversation_service,
        )
        async for _ in orch.generate_response_stream("hello", "sess-1"):
            pass

        call_args = llm.register_functions.call_args
        assert call_args[0][0] == "sess-1"
        assert SIGNAL_TRANSITION_SCHEMA in call_args[0][1]

    async def test_register_functions_called_with_correct_session_id(
        self, mock_conversation_service
    ):
        from ai_assistant.services.llm_service import SIGNAL_TRANSITION_SCHEMA

        llm = Mock()
        llm.register_functions = Mock()

        async def noop_stream(*args, **kwargs):
            if False:
                yield ""

        llm.generate_stream = noop_stream

        orch = ResponseOrchestrator(
            llm_service=llm,
            conversation_service=mock_conversation_service,
        )
        async for _ in orch.generate_response_stream("hello", "my-session-42"):
            pass

        call_args = llm.register_functions.call_args
        assert call_args[0][0] == "my-session-42"
        assert SIGNAL_TRANSITION_SCHEMA in call_args[0][1]


# ─────────────────────────────────────────────────────────────────────────────
# FSM transitions fired during stream
# ─────────────────────────────────────────────────────────────────────────────

class TestFsmTransitionsDuringStream:
    """Key FSM events must be fired at the right points in generate_response_stream."""

    def _make_orch_with_real_fsm(self, mock_llm_service, mock_conversation_service):
        fsm = AgentRuntimeFSM()
        # Advance to LISTENING so the THINKING transition can fire
        fsm.transition("data_channel_wait")
        fsm.transition("data_channel_opened")
        return ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            runtime_fsm=fsm,
        ), fsm

    async def test_llm_stream_started_fires_on_first_chunk(
        self, mock_llm_service, mock_conversation_service
    ):
        async def one_chunk(*args, **kwargs):
            yield "Hello"

        mock_llm_service.generate_stream = one_chunk
        orch, fsm = self._make_orch_with_real_fsm(mock_llm_service, mock_conversation_service)
        # Prime to THINKING
        fsm.transition("final_transcript")
        assert fsm.current_state == AgentRuntimeState.THINKING

        async for _ in orch.generate_response_stream("hi", "sess"):
            pass

        # After text stream completes we should be back at LISTENING
        assert fsm.current_state == AgentRuntimeState.LISTENING

    async def test_tool_call_and_tool_done_fired_around_signal_transition(
        self, mock_llm_service, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE

        async def stream_with_fn(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "finalize"}}

        mock_llm_service.generate_stream = stream_with_fn
        orch, fsm = self._make_orch_with_real_fsm(mock_llm_service, mock_conversation_service)
        fsm.transition("final_transcript")

        states_seen = []
        fsm.on_state_change = lambda _old, new: states_seen.append(new)

        async for _ in orch.generate_response_stream("ready", "sess"):
            pass

        assert AgentRuntimeState.TOOL_EXECUTING in states_seen

    async def test_stream_complete_text_fires_at_end(
        self, mock_llm_service, mock_conversation_service
    ):
        async def text_only(*args, **kwargs):
            yield "Done"

        mock_llm_service.generate_stream = text_only
        orch, fsm = self._make_orch_with_real_fsm(mock_llm_service, mock_conversation_service)
        fsm.transition("final_transcript")

        async for _ in orch.generate_response_stream("hi", "sess"):
            pass

        assert fsm.current_state == AgentRuntimeState.LISTENING


# ─────────────────────────────────────────────────────────────────────────────
# AIConversationService integration inside the orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class TestAIConversationServiceIntegration:
    """Orchestrator must delegate message persistence to AIConversationService."""

    def _make_ai_conv_svc(self):
        svc = Mock()
        svc.save_message = AsyncMock()
        svc.set_topic_title = AsyncMock()
        svc.close_session = AsyncMock()
        return svc

    async def test_user_message_saved_before_stream(
        self, mock_llm_service, mock_conversation_service
    ):
        ai_conv = self._make_ai_conv_svc()

        async def noop(*args, **kwargs):
            if False:
                yield ""

        mock_llm_service.generate_stream = noop
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            ai_conversation_service=ai_conv,
        )
        async for _ in orch.generate_response_stream("My problem", "sess"):
            pass

        # First save_message call must be the user turn
        first_call = ai_conv.save_message.call_args_list[0]
        assert first_call[1]["role"] == "user" or first_call[0][0] == "user"

    async def test_ai_response_saved_after_stream(
        self, mock_llm_service, mock_conversation_service
    ):
        ai_conv = self._make_ai_conv_svc()
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            ai_conversation_service=ai_conv,
        )
        async for _ in orch.generate_response_stream("hi", "sess"):
            pass

        # At least two save_message calls: user + assistant
        assert ai_conv.save_message.call_count >= 2
        # Last save must be the assistant turn
        last_call = ai_conv.save_message.call_args_list[-1]
        role_arg = last_call[1].get("role") or last_call[0][0]
        assert role_arg == "assistant"

    async def test_set_topic_title_called_on_finalize_transition(
        self, mock_llm_service, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.get_problem_summary = Mock(return_value="Elektriker")

        ai_conv = self._make_ai_conv_svc()

        async def stream_with_finalize(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "finalize"}}

        mock_llm_service.generate_stream = stream_with_finalize
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            ai_conversation_service=ai_conv,
        )
        async for _ in orch.generate_response_stream("ready", "sess"):
            pass

        ai_conv.set_topic_title.assert_called_once()

    async def test_close_session_not_called_on_completed_stage(
        self, mock_llm_service, mock_conversation_service
    ):
        """Session must stay open when COMPLETED so the loop-back can continue."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE

        ai_conv = self._make_ai_conv_svc()

        async def stream_with_completed(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "completed"}}

        mock_llm_service.generate_stream = stream_with_completed

        # Make FINALIZE→COMPLETED a legal transition for this test
        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                ai_conversation_service=ai_conv,
            )
            async for _ in orch.generate_response_stream("done", "sess"):
                pass

        ai_conv.close_session.assert_not_called()

    async def test_no_error_when_ai_conversation_service_is_none(
        self, mock_llm_service, mock_conversation_service
    ):
        """Orchestrator must work normally when ai_conversation_service is not provided."""
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("hi", "sess"):
            chunks.append(chunk)
        assert len(chunks) > 0

    async def test_finalize_presentation_persisted_to_firestore(
        self, mock_llm_service, mock_conversation_service
    ):
        """Provider presentation text generated after FINALIZE must be saved."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        ai_conv = self._make_ai_conv_svc()

        call_count = 0

        async def multi_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Main stream: trigger the stage transition
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "finalize"}}
            else:
                # Finalize presentation stream
                yield "Here are 3 providers for you..."

        mock_llm_service.generate_stream = multi_stream
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            ai_conversation_service=ai_conv,
        )
        async for _ in orch.generate_response_stream("ready", "sess"):
            pass

        # A save_message call with stage=FINALIZE must exist for the presentation
        finalize_saves = [
            c for c in ai_conv.save_message.call_args_list
            if c[1].get("stage") == ConversationStage.FINALIZE
        ]
        assert len(finalize_saves) == 1
        assert "providers" in finalize_saves[0][1]["text"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Provider pitch eligibility helper
# ─────────────────────────────────────────────────────────────────────────────

class TestShouldPitchProvider:
    """Unit tests for the _should_pitch_provider static helper."""

    def _ctx(self, is_provider=False, last_asked=None):
        return {
            "user_context": {
                "is_service_provider": is_provider,
                "last_time_asked_being_provider": last_asked,
            }
        }

    def test_returns_false_when_no_user_context(self):
        assert ResponseOrchestrator._should_pitch_provider({}) is False

    def test_returns_false_when_already_provider(self):
        from datetime import datetime, timezone, timedelta
        last_asked = datetime.now(timezone.utc) - timedelta(days=60)
        assert ResponseOrchestrator._should_pitch_provider(
            self._ctx(is_provider=True, last_asked=last_asked)
        ) is False

    def test_returns_false_when_timestamp_is_none(self):
        assert ResponseOrchestrator._should_pitch_provider(
            self._ctx(is_provider=False, last_asked=None)
        ) is False

    def test_returns_false_when_opted_out(self):
        from ai_assistant.firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL
        assert ResponseOrchestrator._should_pitch_provider(
            self._ctx(is_provider=False, last_asked=PROVIDER_PITCH_OPT_OUT_SENTINEL)
        ) is False

    def test_returns_false_when_asked_recently(self):
        from datetime import datetime, timezone, timedelta
        last_asked = datetime.now(timezone.utc) - timedelta(days=10)
        assert ResponseOrchestrator._should_pitch_provider(
            self._ctx(is_provider=False, last_asked=last_asked)
        ) is False

    def test_returns_true_when_all_conditions_met(self):
        from datetime import datetime, timezone, timedelta
        last_asked = datetime.now(timezone.utc) - timedelta(days=60)
        assert ResponseOrchestrator._should_pitch_provider(
            self._ctx(is_provider=False, last_asked=last_asked)
        ) is True


# ─────────────────────────────────────────────────────────────────────────────
# Provider pitch fires after COMPLETED when eligible
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderPitchAfterCompleted:

    def _eligible_ctx(self):
        from datetime import datetime, timezone, timedelta
        return {
            "user_context": {
                "is_service_provider": False,
                "last_time_asked_being_provider": datetime.now(timezone.utc) - timedelta(days=60),
            }
        }

    async def test_pitch_fires_when_eligible(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE

        async def stream_with_completed(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "completed"}}

        mock_llm_service.generate_stream = stream_with_completed

        from unittest.mock import patch
        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("done", "sess", context=self._eligible_ctx()):
                pass

        set_stage_calls = [call[0][0] for call in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.PROVIDER_PITCH in set_stage_calls

    async def test_pitch_skipped_when_already_provider(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE

        async def stream_with_completed(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "completed"}}

        mock_llm_service.generate_stream = stream_with_completed
        ineligible_ctx = {"user_context": {"is_service_provider": True, "last_time_asked_being_provider": None}}

        from unittest.mock import patch
        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("done", "sess", context=ineligible_ctx):
                pass

        set_stage_calls = [call[0][0] for call in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.PROVIDER_PITCH not in set_stage_calls

    async def test_pitch_skipped_when_no_user_context(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE

        async def stream_with_completed(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "completed"}}

        mock_llm_service.generate_stream = stream_with_completed

        from unittest.mock import patch
        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            # No user_context in the context dict
            async for _ in orch.generate_response_stream("done", "sess", context={}):
                pass

        set_stage_calls = [call[0][0] for call in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.PROVIDER_PITCH not in set_stage_calls


# ─────────────────────────────────────────────────────────────────────────────
# Tool result containing signal_transition key
# ─────────────────────────────────────────────────────────────────────────────

class TestToolResultSignalTransition:
    """When a tool returns {"signal_transition": "stage"}, the orchestrator applies it."""

    async def test_tool_result_signal_triggers_stage_change(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.PROVIDER_PITCH

        async def stream_with_tool_call(*args, **kwargs):
            yield {"type": "function_call", "name": "record_provider_interest",
                   "args": {"decision": "accepted"}}

        mock_llm_service.generate_stream = stream_with_tool_call
        mock_tool_registry.execute = AsyncMock(
            return_value={"signal_transition": "provider_onboarding", "status": "accepted"}
        )

        from unittest.mock import patch
        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("yes", "sess"):
                pass

        set_stage_calls = [call[0][0] for call in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.PROVIDER_ONBOARDING in set_stage_calls
