"""
Unit tests for AgentProfile and related helpers in services/agent_profile.py.
"""
import pytest
from dataclasses import FrozenInstanceError

from ai_assistant.services.agent_profile import (
    AgentProfile,
    FULL_PROFILE,
    LITE_PROFILE,
    get_profile,
)
from ai_assistant.services.conversation_service import ConversationStage


# ── get_profile ────────────────────────────────────────────────────────────────

def test_get_profile_full_returns_full_profile():
    assert get_profile("full") is FULL_PROFILE


def test_get_profile_lite_returns_lite_profile():
    assert get_profile("lite") is LITE_PROFILE


def test_get_profile_unknown_falls_back_to_full_profile(caplog):
    result = get_profile("turbo")
    assert result is FULL_PROFILE
    assert "Unknown AGENT_MODE" in caplog.text


def test_get_profile_unknown_warns_once(caplog):
    get_profile("bogus")
    warnings = [r for r in caplog.records if "Unknown AGENT_MODE" in r.message]
    assert len(warnings) == 1


# ── FULL_PROFILE fields ────────────────────────────────────────────────────────

def test_full_profile_name():
    assert FULL_PROFILE.name == "full"


def test_full_profile_voice_enabled():
    assert FULL_PROFILE.voice_enabled is True


def test_full_profile_google_places_not_always_active():
    assert FULL_PROFILE.google_places_always_active is False


def test_full_profile_provider_pitch_enabled():
    assert FULL_PROFILE.provider_pitch_enabled is True


def test_full_profile_finalize_auto_complete_disabled():
    assert FULL_PROFILE.finalize_auto_complete is False


def test_full_profile_prompt_key():
    assert FULL_PROFILE.prompt_key == "full"


def test_full_profile_all_tools_present():
    expected = {
        "search_providers",
        "get_favorites",
        "get_open_requests",
        "create_service_request",
        "record_provider_interest",
        "get_my_competencies",
        "save_competence_batch",
        "delete_competences",
    }
    assert FULL_PROFILE.available_tool_names == frozenset(expected)


def test_full_profile_contains_provider_pitch_transition():
    assert ConversationStage.PROVIDER_PITCH in FULL_PROFILE.legal_transitions[ConversationStage.COMPLETED]


def test_full_profile_contains_provider_onboarding_from_triage():
    assert ConversationStage.PROVIDER_ONBOARDING in FULL_PROFILE.legal_transitions[ConversationStage.TRIAGE]


def test_full_profile_tool_execution_in_transitions():
    assert ConversationStage.TOOL_EXECUTION in FULL_PROFILE.legal_transitions[ConversationStage.TRIAGE]


# ── LITE_PROFILE fields ────────────────────────────────────────────────────────

def test_lite_profile_name():
    assert LITE_PROFILE.name == "lite"


def test_lite_profile_voice_disabled():
    assert LITE_PROFILE.voice_enabled is False


def test_lite_profile_google_places_always_active():
    assert LITE_PROFILE.google_places_always_active is True


def test_lite_profile_provider_pitch_disabled():
    assert LITE_PROFILE.provider_pitch_enabled is False


def test_lite_profile_finalize_auto_complete_enabled():
    assert LITE_PROFILE.finalize_auto_complete is True


def test_lite_profile_prompt_key():
    assert LITE_PROFILE.prompt_key == "lite"


def test_lite_profile_only_search_providers_tool():
    assert LITE_PROFILE.available_tool_names == frozenset({"search_providers"})


def test_lite_profile_no_provider_pitch_in_transitions():
    for targets in LITE_PROFILE.legal_transitions.values():
        assert ConversationStage.PROVIDER_PITCH not in targets


def test_lite_profile_no_provider_onboarding_in_transitions():
    for stage, targets in LITE_PROFILE.legal_transitions.items():
        assert ConversationStage.PROVIDER_ONBOARDING not in targets, (
            f"PROVIDER_ONBOARDING should not appear as a target for {stage} in lite mode"
        )


def test_lite_profile_no_tool_execution_stage():
    assert ConversationStage.TOOL_EXECUTION not in LITE_PROFILE.legal_transitions
    for targets in LITE_PROFILE.legal_transitions.values():
        assert ConversationStage.TOOL_EXECUTION not in targets


# ── Immutability ───────────────────────────────────────────────────────────────

def test_full_profile_is_frozen():
    with pytest.raises(FrozenInstanceError):
        FULL_PROFILE.voice_enabled = False  # type: ignore[misc]


def test_lite_profile_is_frozen():
    with pytest.raises(FrozenInstanceError):
        LITE_PROFILE.provider_pitch_enabled = True  # type: ignore[misc]


def test_available_tool_names_is_frozenset():
    assert isinstance(FULL_PROFILE.available_tool_names, frozenset)
    assert isinstance(LITE_PROFILE.available_tool_names, frozenset)


# ── Transition table consistency ───────────────────────────────────────────────

def test_full_profile_triage_is_initial_stage():
    """TRIAGE is the entry point (GREETING stage was merged into TRIAGE)."""
    assert ConversationStage.TRIAGE in FULL_PROFILE.legal_transitions


def test_lite_profile_triage_is_initial_stage():
    """TRIAGE is the entry point (GREETING stage was merged into TRIAGE)."""
    assert ConversationStage.TRIAGE in LITE_PROFILE.legal_transitions


def test_full_profile_recovery_can_reach_confirmation():
    assert ConversationStage.CONFIRMATION in FULL_PROFILE.legal_transitions[ConversationStage.RECOVERY]


def test_lite_profile_recovery_can_reach_confirmation():
    assert ConversationStage.CONFIRMATION in LITE_PROFILE.legal_transitions[ConversationStage.RECOVERY]


def test_full_profile_finalize_can_reach_completed():
    assert ConversationStage.COMPLETED in FULL_PROFILE.legal_transitions[ConversationStage.FINALIZE]


def test_lite_profile_finalize_can_reach_completed():
    assert ConversationStage.COMPLETED in LITE_PROFILE.legal_transitions[ConversationStage.FINALIZE]


def test_full_and_lite_are_different_objects():
    assert FULL_PROFILE is not LITE_PROFILE


def test_lite_has_fewer_stages_than_full():
    assert len(LITE_PROFILE.legal_transitions) < len(FULL_PROFILE.legal_transitions)
