"""
Unit tests for prompt templates — provider pitch and onboarding.
"""
import pytest

from ai_assistant.prompts_templates import (
    PROVIDER_PITCH_PROMPT,
    PROVIDER_ONBOARDING_PROMPT,
    TRIAGE_CONVERSATION_PROMPT,
)


class TestProviderPitchPrompt:

    def test_record_provider_interest_tool_referenced(self):
        assert "record_provider_interest" in PROVIDER_PITCH_PROMPT

    def test_accepted_outcome_documented(self):
        assert "accepted" in PROVIDER_PITCH_PROMPT

    def test_not_now_outcome_documented(self):
        assert "not_now" in PROVIDER_PITCH_PROMPT

    def test_never_outcome_documented(self):
        assert "never" in PROVIDER_PITCH_PROMPT

    def test_signal_transition_referenced(self):
        assert "signal_transition" in PROVIDER_PITCH_PROMPT

    def test_agent_name_placeholder_present(self):
        assert "{agent_name}" in PROVIDER_PITCH_PROMPT

    def test_language_instruction_placeholder_present(self):
        assert "{language_instruction}" in PROVIDER_PITCH_PROMPT


class TestProviderOnboardingPrompt:

    def test_max_two_questions_enforced(self):
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "2 question" in prompt_lower or "two question" in prompt_lower

    def test_save_competence_batch_tool_referenced(self):
        assert "save_competence_batch" in PROVIDER_ONBOARDING_PROMPT

    def test_get_my_competencies_tool_referenced(self):
        assert "get_my_competencies" in PROVIDER_ONBOARDING_PROMPT

    def test_delete_competences_tool_referenced(self):
        assert "delete_competences" in PROVIDER_ONBOARDING_PROMPT

    def test_summary_and_confirmation_required(self):
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "summary" in prompt_lower or "zusammenfassung" in prompt_lower

    def test_agent_name_placeholder_present(self):
        assert "{agent_name}" in PROVIDER_ONBOARDING_PROMPT

    def test_language_instruction_placeholder_present(self):
        assert "{language_instruction}" in PROVIDER_ONBOARDING_PROMPT

    def test_onboarding_draft_placeholder_present(self):
        assert "{onboarding_draft_json}" in PROVIDER_ONBOARDING_PROMPT

    def test_competence_fields_mentioned(self):
        """All five CompetenceSchema fields should be mentioned so Elin asks for them."""
        for field in ("title", "description", "category", "price_range", "year_of_experience"):
            assert field in PROVIDER_ONBOARDING_PROMPT, f"Field '{field}' not mentioned in onboarding prompt"


class TestTriagePromptOnboardingEntry:

    def test_provider_onboarding_transition_in_triage_contract(self):
        """TRIAGE State Contract must allow entering PROVIDER_ONBOARDING stage."""
        assert "provider_onboarding" in TRIAGE_CONVERSATION_PROMPT
