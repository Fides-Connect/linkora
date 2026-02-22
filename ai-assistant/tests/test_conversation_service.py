"""
Unit tests for ConversationService.
Tests conversation flow, stage management, and provider search timing.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from ai_assistant.services.conversation_service import ConversationService, ConversationStage, is_legal_transition


# ─────────────────────────────────────────────────────────────────────────────
# ConversationStage Enum contract
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationStageEnum:

    def test_all_8_members_exist(self):
        expected = {
            "GREETING", "TRIAGE", "CLARIFY", "TOOL_EXECUTION",
            "CONFIRMATION", "FINALIZE", "RECOVERY", "COMPLETED",
            "PROVIDER_PITCH", "PROVIDER_ONBOARDING",
        }
        actual = {m.name for m in ConversationStage}
        assert actual == expected

    def test_each_member_is_string_valued(self):
        for member in ConversationStage:
            assert isinstance(member.value, str), f"{member.name} value is not a str"

    def test_lookup_by_value(self):
        assert ConversationStage("triage") == ConversationStage.TRIAGE

    def test_members_are_enum_instances(self):
        assert isinstance(ConversationStage.TRIAGE, ConversationStage)


# ─────────────────────────────────────────────────────────────────────────────
# is_legal_transition
# ─────────────────────────────────────────────────────────────────────────────

class TestIsLegalTransition:

    @pytest.mark.parametrize("from_s,to_s", [
        (ConversationStage.GREETING,  ConversationStage.TRIAGE),
        (ConversationStage.TRIAGE,    ConversationStage.FINALIZE),
        (ConversationStage.TRIAGE,    ConversationStage.CLARIFY),
        (ConversationStage.TRIAGE,    ConversationStage.TOOL_EXECUTION),
        (ConversationStage.TRIAGE,    ConversationStage.RECOVERY),
        (ConversationStage.CLARIFY,   ConversationStage.TRIAGE),
        (ConversationStage.FINALIZE,  ConversationStage.COMPLETED),
        (ConversationStage.FINALIZE,  ConversationStage.RECOVERY),
        (ConversationStage.RECOVERY,  ConversationStage.TRIAGE),
        # Provider pitch + onboarding
        (ConversationStage.COMPLETED,          ConversationStage.PROVIDER_PITCH),
        (ConversationStage.PROVIDER_PITCH,     ConversationStage.PROVIDER_ONBOARDING),
        (ConversationStage.PROVIDER_PITCH,     ConversationStage.COMPLETED),
        (ConversationStage.PROVIDER_ONBOARDING, ConversationStage.COMPLETED),
        # Direct onboarding from TRIAGE (existing providers managing skills)
        (ConversationStage.TRIAGE,    ConversationStage.PROVIDER_ONBOARDING),
    ])
    def test_legal_pairs_return_true(self, from_s, to_s):
        assert is_legal_transition(from_s, to_s) is True

    @pytest.mark.parametrize("from_s,to_s", [
        (ConversationStage.GREETING,       ConversationStage.COMPLETED),
        (ConversationStage.COMPLETED,      ConversationStage.TRIAGE),
        (ConversationStage.TRIAGE,         ConversationStage.GREETING),
        (ConversationStage.COMPLETED,      ConversationStage.GREETING),
        (ConversationStage.PROVIDER_PITCH, ConversationStage.TRIAGE),
    ])
    def test_illegal_pairs_return_false(self, from_s, to_s):
        assert is_legal_transition(from_s, to_s) is False

    def test_completed_self_loop_returns_false(self):
        assert is_legal_transition(ConversationStage.COMPLETED, ConversationStage.COMPLETED) is False


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    service = Mock()
    service.generate = AsyncMock(return_value="Hallo! Wie kann ich helfen?")
    
    async def mock_generate_stream(*args, **kwargs):
        yield "Test response"
    
    service.generate_stream = mock_generate_stream
    return service


@pytest.fixture
def mock_data_provider():
    """Mock data provider."""
    provider = Mock()
    provider.search_providers = AsyncMock(return_value=[
        {
            "provider_id": "p1",
            "name": "Test Provider",
            "description": "Expert in plumbing",
            "category": "plumbing"
        },
        {
            "provider_id": "p2",
            "name": "Another Provider",
            "description": "Electrical expert",
            "category": "electrical"
        }
    ])
    return provider


@pytest.fixture
def conversation_service(mock_llm_service, mock_data_provider):
    """Create ConversationService instance."""
    return ConversationService(
        llm_service=mock_llm_service,
        data_provider=mock_data_provider,
        agent_name="TestAgent",
        company_name="TestCompany",
        max_providers=3,
        language='de'
    )


class TestProviderSearchMethod:
    """Test the search_providers_for_request method."""
    
    @pytest.mark.asyncio
    async def test_search_providers_for_request_basic(self, conversation_service, mock_data_provider):
        """Test basic provider search functionality."""
        # Setup: simulate the agent's conversational summary (captured during triage)
        conversation_service.context["user_problem"] = ["Ich brauche einen Klempner für mein Badezimmer"]
        conversation_service.context["ai_responses"] = ["User needs a plumber for bathroom repair", "Latest message"]
        
        # Execute
        await conversation_service.search_providers_for_request()
        
        # Verify: search was called with the agent's conversational summary
        mock_data_provider.search_providers.assert_called_once_with(
            query_text="User needs a plumber for bathroom repair",
            limit=3
        )
        
        # Verify: providers were stored in context
        assert len(conversation_service.context["providers_found"]) == 2
        assert conversation_service.context["providers_found"][0]["provider_id"] == "p1"
    
    @pytest.mark.asyncio
    async def test_search_providers_with_no_category(self, conversation_service, mock_data_provider):
        """Test provider search when no category is detected."""
        # Setup: agent's conversational summary without detected category
        conversation_service.context["user_problem"] = ["I need help with something"]
        conversation_service.context["ai_responses"] = ["User needs general assistance", "Latest message"]
        
        # Execute
        await conversation_service.search_providers_for_request()
        
        # Verify: search was called with conversational summary and None category
        mock_data_provider.search_providers.assert_called_once_with(
            query_text="User needs general assistance",
            limit=3
        )
    
    @pytest.mark.asyncio
    async def test_search_providers_empty_results(self, conversation_service, mock_data_provider):
        """Test provider search when no providers are found."""
        # Setup: mock empty results
        mock_data_provider.search_providers.return_value = []
        conversation_service.context["user_problem"] = ["Very specific request"]
        conversation_service.context["ai_responses"] = ["Specific service needed", "Latest message"]
        
        # Execute
        await conversation_service.search_providers_for_request()
        
        # Verify: providers_found is empty list
        assert conversation_service.context["providers_found"] == []
    
    @pytest.mark.asyncio
    async def test_search_providers_respects_max_limit(self, conversation_service, mock_data_provider):
        """Test that search respects the max_providers limit."""
        # Setup
        conversation_service.max_providers = 5
        conversation_service.context["user_problem"] = ["Need electrician"]
        conversation_service.context["ai_responses"] = ["Electrician needed urgently", "Latest message"]
        
        # Execute
        await conversation_service.search_providers_for_request()
        
        # Verify: limit parameter matches max_providers
        mock_data_provider.search_providers.assert_called_once()
        call_kwargs = mock_data_provider.search_providers.call_args[1]
        assert call_kwargs["limit"] == 5


class TestAccumulateProblemDescription:
    """Test the accumulate_problem_description method."""
    
    @pytest.mark.asyncio
    async def test_accumulate_problem_description(self, conversation_service):
        """Test that problem description is accumulated correctly."""
        # Initial state
        assert conversation_service.context["user_problem"] == []
        
        # Execute: accumulate first input
        await conversation_service.accumulate_problem_description("Mein Wasserhahn tropft")
        
        # Verify
        assert "Mein Wasserhahn tropft" in conversation_service.context["user_problem"]
    
    @pytest.mark.asyncio
    async def test_accumulate_multiple_inputs(self, conversation_service):
        """Test accumulating multiple user inputs."""
        # Execute: accumulate multiple inputs
        await conversation_service.accumulate_problem_description("Ich brauche einen Klempner")
        await conversation_service.accumulate_problem_description("Es ist dringend")
        await conversation_service.accumulate_problem_description("Im Badezimmer")
        
        # Verify: all inputs are accumulated
        problem = conversation_service.context["user_problem"]
        assert any("Klempner" in item for item in problem)
        assert any("dringend" in item for item in problem)
        assert any("Badezimmer" in item for item in problem)
    
    @pytest.mark.asyncio
    async def test_accumulate_does_not_search(self, conversation_service, mock_data_provider):
        """Test that accumulate does NOT trigger provider search."""
        # Execute: accumulate problem description
        await conversation_service.accumulate_problem_description("Ich brauche einen Klempner")
        
        # Verify: search was NOT called
        mock_data_provider.search_providers.assert_not_called()


class TestStageManagement:
    """Test conversation stage management."""

    def test_initial_stage_is_greeting(self, conversation_service):
        """Initial stage must be GREETING."""
        assert conversation_service.get_current_stage() == ConversationStage.GREETING

    def test_set_stage_to_triage(self, conversation_service):
        conversation_service.set_stage(ConversationStage.TRIAGE)
        assert conversation_service.get_current_stage() == ConversationStage.TRIAGE

    def test_set_stage_to_finalize(self, conversation_service):
        conversation_service.set_stage(ConversationStage.FINALIZE)
        assert conversation_service.get_current_stage() == ConversationStage.FINALIZE

    def test_set_stage_to_clarify(self, conversation_service):
        conversation_service.set_stage(ConversationStage.TRIAGE)
        conversation_service.set_stage(ConversationStage.CLARIFY)
        assert conversation_service.get_current_stage() == ConversationStage.CLARIFY

    def test_set_stage_to_recovery(self, conversation_service):
        conversation_service.set_stage(ConversationStage.FINALIZE)
        conversation_service.set_stage(ConversationStage.RECOVERY)
        assert conversation_service.get_current_stage() == ConversationStage.RECOVERY

    def test_set_stage_to_tool_execution(self, conversation_service):
        conversation_service.set_stage(ConversationStage.TRIAGE)
        conversation_service.set_stage(ConversationStage.TOOL_EXECUTION)
        assert conversation_service.get_current_stage() == ConversationStage.TOOL_EXECUTION

    def test_legal_transition_applied_via_set_stage(self, conversation_service):
        """set_stage + is_legal_transition work end-to-end."""
        conversation_service.set_stage(ConversationStage.TRIAGE)
        assert is_legal_transition(
            conversation_service.get_current_stage(), ConversationStage.FINALIZE
        ) is True
        conversation_service.set_stage(ConversationStage.FINALIZE)
        assert conversation_service.get_current_stage() == ConversationStage.FINALIZE


class TestConversationFlow:
    """Test complete conversation flow scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_triage_to_finalize_flow(self, conversation_service, mock_data_provider):
        """Stage is set via set_stage (driven by orchestrator signal_transition) then search runs."""
        # Accumulate problem descriptions during TRIAGE
        conversation_service.set_stage(ConversationStage.TRIAGE)
        await conversation_service.accumulate_problem_description("Mein Wasserhahn tropft")
        await conversation_service.accumulate_problem_description("Es ist im Badezimmer")
        mock_data_provider.search_providers.assert_not_called()

        # Orchestrator calls set_stage when signal_transition("finalize") is received
        assert is_legal_transition(
            conversation_service.get_current_stage(), ConversationStage.FINALIZE
        ) is True
        conversation_service.set_stage(ConversationStage.FINALIZE)

        # Orchestrator then calls search_providers_for_request
        await conversation_service.search_providers_for_request()

        mock_data_provider.search_providers.assert_called_once()
        assert len(conversation_service.context["providers_found"]) > 0
    
    @pytest.mark.asyncio
    async def test_greeting_generation(self, conversation_service, mock_llm_service):
        """Test greeting generation."""
        # Execute
        greeting = await conversation_service.generate_greeting(
            session_id="test-session",
            user_name="Max",
            has_open_request=False
        )
        
        # Verify: greeting was generated
        assert greeting is not None
        assert len(greeting) > 0
        
        # Verify: stage transitioned to TRIAGE after greeting
        assert conversation_service.get_current_stage() == ConversationStage.TRIAGE


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 — prompt templates for new stages
# ─────────────────────────────────────────────────────────────────────────────

