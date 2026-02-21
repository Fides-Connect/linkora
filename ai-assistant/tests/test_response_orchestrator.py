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
