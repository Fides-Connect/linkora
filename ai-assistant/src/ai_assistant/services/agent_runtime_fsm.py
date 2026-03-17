"""
Agent Runtime FSM
Rule-based internal state machine for the media/transport lifecycle.

All transitions are deterministic — no LLM involvement.
The ConversationStage (external, semantic) is owned by ResponseOrchestrator;
this FSM only tracks low-level runtime execution state.
"""
import logging
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class AgentRuntimeState(str, Enum):
    """Internal runtime states for the audio/transport pipeline."""
    BOOTSTRAP          = "bootstrap"
    DATA_CHANNEL_WAIT  = "data_channel_wait"
    LISTENING          = "listening"
    THINKING           = "thinking"
    LLM_STREAMING      = "llm_streaming"
    TOOL_EXECUTING     = "tool_executing"
    SPEAKING           = "speaking"
    INTERRUPTING       = "interrupting"
    MODE_SWITCH        = "mode_switch"
    ERROR_RETRYABLE    = "error_retryable"
    TERMINATED         = "terminated"


# ---------------------------------------------------------------------------
# Transition table
# Format: { source_state: { event: target_state } }
# "interrupt" and "terminate" are handled as universal cross-cutting events.
# ---------------------------------------------------------------------------

_TRANSITIONS: dict[AgentRuntimeState, dict[str, AgentRuntimeState]] = {
    AgentRuntimeState.BOOTSTRAP: {
        "data_channel_wait": AgentRuntimeState.DATA_CHANNEL_WAIT,
    },
    AgentRuntimeState.DATA_CHANNEL_WAIT: {
        "data_channel_opened": AgentRuntimeState.LISTENING,
    },
    AgentRuntimeState.LISTENING: {
        "final_transcript": AgentRuntimeState.THINKING,
        "mode_switch":      AgentRuntimeState.MODE_SWITCH,
    },
    AgentRuntimeState.THINKING: {
        "llm_stream_started": AgentRuntimeState.LLM_STREAMING,
        # Empty-stream recovery: if the LLM yields nothing (e.g. pure function-call
        # stream that was silently buffered, or an exception before the first chunk),
        # stream_complete_text is still issued; allow it to reset to LISTENING so the
        # FSM never sticks in THINKING.
        "stream_complete_text": AgentRuntimeState.LISTENING,
    },
    AgentRuntimeState.LLM_STREAMING: {
        "tool_call":            AgentRuntimeState.TOOL_EXECUTING,
        "tts_started":          AgentRuntimeState.SPEAKING,
        "stream_complete_text": AgentRuntimeState.LISTENING,
    },
    AgentRuntimeState.TOOL_EXECUTING: {
        "tool_done":            AgentRuntimeState.LLM_STREAMING,
        "mode_switch":          AgentRuntimeState.MODE_SWITCH,
        # Error-recovery: if an exception fires mid-tool and the finally block
        # emits stream_complete_text, reset to LISTENING rather than staying stuck.
        "stream_complete_text": AgentRuntimeState.LISTENING,
    },
    AgentRuntimeState.SPEAKING: {
        "playback_done": AgentRuntimeState.LISTENING,
        "mode_switch":   AgentRuntimeState.MODE_SWITCH,
    },
    AgentRuntimeState.INTERRUPTING: {
        "interrupt_handled": AgentRuntimeState.LISTENING,
    },
    AgentRuntimeState.MODE_SWITCH: {
        "mode_switch_done": AgentRuntimeState.LISTENING,
    },
    AgentRuntimeState.ERROR_RETRYABLE: {
        "retry": AgentRuntimeState.LISTENING,
    },
    # TERMINATED: no outbound transitions
    AgentRuntimeState.TERMINATED: {},
}

# Events that fire regardless of source state (except TERMINATED)
_UNIVERSAL_EVENTS: dict[str, AgentRuntimeState] = {
    "interrupt": AgentRuntimeState.INTERRUPTING,
    "terminate": AgentRuntimeState.TERMINATED,
}


class AgentRuntimeFSM:
    """
    Rule-based finite state machine for the agent's runtime lifecycle.

    Transitions are driven by explicit string events emitted by AudioProcessor
    and ResponseOrchestrator.  No LLM decisions happen here.

    Usage::

        fsm = AgentRuntimeFSM()
        fsm.on_state_change = lambda old, new: send_runtime_state_event(new)
        fsm.transition("data_channel_wait")
    """

    def __init__(self) -> None:
        self._current_state: AgentRuntimeState = AgentRuntimeState.BOOTSTRAP
        # Optional callback: (old: AgentRuntimeState, new: AgentRuntimeState) -> None
        self.on_state_change: Optional[Callable[[AgentRuntimeState, AgentRuntimeState], None]] = None

    @property
    def current_state(self) -> AgentRuntimeState:
        return self._current_state

    def transition(self, event: str) -> bool:
        """
        Attempt to transition the FSM with the given event.

        Returns True if a transition occurred, False if the event was ignored
        (unknown or not valid from the current state).  Never raises.
        """
        source = self._current_state

        # TERMINATED absorbs everything except another terminate (idempotent)
        if source == AgentRuntimeState.TERMINATED:
            return False

        # Universal cross-cutting events (interrupt, terminate) take priority
        if event in _UNIVERSAL_EVENTS:
            target = _UNIVERSAL_EVENTS[event]
            if target == source:
                return False
            self._apply(source, target)
            return True

        # State-specific transitions
        state_map = _TRANSITIONS.get(source, {})
        if event not in state_map:
            logger.debug(
                "AgentRuntimeFSM: no rule for event '%s' from state '%s' — ignoring",
                event, source.value,
            )
            return False

        target = state_map[event]
        self._apply(source, target)
        return True

    def _apply(self, old: AgentRuntimeState, new: AgentRuntimeState) -> None:
        self._current_state = new
        logger.info(
            "AgentRuntimeFSM: %s → %s", old.value, new.value
        )
        if self.on_state_change is not None:
            try:
                self.on_state_change(old, new)
            except Exception:
                logger.exception(
                    "AgentRuntimeFSM: on_state_change callback raised"
                )
