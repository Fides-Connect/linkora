"""
Unit tests for AgentRuntimeFSM.
Tests the rule-based internal state machine for media/transport lifecycle.
"""
import pytest
from unittest.mock import Mock

from ai_assistant.services.agent_runtime_fsm import AgentRuntimeState, AgentRuntimeFSM


# ─────────────────────────────────────────────────────────────────────────────
# Enum contract
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRuntimeStateEnum:

    def test_all_11_members_exist(self):
        expected = {
            "BOOTSTRAP", "DATA_CHANNEL_WAIT", "LISTENING", "THINKING",
            "LLM_STREAMING", "TOOL_EXECUTING", "SPEAKING", "INTERRUPTING",
            "MODE_SWITCH", "ERROR_RETRYABLE", "TERMINATED",
        }
        actual = {m.name for m in AgentRuntimeState}
        assert actual == expected

    def test_each_member_is_string_valued(self):
        for member in AgentRuntimeState:
            assert isinstance(member.value, str), f"{member.name} value is not a str"

    def test_lookup_by_value(self):
        assert AgentRuntimeState("thinking") == AgentRuntimeState.THINKING

    def test_members_are_enum_instances(self):
        assert isinstance(AgentRuntimeState.LISTENING, AgentRuntimeState)


# ─────────────────────────────────────────────────────────────────────────────
# Initial state
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRuntimeFSMInitial:

    def test_starts_at_bootstrap(self):
        fsm = AgentRuntimeFSM()
        assert fsm.current_state == AgentRuntimeState.BOOTSTRAP

    def test_on_state_change_initialises_none(self):
        fsm = AgentRuntimeFSM()
        assert fsm.on_state_change is None


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic transitions
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRuntimeFSMTransitions:

    @pytest.fixture
    def fsm(self):
        return AgentRuntimeFSM()

    def _assert_transition(self, fsm, start, event, expected_end):
        fsm._current_state = start
        fsm.transition(event)
        assert fsm.current_state == expected_end, (
            f"Expected {expected_end} after '{event}' from {start}, "
            f"got {fsm.current_state}"
        )

    def test_bootstrap_to_data_channel_wait(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.BOOTSTRAP, "data_channel_wait",
            AgentRuntimeState.DATA_CHANNEL_WAIT
        )

    def test_data_channel_wait_to_listening(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.DATA_CHANNEL_WAIT, "data_channel_opened",
            AgentRuntimeState.LISTENING
        )

    def test_listening_to_thinking_on_final_transcript(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.LISTENING, "final_transcript",
            AgentRuntimeState.THINKING
        )

    def test_thinking_to_llm_streaming(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.THINKING, "llm_stream_started",
            AgentRuntimeState.LLM_STREAMING
        )

    def test_llm_streaming_to_tool_executing_on_tool_call(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.LLM_STREAMING, "tool_call",
            AgentRuntimeState.TOOL_EXECUTING
        )

    def test_tool_executing_back_to_llm_streaming_on_done(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.TOOL_EXECUTING, "tool_done",
            AgentRuntimeState.LLM_STREAMING
        )

    def test_llm_streaming_to_speaking_on_tts_started(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.LLM_STREAMING, "tts_started",
            AgentRuntimeState.SPEAKING
        )

    def test_llm_streaming_to_listening_on_stream_complete_text(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.LLM_STREAMING, "stream_complete_text",
            AgentRuntimeState.LISTENING
        )

    def test_speaking_to_listening_on_playback_done(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.SPEAKING, "playback_done",
            AgentRuntimeState.LISTENING
        )

    def test_interrupting_to_listening_on_interrupt_handled(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.INTERRUPTING, "interrupt_handled",
            AgentRuntimeState.LISTENING
        )

    def test_mode_switch_to_listening_on_mode_switch_done(self, fsm):
        self._assert_transition(
            fsm, AgentRuntimeState.MODE_SWITCH, "mode_switch_done",
            AgentRuntimeState.LISTENING
        )


