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
    _require_fs,
)
from ai_assistant.firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL
from ai_assistant.firestore_service import FirestoreService


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
        return build_default_registry()

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
    def registry(self):
        return build_default_registry()

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
    def registry(self):
        return build_default_registry()

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
        # availability_time subcollection methods
        fs.get_availability_times = AsyncMock(return_value=[])
        fs.create_availability_time = AsyncMock(return_value={"availability_time_id": "at-1"})
        fs.update_availability_time = AsyncMock(return_value={"availability_time_id": "at-1"})
        return fs

    @pytest.fixture
    def registry(self):
        return build_default_registry()

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

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_record_interest_accepted_syncs_is_service_provider_to_weaviate(
        self, mock_hub, registry, mock_firestore
    ):
        """Accepting provider pitch must immediately mirror is_service_provider=True to
        the Weaviate User hub so search filters can see the change before the next request."""
        ctx = self._ctx(mock_firestore)
        await registry.execute(
            "record_provider_interest", {"decision": "accepted"}, ctx
        )
        mock_hub.update_user_hub_properties.assert_called_once_with(
            "user-x", {"is_service_provider": True}
        )

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_record_interest_not_now_does_not_touch_weaviate(
        self, mock_hub, registry, mock_firestore
    ):
        """Non-acceptance decisions must NOT touch the Weaviate User hub."""
        ctx = self._ctx(mock_firestore)
        await registry.execute(
            "record_provider_interest", {"decision": "not_now"}, ctx
        )
        mock_hub.update_user_hub_properties.assert_not_called()

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
        avail = {"monday_time_ranges": [{"start_time": "08:00", "end_time": "12:00"}]}
        skills = [
            {"title": "Gardening", "description": "I love plants", "category": "Garten", "price_range": "€30–€50/h", "availability_time": avail},
            {"title": "Painting", "description": "Interior painting", "category": "Handwerk", "price_range": "€40/h", "availability_time": avail},
        ]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert mock_firestore.create_competence.call_count == 2
        # Must sync ALL competencies from Firestore (not just the current batch)
        # Full dicts are now passed — not just title strings.
        mock_hub.update_competencies_by_user_id.assert_called_once_with(
            "user-x",
            [{"competence_id": "c1", "title": "Plumbing"}, {"competence_id": "c2", "title": "Electrical"}],
        )

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_syncs_all_firestore_competencies_not_just_batch(
        self, mock_hub, registry, mock_firestore
    ):
        """Weaviate must reflect ALL competencies from Firestore, not just the current batch.

        Regression: previously only the batch titles were synced, so adding competencies
        across multiple sessions would overwrite earlier ones in Weaviate.
        """
        ctx = self._ctx(mock_firestore)
        # Only 1 new skill in this batch — but Firestore already has "Plumbing" and "Electrical"
        avail = {"monday_time_ranges": [{"start_time": "08:00", "end_time": "17:00"}]}
        skills = [{"title": "Painting", "description": "Interior painting", "price_range": "€40/h", "availability_time": avail}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)

        # Weaviate sync must use ALL competence dicts from Firestore, not just the new batch.
        # Full dicts are passed so all enriched filter/rank fields reach Weaviate.
        mock_hub.update_competencies_by_user_id.assert_called_once_with(
            "user-x",
            [{"competence_id": "c1", "title": "Plumbing"}, {"competence_id": "c2", "title": "Electrical"}],
        )

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_sets_is_service_provider(
        self, mock_hub, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        avail = {"friday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}]}
        skills = [{"title": "Cleaning", "price_range": "€25/h", "availability_time": avail}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        update_call = mock_firestore.update_user.call_args
        data = update_call.args[1] if len(update_call.args) > 1 else update_call.kwargs.get("update_data", {})
        assert data.get("is_service_provider") is True

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_syncs_is_service_provider_to_weaviate(
        self, mock_hub, registry, mock_firestore
    ):
        """After marking is_service_provider=True in Firestore, the Weaviate User hub
        must also be updated immediately so that provider search filters (which filter
        on the Weaviate User hub) can find the new provider without delay.

        Regression for: provider onboarding via AI chat sets is_service_provider=True
        in Firestore but Weaviate User hub retains False, making the provider invisible
        to all search_providers queries.
        """
        ctx = self._ctx(mock_firestore)
        avail = {"friday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}]}
        skills = [{"title": "Inline Skating Lessons", "price_range": "€30/h", "availability_time": avail}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        mock_hub.update_user_hub_properties.assert_called_once_with(
            "user-x", {"is_service_provider": True}
        )

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_updates_existing_entry(self, mock_hub, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        # UPDATE: competence_id is present, price_range is optional
        skills = [{"competence_id": "c1", "title": "Plumbing Pro"}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        mock_firestore.update_competence.assert_called_once()
        # Weaviate sync must use ALL competence dicts from Firestore, not just the updated title.
        mock_hub.update_competencies_by_user_id.assert_called_once_with(
            "user-x",
            [{"competence_id": "c1", "title": "Plumbing"}, {"competence_id": "c2", "title": "Electrical"}],
        )

    async def test_save_competence_batch_missing_price_range_returns_error(
        self, registry, mock_firestore
    ):
        """New entries without price_range must return an error dict — never reach Firestore."""
        ctx = self._ctx(mock_firestore)
        avail = {"monday_time_ranges": [{"start_time": "08:00", "end_time": "17:00"}]}
        skills = [{"title": "Coaching", "availability_time": avail}]  # price_range intentionally absent
        result = await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert isinstance(result, dict) and "error" in result, (
            "Missing price_range for a new entry must return an error"
        )
        assert "price_range" in result["error"].lower() or "pricing" in result["error"].lower()
        mock_firestore.create_competence.assert_not_called()

    async def test_save_competence_batch_missing_availability_time_returns_error(
        self, registry, mock_firestore
    ):
        """New entries without availability_time must return an error dict — never reach Firestore."""
        ctx = self._ctx(mock_firestore)
        skills = [{"title": "Coaching", "price_range": "€50/h"}]  # availability_time intentionally absent
        result = await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert isinstance(result, dict) and "error" in result, (
            "Missing availability_time for a new entry must return an error"
        )
        assert "availability" in result["error"].lower()
        mock_firestore.create_competence.assert_not_called()

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_update_without_availability_time_is_allowed(
        self, mock_hub, registry, mock_firestore
    ):
        """UPDATE (competence_id present) without availability_time must proceed normally."""
        ctx = self._ctx(mock_firestore)
        skills = [{"competence_id": "c1", "description": "Now offering weekend slots"}]
        result = await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert not (isinstance(result, dict) and "error" in result), (
            "Updates without availability_time must not be blocked"
        )
        mock_firestore.update_competence.assert_called_once()

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_update_without_price_range_is_allowed(
        self, mock_hub, registry, mock_firestore
    ):
        """UPDATE (competence_id present) without price_range must proceed normally."""
        ctx = self._ctx(mock_firestore)
        skills = [{"competence_id": "c1", "description": "Updated description"}]
        result = await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert not (isinstance(result, dict) and "error" in result), (
            "Updates without price_range must not be blocked"
        )
        mock_firestore.update_competence.assert_called_once()

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_deduplicates_by_title(
        self, mock_hub, registry, mock_firestore
    ):
        """When a new skill (no competence_id) has the same title as an existing
        competence (case-insensitive), save_competence_batch must upgrade it to an
        UPDATE — never create a duplicate entry.

        Regression for: "Presentation Help" appearing twice after a second onboarding
        session where the LLM omitted competence_id for an already-registered skill.
        """
        # Firestore already has "Plumbing" (c1) and "Electrical" (c2)
        ctx = self._ctx(mock_firestore)
        # Submit with the same title but no competence_id — simulates LLM omission
        skills = [{"title": "Plumbing", "price_range": "€60/h", "description": "Updated desc"}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)

        # Must call update_competence (with c1), never create_competence
        mock_firestore.update_competence.assert_called_once()
        update_args = mock_firestore.update_competence.call_args
        called_id = update_args.args[1] if len(update_args.args) > 1 else update_args.kwargs.get("competence_id")
        assert called_id == "c1", f"Expected update on 'c1', got '{called_id}'"
        mock_firestore.create_competence.assert_not_called()

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_deduplication_is_case_insensitive(
        self, mock_hub, registry, mock_firestore
    ):
        """Title match for deduplication must be case-insensitive."""
        ctx = self._ctx(mock_firestore)
        skills = [{"title": "plumbing", "price_range": "€60/h"}]  # lowercase
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        mock_firestore.update_competence.assert_called_once()
        mock_firestore.create_competence.assert_not_called()

    # ── availability_time subcollection ──────────────────────────────────────

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_writes_availability_time_subcollection(
        self, mock_hub, registry, mock_firestore
    ):
        """When a skill includes availability_time, it must be validated and written
        to the availability_time subcollection (not stored on the competence doc)."""
        ctx = self._ctx(mock_firestore)
        skills = [
            {
                "title": "Gardening",
                "description": "I love plants",
                "category": "Garten",
                "price_range": "€30–€50/h",
                "availability_time": {
                    "monday_time_ranges": [{"start_time": "09:00", "end_time": "12:00"}],
                },
            }
        ]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        # availability_time must be written to the subcollection
        mock_firestore.create_availability_time.assert_called_once()
        # availability_time must NOT be stored on the competence document itself
        create_call = mock_firestore.create_competence.call_args
        competence_data = create_call.args[1] if len(create_call.args) > 1 else create_call.kwargs.get("competence_data", {})
        assert "availability_time" not in competence_data

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_invalid_availability_time_returns_field_errors(
        self, mock_hub, registry, mock_firestore
    ):
        """A skill with an improperly formatted availability_time must return field-level
        errors so the LLM can self-correct — Firestore must not be written."""
        # Wire real validation so that malformed time strings are actually caught.
        mock_firestore._validate_data = lambda data, schema, exclude_unset=False: \
            FirestoreService._validate_data(mock_firestore, data, schema, exclude_unset)
        mock_firestore._format_validation_errors = FirestoreService._format_validation_errors
        ctx = self._ctx(mock_firestore)
        skills = [
            {
                "title": "Gardening",
                "description": "I love plants",
                "category": "Garten",
                "price_range": "€30–€50/h",
                "availability_time": {
                    "monday_time_ranges": [{"start_time": "09:00", "end_time": "not-a-time"}],
                },
            }
        ]
        result = await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        assert isinstance(result, dict)
        assert "error" in result
        assert "field_errors" in result
        field_errs = result["field_errors"]
        assert any("time" in k.lower() for k in field_errs), (
            f"Expected a time-related field error, got: {field_errs}"
        )
        # Subcollection must NOT be written on validation failure
        mock_firestore.create_availability_time.assert_not_called()

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_updates_existing_availability_time(
        self, mock_hub, registry, mock_firestore
    ):
        """When an existing availability_time doc already exists for the competence,
        update_availability_time must be called instead of create_availability_time."""
        mock_firestore.get_availability_times = AsyncMock(return_value=[
            {"availability_time_id": "at-existing"}
        ])
        ctx = self._ctx(mock_firestore)
        skills = [
            {
                "competence_id": "c1",
                "title": "Plumbing",
                "availability_time": {
                    "tuesday_time_ranges": [{"start_time": "10:00", "end_time": "14:00"}],
                },
            }
        ]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)
        mock_firestore.update_availability_time.assert_called_once()
        mock_firestore.create_availability_time.assert_not_called()

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
    async def test_save_competence_batch_self_heals_when_weaviate_user_missing(
        self, mock_hub, registry, mock_firestore
    ):
        """When Weaviate reports 'User not found', the tool must create the Weaviate user
        from Firestore data and retry with create_competencies_by_user_id.

        Regression for: 'No user found with user_id' logged during save_competence_batch
        when the user exists in Firestore but is absent from Weaviate.
        """
        mock_hub.update_competencies_by_user_id.return_value = {
            "success": False,
            "error": "User not found",
            "updated_uuids": [],
        }
        mock_firestore.get_user = AsyncMock(return_value={
            "user_id": "user-x",
            "name": "Vinh",
            "email": "vinh@example.com",
        })
        ctx = self._ctx(mock_firestore)
        skills = [{"title": "Machine Learning", "price_range": "€80/h", "availability_time": {"monday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}]}}]
        await registry.execute("save_competence_batch", {"skills": skills}, ctx)

        # Must attempt create_user to establish the Weaviate hub row
        mock_hub.create_user.assert_called_once()
        # Must retry sync via update_competencies_by_user_id (called twice: once failing, once in retry)
        assert mock_hub.update_competencies_by_user_id.call_count == 2

    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_save_competence_batch_self_heal_failure_propagates(
        self, mock_hub, registry, mock_firestore
    ):
        """If the self-heal itself fails, the error must propagate — not be swallowed."""
        mock_hub.update_competencies_by_user_id.return_value = {
            "success": False,
            "error": "User not found",
            "updated_uuids": [],
        }
        mock_firestore.get_user = AsyncMock(return_value={"user_id": "user-x"})
        mock_hub.create_user.side_effect = Exception("Weaviate unavailable")
        ctx = self._ctx(mock_firestore)
        with pytest.raises(Exception, match="Weaviate unavailable"):
            await registry.execute("save_competence_batch", {"skills": [{"title": "Plumbing", "price_range": "€50/h"}]}, ctx)


    @patch("ai_assistant.services.agent_tools.HubSpokeIngestion")
    async def test_delete_competences_weaviate_failure_propagates(
        self, mock_hub, registry, mock_firestore
    ):
        """Weaviate sync failure must propagate — not be silently swallowed."""
        mock_hub.remove_competence_by_firestore_id.side_effect = Exception("Weaviate unavailable")
        ctx = self._ctx(mock_firestore)
        with pytest.raises(Exception, match="Weaviate unavailable"):
            await registry.execute("delete_competences", {"competence_ids": ["c1"]}, ctx)


# ─────────────────────────────────────────────────────────────────────────────
# cancel_service_request tool
# ─────────────────────────────────────────────────────────────────────────────

class TestCancelServiceRequestTool:
    """Tests for the cancel_service_request agent tool."""

    @pytest.fixture
    def mock_firestore(self):
        fs = Mock()
        fs.update_service_request = AsyncMock(return_value={"id": "sr-99", "status": "cancelled"})
        return fs

    @pytest.fixture
    def registry(self):
        return build_default_registry()

    def _ctx(self, fs, *, has_cap=True):
        caps = [ToolCapability("service_requests", "write")] if has_cap else []
        return {
            "user_id": "user-abc",
            "user_capabilities": caps,
            "data_provider": Mock(),
            "firestore_service": fs,
        }

    # ── Registration ──────────────────────────────────────────────────────────

    def test_tool_is_registered(self, registry):
        tool = registry.get("cancel_service_request")
        assert tool is not None

    def test_requires_service_requests_write_capability(self, registry):
        tool = registry.get("cancel_service_request")
        assert tool.required_capability == ToolCapability("service_requests", "write")

    def test_schema_has_required_request_id_param(self, registry):
        schema = registry.get("cancel_service_request").schema
        assert "request_id" in schema["parameters"]["properties"]
        assert "request_id" in schema["parameters"]["required"]

    # ── Happy path ────────────────────────────────────────────────────────────

    async def test_calls_update_service_request_with_cancelled_status(
        self, registry, mock_firestore
    ):
        ctx = self._ctx(mock_firestore)
        await registry.execute("cancel_service_request", {"request_id": "sr-99"}, ctx)
        mock_firestore.update_service_request.assert_called_once_with(
            "sr-99", {"status": "cancelled"}
        )

    async def test_returns_cancelled_true_and_request_id(self, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        result = await registry.execute(
            "cancel_service_request", {"request_id": "sr-99"}, ctx
        )
        assert result == {"cancelled": True, "request_id": "sr-99"}

    # ── Error cases ───────────────────────────────────────────────────────────

    async def test_returns_error_when_request_id_missing(self, registry, mock_firestore):
        ctx = self._ctx(mock_firestore)
        result = await registry.execute("cancel_service_request", {}, ctx)
        assert "error" in result
        mock_firestore.update_service_request.assert_not_called()

    async def test_raises_permission_error_without_write_cap(self, registry, mock_firestore):
        ctx = self._ctx(mock_firestore, has_cap=False)
        with pytest.raises(ToolPermissionError) as exc_info:
            await registry.execute("cancel_service_request", {"request_id": "sr-1"}, ctx)
        err = exc_info.value
        assert err.tool_name == "cancel_service_request"
        assert err.required_capability == ToolCapability("service_requests", "write")


# ─────────────────────────────────────────────────────────────────────────────
# _require_fs — fail-fast guard
# ─────────────────────────────────────────────────────────────────────────────

class TestRequireFs:
    """Tests for the _require_fs context-validation helper."""

    def test_returns_fs_when_present(self):
        fs = Mock()
        ctx = {"firestore_service": fs}
        assert _require_fs(ctx) is fs

    def test_raises_runtime_error_when_none(self):
        ctx = {"firestore_service": None}
        with pytest.raises(RuntimeError, match="firestore_service not injected"):
            _require_fs(ctx)

    def test_raises_runtime_error_when_key_missing(self):
        ctx = {}
        with pytest.raises(RuntimeError, match="firestore_service not injected"):
            _require_fs(ctx)

    @pytest.mark.parametrize("tool_name", [
        "get_favorites",
        "get_open_requests",
        "create_service_request",
        "record_provider_interest",
        "get_my_competencies",
        "save_competence_batch",
        "delete_competences",
    ])
    async def test_all_firestore_tools_raise_runtime_error_when_fs_is_none(
        self, tool_name
    ):
        """Every Firestore-dependent tool must raise RuntimeError (not AttributeError)
        when firestore_service is missing from context."""
        registry = build_default_registry()
        all_caps = [
            ToolCapability("favorites", "read"),
            ToolCapability("service_requests", "read"),
            ToolCapability("service_requests", "write"),
            ToolCapability("provider_onboarding", "write"),
        ]
        ctx = {
            "user_id": "u1",
            "user_capabilities": all_caps,
            "data_provider": Mock(),
            "firestore_service": None,  # ← the misconfiguration
        }
        params: dict = {}
        if tool_name == "record_provider_interest":
            params = {"decision": "accepted"}
        elif tool_name == "save_competence_batch":
            params = {"skills": [{"title": "Plumbing"}]}
        elif tool_name == "delete_competences":
            params = {"competence_ids": ["c1"]}

        with pytest.raises(RuntimeError, match="firestore_service not injected"):
            await registry.execute(tool_name, params, ctx)
