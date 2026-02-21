"""
Response Orchestration Service — Agentic Brain
Handles LLM response generation with conversation stage management,
signal_transition dispatch, tool dispatch, and FSM ownership.
"""
import re
import json
import logging
from typing import AsyncIterator, Optional, Union

from langchain_core.messages import AIMessage

from .conversation_service import ConversationService, ConversationStage, is_legal_transition
from .llm_service import LLMService, SIGNAL_TRANSITION_SCHEMA
from .agent_runtime_fsm import AgentRuntimeFSM
from .agent_tools import AgentToolRegistry, ToolPermissionError

logger = logging.getLogger(__name__)

# Matches any identifier(...) pattern — used to strip leaked tool-call text
_TOOL_CALL_TEXT_RE = re.compile(r'\b[a-zA-Z_]\w*\s*\([^)]*\)')


def _strip_tool_call_text(text: str) -> str:
    """Remove identifier(...) patterns from a text chunk.

    Does NOT strip surrounding whitespace so that inter-word spaces in normal
    text are preserved (e.g. "Hello " + "world" stays "Hello world").
    """
    return _TOOL_CALL_TEXT_RE.sub("", text)


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
        ai_conversation_service=None,
    ):
        self.llm_service = llm_service
        self.conversation_service = conversation_service
        self.runtime_fsm: AgentRuntimeFSM = runtime_fsm or AgentRuntimeFSM()
        self.tool_registry = tool_registry
        self.ai_conversation_service = ai_conversation_service

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

        Also:
        - Registers SIGNAL_TRANSITION_SCHEMA per session so Gemini uses
          native function-calling instead of emitting tool calls as text.
        - Strips any leaked identifier(...) patterns from text chunks.
        - Fires AgentRuntimeFSM events at key lifecycle points.
        - Delegates message persistence to ai_conversation_service when set.
        """
        try:
            # Register all tool schemas for this session so Gemini uses
            # function-calling rather than emitting plaintext.
            tool_schemas = [SIGNAL_TRANSITION_SCHEMA]
            if self.tool_registry:
                tool_schemas += self.tool_registry.all_schemas()
            self.llm_service.register_functions(session_id, tool_schemas)

            current_stage = self.conversation_service.get_current_stage()
            logger.debug(
                "Generating response for '%s...' [Stage: %s]",
                user_input[:50], current_stage,
            )

            # Persist the user turn before streaming starts
            if self.ai_conversation_service:
                await self.ai_conversation_service.save_message(
                    role="user", text=user_input, stage=current_stage
                )

            # Accumulate problem description only during triage
            if current_stage == ConversationStage.TRIAGE:
                await self.conversation_service.accumulate_problem_description(user_input)

            # Build prompt for the current stage
            prompt_template = self.conversation_service.create_prompt_for_stage(current_stage)

            # Stream LLM — chunks are either plain strings or function-call dicts
            transitioned_to_finalize = False
            transitioned_to_completed = False
            first_chunk = True
            ai_response_parts: list[str] = []
            pending_tool_results: list[tuple[str, object]] = []

            async for chunk in self.llm_service.generate_stream(
                user_input, prompt_template, session_id
            ):
                # Fire llm_stream_started on the very first chunk (text or tool call)
                if first_chunk:
                    self.runtime_fsm.transition("llm_stream_started")
                    first_chunk = False

                if isinstance(chunk, dict) and chunk.get("type") == "function_call":
                    fn_name = chunk.get("name", "")
                    fn_args = chunk.get("args", {})

                    if fn_name == "signal_transition":
                        self.runtime_fsm.transition("tool_call")
                        target = fn_args.get("target_stage", "")
                        applied = await self.handle_signal_transition_async(target)
                        if applied:
                            try:
                                if ConversationStage(target) == ConversationStage.FINALIZE:
                                    transitioned_to_finalize = True
                                elif ConversationStage(target) == ConversationStage.COMPLETED:
                                    transitioned_to_completed = True
                            except ValueError:
                                pass
                        self.runtime_fsm.transition("tool_done")
                    else:
                        # Execute tool and collect result for LLM feedback loop
                        self.runtime_fsm.transition("tool_call")
                        tool_result = None
                        async for tool_chunk in self.dispatch_tool(
                            fn_name, fn_args, context or {}
                        ):
                            tool_result = tool_chunk
                        self.runtime_fsm.transition("tool_done")

                        if tool_result is not None:
                            is_error = (
                                isinstance(tool_result, dict)
                                and tool_result.get("error")
                            )
                            if not is_error:
                                pending_tool_results.append((fn_name, tool_result))
                                # Surface provider list for stage-context use
                                if (
                                    fn_name == "search_providers"
                                    and isinstance(tool_result, list)
                                ):
                                    self.conversation_service.context["providers_found"] = tool_result
                            else:
                                logger.warning(
                                    "Tool %r returned error: %s", fn_name, tool_result
                                )
                else:
                    # Plain text chunk — strip any leaked tool-call patterns
                    filtered = _strip_tool_call_text(chunk) if isinstance(chunk, str) else chunk
                    if filtered.strip() if isinstance(filtered, str) else filtered:
                        ai_response_parts.append(filtered)
                        yield filtered

            # Feed tool results back into LLM history and generate a follow-up stream
            if pending_tool_results:
                for fn_name, result in pending_tool_results:
                    result_str = (
                        json.dumps(result, ensure_ascii=False, default=str)
                        if isinstance(result, (dict, list))
                        else str(result)
                    )
                    self.llm_service.add_message_to_history(
                        session_id,
                        AIMessage(content=f"[Tool {fn_name} returned: {result_str}]"),
                    )
                follow_up_stage = self.conversation_service.get_current_stage()
                follow_up_template = self.conversation_service.create_prompt_for_stage(
                    follow_up_stage
                )
                async for chunk in self.llm_service.generate_stream(
                    "[Please give the user a helpful response based on the tool result above]",
                    follow_up_template,
                    session_id,
                ):
                    if isinstance(chunk, str):
                        filtered = _strip_tool_call_text(chunk)
                        if filtered.strip():
                            ai_response_parts.append(filtered)
                            yield filtered

            # Stream complete — advance FSM back to LISTENING
            self.runtime_fsm.transition("stream_complete_text")

            # Persist the assembled AI response
            if self.ai_conversation_service:
                final_stage = self.conversation_service.get_current_stage()
                ai_text = "".join(ai_response_parts)
                await self.ai_conversation_service.save_message(
                    role="assistant", text=ai_text, stage=final_stage
                )

            # Update topic title when entering FINALIZE
            if transitioned_to_finalize and self.ai_conversation_service:
                summary = ""
                if hasattr(self.conversation_service, '_get_problem_summary'):
                    summary = self.conversation_service._get_problem_summary()
                await self.ai_conversation_service.set_topic_title(summary)

            # Close session when entering COMPLETED
            if transitioned_to_completed and self.ai_conversation_service:
                completed_stage = self.conversation_service.get_current_stage()
                await self.ai_conversation_service.close_session(completed_stage)

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