# ─────────────────────────────────────────────────────────────────────────────
# Interrupt from any state
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRuntimeFSMInterruptFromAny:

    @pytest.fixture
    def fsm(self):
        return AgentRuntimeFSM()

    @pytest.mark.parametrize("source", [
        AgentRuntimeState.LISTENING,
        AgentRuntimeState.THINKING,
        AgentRuntimeState.LLM_STREAMING,
        AgentRuntimeState.SPEAKING,
        AgentRuntimeState.TOOL_EXECUTING,
    ])
    def test_interrupt_transitions_to_interrupting(self, fsm, source):
        fsm._current_state = source
        fsm.transition("interrupt")
        assert fsm.current_state == AgentRuntimeState.INTERRUPTING, (
            f"Expected INTERRUPTING after interrupt from {source}"
        )

    def test_interrupt_from_terminated_stays_terminated(self, fsm):
        fsm._current_state = AgentRuntimeState.TERMINATED
        fsm.transition("interrupt")
        assert fsm.current_state == AgentRuntimeState.TERMINATED

    def test_terminate_from_any_non_terminal_state(self, fsm):
        for state in AgentRuntimeState:
            if state == AgentRuntimeState.TERMINATED:
                continue
            fsm._current_state = state
            fsm.transition("terminate")
            assert fsm.current_state == AgentRuntimeState.TERMINATED, (
                f"Expected TERMINATED after terminate from {state}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# on_state_change callback
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRuntimeFSMCallback:

    def test_callback_called_with_old_and_new_state(self):
        fsm = AgentRuntimeFSM()
        calls = []
        fsm.on_state_change = lambda old, new: calls.append((old, new))

        fsm.transition("data_channel_wait")

        assert len(calls) == 1
        assert calls[0] == (AgentRuntimeState.BOOTSTRAP, AgentRuntimeState.DATA_CHANNEL_WAIT)

    def test_callback_receives_enum_values(self):
        fsm = AgentRuntimeFSM()
        received_types = []
        fsm.on_state_change = lambda old, new: received_types.extend([type(old), type(new)])

        fsm.transition("data_channel_wait")

        assert all(t is AgentRuntimeState for t in received_types)

    def test_callback_not_called_on_unknown_event(self):
        fsm = AgentRuntimeFSM()
        calls = []
        fsm.on_state_change = lambda old, new: calls.append((old, new))

        fsm.transition("nonexistent_event")

        assert calls == []

    def test_callback_called_on_each_valid_transition(self):
        fsm = AgentRuntimeFSM()
        call_count = []
        fsm.on_state_change = lambda old, new: call_count.append(1)

        fsm.transition("data_channel_wait")   # BOOTSTRAP → DATA_CHANNEL_WAIT
        fsm.transition("data_channel_opened") # DATA_CHANNEL_WAIT → LISTENING

        assert len(call_count) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Illegal / unknown transitions (no-ops)
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRuntimeFSMIllegalTransitions:

    def test_unknown_event_leaves_state_unchanged(self):
        fsm = AgentRuntimeFSM()
        fsm.transition("totally_unknown_event")
        assert fsm.current_state == AgentRuntimeState.BOOTSTRAP

    def test_unknown_event_does_not_raise(self):
        fsm = AgentRuntimeFSM()
        # Must not raise any exception
        fsm.transition("bogus_event_xyz")

    def test_final_transcript_from_bootstrap_is_no_op(self):
        """BOOTSTRAP has no 'final_transcript' rule — must stay put."""
        fsm = AgentRuntimeFSM()
        fsm.transition("final_transcript")
        assert fsm.current_state == AgentRuntimeState.BOOTSTRAP

    def test_no_state_change_when_no_rule_matches(self):
        fsm = AgentRuntimeFSM()
        fsm._current_state = AgentRuntimeState.SPEAKING
        fsm.transition("data_channel_opened")  # not a valid event from SPEAKING
        assert fsm.current_state == AgentRuntimeState.SPEAKING
