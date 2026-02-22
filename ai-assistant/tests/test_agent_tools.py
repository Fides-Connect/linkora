"""
Unit tests for agent_tools: ToolCapability, AgentTool, AgentToolRegistry.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from ai_assistant.services.agent_tools import (
    ToolCapability,
    AgentTool,
    AgentToolRegistry,
    ToolPermissionError,
    check_capability,
    build_default_registry,
)
from ai_assistant.firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL


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

# ─────────────────────────────────────────────────────────────────────────────
# Provider onboarding tools
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderOnboardingTools:
    """Tests for the four provider-onboarding agent tools."""

    ONBOARDING_CAP = ToolCapability("provider_onboarding", "write")

    @pytest.fixture
    def mock_firestore(self):
        fs = Mock()
        fs.update_user = AsyncMock(return_value={"user_id": "user-x"})
        fs.get_competencies = AsyncMock(return_value=[
            {"competence_id": "c1", "title": "Plumbing"},
            {"competence_id": "c2", "title": "Electrical"},
        ])
        fs.create_competence = AsyncMock(return_value={"competence_id": "c-new", "title": "Gardening"})
        fs.update_competence = AsyncMock(return_value={"competence_id": "c1", "title": "Plumbing Pro"})
        fs.remove_competence = AsyncMock(return_value=True)
        return fs

    @pytest.fixture
    def registry(self, mock_firestore):
        dp = Mock()
        return build_default_registry(dp, mock_firestore)

    def _ctx(self, fs):
        return {
            "user_id": "user-x",
            "user_capabilities": [self.ONBOARDING_CAP],
            "data_provider": Mock(),
            "firestore_service": fs,
        }

    # ── Registration ────────────────────────────────────────────────────────

    def test_all_four_tools_registered(self, registry):
        for name in (
            "record_provider_interest",
            "get_my_competencies",
            "save_competence_batch",
            "delete_competences",
        ):
            assert registry.get(name) is not None, f"Tool '{name}' not registered"

    def test_all_four_require_onboarding_capability(self, registry):
        for name in (
            "record_provider_interest",
            "get_my_competencies",
            "save_competence_batch",
            "delete_competences",
        ):
            tool = registry.get(name)
            assert tool.required_capability == self.ONBOARDING_CAP, (
                f"Tool '{name}' has wrong capability: {tool.required_capability}"
            )

    async def test_onboarding_tools_raise_permission_error_without_cap(self, registry):
        no_cap_ctx = {
            "user_id": "u",
            "user_capabilities": [],
            "data_provider": Mock(),
            "firestore_service": Mock(),
        }
        with pytest.raises(ToolPermissionError):
            await registry.execute("record_provider_interest", {"decision": "accepted"}, no_cap_ctx)

    # ── record_provider_interest ─────────────────────────────────────────────

    async def test_record_interest_accepted_sets_is_service_provider(
        self, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        result = await registry.execute(
            "record_provider_interest", {"decision": "accepted"}, ctx
        )
        update_call = mock_firestore.update_user.call_args
        data = update_call.args[1] if len(update_call.args) > 1 else update_call.kwargs.get("update_data", {})
        assert data.get("is_service_provider") is True

    async def test_record_interest_accepted_returns_signal_transition(
        self, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        result = await registry.execute(
            "record_provider_interest", {"decision": "accepted"}, ctx
        )
        assert isinstance(result, dict)
        assert result.get("signal_transition") == "provider_onboarding"

    async def test_record_interest_not_now_sets_current_timestamp(
        self, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        await registry.execute("record_provider_interest", {"decision": "not_now"}, ctx)
        update_call = mock_firestore.update_user.call_args
        data = update_call.args[1] if len(update_call.args) > 1 else update_call.kwargs.get("update_data", {})
        ts = data.get("last_time_asked_being_provider")
        assert isinstance(ts, datetime)
        # Should NOT be the sentinel
        assert ts != PROVIDER_PITCH_OPT_OUT_SENTINEL

    async def test_record_interest_never_sets_opt_out_sentinel(
        self, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        await registry.execute("record_provider_interest", {"decision": "never"}, ctx)
        update_call = mock_firestore.update_user.call_args
        data = update_call.args[1] if len(update_call.args) > 1 else update_call.kwargs.get("update_data", {})
        assert data.get("last_time_asked_being_provider") == PROVIDER_PITCH_OPT_OUT_SENTINEL

    # ── get_my_competencies ──────────────────────────────────────────────────

    async def test_get_my_competencies_calls_firestore(self, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        result = await registry.execute("get_my_competencies", {}, ctx)
        mock_firestore.get_competencies.assert_called_once_with("user-x")
        assert len(result) == 2

    # ── save_competence_batch ────────────────────────────────────────────────

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_creates_new_entries(self, mock_hub, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        skills = [
            {"title": "Gardening", "description": "I love plants", "category": "Garten"},
            {"title": "Painting", "description": "Interior painting", "category": "Handwerk"},
        ]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert mock_firestore.create_competence.call_count == 2
        mock_hub.update_competencies_by_user_id.assert_called_once_with(
            "user-x", ["Gardening", "Painting"]
        )

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_sets_is_service_provider(
        self, mock_hub, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        skills = [{"title": "Cleaning"}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        update_call = mock_firestore.update_user.call_args
        data = update_call.args[1] if len(update_call.args) > 1 else update_call.kwargs.get("update_data", {})
        assert data.get("is_service_provider") is True

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_updates_existing_entry(self, mock_hub, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        skills = [{"competence_id": "c1", "title": "Plumbing Pro"}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        mock_firestore.update_competence.assert_called_once()
        mock_hub.update_competencies_by_user_id.assert_called_once_with("user-x", ["Plumbing Pro"])

    # ── delete_competences ───────────────────────────────────────────────────

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_delete_competences_calls_delete_per_id(self, mock_hub, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        await registry.execute(
            "delete_competences", {"competence_ids": ["c1", "c2"]}, ctx
        )
        assert mock_firestore.remove_competence.call_count == 2
        calls = [c.args for c in mock_firestore.remove_competence.call_args_list]
        deleted_ids = [c[1] for c in calls]  # second positional arg is competence_id
        assert "c1" in deleted_ids
        assert "c2" in deleted_ids
        mock_hub.remove_competence_by_firestore_id.assert_any_call("c1")
        mock_hub.remove_competence_by_firestore_id.assert_any_call("c2")

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_weaviate_failure_propagates(
        self, mock_hub, registry, mock_firestore
    ):
        """Weaviate sync failure must propagate — not be silently swallowed."""
        mock_hub.update_competencies_by_user_id.side_effect = Exception("Weaviate unavailable")
        ctx = self._ctx(mock_firestore)
        skills = [{"title": "Plumbing"}]
        with pytest.raises(Exception, match="Weaviate unavailable"):
            await registry.execute("save_competence_batch", {"skills": skills}, ctx)

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_delete_competences_weaviate_failure_propagates(
        self, mock_hub, registry, mock_firestore
    ):
        """Weaviate sync failure must propagate — not be silently swallowed."""
        mock_hub.remove_competence_by_firestore_id.side_effect = Exception("Weaviate unavailable")
        ctx = self._ctx(mock_firestore)
        with pytest.raises(Exception, match="Weaviate unavailable"):
            await registry.execute("delete_competences", {"competence_ids": ["c1"]}, ctx)