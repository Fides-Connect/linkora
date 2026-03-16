"""
Unit tests for LLMService — Phase 6 additions:
  - SIGNAL_TRANSITION_SCHEMA constant
  - register_functions() per-session function registry
  - generate_stream() yielding function-call dicts for tool calls
"""
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock

from ai_assistant.services.llm_service import LLMService, SIGNAL_TRANSITION_SCHEMA


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def llm_service():
    with patch("ai_assistant.services.llm_service.ChatGoogleGenerativeAI"):
        return LLMService(api_key="test-key")


def _make_text_chunk(text: str):
    """Return a mock AIMessageChunk that carries plain text content."""
    chunk = Mock()
    chunk.content = text
    chunk.tool_call_chunks = []
    return chunk


def _make_tool_call_chunk(name: str, args_json: str, index: int = 0):
    """Return a mock AIMessageChunk carrying a single ToolCallChunk."""
    chunk = Mock()
    chunk.content = ""
    tc = {"name": name, "args": args_json, "index": index, "id": f"call_{index}"}
    chunk.tool_call_chunks = [tc]
    return chunk


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL_TRANSITION_SCHEMA constant
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalTransitionSchema:

    def test_name_is_signal_transition(self):
        assert SIGNAL_TRANSITION_SCHEMA["name"] == "signal_transition"

    def test_has_parameters_field(self):
        assert "parameters" in SIGNAL_TRANSITION_SCHEMA

    def test_target_stage_is_required_parameter(self):
        params = SIGNAL_TRANSITION_SCHEMA["parameters"]
        assert "target_stage" in params.get("properties", {})
        assert "target_stage" in params.get("required", [])

    def test_description_is_non_empty(self):
        assert SIGNAL_TRANSITION_SCHEMA.get("description", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# register_functions
# ─────────────────────────────────────────────────────────────────────────────

class TestRegisterFunctions:

    def test_register_stores_schemas_for_session(self, llm_service):
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        assert llm_service._session_functions.get("sess1") == [SIGNAL_TRANSITION_SCHEMA]

    def test_register_overwrites_previous_schemas(self, llm_service):
        llm_service.register_functions("sess1", [{"name": "old"}])
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        assert llm_service._session_functions["sess1"][0]["name"] == "signal_transition"

    def test_register_empty_list_clears_functions(self, llm_service):
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        llm_service.register_functions("sess1", [])
        assert llm_service._session_functions["sess1"] == []

    def test_different_sessions_are_isolated(self, llm_service):
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        llm_service.register_functions("sess2", [])
        assert llm_service._session_functions["sess2"] == []
        assert llm_service._session_functions["sess1"] == [SIGNAL_TRANSITION_SCHEMA]

    def test_session_functions_initialises_empty(self, llm_service):
        assert isinstance(llm_service._session_functions, dict)
        assert len(llm_service._session_functions) == 0


# ─────────────────────────────────────────────────────────────────────────────
# generate_stream — text chunks
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateStreamText:

    async def test_text_chunks_yielded_as_strings(self, llm_service):
        prompt_mock = Mock()

        async def fake_astream(*args, **kwargs):
            yield _make_text_chunk("Hello ")
            yield _make_text_chunk("world")

        chain_mock = Mock()
        chain_mock.astream = fake_astream

        with patch.object(llm_service, "create_chain_with_history", return_value=chain_mock):
            chunks = []
            async for c in llm_service.generate_stream("hi", prompt_mock, "sess1"):
                chunks.append(c)

        assert all(isinstance(c, str) for c in chunks)
        assert "".join(chunks) == "Hello world"

    async def test_no_function_call_chunks_without_registered_functions(self, llm_service):
        prompt_mock = Mock()

        async def fake_astream(*args, **kwargs):
            yield _make_text_chunk("plain text")

        chain_mock = Mock()
        chain_mock.astream = fake_astream

        with patch.object(llm_service, "create_chain_with_history", return_value=chain_mock):
            chunks = []
            async for c in llm_service.generate_stream("hi", prompt_mock, "sess1"):
                chunks.append(c)

        assert not any(isinstance(c, dict) for c in chunks)


# ─────────────────────────────────────────────────────────────────────────────
# generate_stream — function call chunks
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateStreamFunctionCalls:

    async def test_function_call_yielded_as_dict(self, llm_service):
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        prompt_mock = Mock()

        async def fake_astream(*args, **kwargs):
            yield _make_tool_call_chunk(
                "signal_transition",
                json.dumps({"target_stage": "finalize"}),
            )

        chain_mock = Mock()
        chain_mock.astream = fake_astream

        with patch.object(llm_service, "create_chain_with_history", return_value=chain_mock):
            chunks = []
            async for c in llm_service.generate_stream("hi", prompt_mock, "sess1"):
                chunks.append(c)

        fn_calls = [c for c in chunks if isinstance(c, dict) and c.get("type") == "function_call"]
        assert len(fn_calls) == 1
        assert fn_calls[0]["name"] == "signal_transition"
        assert fn_calls[0]["args"]["target_stage"] == "finalize"

    async def test_mixed_text_and_function_call(self, llm_service):
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        prompt_mock = Mock()

        async def fake_astream(*args, **kwargs):
            yield _make_text_chunk("Okay, searching now. ")
            yield _make_tool_call_chunk(
                "signal_transition",
                json.dumps({"target_stage": "finalize"}),
            )

        chain_mock = Mock()
        chain_mock.astream = fake_astream

        with patch.object(llm_service, "create_chain_with_history", return_value=chain_mock):
            chunks = []
            async for c in llm_service.generate_stream("go", prompt_mock, "sess1"):
                chunks.append(c)

        text_chunks = [c for c in chunks if isinstance(c, str)]
        fn_chunks = [c for c in chunks if isinstance(c, dict)]
        assert len(text_chunks) >= 1
        assert len(fn_chunks) == 1
        assert fn_chunks[0]["name"] == "signal_transition"

    async def test_multi_chunk_args_accumulated(self, llm_service):
        """Tool call args split across multiple stream chunks must be reassembled."""
        llm_service.register_functions("sess1", [SIGNAL_TRANSITION_SCHEMA])
        prompt_mock = Mock()

        async def fake_astream(*args, **kwargs):
            # First chunk: name + partial args
            yield _make_tool_call_chunk("signal_transition", '{"target_stage": "fin', 0)
            # Second chunk: remaining args (no name)
            chunk2 = Mock()
            chunk2.content = ""
            chunk2.tool_call_chunks = [{"name": "", "args": 'alize"}', "index": 0, "id": None}]
            yield chunk2

        chain_mock = Mock()
        chain_mock.astream = fake_astream

        with patch.object(llm_service, "create_chain_with_history", return_value=chain_mock):
            chunks = []
            async for c in llm_service.generate_stream("go", prompt_mock, "sess1"):
                chunks.append(c)

        fn_calls = [c for c in chunks if isinstance(c, dict) and c.get("type") == "function_call"]
        assert len(fn_calls) == 1
        assert fn_calls[0]["args"]["target_stage"] == "finalize"


# ─────────────────────────────────────────────────────────────────────────────
# pop_trailing_human_message
# ─────────────────────────────────────────────────────────────────────────────

class TestPopTrailingHumanMessage:
    """pop_trailing_human_message repairs history after a cancelled LLM stream."""

    def test_returns_none_on_empty_history(self, llm_service):
        result = llm_service.pop_trailing_human_message("empty-session")
        assert result is None

    def test_returns_none_when_last_message_is_ai(self, llm_service):
        from langchain_core.messages import AIMessage, HumanMessage
        llm_service.add_message_to_history("s1", HumanMessage(content="hello"))
        llm_service.add_message_to_history("s1", AIMessage(content="hi there"))
        result = llm_service.pop_trailing_human_message("s1")
        assert result is None
        # AI message is still in history
        assert len(llm_service.get_session_history("s1").messages) == 2

    def test_pops_trailing_human_message_and_returns_text(self, llm_service):
        from langchain_core.messages import HumanMessage
        llm_service.add_message_to_history("s1", HumanMessage(content="find me a plumber"))
        result = llm_service.pop_trailing_human_message("s1")
        assert result == "find me a plumber"
        assert len(llm_service.get_session_history("s1").messages) == 0

    def test_pops_only_last_message(self, llm_service):
        from langchain_core.messages import AIMessage, HumanMessage
        llm_service.add_message_to_history("s1", HumanMessage(content="first"))
        llm_service.add_message_to_history("s1", AIMessage(content="reply"))
        llm_service.add_message_to_history("s1", HumanMessage(content="second"))
        result = llm_service.pop_trailing_human_message("s1")
        assert result == "second"
        # First two messages remain
        assert len(llm_service.get_session_history("s1").messages) == 2

    def test_does_not_pop_non_trailing_human_message(self, llm_service):
        """A HumanMessage that is NOT the last item must not be removed."""
        from langchain_core.messages import AIMessage, HumanMessage
        llm_service.add_message_to_history("s1", HumanMessage(content="early"))
        llm_service.add_message_to_history("s1", AIMessage(content="response"))
        result = llm_service.pop_trailing_human_message("s1")
        assert result is None
        assert len(llm_service.get_session_history("s1").messages) == 2

    def test_sessions_are_independent(self, llm_service):
        from langchain_core.messages import HumanMessage
        llm_service.add_message_to_history("sA", HumanMessage(content="session A"))
        llm_service.add_message_to_history("sB", HumanMessage(content="session B"))
        resultA = llm_service.pop_trailing_human_message("sA")
        assert resultA == "session A"
        # Session B untouched
        assert len(llm_service.get_session_history("sB").messages) == 1
