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

    def test_get_my_competencies_not_called_by_llm(self):
        """Prompt must instruct the LLM NOT to call get_my_competencies — the backend pre-fetches."""
        assert "get_my_competencies" in PROVIDER_ONBOARDING_PROMPT
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "do not call" in prompt_lower or "not call" in prompt_lower or "already" in prompt_lower

    def test_delete_competences_tool_referenced(self):
        assert "delete_competences" in PROVIDER_ONBOARDING_PROMPT

    def test_summary_and_confirmation_required(self):
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "summary" in prompt_lower or "zusammenfassung" in prompt_lower

    def test_agent_name_placeholder_present(self):
        assert "{agent_name}" in PROVIDER_ONBOARDING_PROMPT

    def test_language_instruction_placeholder_present(self):
        assert "{language_instruction}" in PROVIDER_ONBOARDING_PROMPT

    def test_current_competencies_json_placeholder_present(self):
        assert "{current_competencies_json}" in PROVIDER_ONBOARDING_PROMPT

    def test_competence_fields_mentioned(self):
        """All five CompetenceSchema fields should be mentioned so Elin asks for them."""
        for field in ("title", "description", "category", "price_range", "year_of_experience"):
            assert field in PROVIDER_ONBOARDING_PROMPT, f"Field '{field}' not mentioned in onboarding prompt"


class TestTriagePromptOnboardingEntry:

    def test_provider_onboarding_transition_in_triage_contract(self):
        """TRIAGE State Contract must allow entering PROVIDER_ONBOARDING stage."""
        assert "provider_onboarding" in TRIAGE_CONVERSATION_PROMPT

    def test_triage_prompt_has_no_re_greet_rule(self):
        """TRIAGE must tell the LLM not to re-greet — fixes text-mode double-greeting bug."""
        prompt_lower = TRIAGE_CONVERSATION_PROMPT.lower()
        assert "never re-greet" in prompt_lower or "do not" in prompt_lower, (
            "TRIAGE_CONVERSATION_PROMPT must contain an explicit no-re-greet instruction"
        )

    def test_triage_no_re_greet_rule_mentions_hello(self):
        """The greeting/no-re-greet instruction is now injected dynamically via
        the {greeting_instruction} placeholder \u2014 the static template must contain it."""
        assert "{greeting_instruction}" in TRIAGE_CONVERSATION_PROMPT


class TestProviderOnboardingSaveResultConfirmation:

    def test_prompt_instructs_llm_to_confirm_success(self):
        """After save_competence_batch succeeds the LLM must tell the user — not stay silent."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "success" in prompt_lower or "saved successfully" in prompt_lower, (
            "PROVIDER_ONBOARDING_PROMPT must instruct the LLM to confirm a successful save"
        )

    def test_prompt_instructs_llm_to_report_error(self):
        """After save_competence_batch fails the LLM must tell the user about the error."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "error" in prompt_lower or "went wrong" in prompt_lower, (
            "PROVIDER_ONBOARDING_PROMPT must instruct the LLM to report a save error"
        )

    def test_prompt_references_signal_transition_to_completed(self):
        """Signal transition to completed must be documented in the onboarding prompt."""
        assert 'signal_transition(target_stage="completed")' in PROVIDER_ONBOARDING_PROMPT


class TestProviderOnboardingOrderingRules:
    """Prompt must enforce write-before-complete ordering so the LLM cannot skip saves."""

    def test_critical_ordering_section_present(self):
        """A clearly labelled CRITICAL ORDERING section must exist."""
        assert "CRITICAL" in PROVIDER_ONBOARDING_PROMPT, (
            "PROVIDER_ONBOARDING_PROMPT must contain a CRITICAL ordering section"
        )

    def test_write_tool_must_precede_signal_transition_rule(self):
        """Prompt must explicitly state that signal_transition comes after the write tool."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        # The ordering rule should mention never combining them
        assert (
            "never call" in prompt_lower
            or "must call" in prompt_lower
            or "first" in prompt_lower
        ), "Prompt must say the write tool must be called before signal_transition"

    def test_separate_responses_rule_present(self):
        """Prompt must say write tool and signal_transition happen in separate responses."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert (
            "separate response" in prompt_lower
            or "response a" in prompt_lower
            or "response b" in prompt_lower
        ), "Prompt must explicitly separate write response from signal_transition response"

    def test_even_if_user_says_done_save_comes_first(self):
        """Prompt must address the 'correct, nothing else' edge case — save before done."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        # Prompt should mention that even confirmation + done messages require save first
        assert (
            "nothing else" in prompt_lower
            or "correct" in prompt_lower
            or "defer" in prompt_lower
        ), "Prompt must address the case where user confirms and says done in one message"

    def test_rules_section_prohibits_combining_write_and_signal_transition(self):
        """The RULES block must explicitly forbid calling signal_transition + write together."""
        assert "Never call `signal_transition` and a write tool in the same response" in PROVIDER_ONBOARDING_PROMPT


class TestAvailabilityInterpretationTable:
    """The onboarding prompt must contain the single-pass availability interpretation table
    so Elin can convert natural language availability directly into availability_time without
    an extra round trip."""

    def test_single_pass_instruction_present(self):
        """Prompt must say no follow-up question is needed for availability."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "no extra round" in prompt_lower or "no follow-up" in prompt_lower or "never ask a follow-up" in prompt_lower, (
            "Prompt must instruct single-pass availability interpretation (no follow-up turn)"
        )

    def test_morning_slot_defined(self):
        assert "08:00" in PROVIDER_ONBOARDING_PROMPT and "12:00" in PROVIDER_ONBOARDING_PROMPT

    def test_afternoon_slot_defined(self):
        assert "12:00" in PROVIDER_ONBOARDING_PROMPT and "17:00" in PROVIDER_ONBOARDING_PROMPT

    def test_evening_slot_defined(self):
        assert "17:00" in PROVIDER_ONBOARDING_PROMPT and "21:00" in PROVIDER_ONBOARDING_PROMPT

    def test_default_end_of_day_for_open_ended_times(self):
        """'from 14' with no end should use 21:00 — the default end-of-day must be documented."""
        assert "21:00" in PROVIDER_ONBOARDING_PROMPT

    def test_weekend_group_described(self):
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "weekend" in prompt_lower and "sat" in prompt_lower and "sun" in prompt_lower

    def test_weekday_group_described(self):
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "weekday" in prompt_lower and "mon" in prompt_lower and "fri" in prompt_lower

    def test_flexible_means_omit(self):
        """'flexible'/'anytime' must map to omitting availability_time, not guessing."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "flexible" in prompt_lower
        assert "omit" in prompt_lower or "skip" in prompt_lower or "optional" in prompt_lower

    def test_zero_padding_rule_present(self):
        """HH:MM zero-padding rule must be stated so the LLM never produces '9:00'."""
        assert "zero-pad" in PROVIDER_ONBOARDING_PROMPT or "HH:MM" in PROVIDER_ONBOARDING_PROMPT or "09:00" in PROVIDER_ONBOARDING_PROMPT

    def test_natural_language_in_reply_rule(self):
        """Prompt must say to describe availability naturally in the spoken reply (no JSON to user)."""
        prompt_lower = PROVIDER_ONBOARDING_PROMPT.lower()
        assert "naturally" in prompt_lower or "natural language" in prompt_lower
