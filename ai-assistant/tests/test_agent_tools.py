"""
Unit tests for agent_tools: ToolCapability, AgentTool, AgentToolRegistry.
"""
import pytest
from unittest.mock import AsyncMock, Mock

from ai_assistant.services.agent_tools import (
    ToolCapability,
    AgentTool,
    AgentToolRegistry,
    ToolPermissionError,
    check_capability,
    build_default_registry,
)


# ─────────────────────────────────────────────────────────────────────────────
# ToolCapability
# ─────────────────────────────────────────────────────────────────────────────

class TestToolCapability:

    def test_has_scope_and_action(self):
        cap = ToolCapability(scope="providers", action="read")
        assert cap.scope == "providers"
        assert cap.action == "read"

    def test_equal_instances_compare_equal(self):
        cap1 = ToolCapability(scope="providers", action="read")
        cap2 = ToolCapability(scope="providers", action="read")
        assert cap1 == cap2

    def test_different_scope_not_equal(self):
        assert ToolCapability("providers", "read") != ToolCapability("favorites", "read")

    def test_different_action_not_equal(self):
        assert ToolCapability("providers", "read") != ToolCapability("providers", "write")


# ─────────────────────────────────────────────────────────────────────────────
# check_capability
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckCapability:

    def test_returns_true_when_present(self):
        required = ToolCapability("providers", "read")
        user_caps = [
            ToolCapability("favorites", "read"),
            ToolCapability("providers", "read"),
        ]
        assert check_capability(required, user_caps) is True

    def test_returns_false_when_absent(self):
        required = ToolCapability("providers", "write")
        user_caps = [ToolCapability("providers", "read")]
        assert check_capability(required, user_caps) is False

    def test_returns_false_for_empty_list(self):
        assert check_capability(ToolCapability("x", "y"), []) is False


# ─────────────────────────────────────────────────────────────────────────────
# AgentTool structure for each of the 4 built-in tools
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentToolStructure:

    @pytest.fixture
    def registry(self):
        dp = Mock()
        fs = Mock()
        return build_default_registry(dp, fs)

    @pytest.mark.parametrize("tool_name,expected_cap", [
        ("search_providers",     ToolCapability("providers", "read")),
        ("get_favorites",        ToolCapability("favorites", "read")),
        ("get_open_requests",    ToolCapability("service_requests", "read")),
        ("create_service_request", ToolCapability("service_requests", "write")),
    ])
    def test_required_capability(self, registry, tool_name, expected_cap):
        tool = registry.get(tool_name)
        assert tool is not None, f"Tool '{tool_name}' not found"
        assert tool.required_capability == expected_cap

    @pytest.mark.parametrize("tool_name", [
        "search_providers", "get_favorites", "get_open_requests", "create_service_request"
    ])
    def test_has_name_and_description(self, registry, tool_name):
        tool = registry.get(tool_name)
        assert tool.name == tool_name
        assert isinstance(tool.description, str) and tool.description

    @pytest.mark.parametrize("tool_name", [
        "search_providers", "get_favorites", "get_open_requests", "create_service_request"
    ])
    def test_schema_has_required_keys(self, registry, tool_name):
        tool = registry.get(tool_name)
        schema = tool.schema
        assert isinstance(schema, dict)
        assert "name" in schema
        assert "parameters" in schema