class TestPromptTemplatesForNewStages:

    def test_clarify_stage_uses_dedicated_template(self, conversation_service):
        from ai_assistant.prompts_templates import CLARIFY_PROMPT
        template = conversation_service.create_prompt_for_stage(ConversationStage.CLARIFY)
        # The system message should contain CLARIFY_PROMPT content, not TRIAGE
        rendered = str(template.messages[0])
        assert "CLARIFY" in rendered.upper() or "clarif" in rendered.lower()

    def test_confirmation_stage_uses_dedicated_template(self, conversation_service):
        template = conversation_service.create_prompt_for_stage(ConversationStage.CONFIRMATION)
        rendered = str(template.messages[0])
        assert "CONFIRMATION" in rendered.upper() or "confirm" in rendered.lower()

    def test_recovery_stage_uses_dedicated_template(self, conversation_service):
        template = conversation_service.create_prompt_for_stage(ConversationStage.RECOVERY)
        rendered = str(template.messages[0])
        assert "RECOVERY" in rendered.upper() or "recover" in rendered.lower()

    def test_triage_prompt_contains_state_contract(self, conversation_service):
        from ai_assistant.prompts_templates import TRIAGE_CONVERSATION_PROMPT
        assert "signal_transition" in TRIAGE_CONVERSATION_PROMPT
        assert "State Contract" in TRIAGE_CONVERSATION_PROMPT

    def test_clarify_prompt_exported(self):
        from ai_assistant.prompts_templates import CLARIFY_PROMPT
        assert "signal_transition" in CLARIFY_PROMPT
        assert CLARIFY_PROMPT.strip()

    def test_confirmation_prompt_exported(self):
        from ai_assistant.prompts_templates import CONFIRMATION_PROMPT
        assert "signal_transition" in CONFIRMATION_PROMPT
        assert CONFIRMATION_PROMPT.strip()

    def test_recovery_prompt_exported(self):
        from ai_assistant.prompts_templates import RECOVERY_PROMPT
        assert "signal_transition" in RECOVERY_PROMPT
        assert RECOVERY_PROMPT.strip()

