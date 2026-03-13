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

    def test_all_10_members_exist(self):
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
        (ConversationStage.TRIAGE,    ConversationStage.CONFIRMATION),
        (ConversationStage.TRIAGE,    ConversationStage.CLARIFY),
        (ConversationStage.TRIAGE,    ConversationStage.TOOL_EXECUTION),
        (ConversationStage.TRIAGE,    ConversationStage.RECOVERY),
        (ConversationStage.CLARIFY,   ConversationStage.TRIAGE),
        (ConversationStage.FINALIZE,  ConversationStage.COMPLETED),
        (ConversationStage.FINALIZE,  ConversationStage.RECOVERY),
        (ConversationStage.RECOVERY,  ConversationStage.TRIAGE),
        # Provider pitch + onboarding
        (ConversationStage.COMPLETED,          ConversationStage.PROVIDER_PITCH),
        (ConversationStage.COMPLETED,          ConversationStage.TRIAGE),
        (ConversationStage.PROVIDER_PITCH,     ConversationStage.PROVIDER_ONBOARDING),
        (ConversationStage.PROVIDER_PITCH,     ConversationStage.COMPLETED),
        (ConversationStage.PROVIDER_ONBOARDING, ConversationStage.COMPLETED),
        # Provider stages can escape back to triage (user pivots to seeking a service)
        (ConversationStage.PROVIDER_PITCH,     ConversationStage.TRIAGE),
        (ConversationStage.PROVIDER_ONBOARDING, ConversationStage.TRIAGE),
        # Direct onboarding from TRIAGE (existing providers managing skills)
        (ConversationStage.TRIAGE,    ConversationStage.PROVIDER_ONBOARDING),
    ])
    def test_legal_pairs_return_true(self, from_s, to_s):
        assert is_legal_transition(from_s, to_s) is True

    @pytest.mark.parametrize("from_s,to_s", [
        (ConversationStage.GREETING,       ConversationStage.COMPLETED),
        (ConversationStage.TRIAGE,         ConversationStage.GREETING),
        (ConversationStage.TRIAGE,         ConversationStage.FINALIZE),
        (ConversationStage.COMPLETED,      ConversationStage.GREETING),
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

    # In-memory histories keyed by session_id — mirrors the real LLMService.
    _histories: dict = {}

    class _FakeHistory:
        def __init__(self):
            self.messages = []

        def add_message(self, msg):
            self.messages.append(msg)

    def _get_history(sid: str) -> _FakeHistory:
        if sid not in _histories:
            _histories[sid] = _FakeHistory()
        return _histories[sid]

    service.get_session_history = Mock(side_effect=_get_history)

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
        # no cross_encoder_service — reranking skipped in unit tests
    )


class TestProviderSearchMethod:
    """Test the search_providers_for_request method."""

    async def test_search_triggers_data_provider_call(
        self, conversation_service, mock_data_provider
    ):
        """search_providers_for_request always calls the data provider."""
        conversation_service.context["user_problem"] = ["Ich brauche einen Klempner"]
        await conversation_service.search_providers_for_request()
        mock_data_provider.search_providers.assert_called_once()

    async def test_uses_recorded_ai_response_as_summary(
        self, conversation_service, mock_data_provider, mock_llm_service
    ):
        """_generate_structured_query receives the last recorded AI response."""
        conversation_service.record_ai_response("Klempner für Badezimmer, dringend")
        await conversation_service.search_providers_for_request()
        # generate is called twice: structured-query extraction (index 0) + HyDE (index 1)
        assert mock_llm_service.generate.call_count == 2
        # First call is the structured query extraction — must contain the summary
        first_call_prompt = mock_llm_service.generate.call_args_list[0][0][0][0].content
        assert "Klempner für Badezimmer" in first_call_prompt

    async def test_falls_back_to_user_problem_when_no_ai_response(
        self, conversation_service, mock_data_provider, mock_llm_service
    ):
        """Falls back to joined user inputs when no AI response has been recorded."""
        conversation_service.context["user_problem"] = ["I need an electrician"]
        await conversation_service.search_providers_for_request()
        # First generate call is the structured query extraction
        first_call_prompt = mock_llm_service.generate.call_args_list[0][0][0][0].content
        assert "Electrician" in first_call_prompt

    async def test_providers_stored_in_context(
        self, conversation_service, mock_data_provider
    ):
        """Found providers are stored in context['providers_found']."""
        conversation_service.context["user_problem"] = ["need plumber"]
        await conversation_service.search_providers_for_request()
        assert len(conversation_service.context["providers_found"]) == 2
        assert conversation_service.context["providers_found"][0]["provider_id"] == "p1"

    async def test_empty_results_stored_in_context(
        self, conversation_service, mock_data_provider
    ):
        """Empty provider list stored in context when search returns nothing."""
        mock_data_provider.search_providers.return_value = []
        conversation_service.context["user_problem"] = ["very specific"]
        await conversation_service.search_providers_for_request()
        assert conversation_service.context["providers_found"] == []

    async def test_respects_max_providers_limit(
        self, conversation_service, mock_data_provider
    ):
        """max_providers is passed directly; HubSpokeSearch does its own wide-net expansion."""
        conversation_service.max_providers = 5
        conversation_service.context["user_problem"] = ["need electrician"]
        await conversation_service.search_providers_for_request()
        call_kwargs = mock_data_provider.search_providers.call_args[1]
        # max_providers passed directly — no pre-multiplication here;
        # HubSpokeSearch.hybrid_search_providers handles min(limit * 5, 30) internally.
        assert call_kwargs["limit"] == 5

    async def test_history_excerpt_included_when_session_id_provided(
        self, conversation_service, mock_data_provider, mock_llm_service
    ):
        """Last 3 history messages appear in the structured-query extraction prompt."""
        from langchain_core.messages import HumanMessage as HM, AIMessage as AM
        history = mock_llm_service.get_session_history("sess-x")
        history.add_message(HM(content="I need a plumber"))
        history.add_message(AM(content="Sure! Is it urgent?"))
        history.add_message(HM(content="Yes, today please"))
        conversation_service.context["user_problem"] = ["plumber"]
        await conversation_service.search_providers_for_request(session_id="sess-x")
        # First generate call is structured query; second is HyDE
        first_call_prompt = mock_llm_service.generate.call_args_list[0][0][0][0].content
        assert "Yes, today please" in first_call_prompt
        assert "Is it urgent?" in first_call_prompt


class TestHydeGeneration:
    """Tests for _generate_hyde_text."""

    async def test_returns_llm_output(self, conversation_service, mock_llm_service):
        mock_llm_service.generate = AsyncMock(return_value="A skilled plumber with 10 years of experience.")
        result = await conversation_service._generate_hyde_text("I need a plumber")
        assert "plumber" in result.lower()

    async def test_uses_hyde_prompt_template(self, conversation_service, mock_llm_service):
        """The prompt sent to generate() must contain the problem summary."""
        mock_llm_service.generate = AsyncMock(return_value="Some profile text")
        await conversation_service._generate_hyde_text("leaking pipe under sink")
        prompt_text = mock_llm_service.generate.call_args[0][0][0].content
        assert "leaking pipe under sink" in prompt_text

    async def test_returns_empty_string_on_error(self, conversation_service, mock_llm_service):
        """On LLM failure, _generate_hyde_text returns '' without raising."""
        mock_llm_service.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        result = await conversation_service._generate_hyde_text("test")
        assert result == ""


class TestSearchProvidersPipelineIntegration:
    """Integration tests for the full multi-stage pipeline in search_providers_for_request."""

    async def test_hyde_text_passed_to_data_provider(
        self, conversation_service, mock_data_provider, mock_llm_service
    ):
        """data_provider.search_providers receives hyde_text kwarg."""
        mock_llm_service.generate = AsyncMock(
            side_effect=[
                '{"available_time": "flex", "category": "Plumber", "criterions": []}',
                "Expert plumber specialising in residential water systems.",
            ]
        )
        conversation_service.context["user_problem"] = ["I need a plumber"]
        await conversation_service.search_providers_for_request()
        call_kwargs = mock_data_provider.search_providers.call_args[1]
        assert "hyde_text" in call_kwargs
        assert call_kwargs["hyde_text"] == "Expert plumber specialising in residential water systems."

    async def test_reranking_applied_when_cross_encoder_wired(
        self, mock_llm_service, mock_data_provider
    ):
        """When cross_encoder_service is injected, rerank() is called and results replaced."""
        reranked = [{"provider_id": "px", "rerank_score": 0.99}]
        mock_cross_encoder = Mock()
        mock_cross_encoder.rerank = AsyncMock(return_value=reranked)

        service = ConversationService(
            llm_service=mock_llm_service,
            data_provider=mock_data_provider,
            max_providers=5,
            cross_encoder_service=mock_cross_encoder,
        )
        service.context["user_problem"] = ["need electrician"]
        await service.search_providers_for_request()

        mock_cross_encoder.rerank.assert_called_once()
        assert service.context["providers_found"] == reranked

    async def test_no_reranking_when_cross_encoder_absent(
        self, conversation_service, mock_data_provider
    ):
        """Without cross_encoder_service, providers are simply sliced to max_providers."""
        conversation_service.max_providers = 1
        conversation_service.context["user_problem"] = ["test"]
        await conversation_service.search_providers_for_request()
        # mock_data_provider returns 2 providers; sliced to 1
        assert len(conversation_service.context["providers_found"]) == 1


class TestStructuredQueryExtractionPrompt:
    """Tests for structured query extraction — specifically the available_time field
    and its English-only token constraint (Bug 2 fix)."""

    def test_prompt_contains_english_token_instruction(self):
        """STRUCTURED_QUERY_EXTRACTION_PROMPT must instruct the LLM to output English
        time tokens even in non-English sessions (e.g. 'monday' not 'Montag')."""
        from ai_assistant.prompts_templates import STRUCTURED_QUERY_EXTRACTION_PROMPT
        prompt_lower = STRUCTURED_QUERY_EXTRACTION_PROMPT.lower()
        assert "monday" in prompt_lower, (
            "Prompt must list 'monday' as an example to ensure English tokens are used"
        )
        # The prompt uses 'Montag' as a negative example ("use 'monday' not 'Montag'"),
        # which is correct — it teaches the LLM what NOT to do.
        assert "never output translated day names" in prompt_lower, (
            "Prompt must explicitly forbid translated day names"
        )
        assert "english time tokens" in prompt_lower, (
            "Prompt must explicitly require English time tokens"
        )

    async def test_german_day_name_in_available_time_skips_filter(self):
        """If the LLM ignores the prompt instruction and returns a German day name,
        the availability filter must still be skipped gracefully (no crash, no bogus filter).

        This is a safety regression test: before Bug-2 fix, German sessions would silently
        produce no availability filter (correct outcome, wrong reason). After the fix the
        prompt guidance steers the LLM to produce 'monday' instead. But even if it
        doesn't, the token-intersection guard in _build_filters_and_query must protect us.
        """
        from unittest.mock import patch, MagicMock
        from ai_assistant.hub_spoke_search import HubSpokeSearch

        german_day_names = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        for german in german_day_names:
            with patch("ai_assistant.hub_spoke_search.Filter") as MockFilter:
                mock_fi = MagicMock()
                mock_fi.__and__ = MagicMock(return_value=mock_fi)
                mock_fi.__or__ = MagicMock(return_value=mock_fi)
                mock_fi.by_property.return_value = mock_fi
                mock_fi.greater_or_equal.return_value = mock_fi
                mock_fi.is_none.return_value = mock_fi
                mock_fi.equal.return_value = mock_fi
                mock_fi.contains_any.return_value = mock_fi
                MockFilter.by_property.return_value = mock_fi
                MockFilter.by_ref.return_value = mock_fi

                _, _, _, flag = HubSpokeSearch._build_filters_and_query(
                    {"available_time": german, "category": "Electrician", "criterions": []},
                    max_inactive_days=180,
                )

                property_names_used = [c.args[0] for c in MockFilter.by_property.call_args_list]
                assert "availability_tags" not in property_names_used, (
                    f"German day name {german!r} must not add an availability_tags filter "
                    f"(it is not in _AVAILABILITY_TOKENS)"
                )
                assert flag is False, f"availability_filter_applied must be False for German day {german!r}"

    async def test_english_day_name_in_available_time_applies_filter(self):
        """When the LLM correctly outputs an English day name, the filter MUST fire."""
        from unittest.mock import patch, MagicMock
        from ai_assistant.hub_spoke_search import HubSpokeSearch

        for english in ["monday", "tuesday", "saturday", "morning", "evening"]:
            with patch("ai_assistant.hub_spoke_search.Filter") as MockFilter:
                mock_fi = MagicMock()
                mock_fi.__and__ = MagicMock(return_value=mock_fi)
                mock_fi.__or__ = MagicMock(return_value=mock_fi)
                mock_fi.by_property.return_value = mock_fi
                mock_fi.greater_or_equal.return_value = mock_fi
                mock_fi.is_none.return_value = mock_fi
                mock_fi.equal.return_value = mock_fi
                mock_fi.contains_any.return_value = mock_fi
                MockFilter.by_property.return_value = mock_fi
                MockFilter.by_ref.return_value = mock_fi

                _, _, _, flag = HubSpokeSearch._build_filters_and_query(
                    {"available_time": english, "category": "Electrician", "criterions": []},
                    max_inactive_days=180,
                )
                assert flag is True, f"availability_filter_applied must be True for {english!r}"


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


class TestRecordAiResponse:
    """Unit tests for ConversationService.record_ai_response()."""

    def test_non_empty_text_is_appended(self, conversation_service):
        conversation_service.record_ai_response("Sounds like you need a plumber.")
        assert conversation_service.context["ai_responses"] == ["Sounds like you need a plumber."]

    def test_empty_string_is_ignored(self, conversation_service):
        conversation_service.record_ai_response("")
        assert conversation_service.context["ai_responses"] == []

    def test_whitespace_only_is_ignored(self, conversation_service):
        conversation_service.record_ai_response("   \n  ")
        assert conversation_service.context["ai_responses"] == []

    def test_multiple_calls_accumulate(self, conversation_service):
        conversation_service.record_ai_response("First response")
        conversation_service.record_ai_response("Second response")
        assert len(conversation_service.context["ai_responses"]) == 2
        assert conversation_service.context["ai_responses"][-1] == "Second response"


class TestGetProblemSummary:
    """Unit tests for ConversationService.get_problem_summary()."""

    def test_returns_last_ai_response_when_present(self, conversation_service):
        conversation_service.record_ai_response("First AI turn")
        conversation_service.record_ai_response("Confirmed: plumber needed urgently")
        assert conversation_service.get_problem_summary() == "Confirmed: plumber needed urgently"

    def test_falls_back_to_user_problem_when_no_ai_response(self, conversation_service):
        conversation_service.context["user_problem"] = ["I need", "a plumber"]
        summary = conversation_service.get_problem_summary()
        assert summary == "I need a plumber"

    def test_returns_empty_string_when_both_empty(self, conversation_service):
        # ai_responses is [] and user_problem is [] → join([]) == ""
        summary = conversation_service.get_problem_summary()
        assert summary == ""


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
        """set_stage + is_legal_transition work end-to-end: TRIAGE → CONFIRMATION → FINALIZE."""
        conversation_service.set_stage(ConversationStage.TRIAGE)
        # Direct TRIAGE → FINALIZE is now illegal
        assert is_legal_transition(
            conversation_service.get_current_stage(), ConversationStage.FINALIZE
        ) is False
        # Mandatory confirmation gate: TRIAGE → CONFIRMATION is legal
        assert is_legal_transition(
            conversation_service.get_current_stage(), ConversationStage.CONFIRMATION
        ) is True
        conversation_service.set_stage(ConversationStage.CONFIRMATION)
        # CONFIRMATION → FINALIZE is legal
        assert is_legal_transition(
            conversation_service.get_current_stage(), ConversationStage.FINALIZE
        ) is True
        conversation_service.set_stage(ConversationStage.FINALIZE)
        assert conversation_service.get_current_stage() == ConversationStage.FINALIZE


class TestConversationFlow:
    """Test complete conversation flow scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_triage_to_finalize_flow(self, conversation_service, mock_data_provider):
        """Stage advances TRIAGE → CONFIRMATION → FINALIZE via two orchestrator signal_transitions."""
        # Accumulate problem descriptions during TRIAGE
        conversation_service.set_stage(ConversationStage.TRIAGE)
        await conversation_service.accumulate_problem_description("Mein Wasserhahn tropft")
        await conversation_service.accumulate_problem_description("Es ist im Badezimmer")
        mock_data_provider.search_providers.assert_not_called()

        # Orchestrator calls set_stage when signal_transition("confirmation") is received
        assert is_legal_transition(
            conversation_service.get_current_stage(), ConversationStage.CONFIRMATION
        ) is True
        conversation_service.set_stage(ConversationStage.CONFIRMATION)

        # TRIAGE → FINALIZE is now illegal
        assert is_legal_transition(
            ConversationStage.TRIAGE, ConversationStage.FINALIZE
        ) is False

        # Orchestrator calls set_stage when signal_transition("finalize") is received from CONFIRMATION
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
        """Test greeting generation returns text without managing stage."""
        # Execute — new signature: no session_id, no manage_stage
        greeting = await conversation_service.generate_greeting_text(
            user_name="Max",
            has_open_request=False,
        )

        # Verify: greeting was generated
        assert greeting is not None
        assert len(greeting) > 0

        # Stage is NOT advanced by generate_greeting_text — still GREETING
        assert conversation_service.get_current_stage() == ConversationStage.GREETING


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


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER_ONBOARDING prompt — is_service_provider injection
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderOnboardingPromptIsServiceProvider:
    """Verifies that create_prompt_for_stage(PROVIDER_ONBOARDING) correctly
    injects the is_service_provider flag from conversation_service.context
    into the rendered prompt."""

    def test_false_flag_renders_false_in_prompt(self, conversation_service):
        """is_service_provider=False must appear in the rendered system message."""
        conversation_service.context["is_service_provider"] = False
        template = conversation_service.create_prompt_for_stage(
            ConversationStage.PROVIDER_ONBOARDING
        )
        rendered = str(template.messages[0])
        assert "False" in rendered, (
            "is_service_provider=False must be visible in the PROVIDER_ONBOARDING prompt"
        )

    def test_true_flag_renders_true_in_prompt(self, conversation_service):
        """is_service_provider=True must appear in the rendered system message."""
        conversation_service.context["is_service_provider"] = True
        template = conversation_service.create_prompt_for_stage(
            ConversationStage.PROVIDER_ONBOARDING
        )
        rendered = str(template.messages[0])
        assert "True" in rendered, (
            "is_service_provider=True must be visible in the PROVIDER_ONBOARDING prompt"
        )

    def test_prompt_contains_step_0_when_not_provider(self, conversation_service):
        """STEP 0 intent-gate instructions must be present in the prompt."""
        conversation_service.context["is_service_provider"] = False
        template = conversation_service.create_prompt_for_stage(
            ConversationStage.PROVIDER_ONBOARDING
        )
        rendered = str(template.messages[0])
        assert "STEP 0" in rendered, "STEP 0 section must be in the PROVIDER_ONBOARDING prompt"
        assert "record_provider_interest" in rendered, (
            "record_provider_interest call must be instructed in STEP 0"
        )

    def test_context_defaults_to_false(self, conversation_service):
        """If is_service_provider is not set in context it defaults to False
        without raising a KeyError."""
        conversation_service.context.pop("is_service_provider", None)
        # Should not raise
        template = conversation_service.create_prompt_for_stage(
            ConversationStage.PROVIDER_ONBOARDING
        )
        rendered = str(template.messages[0])
        assert "False" in rendered
