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
        mock_conversation_service.get_current_stage.return_value = ConversationStage.CONFIRMATION
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

    async def test_finalize_target_is_thin_wrapper_no_side_effects(
        self, orchestrator, mock_conversation_service
    ):
        """handle_signal_transition_async is now a thin wrapper: it applies the
        stage but does NOT trigger provider search.  Side effects (search,
        competency fetch, context reset) are handled by
        _apply_signal_transition_with_payload inside generate_response_stream."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.CONFIRMATION
        result = await orchestrator.handle_signal_transition_async("finalize")
        assert result is True
        mock_conversation_service.search_providers_for_request.assert_not_called()

    async def test_non_finalize_target_does_not_trigger_search(
        self, orchestrator, mock_conversation_service
    ):
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        await orchestrator.handle_signal_transition_async("clarify")
        mock_conversation_service.search_providers_for_request.assert_not_called()

    async def test_apply_payload_finalize_calls_search_with_session_id(
        self, orchestrator, mock_conversation_service
    ):
        """_apply_signal_transition_with_payload triggers search and forwards session_id.
        When providers are found, the payload has stage='finalize' and current_provider."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.CONFIRMATION
        mock_conversation_service.context["providers_found"] = [{"user": {"user_id": "p1", "name": "Alice"}, "title": "Electrical work", "score": 0.9}]
        pending: list = []
        await orchestrator._apply_signal_transition_with_payload(
            "finalize", "sess-42", None, pending
        )
        mock_conversation_service.search_providers_for_request.assert_called_once_with("sess-42")
        assert any(r.get("stage") == "finalize" for _, r in pending)

    async def test_apply_payload_finalize_zero_results_bypasses_to_triage(
        self, orchestrator, mock_conversation_service
    ):
        """Zero providers found: FINALIZE bypasses to TRIAGE with zero_result_event."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.CONFIRMATION
        mock_conversation_service.context["providers_found"] = []
        pending: list = []
        await orchestrator._apply_signal_transition_with_payload(
            "finalize", "sess-42", None, pending
        )
        mock_conversation_service.search_providers_for_request.assert_called_once_with("sess-42")
        assert any(
            isinstance(r, dict) and r.get("stage") == "triage" and "zero_result_event" in r
            for _, r in pending
        ), f"Expected triage+zero_result_event in pending, got: {pending}"

    async def test_finalize_from_provider_onboarding_skips_provider_search(
        self, orchestrator, mock_conversation_service
    ):
        """PROVIDER_ONBOARDING → FINALIZE is illegal; even if forced, search must not run."""
        # PROVIDER_ONBOARDING → FINALIZE is not in _LEGAL_TRANSITIONS, so the
        # transition is rejected and search_providers_for_request must not be called.
        mock_conversation_service.get_current_stage.return_value = ConversationStage.PROVIDER_ONBOARDING
        result = await orchestrator.handle_signal_transition_async("finalize")
        assert result is False
        mock_conversation_service.search_providers_for_request.assert_not_called()

    async def test_finalize_from_provider_onboarding_guard_if_stage_bypassed(
        self, orchestrator, mock_conversation_service
    ):
        """Even if set_stage fires (e.g. mock bypass), the guard skips the search."""
        # Simulate previous_stage == PROVIDER_ONBOARDING by returning it on the first
        # get_current_stage call, then returning FINALIZE after set_stage is called.
        mock_conversation_service.get_current_stage.side_effect = [
            ConversationStage.PROVIDER_ONBOARDING,  # queried as previous_stage
            ConversationStage.FINALIZE,              # queried later
        ]
        # Make is_legal_transition accept the transition so the applied path runs.
        mock_conversation_service.set_stage.return_value = None  # no-op

        # Patch the legality check by making the service return True for set_stage call.
        # We bypass by calling the internal sync helper with a forged legal response.
        # The simplest approach: patch handle_signal_transition to return True.
        original = orchestrator.handle_signal_transition
        orchestrator.handle_signal_transition = Mock(return_value=True)
        try:
            await orchestrator.handle_signal_transition_async("finalize")
        finally:
            orchestrator.handle_signal_transition = original

        mock_conversation_service.search_providers_for_request.assert_not_called()


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
        mock_conversation_service.get_current_stage.return_value = ConversationStage.CONFIRMATION
        # Provide at least one provider so the zero-result bypass does not fire.
        mock_conversation_service.context["providers_found"] = [{"user": {"user_id": "p1", "name": "Alice"}, "title": "Electrical work", "score": 0.9}]
        call_count = 0

        async def stream_with_transition(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield "Searching now..."
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "finalize"}}
            else:
                # Follow-up presentation stream — yield text only, no new transition
                yield "Here are your providers."

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
            "I need an electrician", "test-session"
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
        mock_conversation_service.get_current_stage.return_value = ConversationStage.CONFIRMATION
        mock_conversation_service.get_problem_summary = Mock(return_value="electrician")

        ai_conv = self._make_ai_conv_svc()
        call_count = 0

        async def stream_with_finalize(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "finalize"}}
            else:
                yield "Here are providers."

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

        # A save_message call with the presentation text must exist
        presentation_saves = [
            c for c in ai_conv.save_message.call_args_list
            if "providers" in (c[1].get("text") or "").lower()
        ]
        assert len(presentation_saves) == 1, (
            f"Expected 1 save_message with 'providers' in text; "
            f"got {len(presentation_saves)}: {[c[1] for c in ai_conv.save_message.call_args_list]}"
        )


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


# ─────────────────────────────────────────────────────────────────────────────
# Follow-up stream signal_transition handling
# ─────────────────────────────────────────────────────────────────────────────

class TestFollowUpStreamSignalTransition:
    """When a tool is called in the main stream, the follow-up stream may emit a
    signal_transition function call.  The orchestrator must handle it — not drop it.

    Regression for bug: follow-up stream only processed str chunks, so
    signal_transition("completed") from PROVIDER_ONBOARDING was silently discarded,
    leaving the user with no response and no loop-back.
    """

    async def test_signal_transition_in_follow_up_stream_advances_stage(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """signal_transition("completed") emitted in the follow-up stream must be applied."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.PROVIDER_ONBOARDING

        call_count = 0

        async def multi_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Main stream: LLM calls save_competence_batch
                yield {"type": "function_call", "name": "save_competence_batch",
                       "args": {"skills": [{"title": "Plumbing"}]}}
            else:
                # Follow-up stream: LLM first confirms success in text, then transitions
                yield "Your skills have been saved successfully!"
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "completed"}}

        mock_llm_service.generate_stream = multi_stream
        mock_tool_registry.execute = AsyncMock(
            return_value={"saved": [{"competence_id": "c1"}], "count": 1}
        )

        from unittest.mock import patch
        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            chunks = []
            async for chunk in orch.generate_response_stream("yes", "sess"):
                chunks.append(chunk)

        set_stage_calls = [call[0][0] for call in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.COMPLETED in set_stage_calls, (
            "signal_transition('completed') in the follow-up stream must advance the stage"
        )

    async def test_text_from_follow_up_stream_is_yielded(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Text chunks yielded by the follow-up stream must reach the caller."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.PROVIDER_ONBOARDING

        call_count = 0

        async def multi_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "save_competence_batch",
                       "args": {"skills": [{"title": "Gardening"}]}}
            else:
                yield "Your competencies are live on your profile!"

        mock_llm_service.generate_stream = multi_stream
        mock_tool_registry.execute = AsyncMock(
            return_value={"saved": [{"competence_id": "c2"}], "count": 1}
        )

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        chunks = []
        async for chunk in orch.generate_response_stream("yes", "sess"):
            if isinstance(chunk, str):
                chunks.append(chunk)

        combined = "".join(chunks)
        assert "competencies are live" in combined, (
            "Confirmation text from the follow-up stream must reach the caller"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TRIAGE → PROVIDER_ONBOARDING opener
# ─────────────────────────────────────────────────────────────────────────────

class TestTriageToProviderOnboardingOpener:
    """When TRIAGE calls signal_transition('provider_onboarding'), the orchestrator must:
    1. pre-fetch competencies immediately,
    2. trigger a follow-up LLM stream (so the user receives an opening message),
    3. use the PROVIDER_ONBOARDING prompt for that follow-up.
    """

    async def test_follow_up_stream_fires_after_triage_to_provider_onboarding(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """A follow-up LLM stream must run after the TRIAGE→PROVIDER_ONBOARDING
        transition so the user sees the competency opener.
        The opener must pass the original user_input (not a whitespace placeholder)
        to avoid injecting a spurious HumanMessage into LLM history."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_tool_registry.execute = AsyncMock(return_value=[{"title": "Plumbing"}])

        call_count = 0
        call_inputs: list[str] = []

        async def stream(prompt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            call_inputs.append(prompt)
            if call_count == 1:
                # Main TRIAGE stream: only a signal_transition, no text
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "provider_onboarding"}}
            else:
                # Follow-up PROVIDER_ONBOARDING stream: opener text
                yield "You have Plumbing registered."

        mock_llm_service.generate_stream = stream
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }

        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            chunks = []
            async for chunk in orch.generate_response_stream("show me my skills", "sess"):
                if isinstance(chunk, str):
                    chunks.append(chunk)

        assert call_count == 2, (
            "LLM must be called twice: once for TRIAGE, once for the PROVIDER_ONBOARDING opener"
        )
        assert "Plumbing" in "".join(chunks), (
            "The PROVIDER_ONBOARDING opener text must reach the caller"
        )
        # Opener must receive the real user input, not a whitespace placeholder,
        # to avoid consecutive HumanMessage(" ") entries in LLM history.
        assert call_inputs[1] == "show me my skills", (
            "The opener must pass the original user_input to generate_stream, "
            f"not a whitespace placeholder. Got: {call_inputs[1]!r}"
        )

    async def test_competencies_prefetched_before_followup_on_provider_onboarding_entry(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Competencies must be fetched before the follow-up stream runs so the
        PROVIDER_ONBOARDING prompt has the correct `current_competencies_json`."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_tool_registry.execute = AsyncMock(return_value=[{"title": "Gardening"}])

        async def stream(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "provider_onboarding"}}

        mock_llm_service.generate_stream = stream
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }

        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("show my skills", "sess"):
                pass

        competencies = mock_conversation_service.context.get("current_competencies", [])
        assert competencies == [{"title": "Gardening"}], (
            "Competencies must be pre-fetched and stored in context before the follow-up stream"
        )


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER_ONBOARDING write-before-complete guard
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderOnboardingWriteGuard:
    """Competence interview pipeline: pre-fetch, post-write refresh, and guard behaviour.

    The guard is now a soft warning: signal_transition('completed') from
    PROVIDER_ONBOARDING is always allowed so the "user chose no changes" path
    works without a write tool call.
    """

    async def test_signal_transition_completed_allowed_without_prior_write(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """signal_transition('completed') without a prior write tool must be ALLOWED:
        this is the 'user chose no changes' path.  Stage must advance to COMPLETED
        and no blocking error must be fed to LLM history."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        call_count = 0

        async def stream_signal_only(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Main stream: signal_transition only, no write tool
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "completed"}}
            else:
                yield ""

        mock_llm_service.generate_stream = stream_signal_only
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }

        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("nothing to change", "sess"):
                pass

        # Stage must have advanced to COMPLETED
        set_stage_calls = [
            call[0][0] for call in mock_conversation_service.set_stage.call_args_list
        ]
        assert ConversationStage.COMPLETED in set_stage_calls, (
            "Stage must advance to COMPLETED when user chose no changes "
            "(signal_transition without prior write must be allowed)"
        )

        # No blocking error must have been fed to LLM history
        history_calls = mock_llm_service.add_message_to_history.call_args_list
        messages = [
            c[0][1].content for c in history_calls if hasattr(c[0][1], "content")
        ]
        assert not any(
            "cannot complete" in m.lower() or "must call save" in m.lower()
            for m in messages
        ), "A blocking error must NOT be fed to history for the no-changes path"

    async def test_signal_transition_completed_allowed_after_save_in_same_stream(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """If save_competence_batch is called earlier in the same stream, a subsequent
        signal_transition('completed') must be allowed."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }
        call_count = 0

        async def stream_save_then_signal(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "save_competence_batch",
                       "args": {"skills": [{"title": "Cycling"}]}}
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "completed"}}
            else:
                yield ""

        mock_llm_service.generate_stream = stream_save_then_signal
        mock_tool_registry.execute = AsyncMock(
            return_value={"saved": [{"competence_id": "c1"}], "count": 1}
        )

        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("yes", "sess"):
                pass

        set_stage_calls = [
            call[0][0] for call in mock_conversation_service.set_stage.call_args_list
        ]
        assert ConversationStage.COMPLETED in set_stage_calls, (
            "signal_transition('completed') must succeed when save_competence_batch "
            "was called earlier in the same stream"
        )

    async def test_pre_fetches_competencies_for_provider_onboarding_stage(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """When stage is PROVIDER_ONBOARDING the orchestrator must call
        get_my_competencies via the tool registry BEFORE the LLM stream
        and store the result in context['current_competencies']."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }

        fetched = [{"competence_id": "c1", "title": "Plumbing"}]
        call_order: list[str] = []

        async def execute_side_effect(name, params, ctx):
            call_order.append(name)
            if name == "get_my_competencies":
                return fetched
            return {"result": "ok"}

        mock_tool_registry.execute = execute_side_effect

        llm_called_after: list[bool] = []
        original_stream = mock_llm_service.generate_stream

        async def tracked_stream(*args, **kwargs):
            llm_called_after.append(
                "get_my_competencies" in call_order
            )
            yield "Done"

        mock_llm_service.generate_stream = tracked_stream

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream("manage skills", "sess"):
            pass

        assert mock_conversation_service.context["current_competencies"] == fetched, (
            "Pre-fetched competencies must be stored in context['current_competencies']"
        )
        assert llm_called_after and llm_called_after[0], (
            "get_my_competencies must be called before the LLM stream starts"
        )

    async def test_refreshes_competencies_after_write_tool(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """After save_competence_batch succeeds, get_my_competencies must be called
        again so context['current_competencies'] reflects the updated list."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }

        initial = [{"competence_id": "c1", "title": "Plumbing"}]
        after_save = [
            {"competence_id": "c1", "title": "Plumbing"},
            {"competence_id": "c2", "title": "Carpentry"},
        ]
        call_count_get = 0

        async def execute_side_effect(name, params, ctx):
            nonlocal call_count_get
            if name == "get_my_competencies":
                call_count_get += 1
                return initial if call_count_get == 1 else after_save
            if name == "save_competence_batch":
                return {"saved": [{"competence_id": "c2"}], "count": 1}
            return {"result": "ok"}

        mock_tool_registry.execute = execute_side_effect
        call_count = 0

        async def stream_with_save(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "save_competence_batch",
                       "args": {"skills": [{"title": "Carpentry"}]}}
            else:
                yield "Saved!"

        mock_llm_service.generate_stream = stream_with_save

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream("add Carpentry", "sess"):
            pass

        assert mock_conversation_service.context["current_competencies"] == after_save, (
            "context['current_competencies'] must be refreshed after save_competence_batch"
        )
        assert call_count_get == 2, (
            "get_my_competencies must be called twice: once for pre-fetch, once for post-write refresh"
        )

    async def test_unknown_signal_transition_stage_feeds_error_to_llm_history(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """signal_transition with an empty/unrecognised target_stage must inject
        a descriptive error into LLM history so the model can self-correct."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        call_count = 0

        async def stream_empty_stage(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": ""}}   # empty / malformed
            else:
                yield "Let me try again."

        mock_llm_service.generate_stream = stream_empty_stage
        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream("done", "sess"):
            pass

        # Stage must not have changed
        mock_conversation_service.set_stage.assert_not_called()

        # Failure must be fed back to LLM via history
        history_calls = mock_llm_service.add_message_to_history.call_args_list
        messages = [
            c[0][1].content for c in history_calls if hasattr(c[0][1], "content")
        ]
        assert any("error" in m.lower() or "failed" in m.lower() for m in messages), (
            "A signal_transition failure must be fed back as an error into LLM history"
        )

    async def test_provider_onboarding_empty_signal_after_text_triggers_write_tool_correction(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Regression: LLM in PROVIDER_ONBOARDING yields text then calls
        signal_transition(target_stage="") (empty / unrecognised stage value).

        Expected behaviour:
        - The transition is rejected (empty string is not a valid ConversationStage).
        - A descriptive error is injected into pending results and fed to LLM history.
        - The follow-up stream is triggered and its output is included in the response.
        - Stage must NOT advance (set_stage not called).
        """
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }
        call_count = 0

        async def stream_text_then_bad_signal(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Exact pattern from bug reports: text first, then wrong signal
                yield "Perfect. I just need a few seconds to search our database..."
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": ""}}
            else:
                # Follow-up stream after the correction injection
                yield "Thanks, I have now saved your skills."

        mock_llm_service.generate_stream = stream_text_then_bad_signal

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        chunks: list[str] = []
        async for chunk in orch.generate_response_stream("yeah correct", "sess"):
            if isinstance(chunk, str):
                chunks.append(chunk)

        combined = "".join(chunks)

        # Follow-up stream must have been triggered and its text included
        assert "Thanks, I have now saved your skills." in combined, (
            "Follow-up stream output must be included in response — the hard pre-check "
            "guard must not suppress the follow-up even after text was yielded"
        )

        # Stage must NOT have advanced (no valid transition was applied)
        mock_conversation_service.set_stage.assert_not_called()

        # The correction error must have been fed back to LLM history
        history_calls = mock_llm_service.add_message_to_history.call_args_list
        messages = [
            c[0][1].content for c in history_calls if hasattr(c[0][1], "content")
        ]
        assert any(
            "write tool" in m.lower() or "save_competence_batch" in m.lower()
            or "invalid" in m.lower() or "error" in m.lower()
            for m in messages
        ), (
            "A transition failure error must be fed into LLM history so the "
            "follow-up stream can self-correct"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Provider stage escape to TRIAGE
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderStageEscapeToTriage:
    """signal_transition('triage') must be allowed from PROVIDER_ONBOARDING and
    PROVIDER_PITCH — the user may pivot mid-conversation to seek a service.
    The old hardcoded guard that blocked any non-'completed' target from
    PROVIDER_ONBOARDING must no longer fire."""

    async def test_provider_onboarding_to_triage_allowed(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """LLM calls signal_transition('triage') from PROVIDER_ONBOARDING
        (user says they want to find a provider, not manage skills).
        Stage must advance to TRIAGE and no error must be injected."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }
        call_count = 0

        async def stream_triage(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "triage"}}
            else:
                yield "Of course! Let me help you find a provider."

        mock_llm_service.generate_stream = stream_triage

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream(
            "no, I am looking for someone teaching me inliner skating", "sess"
        ):
            pass

        set_stage_calls = [c[0][0] for c in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.TRIAGE in set_stage_calls, (
            "signal_transition('triage') from PROVIDER_ONBOARDING must be applied — "
            "the old blocking guard must no longer reject it"
        )

        # No error should have been fed to LLM history for this valid transition
        history_calls = mock_llm_service.add_message_to_history.call_args_list
        messages = [
            c[0][1].content for c in history_calls if hasattr(c[0][1], "content")
        ]
        assert not any(
            '"error"' in m and "triage" in m.lower() for m in messages
        ), "No blocking error should be injected for a valid ONBOARDING→TRIAGE transition"

    async def test_provider_pitch_to_triage_allowed(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """signal_transition('triage') from PROVIDER_PITCH must be applied."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_PITCH
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }
        call_count = 0

        async def stream_triage(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "triage"}}
            else:
                yield "Sure, let me help you search."

        mock_llm_service.generate_stream = stream_triage

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream("I want to find someone", "sess"):
            pass

        set_stage_calls = [c[0][0] for c in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.TRIAGE in set_stage_calls

    async def test_no_re_pitch_after_record_provider_interest_not_now(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """record_provider_interest('not_now') must update in-memory user_context
        so that when signal_transition('completed') fires next, _should_pitch_provider
        returns False and the pitch is NOT re-triggered."""
        from datetime import datetime, timezone, timedelta

        # User is pitch-eligible: non-provider, asked 60 days ago
        sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)
        context = {
            "user_context": {
                "is_service_provider": False,
                "last_time_asked_being_provider": sixty_days_ago,
            }
        }
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_PITCH
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
        }

        async def stream_with_record(*args, **kwargs):
            yield {"type": "function_call", "name": "record_provider_interest",
                   "args": {"decision": "not_now"}}

        mock_llm_service.generate_stream = stream_with_record
        mock_tool_registry.execute = AsyncMock(return_value={"status": "not_now"})

        from unittest.mock import patch
        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("not now", "sess", context=context):
                pass

        # last_time_asked must have been refreshed to ~now (within last 5 seconds)
        updated = context["user_context"].get("last_time_asked_being_provider")
        assert updated is not None
        assert (datetime.now(timezone.utc) - updated).total_seconds() < 5, (
            "In-memory last_time_asked_being_provider must be refreshed after 'not_now' "
            "so _should_pitch_provider won't re-fire on the next COMPLETED transition"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Same-stage guard: signal_transition embedded in tool result
# ─────────────────────────────────────────────────────────────────────────────

class TestSameStageToolResultGuard:
    """record_provider_interest(accepted) can legally be called from within
    PROVIDER_ONBOARDING (STEP 0 intent gate).  Its tool result carries
    {"signal_transition": "provider_onboarding"} which must NOT trigger a
    re-entry attempt — the orchestrator should silently skip it."""

    async def test_same_stage_signal_in_tool_result_is_skipped(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """No set_stage call with PROVIDER_ONBOARDING when already in that stage
        and the tool result embeds signal_transition='provider_onboarding'."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [], "is_service_provider": False,
        }

        async def stream_accepted(*args, **kwargs):
            yield {"type": "function_call", "name": "record_provider_interest",
                   "args": {"decision": "accepted"}}

        mock_llm_service.generate_stream = stream_accepted
        # Tool returns the signal that would normally trigger onboarding entry
        mock_tool_registry.execute = AsyncMock(
            return_value={"signal_transition": "provider_onboarding", "status": "accepted"}
        )

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream("I could teach cooking", "sess"):
            pass

        # set_stage must NOT have been called with PROVIDER_ONBOARDING (self-loop)
        for call in mock_conversation_service.set_stage.call_args_list:
            assert call[0][0] != ConversationStage.PROVIDER_ONBOARDING, (
                "set_stage(PROVIDER_ONBOARDING) must NOT be called when already in "
                "PROVIDER_ONBOARDING — same-stage self-loop guard failed"
            )

    async def test_different_stage_signal_in_tool_result_is_applied(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """A tool result with signal_transition to a DIFFERENT stage must still
        be applied normally (guard must not block legitimate transitions)."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_PITCH
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [], "is_service_provider": False,
        }

        async def stream_accepted(*args, **kwargs):
            yield {"type": "function_call", "name": "record_provider_interest",
                   "args": {"decision": "accepted"}}

        mock_llm_service.generate_stream = stream_accepted
        mock_tool_registry.execute = AsyncMock(
            return_value={"signal_transition": "provider_onboarding", "status": "accepted"}
        )

        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("yes I want to", "sess"):
                pass

        set_stage_calls = [c[0][0] for c in mock_conversation_service.set_stage.call_args_list]
        assert ConversationStage.PROVIDER_ONBOARDING in set_stage_calls, (
            "Transition from PROVIDER_PITCH → PROVIDER_ONBOARDING must still be applied"
        )


# ─────────────────────────────────────────────────────────────────────────────
# is_service_provider sync into conversation_service.context
# ─────────────────────────────────────────────────────────────────────────────

class TestIsServiceProviderContextSync:
    """ResponseOrchestrator must mirror user_context.is_service_provider into
    conversation_service.context on every PROVIDER_ONBOARDING turn."""

    async def test_is_service_provider_synced_on_entry(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """When entering PROVIDER_ONBOARDING via signal_transition, is_service_provider
        from user_context must be stored in conversation_service.context."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.TRIAGE
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [],
        }
        mock_tool_registry.execute = AsyncMock(return_value=[])

        async def stream_transition(*args, **kwargs):
            yield {"type": "function_call", "name": "signal_transition",
                   "args": {"target_stage": "provider_onboarding"}}

        mock_llm_service.generate_stream = stream_transition
        context = {"user_context": {"is_service_provider": True, "user_id": "u1"}}

        from unittest.mock import patch
        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = ResponseOrchestrator(
                llm_service=mock_llm_service,
                conversation_service=mock_conversation_service,
                tool_registry=mock_tool_registry,
            )
            async for _ in orch.generate_response_stream("manage my skills", "sess", context=context):
                pass

        assert mock_conversation_service.context.get("is_service_provider") is True, (
            "is_service_provider=True from user_context must be propagated into "
            "conversation_service.context on PROVIDER_ONBOARDING entry"
        )

    async def test_record_provider_interest_accepted_updates_context(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """After record_provider_interest(accepted) fires, conversation_service.context
        must have is_service_provider=True so the next prompt renders with STEP 0 skipped."""
        mock_conversation_service.get_current_stage.return_value = (
            ConversationStage.PROVIDER_ONBOARDING
        )
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
            "current_competencies": [], "is_service_provider": False,
        }
        context = {"user_context": {"is_service_provider": False, "user_id": "u1"}}

        async def stream_accepted(*args, **kwargs):
            yield {"type": "function_call", "name": "record_provider_interest",
                   "args": {"decision": "accepted"}}

        mock_llm_service.generate_stream = stream_accepted
        mock_tool_registry.execute = AsyncMock(
            return_value={"signal_transition": "provider_onboarding", "status": "accepted"}
        )

        orch = ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )
        async for _ in orch.generate_response_stream("I could help", "sess", context=context):
            pass

        assert mock_conversation_service.context.get("is_service_provider") is True, (
            "conversation_service.context['is_service_provider'] must be True after "
            "record_provider_interest(accepted) so STEP 0 is skipped next turn"
        )


# ─────────────────────────────────────────────────────────────────────────────
# search_providers cache-skip guard in FINALIZE
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchProvidersCacheGuardInFinalize:
    """The cache-skip guard must only bypass a Weaviate re-fetch when the cached
    result is non-empty.  When providers_found == [], a re-fetch is required so
    that a repaired Weaviate dataset (or a search that was interrupted on the
    first FINALIZE entry) is picked up on the next LLM turn."""

    @staticmethod
    def _make_orchestrator(
        mock_llm_service,
        mock_conversation_service,
        mock_tool_registry,
    ):
        return ResponseOrchestrator(
            llm_service=mock_llm_service,
            conversation_service=mock_conversation_service,
            tool_registry=mock_tool_registry,
        )

    async def test_cache_used_when_providers_already_found(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """When providers_found has entries, the LLM-triggered search_providers call
        must return the cache and NOT call the tool registry again."""
        cached = [{"user": {"name": "Alice"}, "title": "Coaching"}]
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": cached, "current_provider_index": 0,
        }

        async def stream_search(*args, **kwargs):
            yield {"type": "function_call", "name": "search_providers", "args": {}}
            yield "Great, I found someone."

        mock_llm_service.generate_stream = stream_search

        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        chunks = []
        async for c in orch.generate_response_stream("good", "sess"):
            chunks.append(c)

        # Tool registry must NOT be called for search_providers — cache was used
        for call in mock_tool_registry.execute.call_args_list:
            assert call.args[0] != "search_providers", (
                "search_providers must be served from cache when providers_found is non-empty"
            )

    async def test_refetch_triggered_when_cache_is_empty(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """When providers_found is empty (e.g. first search was interrupted or
        returned 0 due to stale Weaviate data), the next LLM call to search_providers
        must execute the real tool, giving Weaviate a second chance."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
        }

        async def stream_search(*args, **kwargs):
            yield {"type": "function_call", "name": "search_providers", "args": {}}

        mock_llm_service.generate_stream = stream_search
        mock_tool_registry.execute = AsyncMock(return_value=[{"user": {"name": "Bob"}}])

        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        async for _ in orch.generate_response_stream("good", "sess"):
            pass

        # Tool registry MUST have been called for search_providers
        executed_names = [c.args[0] for c in mock_tool_registry.execute.call_args_list]
        assert "search_providers" in executed_names, (
            "search_providers must re-fetch when providers_found cache is empty"
        )

    async def test_followup_stream_refetches_when_cache_empty(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Same empty-cache rule applies to the follow-up LLM stream in FINALIZE."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE
        mock_conversation_service.context = {
            "user_problem": [], "providers_found": [], "current_provider_index": 0,
        }

        # First stream: signal_transition → follow-up stream: search_providers
        turn = 0

        async def two_turn_stream(*args, **kwargs):
            nonlocal turn
            if turn == 0:
                turn += 1
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "finalize"}}
            else:
                yield {"type": "function_call", "name": "search_providers", "args": {}}

        mock_llm_service.generate_stream = two_turn_stream
        # Return empty from search_providers_for_request (auto-search on FINALIZE entry)
        mock_conversation_service.search_providers_for_request = AsyncMock(return_value=[])
        mock_tool_registry.execute = AsyncMock(return_value=[{"user": {"name": "Carol"}}])

        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        async for _ in orch.generate_response_stream("yes", "sess"):
            pass

        # Tool registry must have been called for search_providers in follow-up
        executed_names = [c.args[0] for c in mock_tool_registry.execute.call_args_list]
        assert "search_providers" in executed_names, (
            "Follow-up stream must re-fetch search_providers when cache is empty"
        )


# ─────────────────────────────────────────────────────────────────────────────
# accept_provider follow-up: no duplicate message
# ─────────────────────────────────────────────────────────────────────────────

class TestAcceptProviderNoDuplicateMessage:
    """Regression: after accept_provider fires FINALIZE → COMPLETED, the follow-up
    stream must NOT misinterpret the previous user utterance (e.g. "it's berlin")
    as a new service request and generate a spurious second TRIAGE loop.

    Bug trace:
      1. User in FINALIZE says "it's berlin".
      2. LLM calls accept_provider → create_service_request executes → COMPLETED.
      3. follow_up_input = "it's berlin" was fed to LOOP_BACK_PROMPT.
      4. LLM saw it as a new topic → signal_transition("triage") → second follow-up
         stream ran against TRIAGE, producing a duplicate message and then an illegal
         TRIAGE → COMPLETED attempt.
    """

    @staticmethod
    def _make_orchestrator(mock_llm, mock_conv, mock_registry):
        return ResponseOrchestrator(
            llm_service=mock_llm,
            conversation_service=mock_conv,
            tool_registry=mock_registry,
        )

    async def test_no_triage_loop_after_accept_provider(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """After accept_provider, the follow-up stream must NOT receive the user's
        prior location utterance as its input — preventing a spurious triage loop."""
        from unittest.mock import call, patch

        # Start in FINALIZE; stage advances to COMPLETED inside _handle_finalize_tool.
        stage_sequence = [
            ConversationStage.FINALIZE,   # initial stage check
            ConversationStage.FINALIZE,   # tool registration check
            ConversationStage.FINALIZE,   # prompt build
            ConversationStage.COMPLETED,  # follow-up stream stage (after transition)
        ]
        mock_conversation_service.get_current_stage.side_effect = stage_sequence + [
            ConversationStage.COMPLETED
        ] * 10  # subsequent calls stay COMPLETED
        mock_conversation_service.context = {
            "user_problem": [],
            "providers_found": [{"user": {"user_id": "p1", "name": "David"}, "title": "Lighting", "score": 0.9}],
            "current_provider_index": 0,
        }

        # create_service_request returns a successful result
        mock_tool_registry.execute = AsyncMock(
            return_value={"id": "req-123", "title": "New lights"}
        )

        stream_inputs: list[str] = []
        call_count = 0

        async def capture_stream(user_input, template, session_id):
            nonlocal call_count
            call_count += 1
            stream_inputs.append(user_input)
            if call_count == 1:
                # Main stream: LLM calls accept_provider
                yield {
                    "type": "function_call",
                    "name": "accept_provider",
                    "args": {
                        "provider_id": "p1",
                        "title": "New lights",
                        "description": "Install balcony lights",
                        "location": "Berlin",
                    },
                }
            else:
                # Follow-up stream: LLM confirms and stops (no spurious triage call)
                yield "Your request has been sent to David. He will be in touch shortly."

        mock_llm_service.generate_stream = capture_stream

        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = self._make_orchestrator(
                mock_llm_service, mock_conversation_service, mock_tool_registry
            )
            chunks = [c async for c in orch.generate_response_stream("it's berlin", "sess")]

        # The fix: follow-up input must be " " (not "it's berlin") when accept_provider
        # is in the pending batch.
        assert len(stream_inputs) >= 2, "Expected at least main + follow-up stream"
        follow_up_input_used = stream_inputs[1]
        assert follow_up_input_used == " ", (
            f"Follow-up input after accept_provider must be ' ' to avoid LOOP_BACK_PROMPT "
            f"misreading the prior location answer as a new topic, got {follow_up_input_used!r}"
        )

    async def test_accept_provider_generates_single_confirmation(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Only one text response must be generated across all streams: the COMPLETED
        confirmation.  No TRIAGE loop should produce a second message."""
        from unittest.mock import patch

        mock_conversation_service.get_current_stage.side_effect = (
            [ConversationStage.FINALIZE] * 5 + [ConversationStage.COMPLETED] * 15
        )
        mock_conversation_service.context = {
            "user_problem": [],
            "providers_found": [{"user": {"user_id": "p1", "name": "David"}, "title": "Lighting", "score": 0.9}],
            "current_provider_index": 0,
        }
        mock_tool_registry.execute = AsyncMock(
            return_value={"id": "req-123", "title": "New lights"}
        )

        call_count = 0

        async def controlled_stream(user_input, template, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {
                    "type": "function_call",
                    "name": "accept_provider",
                    "args": {"provider_id": "p1", "title": "New lights"},
                }
            elif call_count == 2:
                yield "Your request has been sent. Is there anything else I can help you with?"
            # No further streams; call_count >= 3 would indicate a spurious TRIAGE loop.

        mock_llm_service.generate_stream = controlled_stream

        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            orch = self._make_orchestrator(
                mock_llm_service, mock_conversation_service, mock_tool_registry
            )
            texts = [c async for c in orch.generate_response_stream("it's berlin", "sess")
                     if isinstance(c, str)]

        # All text should come from stream call #2 (the COMPLETED follow-up).
        # If a spurious TRIAGE loop had run, call_count would be >= 3.
        assert call_count == 2, (
            f"Expected exactly 2 LLM stream calls (main + COMPLETED follow-up), "
            f"got {call_count} — a spurious TRIAGE loop is running."
        )
        assert any("request has been sent" in t for t in texts)


# ─────────────────────────────────────────────────────────────────────────────
# _handle_finalize_tool — unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestHandleFinalizeToolUnit:
    """Direct unit tests for ResponseOrchestrator._handle_finalize_tool.

    Each test calls the method directly and inspects the *pending* list to verify
    the correct payload is appended without running a full stream.
    """

    @staticmethod
    def _make_orchestrator(mock_llm, mock_conv, mock_registry):
        return ResponseOrchestrator(
            llm_service=mock_llm,
            conversation_service=mock_conv,
            tool_registry=mock_registry,
        )

    async def test_no_provider_id_appends_error(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Missing provider_id → error payload appended; registry never called."""
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool("accept_provider", {}, "sess", {}, pending)
        assert any(
            name == "accept_provider" and isinstance(result, dict) and result.get("error")
            for name, result in pending
        ), f"Expected error payload in pending, got: {pending}"
        mock_tool_registry.execute.assert_not_called()

    async def test_no_location_appends_location_required(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Missing location → location_required error; registry never called (GAP-2 guard)."""
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        mock_conversation_service.context["providers_found"] = []
        pending: list = []
        await orch._handle_finalize_tool(
            "accept_provider",
            {"provider_id": "uid-abc"},
            "sess",
            {},
            pending,
        )
        errors = [result for name, result in pending if name == "accept_provider"]
        assert errors, "Expected an accept_provider payload"
        assert errors[0].get("error") == "location_required", (
            f"Expected location_required error, got: {errors[0]}"
        )
        mock_tool_registry.execute.assert_not_called()

    async def test_valid_call_invokes_create_service_request(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Valid accept_provider args → create_service_request called with selected_provider_user_id."""
        mock_conversation_service.context["providers_found"] = []
        mock_tool_registry.execute = AsyncMock(return_value={"id": "req-1", "title": "Fix pipes"})
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool(
            "accept_provider",
            {"provider_id": "uid-p1", "location": "Berlin", "category": "plumbing", "title": "Fix pipes"},
            "sess",
            {},
            pending,
        )
        mock_tool_registry.execute.assert_called_once()
        call_args = mock_tool_registry.execute.call_args
        assert call_args[0][0] == "create_service_request"
        csr_args = call_args[0][1]
        assert csr_args["selected_provider_user_id"] == "uid-p1"
        assert csr_args["location"] == "Berlin"
        assert csr_args["category"] == "plumbing"

    async def test_rerank_score_enriched_as_sigmoid(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Accepted provider with rerank_score → _candidate_matching_score = sigmoid * 100."""
        import math
        raw = 2.0
        expected_score = round(1.0 / (1.0 + math.exp(-raw)) * 100, 1)
        mock_conversation_service.context["providers_found"] = [
            {"user": {"user_id": "uid-p1", "name": "Hans"}, "title": "Electrician", "score": 0.5, "rerank_score": raw}
        ]
        mock_tool_registry.execute = AsyncMock(return_value={"id": "req-2"})
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool(
            "accept_provider",
            {"provider_id": "uid-p1", "location": "Munich", "category": "electrical"},
            "sess",
            {},
            pending,
        )
        csr_args = mock_tool_registry.execute.call_args[0][1]
        assert csr_args.get("_candidate_matching_score") == expected_score

    async def test_hybrid_score_used_when_no_rerank_score(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Provider without rerank_score but with score → _candidate_matching_score = score * 100."""
        mock_conversation_service.context["providers_found"] = [
            {"user": {"user_id": "uid-p2", "name": "Petra"}, "title": "Plumber", "score": 0.75}
        ]
        mock_tool_registry.execute = AsyncMock(return_value={"id": "req-3"})
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool(
            "accept_provider",
            {"provider_id": "uid-p2", "location": "Hamburg", "category": "plumbing"},
            "sess",
            {},
            pending,
        )
        csr_args = mock_tool_registry.execute.call_args[0][1]
        assert csr_args.get("_candidate_matching_score") == round(0.75 * 100, 1)

    async def test_no_score_when_provider_not_in_list(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """provider_id not found in providers_found → request still created, no score enrichment."""
        mock_conversation_service.context["providers_found"] = [
            {"user": {"user_id": "uid-other", "name": "Other"}, "title": "Other", "score": 0.9}
        ]
        mock_tool_registry.execute = AsyncMock(return_value={"id": "req-4"})
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool(
            "accept_provider",
            {"provider_id": "uid-unknown", "location": "Berlin", "category": "repair"},
            "sess",
            {},
            pending,
        )
        mock_tool_registry.execute.assert_called_once()
        csr_args = mock_tool_registry.execute.call_args[0][1]
        assert "_candidate_matching_score" not in csr_args

    async def test_reject_and_fetch_next_presents_next_provider(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """reject_and_fetch_next at index 0 → index incremented to 1, next provider returned."""
        p2 = {"user": {"user_id": "uid-p2", "name": "Lena"}, "title": "Gardener", "score": 0.8}
        mock_conversation_service.context = {
            "user_problem": [],
            "providers_found": [
                {"user": {"user_id": "uid-p1", "name": "Karl"}, "title": "Gardener", "score": 0.9},
                p2,
            ],
            "current_provider_index": 0,
        }
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool("reject_and_fetch_next", {}, "sess", {}, pending)
        assert mock_conversation_service.context["current_provider_index"] == 1
        payloads = [r for name, r in pending if name == "reject_and_fetch_next"]
        assert payloads and payloads[0].get("status") == "next_provider"
        assert payloads[0].get("current_provider") == p2

    async def test_reject_and_fetch_next_exhausted_reports_exhausted(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """reject_and_fetch_next when already at last provider → transitions to TRIAGE
        with a zero_result_event hint; no next_provider payload is appended."""
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE
        mock_conversation_service.context = {
            "user_problem": [],
            "providers_found": [
                {"user": {"user_id": "uid-p1", "name": "Karl"}, "title": "Gardener", "score": 0.9},
            ],
            "current_provider_index": 0,
        }
        orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
        pending: list = []
        await orch._handle_finalize_tool("reject_and_fetch_next", {}, "sess", {}, pending)

        # No next_provider should have been appended — list is exhausted
        next_payloads = [r for name, r in pending if name == "reject_and_fetch_next"]
        assert not next_payloads or all(
            r.get("status") != "next_provider" for r in next_payloads
        ), f"Expected no next_provider when list exhausted, got: {next_payloads}"

        # A triage stage with zero_result_event must appear in the pending payloads
        triage_payloads = [
            r for _, r in pending
            if isinstance(r, dict) and r.get("stage") == "triage" and "zero_result_event" in r
        ]
        assert triage_payloads, (
            f"Expected triage+zero_result_event payload when all providers exhausted, got: {pending}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# FINALIZE happy-path streams: reject→accept chain and cache exhaustion
# ─────────────────────────────────────────────────────────────────────────────

class TestFinalizeHappyPathStream:
    """Integration-level stream tests covering multi-turn FINALIZE flows:
    - Test Case 2: user rejects first provider then accepts the second.
    - Test Case 3: user rejects all providers → exhaustion → back to TRIAGE.
    """

    @staticmethod
    def _make_orchestrator(mock_llm, mock_conv, mock_registry):
        return ResponseOrchestrator(
            llm_service=mock_llm,
            conversation_service=mock_conv,
            tool_registry=mock_registry,
        )

    async def test_reject_then_accept_chain(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """User rejects provider p1 then accepts p2.

        Sequence:
          Stream 1 (FINALIZE): LLM calls reject_and_fetch_next()
          Stream 2 (FINALIZE follow-up re-presentation): LLM calls accept_provider(p2)
          Stream 3 (COMPLETED follow-up): LLM confirms
        """
        from unittest.mock import patch

        p1 = {"user": {"user_id": "uid-p1", "name": "Karl"}, "title": "Plumber", "score": 0.9}
        p2 = {"user": {"user_id": "uid-p2", "name": "Lena"}, "title": "Plumber", "score": 0.8}
        mock_conversation_service.context = {
            "user_problem": [],
            "providers_found": [p1, p2],
            "current_provider_index": 0,
        }
        mock_conversation_service.get_current_stage.side_effect = (
            [ConversationStage.FINALIZE] * 10 + [ConversationStage.COMPLETED] * 10
        )
        mock_tool_registry.execute = AsyncMock(return_value={"id": "req-99", "title": "Pipes"})

        call_count = 0

        async def stream(user_input, template, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "reject_and_fetch_next", "args": {}}
            elif call_count == 2:
                yield {
                    "type": "function_call",
                    "name": "accept_provider",
                    "args": {"provider_id": "uid-p2", "location": "Berlin", "category": "plumbing"},
                }
            else:
                yield "Request sent to Lena."

        mock_llm_service.generate_stream = stream

        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
            chunks = [c async for c in orch.generate_response_stream("no, next one", "sess")]

        # create_service_request must have been called with p2's uid
        executed = [c.args[0] for c in mock_tool_registry.execute.call_args_list]
        assert "create_service_request" in executed
        csr_args = next(
            c.args[1] for c in mock_tool_registry.execute.call_args_list if c.args[0] == "create_service_request"
        )
        assert csr_args["selected_provider_user_id"] == "uid-p2"
        # p1 must have been skipped (index bumped)
        assert mock_conversation_service.context["current_provider_index"] == 1

    async def test_all_providers_rejected_raises_triage(
        self, mock_llm_service, mock_conversation_service, mock_tool_registry
    ):
        """Rejecting the last provider in the list triggers all_providers_exhausted,
        which the orchestrator must handle by transitioning back to TRIAGE
        or returning the exhaustion payload for the LLM to route appropriately."""
        from unittest.mock import patch

        p1 = {"user": {"user_id": "uid-p1", "name": "Karl"}, "title": "Plumber", "score": 0.9}
        mock_conversation_service.context = {
            "user_problem": [],
            "providers_found": [p1],
            "current_provider_index": 0,
        }
        mock_conversation_service.get_current_stage.return_value = ConversationStage.FINALIZE

        call_count = 0

        async def stream(user_input, template, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "reject_and_fetch_next", "args": {}}
            else:
                yield "I'm sorry, no more providers are available."

        mock_llm_service.generate_stream = stream

        with patch("ai_assistant.services.response_orchestrator.is_legal_transition", return_value=True):
            orch = self._make_orchestrator(mock_llm_service, mock_conversation_service, mock_tool_registry)
            chunks = [c async for c in orch.generate_response_stream("no one else?", "sess")]

        # The follow-up stream must have been called (to deliver the "no more" message)
        assert call_count >= 2, (
            f"Expected follow-up LLM call after exhaustion, got call_count={call_count}"
        )
        # create_service_request must NOT have been called
        executed = [c.args[0] for c in mock_tool_registry.execute.call_args_list]
        assert "create_service_request" not in executed, (
            "create_service_request must not be called when all providers are exhausted"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Follow-up chain: 3-hop oscillation regression
# ─────────────────────────────────────────────────────────────────────────────

class TestFollowUpBoundedLoop:
    """Tests for the bounded follow-up loop that replaced the fixed 2-pass pattern.

    Regression: a 3-hop chain (TRIAGE→CONFIRMATION→TRIAGE→CONFIRMATION) silently
    dropped the third-hop pending results because the old code only had 2 fixed
    follow-up slots.  After the fix the loop runs up to MAX_FOLLOW_UP_DEPTH=4
    times and the final CONFIRMATION stage always produces a response.
    """

    @staticmethod
    def _make_orchestrator_with_stage_tracker(llm_fn, stages):
        """Build an orchestrator whose conversation_service.get_current_stage()
        returns successive values from *stages* on each call and whose
        generate_stream calls *llm_fn* to drive the stream chunks.
        """
        from unittest.mock import patch

        llm = Mock()
        llm.generate_stream = llm_fn
        llm.register_functions = Mock()
        llm.add_message_to_history = Mock()

        conv = Mock()
        conv.language = "en"
        _stage_iter = iter(stages)

        def _next_stage():
            try:
                return next(_stage_iter)
            except StopIteration:
                return ConversationStage.CONFIRMATION

        conv.get_current_stage = _next_stage
        conv.set_stage = Mock()
        conv.accumulate_problem_description = AsyncMock()
        conv.search_providers_for_request = AsyncMock()
        conv.record_ai_response = Mock()
        conv.create_prompt_for_stage = Mock(return_value="prompt")
        conv.get_problem_summary = Mock(return_value="summary")
        conv.reset_request_context = Mock()
        conv.context = {
            "user_problem": [],
            "providers_found": [],
            "current_provider_index": 0,
        }

        registry = Mock()
        registry.execute = AsyncMock(return_value=[])
        registry.all_schemas.return_value = []

        orch = ResponseOrchestrator(
            llm_service=llm,
            conversation_service=conv,
            tool_registry=registry,
        )
        return orch, conv

    async def test_three_hop_chain_produces_final_response(self):
        """Simulate TRIAGE→CONFIRMATION→TRIAGE→CONFIRMATION (3 hops).

        The main stream emits signal_transition("confirmation") from TRIAGE.
        Follow-up 1 (CONFIRMATION) emits signal_transition("triage").
        Follow-up 2 (TRIAGE) emits signal_transition("confirmation").
        Follow-up 3 (CONFIRMATION) emits text: "Here is your confirmation summary."

        The old 2-pass code would silently drop follow-up 3. The bounded loop
        must produce the final text so the user gets a response.
        """
        from unittest.mock import patch

        call_count = 0

        async def mock_stream(user_input, template, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Main stream (TRIAGE): emit transition to CONFIRMATION
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "confirmation"}}
            elif call_count == 2:
                # Follow-up 1 (CONFIRMATION): LLM misreads input, goes back to TRIAGE
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "triage"}}
            elif call_count == 3:
                # Follow-up 2 (TRIAGE): accumulated context triggers CONFIRMATION again
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "confirmation"}}
            else:
                # Follow-up 3 (CONFIRMATION): final response
                yield "Here is your confirmation summary."

        # Stage sequence returned by get_current_stage():
        # call 1: TRIAGE (main stream stage check for tools)
        # call 2: TRIAGE (accumulate_problem_description check)
        # call 3: TRIAGE (for prompt creation in main stream)
        # follow-up calls use CONFIRMATION / TRIAGE alternately
        stages = [
            ConversationStage.TRIAGE,   # initial stage read
            ConversationStage.TRIAGE,   # FINALIZE check
            ConversationStage.TRIAGE,   # prompt creation
            ConversationStage.CONFIRMATION,  # follow-up 1 stage
            ConversationStage.TRIAGE,        # follow-up 2 stage
            ConversationStage.CONFIRMATION,  # follow-up 3 stage
            ConversationStage.CONFIRMATION,  # final save_message stage
        ]

        orch, conv = self._make_orchestrator_with_stage_tracker(mock_stream, iter(stages))

        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            chunks = [c async for c in orch.generate_response_stream(
                "hmm can you try once again please", "sess"
            )]

        text_chunks = [c for c in chunks if isinstance(c, str)]
        assert "Here is your confirmation summary." in text_chunks, (
            f"Expected the final CONFIRMATION response in chunks but got: {text_chunks}"
        )
        assert call_count == 4, (
            f"Expected 4 LLM calls (main + 3 follow-ups), got {call_count}"
        )

    async def test_two_hop_chain_still_works(self):
        """The common 2-hop case (TRIAGE→CONFIRMATION, CONFIRMATION emits text)
        must continue to work exactly as before.
        """
        from unittest.mock import patch

        call_count = 0

        async def mock_stream(user_input, template, session_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "function_call", "name": "signal_transition",
                       "args": {"target_stage": "confirmation"}}
            else:
                yield "Here is your confirmation summary."

        stages = [
            ConversationStage.TRIAGE,
            ConversationStage.TRIAGE,
            ConversationStage.TRIAGE,
            ConversationStage.CONFIRMATION,
            ConversationStage.CONFIRMATION,
        ]

        orch, conv = self._make_orchestrator_with_stage_tracker(mock_stream, iter(stages))

        with patch(
            "ai_assistant.services.response_orchestrator.is_legal_transition",
            return_value=True,
        ):
            chunks = [c async for c in orch.generate_response_stream("I need a plumber", "sess")]

        text_chunks = [c for c in chunks if isinstance(c, str)]
        assert "Here is your confirmation summary." in text_chunks
        assert call_count == 2