"""
Response Orchestration Service — Agentic Brain
Handles LLM response generation with conversation stage management,
signal_transition dispatch, tool dispatch, and FSM ownership.
"""
import logging
from typing import AsyncIterator, Optional, Union

from .conversation_service import ConversationService, ConversationStage, is_legal_transition
from .llm_service import LLMService
from .agent_runtime_fsm import AgentRuntimeFSM
from .agent_tools import AgentToolRegistry, ToolPermissionError

logger = logging.getLogger(__name__)


class ResponseOrchestrator:
    """
    Orchestrates LLM response generation with stage-aware conversation flow.
    Acts as the agentic brain: owns the AgentRuntimeFSM, dispatches tools,
    and handles signal_transition function calls from the LLM.
    """

    def __init__(
        self,
        llm_service: LLMService,
        conversation_service: ConversationService,
        runtime_fsm: Optional[AgentRuntimeFSM] = None,
        tool_registry: Optional[AgentToolRegistry] = None,
    ):
        self.llm_service = llm_service
        self.conversation_service = conversation_service
        self.runtime_fsm: AgentRuntimeFSM = runtime_fsm or AgentRuntimeFSM()
        self.tool_registry = tool_registry

    # ── Stage helpers ──────────────────────────────────────────────────────────

    def handle_signal_transition(self, target_str: str) -> bool:
        """
        Validate and apply a stage transition requested by the LLM (sync).

        Returns True if the transition was legal and applied, False otherwise.
        Illegal or unknown targets are logged and silently ignored — the FSM
        never gets into an inconsistent state this way.
        """
        try:
            target = ConversationStage(target_str)
        except ValueError:
            logger.warning("handle_signal_transition: unknown stage %r — ignored", target_str)
            return False

        current = self.conversation_service.get_current_stage()
        if not is_legal_transition(current, target):
            logger.warning(
                "handle_signal_transition: illegal %s → %s — ignored", current, target
            )
            return False

        self.conversation_service.set_stage(target)
        logger.info("Stage transition applied: %s → %s", current, target)
        return True

    async def handle_signal_transition_async(self, target_str: str) -> bool:
        """
        Async variant of handle_signal_transition.

        In addition to applying the stage, triggers a Weaviate provider search
        when the target stage is FINALIZE.
        """
        applied = self.handle_signal_transition(target_str)
        if applied:
            try:
                if ConversationStage(target_str) == ConversationStage.FINALIZE:
                    await self.conversation_service.search_providers_for_request()
            except ValueError:
                pass  # already caught above; can't happen here
        return applied

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    async def dispatch_tool(
        self,
        name: str,
        params: dict,
        context: dict,
    ) -> AsyncIterator[Union[str, dict]]:
        """
        Dispatch a tool call through the registry.

        Yields the raw result dict on success, or an error dict on failure.
        The caller decides how to surface these to the client.
        """
        if self.tool_registry is None:
            yield {"error": "no_registry", "tool": name}
            return

        try:
            result = await self.tool_registry.execute(name, params, context)
            yield result
        except ToolPermissionError as exc:
            yield {
                "error": "permission_denied",
                "tool": exc.tool_name,
                "required_capability": str(exc.required_capability),
            }
        except KeyError:
            yield {"error": "unknown_tool", "tool": name}
        except Exception as exc:
            logger.error("Tool %r raised unexpected error: %s", name, exc, exc_info=True)
            yield {"error": "tool_error", "tool": name, "detail": str(exc)}

    # ── Main stream ────────────────────────────────────────────────────────────

    async def generate_response_stream(
        self,
        user_input: str,
        session_id: str,
        context: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """
        Generate streaming response with stage-aware conversation flow.

        Handles both plain-text LLM chunks and function-call dicts
        (signal_transition, arbitrary tool calls) yielded by the LLM service.
        """
        try:
            current_stage = self.conversation_service.get_current_stage()
            logger.debug(
                "Generating response for '%s...' [Stage: %s]",
                user_input[:50], current_stage,
            )

            # Accumulate problem description only during triage
            if current_stage == ConversationStage.TRIAGE:
                await self.conversation_service.accumulate_problem_description(user_input)

            # Build prompt for the current stage
            prompt_template = self.conversation_service.create_prompt_for_stage(current_stage)

            # Stream LLM — chunks are either plain strings or function-call dicts
            transitioned_to_finalize = False
            async for chunk in self.llm_service.generate_stream(
                user_input, prompt_template, session_id
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "function_call":
                    fn_name = chunk.get("name", "")
                    fn_args = chunk.get("args", {})

                    if fn_name == "signal_transition":
                        target = fn_args.get("target_stage", "")
                        applied = await self.handle_signal_transition_async(target)
                        if applied:
                            try:
                                if ConversationStage(target) == ConversationStage.FINALIZE:
                                    transitioned_to_finalize = True
                            except ValueError:
                                pass
                    else:
                        # Forward arbitrary tool calls; surface text results to client
                        async for tool_chunk in self.dispatch_tool(
                            fn_name, fn_args, context or {}
                        ):
                            if isinstance(tool_chunk, str):
                                yield tool_chunk
                else:
                    yield chunk  # plain text chunk → forward directly

            # Auto-generate provider presentation after entering FINALIZE
            if transitioned_to_finalize:
                async for chunk in self._generate_finalize_presentation(session_id):
                    yield chunk

        except Exception as exc:
            logger.error("Error in response orchestration: %s", exc, exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _generate_finalize_presentation(
        self, session_id: str
    ) -> AsyncIterator[str]:
        """Auto-generate provider presentation after entering FINALIZE stage."""
        logger.info("Auto-generating provider presentation in FINALIZE stage")
        prompt_template = self.conversation_service.create_prompt_for_stage(
            ConversationStage.FINALIZE
        )
        async for chunk in self.llm_service.generate_stream(" ", prompt_template, session_id):
            if isinstance(chunk, str):
                yield chunk