# ─────────────────────────────────────────────────────────────────────────────
# AgentToolRegistry
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentToolRegistry:

    @pytest.fixture
    def mock_data_provider(self):
        dp = Mock()
        dp.search_providers = AsyncMock(return_value=[{"id": "p1"}])
        return dp

    @pytest.fixture
    def mock_firestore(self):
        fs = Mock()
        fs.get_user_favorites = AsyncMock(return_value=[])
        fs.get_service_requests = AsyncMock(return_value=[])
        fs.create_service_request = AsyncMock(return_value={"id": "sr1"})
        return fs

    @pytest.fixture
    def registry(self, mock_data_provider, mock_firestore):
        return build_default_registry(mock_data_provider, mock_firestore)

    @pytest.fixture
    def full_context(self, mock_data_provider, mock_firestore):
        return {
            "user_id": "user-123",
            "user_capabilities": [
                ToolCapability("providers", "read"),
                ToolCapability("favorites", "read"),
                ToolCapability("service_requests", "read"),
                ToolCapability("service_requests", "write"),
            ],
            "data_provider": mock_data_provider,
            "firestore_service": mock_firestore,
        }

    @pytest.fixture
    def no_cap_context(self, mock_data_provider, mock_firestore):
        return {
            "user_id": "user-456",
            "user_capabilities": [],
            "data_provider": mock_data_provider,
            "firestore_service": mock_firestore,
        }

    def test_get_known_tool(self, registry):
        tool = registry.get("search_providers")
        assert tool is not None
        assert tool.name == "search_providers"

    def test_get_unknown_tool_returns_none(self, registry):
        assert registry.get("completely_unknown") is None

    async def test_execute_happy_path(self, registry, full_context):
        result = await registry.execute("search_providers", {"query": "plumber"}, full_context)
        assert result is not None

    async def test_execute_raises_permission_error_when_no_cap(self, registry, no_cap_context):
        with pytest.raises(ToolPermissionError) as exc_info:
            await registry.execute("search_providers", {}, no_cap_context)
        err = exc_info.value
        assert err.tool_name == "search_providers"
        assert err.required_capability == ToolCapability("providers", "read")

    async def test_permission_error_contains_tool_and_cap_in_message(self, registry, no_cap_context):
        with pytest.raises(ToolPermissionError) as exc_info:
            await registry.execute("get_favorites", {}, no_cap_context)
        assert "get_favorites" in str(exc_info.value)

    async def test_execute_unknown_tool_raises_key_error(self, registry, full_context):
        with pytest.raises(KeyError):
            await registry.execute("does_not_exist", {}, full_context)


# ─────────────────────────────────────────────────────────────────────────────
# Tool execute contracts
# ─────────────────────────────────────────────────────────────────────────────

class TestToolExecuteContracts:

    @pytest.fixture
    def mock_data_provider(self):
        dp = Mock()
        dp.search_providers = AsyncMock(return_value=[{"id": "p1"}])
        return dp

    @pytest.fixture
    def mock_firestore(self):
        fs = Mock()
        fs.get_user_favorites = AsyncMock(return_value=[{"id": "fav1"}])
        fs.get_service_requests = AsyncMock(return_value=[{"id": "sr1"}])
        fs.create_service_request = AsyncMock(return_value={"id": "sr-new"})
        return fs

    @pytest.fixture
    def registry(self, mock_data_provider, mock_firestore):
        return build_default_registry(mock_data_provider, mock_firestore)

    def _ctx(self, dp, fs):
        return {
            "user_id": "user-abc",
            "user_capabilities": [
                ToolCapability("providers", "read"),
                ToolCapability("favorites", "read"),
                ToolCapability("service_requests", "read"),
                ToolCapability("service_requests", "write"),
            ],
            "data_provider": dp,
            "firestore_service": fs,
        }

    async def test_search_providers_calls_data_provider(
        self, registry, mock_data_provider, mock_firestore
    ):
        ctx = self._ctx(mock_data_provider, mock_firestore)
        await registry.execute("search_providers", {"query": "electrician"}, ctx)
        mock_data_provider.search_providers.assert_called_once()

    async def test_get_favorites_calls_firestore(
        self, registry, mock_data_provider, mock_firestore
    ):
        ctx = self._ctx(mock_data_provider, mock_firestore)
        await registry.execute("get_favorites", {}, ctx)
        mock_firestore.get_user_favorites.assert_called_once_with("user-abc")

    async def test_get_open_requests_calls_firestore(
        self, registry, mock_data_provider, mock_firestore
    ):
        ctx = self._ctx(mock_data_provider, mock_firestore)
        await registry.execute("get_open_requests", {}, ctx)
        mock_firestore.get_service_requests.assert_called_once()

    async def test_create_service_request_calls_firestore(
        self, registry, mock_data_provider, mock_firestore
    ):
        ctx = self._ctx(mock_data_provider, mock_firestore)
        await registry.execute(
            "create_service_request",
            {"title": "Fix leaking tap", "description": "Bathroom tap drips"},
            ctx,
        )
        mock_firestore.create_service_request.assert_called_once()
