"""
Response Orchestration Service — Agentic Brain
Handles LLM response generation with conversation stage management,
signal_transition dispatch, tool dispatch, and FSM ownership.
"""
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator, Optional, Union

from langchain_core.messages import AIMessage

from .conversation_service import ConversationService, ConversationStage, is_legal_transition
from .llm_service import LLMService, SIGNAL_TRANSITION_SCHEMA
from .agent_runtime_fsm import AgentRuntimeFSM
from .agent_tools import AgentToolRegistry, ToolPermissionError

logger = logging.getLogger(__name__)

# Matches known tool-call names leaked as plain text — e.g. signal_transition(target_stage="finalize").
# Intentionally restricted to tool names registered in build_default_registry so that
# normal prose containing parentheses ("call me (555) 123-4567") is never stripped.
_KNOWN_TOOL_NAMES_RE = re.compile(
    r'\b(?:signal_transition|search_providers|get_favorites|get_open_requests'
    r'|create_service_request|record_provider_interest|get_my_competencies'
    r'|save_competence_batch|delete_competences)\s*\([^)]*\)'
)
_TOOL_CALL_TEXT_RE = _KNOWN_TOOL_NAMES_RE  # alias kept for backward compat with tests


def _strip_tool_call_text(text: str) -> str:
    """Remove known tool-call name(...) patterns from a text chunk.

    Only strips the specific tool names registered in the default registry —
    not arbitrary identifiers — so normal prose with parentheses is preserved.
    Does NOT strip surrounding whitespace so inter-word spaces remain intact.
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

    async def handle_signal_transition_async(
        self, target_str: str, session_id: str = ""
    ) -> bool:
        """Async variant of handle_signal_transition.

        In addition to applying the stage, triggers a Weaviate provider search
        when the target stage is FINALIZE, forwarding the active session so the
        extractor can include the last 3 history messages.
        """
        previous_stage = self.conversation_service.get_current_stage()
        applied = self.handle_signal_transition(target_str)
        if applied:
            try:
                target_stage = ConversationStage(target_str)
                if target_stage == ConversationStage.FINALIZE:
                    await self.conversation_service.search_providers_for_request(session_id)
                elif (
                    target_stage == ConversationStage.TRIAGE
                    and previous_stage == ConversationStage.COMPLETED
                ):
                    self.conversation_service.reset_request_context()
            except ValueError:
                pass  # already caught above; can't happen here
        return applied

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    @staticmethod
    def _should_pitch_provider(context: Optional[dict]) -> bool:
        """
        Return True when all eligibility conditions for the provider pitch are met:
          1. user_context is present in context
          2. is_service_provider is False
          3. last_time_asked_being_provider is not None
          4. last_time_asked_being_provider != PROVIDER_PITCH_OPT_OUT_SENTINEL
          5. at least 30 days have elapsed since last_time_asked_being_provider
        """
        if not context:
            return False
        user_ctx = context.get("user_context", {})
        if not user_ctx:
            return False
        if user_ctx.get("is_service_provider", False):
            return False
        last_asked = user_ctx.get("last_time_asked_being_provider")
        if last_asked is None:
            return False

        # Import here to avoid circular imports at module load time
        from ..firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL
        if last_asked == PROVIDER_PITCH_OPT_OUT_SENTINEL:
            return False

        now = datetime.now(timezone.utc)
        if last_asked.tzinfo is None:
            last_asked = last_asked.replace(tzinfo=timezone.utc)
        return (now - last_asked) >= timedelta(days=30)

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
            transitioned_to_triage_from_completed = False
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
                        applied = await self.handle_signal_transition_async(target, session_id)
                        if applied:
                            try:
                                if ConversationStage(target) == ConversationStage.FINALIZE:
                                    transitioned_to_finalize = True
                                elif ConversationStage(target) == ConversationStage.COMPLETED:
                                    transitioned_to_completed = True
                                elif (
                                    ConversationStage(target) == ConversationStage.TRIAGE
                                    and current_stage == ConversationStage.COMPLETED
                                ):
                                    transitioned_to_triage_from_completed = True
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
                                # If the tool returned a stage transition signal, apply it
                                if isinstance(tool_result, dict) and "signal_transition" in tool_result:
                                    sig_target = tool_result["signal_transition"]
                                    await self.handle_signal_transition_async(sig_target)
                                # Surface provider list for stage-context use
                                if (
                                    fn_name == "search_providers"
                                    and isinstance(tool_result, list)
                                ):
                                    self.conversation_service.context["providers_found"] = tool_result
                                # Link created service request to conversation
                                if (
                                    fn_name == "create_service_request"
                                    and self.ai_conversation_service
                                ):
                                    req_id = (
                                        tool_result.get("id")
                                        or tool_result.get("service_request_id")
                                        if isinstance(tool_result, dict)
                                        else str(tool_result)
                                    )
                                    if req_id:
                                        await self.ai_conversation_service.set_request_id(req_id)
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
                    " ",
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

            # Assemble and record the AI response so get_problem_summary()
            # returns the LLM's confirmed job summary on subsequent calls.
            ai_text = "".join(ai_response_parts)
            self.conversation_service.record_ai_response(ai_text)

            # Persist the assembled AI response (skip if empty — e.g. the LLM
            # emitted only a function call with no accompanying text)
            if self.ai_conversation_service and ai_text.strip():
                final_stage = self.conversation_service.get_current_stage()
                await self.ai_conversation_service.save_message(
                    role="assistant", text=ai_text, stage=final_stage
                )

            # Update topic title when entering FINALIZE
            if transitioned_to_finalize and self.ai_conversation_service:
                summary = self.conversation_service.get_problem_summary()
                await self.ai_conversation_service.set_topic_title(summary)

            # Auto-generate provider presentation after entering FINALIZE
            if transitioned_to_finalize:
                finalize_parts: list[str] = []
                yield {"type": "new_bubble"}  # open a fresh bubble before presentation
                async for chunk in self._generate_finalize_presentation(session_id):
                    finalize_parts.append(chunk)
                    yield chunk
                if finalize_parts and self.ai_conversation_service:
                    finalize_text = "".join(finalize_parts)
                    await self.ai_conversation_service.save_message(
                        role="assistant",
                        text=finalize_text,
                        stage=ConversationStage.FINALIZE,
                    )

            # After COMPLETED: pitch eligible users; loop back for everyone else
            if transitioned_to_completed:
                pitch_launched = False
                if self._should_pitch_provider(context):
                    applied = await self.handle_signal_transition_async("provider_pitch")
                    if applied:
                        pitch_launched = True
                        yield {"type": "new_bubble"}
                        async for chunk in self._generate_provider_pitch_stream(session_id):
                            yield chunk

                if not pitch_launched:
                    yield {"type": "new_bubble"}
                    loop_back_triggered_triage = False
                    async for chunk in self._generate_loop_back_stream(session_id):
                        if isinstance(chunk, dict) and chunk.get("type") == "triage_triggered":
                            loop_back_triggered_triage = True
                        else:
                            yield chunk
                    if loop_back_triggered_triage:
                        yield {"type": "new_bubble"}
                        triage_parts: list[str] = []
                        async for chunk in self._generate_triage_opener_stream(user_input, session_id):
                            triage_parts.append(chunk)
                            yield chunk
                        if triage_parts and self.ai_conversation_service:
                            await self.ai_conversation_service.save_message(
                                role="assistant",
                                text="".join(triage_parts),
                                stage=ConversationStage.TRIAGE,
                            )

            # Auto-start TRIAGE scoping when the user replied in COMPLETED with a new
            # request and the main stream (not the loop-back) triggered the transition.
            if transitioned_to_triage_from_completed:
                yield {"type": "new_bubble"}
                triage_parts_main: list[str] = []
                async for chunk in self._generate_triage_opener_stream(user_input, session_id):
                    triage_parts_main.append(chunk)
                    yield chunk
                if triage_parts_main and self.ai_conversation_service:
                    await self.ai_conversation_service.save_message(
                        role="assistant",
                        text="".join(triage_parts_main),
                        stage=ConversationStage.TRIAGE,
                    )

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

    async def _generate_provider_pitch_stream(
        self, session_id: str
    ) -> AsyncIterator[str]:
        """Auto-generate provider pitch after entering PROVIDER_PITCH stage."""
        logger.info("Auto-generating provider pitch in PROVIDER_PITCH stage")
        prompt_template = self.conversation_service.create_prompt_for_stage(
            ConversationStage.PROVIDER_PITCH
        )
        async for chunk in self.llm_service.generate_stream(" ", prompt_template, session_id):
            if isinstance(chunk, str):
                yield chunk

    async def _generate_loop_back_stream(
        self, session_id: str
    ) -> AsyncIterator[str]:
        """Auto-generate the loop-back question after COMPLETED stage.

        Asks the user warmly whether they need help with anything else.
        The LLM uses LOOP_BACK_PROMPT which instructs it to call
        signal_transition(target_stage="triage") if the user wants more help,
        or give a short farewell otherwise.

        IMPORTANT: The LLM may skip the warm-up sentence entirely and emit
        only a signal_transition("triage") function call (e.g. when the user
        already indicated they want more help in the same turn).  This helper
        handles that case by processing the tool call instead of silently
        dropping it.
        """
        logger.info("Auto-generating loop-back question in COMPLETED stage")
        prompt_template = self.conversation_service.create_prompt_for_stage(
            ConversationStage.COMPLETED
        )
        pending_tool_results: list[tuple[str, object]] = []
        async for chunk in self.llm_service.generate_stream(" ", prompt_template, session_id):
            if isinstance(chunk, dict) and chunk.get("type") == "function_call":
                fn_name = chunk.get("name", "")
                fn_args = chunk.get("args", {})
                if fn_name == "signal_transition":
                    target = fn_args.get("target_stage", "")
                    applied = await self.handle_signal_transition_async(target, session_id)
                    if applied and target == "triage":
                        # Signal to the caller that a TRIAGE opener should be generated.
                        # We yield a sentinel rather than generating inline so the caller
                        # can pass the user's original input to the TRIAGE stream.
                        yield {"type": "triage_triggered"}
                else:
                    # Other tools are unlikely here but handle gracefully
                    tool_result = None
                    async for tool_chunk in self.dispatch_tool(fn_name, fn_args, {}):
                        tool_result = tool_chunk
                    if tool_result is not None and not (
                        isinstance(tool_result, dict) and tool_result.get("error")
                    ):
                        pending_tool_results.append((fn_name, tool_result))
            elif isinstance(chunk, str):
                filtered = _strip_tool_call_text(chunk)
                if filtered.strip():
                    yield filtered

        # If there were tool results, feed them back and generate a follow-up
        if pending_tool_results:
            import json
            from langchain_core.messages import AIMessage as _AIMessage
            for fn_name, result in pending_tool_results:
                result_str = (
                    json.dumps(result, ensure_ascii=False, default=str)
                    if isinstance(result, (dict, list))
                    else str(result)
                )
                self.llm_service.add_message_to_history(
                    session_id,
                    _AIMessage(content=f"[Tool {fn_name} returned: {result_str}]"),
                )
            follow_up_stage = self.conversation_service.get_current_stage()
            follow_up_template = self.conversation_service.create_prompt_for_stage(follow_up_stage)
            async for chunk in self.llm_service.generate_stream(" ", follow_up_template, session_id):
                if isinstance(chunk, str):
                    filtered = _strip_tool_call_text(chunk)
                    if filtered.strip():
                        yield filtered

    async def _generate_triage_opener_stream(
        self, user_input: str, session_id: str
    ) -> AsyncIterator[str]:
        """Auto-generate the first TRIAGE response after looping back from COMPLETED.

        Passes the user's original input (which already describes the new topic)
        directly to the TRIAGE LLM so it can start scoping immediately without
        requiring an extra round-trip from the user.
        """
        logger.info("Auto-generating TRIAGE opener after COMPLETED→TRIAGE loop-back")
        prompt_template = self.conversation_service.create_prompt_for_stage(
            ConversationStage.TRIAGE
        )
        async for chunk in self.llm_service.generate_stream(user_input, prompt_template, session_id):
            if isinstance(chunk, str):
                filtered = _strip_tool_call_text(chunk)
                if filtered.strip():
                    yield filtered
