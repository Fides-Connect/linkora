"""
Response Orchestration Service — Agentic Brain
Handles LLM response generation with conversation stage management,
signal_transition dispatch, tool dispatch, and FSM ownership.
"""
import re
import json
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator, Optional, Union

from langchain_core.messages import AIMessage

from .conversation_service import ConversationService, ConversationStage, is_legal_transition
from .llm_service import LLMService, SIGNAL_TRANSITION_SCHEMA
from .agent_runtime_fsm import AgentRuntimeFSM
from .agent_tools import AgentToolRegistry, ToolPermissionError, FINALIZE_TOOL_SCHEMAS
from ..prompts_templates import get_fallback_error_message
from ..data_provider import SearchUnavailableError  # noqa: F401 (used below)

logger = logging.getLogger(__name__)

# Matches known tool-call names leaked as plain text — e.g. signal_transition(target_stage="finalize").
# Intentionally restricted to tool names registered in build_default_registry so that
# normal prose containing parentheses ("call me (555) 123-4567") is never stripped.
_KNOWN_TOOL_NAMES_RE = re.compile(
    r'\b(?:signal_transition|search_providers|get_favorites|get_open_requests'
    r'|create_service_request|cancel_service_request|record_provider_interest|get_my_competencies'
    r'|save_competence_batch|delete_competences'
    r'|accept_provider|reject_and_fetch_next|cancel_search)\s*\([^)]*\)'
)

def _strip_tool_call_text(text: str) -> str:
    """Remove known tool-call name(...) patterns from a text chunk.

    Only strips the specific tool names registered in the default registry —
    not arbitrary identifiers — so normal prose with parentheses is preserved.
    Does NOT strip surrounding whitespace so inter-word spaces remain intact.
    """
    return _KNOWN_TOOL_NAMES_RE.sub("", text)


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
        """Async variant — thin wrapper around the sync helper.

        Side effects (provider search, context reset, competency fetch) are
        performed by _apply_signal_transition_with_payload in the stream loop.
        This variant is kept for compatibility with session_starter and tests.
        """
        return self.handle_signal_transition(target_str)

    async def _apply_signal_transition_with_payload(
        self,
        target: str,
        session_id: str,
        context: Optional[dict],
        pending: list,
        user_input: str = "",
    ) -> bool:
        """Apply a stage transition, run its side effects, and append a structured
        payload to *pending* so the follow-up LLM stream has full context.

        Returns True when the transition was accepted; on failure the error is
        appended to *pending* and False is returned.
        """
        previous_stage = self.conversation_service.get_current_stage()
        applied = self.handle_signal_transition(target)
        if not applied:
            logger.warning(
                "signal_transition to '%s' failed in stage %s; "
                "injecting error to trigger follow-up self-correction.",
                target, previous_stage,
            )
            pending.append((
                "signal_transition",
                {
                    "error": (
                        f"Transition to '{target}' failed — unrecognised or "
                        "illegal stage at this point. Verify the "
                        "target_stage value and the current conversation stage."
                    )
                },
            ))
            return False

        try:
            target_stage = ConversationStage(target)
        except ValueError:
            pending.append(("signal_transition", {"stage": target}))
            return True

        if target_stage == ConversationStage.FINALIZE:
            if previous_stage == ConversationStage.PROVIDER_ONBOARDING:
                logger.warning("Skipping provider search: previous stage was PROVIDER_ONBOARDING")
                providers: list = []
            else:
                await self.conversation_service.search_providers_for_request(session_id)
                # Divert to RECOVERY if Weaviate was unreachable. This prevents the
                # system from presenting zero results as if no provider matched.
                if self.conversation_service.context.pop("search_error", None) == "unavailable":
                    logger.warning(
                        "Weaviate unavailable during FINALIZE provider search — diverting to RECOVERY."
                    )
                    self.handle_signal_transition("recovery")
                    return True
                # Read providers stored by search_providers_for_request; avoids
                # the previous `await … or []` pattern that overwrote context.
                providers: list = self.conversation_service.context.get("providers_found", [])
            # Keep context cache in sync for follow-up stream cache-hit logic.
            self.conversation_service.context["providers_found"] = providers
            # Reset provider cursor so the LLM always starts from the first result.
            self.conversation_service.context["current_provider_index"] = 0
            # Update topic title as soon as we enter FINALIZE
            if self.ai_conversation_service:
                summary = self.conversation_service.get_problem_summary()
                await self.ai_conversation_service.set_topic_title(summary)
            # Zero-result bypass: skip FINALIZE entirely and return to TRIAGE.
            if len(providers) == 0:
                logger.info("Zero providers found — bypassing FINALIZE, returning to TRIAGE.")
                self.handle_signal_transition("triage")
                pending.append(("signal_transition", {
                    "stage": "triage",
                    "zero_result_event": (
                        "No service providers were found for this request. "
                        "Apologise briefly and invite the user to adjust their criteria."
                    ),
                }))
                return True
            current_provider = providers[0]
            pending.append(("signal_transition", {
                "stage": "finalize",
                "current_provider": current_provider,
            }))

        elif target_stage == ConversationStage.PROVIDER_ONBOARDING:
            comps: list = []
            if self.tool_registry:
                try:
                    result = await self.tool_registry.execute(
                        "get_my_competencies", {}, context or {}
                    )
                    comps = result if isinstance(result, list) else []
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "Failed to fetch competencies for PROVIDER_ONBOARDING payload: %s", exc
                    )
            self.conversation_service.context["current_competencies"] = comps
            # Record the baseline count so ongoing turns can detect concurrent
            # modifications from another session (B11).
            self.conversation_service.context["onboarding_baseline_count"] = len(comps)
            # Mirror is_service_provider so STEP 0 in the prompt renders correctly.
            _user_ctx = (context or {}).get("user_context", {})
            self.conversation_service.context["is_service_provider"] = (
                _user_ctx.get("is_service_provider", False)
            )
            logger.debug(
                "Fetched %d competencies for PROVIDER_ONBOARDING payload", len(comps)
            )
            pending.append(("signal_transition", {
                "stage": "provider_onboarding",
                "competencies": comps,
            }))

        elif target_stage == ConversationStage.COMPLETED:
            if previous_stage == ConversationStage.PROVIDER_ONBOARDING:
                self.conversation_service.reset_request_context()
                logger.info("Request context cleared after PROVIDER_ONBOARDING → COMPLETED")
            pitch_eligible = await self._should_pitch_provider_async(context)
            if pitch_eligible:
                pitch_applied = self.handle_signal_transition("provider_pitch")
                if not pitch_applied:
                    pitch_eligible = False
                    logger.warning(
                        "provider_pitch transition rejected; falling back to loop-back"
                    )
            pending.append(("signal_transition", {
                "stage": "completed",
                "pitch_eligible": pitch_eligible,
            }))

        elif target_stage == ConversationStage.TRIAGE:
            if previous_stage in (
                ConversationStage.COMPLETED, ConversationStage.FINALIZE,
                ConversationStage.PROVIDER_ONBOARDING, ConversationStage.PROVIDER_PITCH,
            ):
                # B9: preserve the triggering utterance BEFORE wiping context so it
                # can be re-injected as the first problem entry of the new TRIAGE session.
                triggering_utterance = user_input.strip() if user_input else ""
                self.conversation_service.reset_request_context()
                if triggering_utterance:
                    self.conversation_service.context["user_problem"].append(triggering_utterance)
                    logger.info(
                        "Preserved triggering utterance '%s...' for new TRIAGE session",
                        triggering_utterance[:50],
                    )
            pending.append(("signal_transition", {"stage": "triage"}))

        else:
            pending.append(("signal_transition", {"stage": target}))

        return True

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

    async def _should_pitch_provider_async(self, context: Optional[dict]) -> bool:
        """Async variant of _should_pitch_provider that adds a real-time Firestore
        sanity check just before entering PROVIDER_PITCH.

        In-memory check runs first (cheap); only on success does it hit Firestore
        to guard against a concurrent session that already made the user a provider.
        """
        if not self._should_pitch_provider(context):
            return False
        # B1: real-time authoritative check so we don't pitch a user who became
        # a provider in another concurrent session between session start and now.
        fs = (context or {}).get("firestore_service")
        user_id = (context or {}).get("user_id")
        if fs and user_id:
            try:
                fresh_user = await fs.get_user(user_id)
                if fresh_user and fresh_user.get("is_service_provider", False):
                    logger.info(
                        "Real-time check: user %s is already a provider — skipping provider pitch",
                        user_id,
                    )
                    # Sync in-memory context so we don't re-check next turn
                    if context and "user_context" in context:
                        context["user_context"]["is_service_provider"] = True
                    return False
            except Exception as exc:
                logger.warning(
                    "Real-time is_service_provider check failed for %s: %s — proceeding with in-memory value",
                    user_id, exc,
                )
        return True

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

    async def _run_follow_up_stream(
        self,
        pending: list,
        follow_up_input: str,
        session_id: str,
        context: Optional[dict],
        ai_response_parts: list,
        new_pending: list,
    ) -> AsyncIterator[Union[str, dict]]:
        """Run one follow-up LLM stream after a batch of pending tool results.

        1. All pending results are added to LLM history as AIMessages.
        2. If any result is a signal_transition payload, a "new_bubble" dict is
           yielded and the real *follow_up_input* is used (avoids blank
           HumanMessage that causes consecutive-human-message errors in Gemini).
        3. The stream runs with the current (possibly newly-transitioned) stage.
        4. Text chunks are appended to *ai_response_parts* and yielded to the
           caller. Tool calls in the follow-up populate *new_pending* so the
           caller can run a second pass.
        """
        if not pending:
            return

        # Feed all results into LLM history
        for fn_name, result in pending:
            result_str = (
                json.dumps(result, ensure_ascii=False, default=str)
                if isinstance(result, (dict, list))
                else str(result)
            )
            self.llm_service.add_message_to_history(
                session_id,
                AIMessage(content=f"[Tool {fn_name} returned: {result_str}]"),
            )

        has_transition = any(n == "signal_transition" for n, _ in pending)
        if has_transition:
            yield {"type": "new_bubble"}

        follow_up_stage = self.conversation_service.get_current_stage()
        follow_up_template = self.conversation_service.create_prompt_for_stage(follow_up_stage)
        # Use the real user input when a stage transition is present to avoid
        # storing a blank HumanMessage that would upset Gemini on the next turn.
        # Exception: when accept_provider triggered the transition internally (the user's
        # last utterance was a location/date answer, not a new service intent), feeding it
        # to LOOP_BACK_PROMPT causes the LLM to misread it as a new topic, call
        # signal_transition("triage"), and generate a duplicate confirmation message.
        _is_automated_provider_acceptance = any(n == "accept_provider" for n, _ in pending)
        if _is_automated_provider_acceptance:
            actual_input = " "
        else:
            actual_input = follow_up_input if has_transition else " "

        # In FINALIZE, restrict the LLM to only the three FINALIZE tools.
        if follow_up_stage == ConversationStage.FINALIZE:
            self.llm_service.register_functions(session_id, list(FINALIZE_TOOL_SCHEMAS))

        # Extract zero_result_event hint from any triage payload (set by reject_and_fetch_next
        # when the provider list is exhausted) so we can inject it into the human turn.
        _zero_event: Optional[str] = None
        for _pname, _ppayload in pending:
            if isinstance(_ppayload, dict) and _ppayload.get("stage") == "triage":
                _zero_event = _ppayload.get("zero_result_event")
                break
        if _zero_event:
            actual_input = f"{actual_input} [{_zero_event}]".strip()

        async for chunk in self.llm_service.generate_stream(
            actual_input, follow_up_template, session_id
        ):
            if isinstance(chunk, dict) and chunk.get("type") == "function_call":
                fu_name = chunk.get("name", "")
                fu_args = chunk.get("args", {})

                if fu_name == "signal_transition":
                    fu_target = fu_args.get("target_stage", "")
                    current = self.conversation_service.get_current_stage()
                    _write_tools = ("save_competence_batch", "delete_competences")
                    if (
                        current == ConversationStage.PROVIDER_ONBOARDING
                        and fu_target == ConversationStage.COMPLETED.value
                        and not any(n in _write_tools for n, _ in pending)
                    ):
                        logger.info(
                            "signal_transition('completed') from PROVIDER_ONBOARDING "
                            "in follow-up without a write — user chose no changes."
                        )
                    await self._apply_signal_transition_with_payload(
                        fu_target, session_id, context, new_pending
                    )
                else:
                    # FINALIZE-stage tools are intercepted here.
                    if fu_name in ("accept_provider", "reject_and_fetch_next", "cancel_search"):
                        await self._handle_finalize_tool(
                            fu_name, fu_args, session_id, context, new_pending
                        )
                    else:
                    # Guard: search_providers is redundant in FINALIZE when the
                    # auto-search already ran and returned results on stage entry.
                    # If the cached list is empty the first search may have been
                    # interrupted or used stale Weaviate data — re-fetch in that
                    # case so a repaired dataset is picked up.
                        _cached_providers = self.conversation_service.context.get(
                            "providers_found", []
                        )
                        if (
                            fu_name == "search_providers"
                            and self.conversation_service.get_current_stage()
                                == ConversationStage.FINALIZE
                            and _cached_providers
                        ):
                            tool_result = _cached_providers
                            logger.info(
                                "Intercepted search_providers in FINALIZE (follow-up) — "
                                "returning %d cached provider(s), skipping re-fetch.",
                                len(tool_result),
                            )
                        else:
                            tool_result = None
                            async for tc in self.dispatch_tool(fu_name, fu_args, context or {}):
                                tool_result = tc
                        if tool_result is not None and not (
                            isinstance(tool_result, dict) and tool_result.get("error")
                        ):
                            new_pending.append((fu_name, tool_result))
                            if isinstance(tool_result, dict) and "signal_transition" in tool_result:
                                await self._apply_signal_transition_with_payload(
                                    tool_result["signal_transition"], session_id, context, new_pending
                                )
            elif isinstance(chunk, str):
                filtered = _strip_tool_call_text(chunk)
                if filtered.strip():
                    ai_response_parts.append(filtered)
                    yield filtered

    async def _handle_finalize_tool(
        self,
        fn_name: str,
        fn_args: dict,
        session_id: str,
        context: Optional[dict],
        pending: list,
    ) -> None:
        """Dispatch FINALIZE-stage tool calls outside the tool registry.

        Handles accept_provider, reject_and_fetch_next, and cancel_search by
        executing their side effects and appending result payloads to *pending*
        for the follow-up LLM stream to respond to.
        """
        providers = self.conversation_service.context.get("providers_found", [])

        if fn_name == "accept_provider":
            provider_id = fn_args.get("provider_id", "")
            if not provider_id:
                logger.warning("accept_provider called with no provider_id — aborting service request creation.")
                pending.append(("accept_provider", {"error": "No provider selected"}))
                return
            location = fn_args.get("location", "")
            if not location:
                logger.warning("accept_provider called with no location — asking user before creating request.")
                pending.append(("accept_provider", {"error": "location_required", "message": "Please provide the city or address where the service is needed."}))
                return
            csr_args: dict = {"selected_provider_user_id": provider_id}
            for field in (
                "title", "description", "location", "category",
                "start_date", "end_date", "amount_value", "currency",
                "requested_competencies",
            ):
                if fn_args.get(field) is not None:
                    csr_args[field] = fn_args[field]

            # Enrich the provider candidate record with the actual match score
            # and reasons derived from the search/rerank results stored in context.
            accepted_provider = next(
                (p for p in providers if p.get("user", {}).get("user_id") == provider_id),
                None,
            )
            if accepted_provider is not None:
                if "rerank_score" in accepted_provider:
                    raw = float(accepted_provider["rerank_score"])
                    csr_args["_candidate_matching_score"] = round(
                        1.0 / (1.0 + math.exp(-raw)) * 100, 1
                    )
                elif "score" in accepted_provider:
                    csr_args["_candidate_matching_score"] = round(
                        float(accepted_provider["score"]) * 100, 1
                    )
                reasons = [t for t in [accepted_provider.get("title")] if t]
                if reasons:
                    csr_args["_candidate_matching_score_reasons"] = reasons

            result: Optional[dict] = None
            if self.tool_registry:
                try:
                    result = await self.tool_registry.execute(
                        "create_service_request", csr_args, context or {}
                    )
                except Exception as exc:
                    logger.warning("accept_provider: create_service_request failed: %s", exc)
                    result = {"error": str(exc)}
            if result is None:
                result = {"error": "Tool registry unavailable"}

            pending.append(("accept_provider", result))
            if not result.get("error"):
                # Link the newly created service request to the AI conversation
                # document (§6.4). This must happen here because create_service_request
                # is called internally — the outer tool-dispatch block never sees it.
                if self.ai_conversation_service and isinstance(result, dict):
                    req_id = result.get("id") or result.get("service_request_id")
                    if req_id:
                        await self.ai_conversation_service.set_request_id(req_id)
                await self._apply_signal_transition_with_payload(
                    "completed", session_id, context, pending, user_input=""
                )

        elif fn_name == "reject_and_fetch_next":
            idx = self.conversation_service.context.get("current_provider_index", 0) + 1
            self.conversation_service.context["current_provider_index"] = idx

            if idx < len(providers):
                next_provider = providers[idx]
                pending.append(("reject_and_fetch_next", {
                    "status": "next_provider",
                    "current_provider": next_provider,
                }))
            else:
                logger.info(
                    "Provider list exhausted at index %d — returning to TRIAGE.", idx
                )
                await self._apply_signal_transition_with_payload(
                    "triage", session_id, context, pending, user_input=""
                )
                # Enrich the triage payload with an exhaustion hint.
                for _, ppayload in pending:
                    if (
                        isinstance(ppayload, dict)
                        and ppayload.get("stage") == "triage"
                        and "zero_result_event" not in ppayload
                    ):
                        ppayload["zero_result_event"] = (
                            "All available providers have been reviewed and none were accepted. "
                            "Apologise briefly and invite the user to adjust their criteria."
                        )
                        break

        elif fn_name == "cancel_search":
            await self._apply_signal_transition_with_payload(
                "triage", session_id, context, pending, user_input=""
            )
            pending.append(("cancel_search", {
                "status": "cancelled",
                "message": (
                    "User cancelled the search. Acknowledge briefly "
                    "then offer further help."
                ),
            }))

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

        Flow:
        1. Main LLM stream — text chunks yielded directly; signal_transition and
           tool calls go to pending_tool_results (signal_transition payloads
           include side-effect data: providers, competencies, pitch eligibility).
        2. First follow-up stream — runs if pending_tool_results is non-empty;
           handles the auto-response for finalize, onboarding, completed, etc.
        3. Second follow-up stream — runs if the first follow-up itself triggered
           new signal_transitions or tool calls (e.g. loop-back → triage).

        Registers SIGNAL_TRANSITION_SCHEMA so Gemini uses native function-calling.
        Fires AgentRuntimeFSM events at key lifecycle points.
        Delegates message persistence to ai_conversation_service when set.
        """
        try:
            # ── Determine stage before registering tools ────────────────────────
            current_stage = self.conversation_service.get_current_stage()

            # ── Register tools ─────────────────────────────────────────────────
            # In FINALIZE, restrict the LLM to only the three FINALIZE tools so it
            # cannot call signal_transition, create_service_request, etc.
            if current_stage == ConversationStage.FINALIZE:
                tool_schemas = list(FINALIZE_TOOL_SCHEMAS)
            else:
                tool_schemas = [SIGNAL_TRANSITION_SCHEMA]
                if self.tool_registry:
                    tool_schemas += self.tool_registry.all_schemas()
            self.llm_service.register_functions(session_id, tool_schemas)

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

            # Pre-fetch competencies for ongoing PROVIDER_ONBOARDING turns so the
            # stage prompt always has the up-to-date list without the LLM calling
            # get_my_competencies.  (Freshly transitioned sessions are handled by
            # _apply_signal_transition_with_payload.)
            if current_stage == ConversationStage.PROVIDER_ONBOARDING and self.tool_registry:
                try:
                    competencies = await self.tool_registry.execute(
                        "get_my_competencies", {}, context or {}
                    )
                    self.conversation_service.context["current_competencies"] = (
                        competencies if isinstance(competencies, list) else []
                    )
                    # Keep is_service_provider in sync so STEP 0 reflects reality.
                    _uctx = (context or {}).get("user_context", {})
                    self.conversation_service.context["is_service_provider"] = (
                        _uctx.get("is_service_provider", False)
                    )
                    logger.debug(
                        "Pre-fetched %d competencies for PROVIDER_ONBOARDING",
                        len(self.conversation_service.context["current_competencies"]),
                    )
                    # B11: Detect concurrent-session competency changes and
                    # discard the in-memory draft so the user is not silently
                    # overwritten by a stale onboarding conversation.
                    _baseline = self.conversation_service.context.get(
                        "onboarding_baseline_count"
                    )
                    _live_count = len(
                        self.conversation_service.context["current_competencies"]
                    )
                    if _baseline is not None and _live_count != _baseline:
                        logger.info(
                            "Concurrent modification detected: competency count "
                            "changed from %d → %d; discarding onboarding draft",
                            _baseline,
                            _live_count,
                        )
                        self.conversation_service.context["onboarding_draft"] = []
                        self.conversation_service.context["onboarding_baseline_count"] = (
                            _live_count
                        )
                        self.conversation_service.context[
                            "onboarding_draft_invalidated"
                        ] = True
                    else:
                        self.conversation_service.context.pop(
                            "onboarding_draft_invalidated", None
                        )
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to pre-fetch competencies: %s", exc)

            # Build prompt for the current stage
            prompt_template = self.conversation_service.create_prompt_for_stage(current_stage)

            # ── Main LLM stream ─────────────────────────────────────────────────
            first_chunk = True
            ai_response_parts: list[str] = []
            pending_tool_results: list[tuple[str, object]] = []

            async for chunk in self.llm_service.generate_stream(
                user_input, prompt_template, session_id
            ):
                if first_chunk:
                    self.runtime_fsm.transition("llm_stream_started")
                    first_chunk = False

                if isinstance(chunk, dict) and chunk.get("type") == "function_call":
                    fn_name = chunk.get("name", "")
                    fn_args = chunk.get("args", {})

                    if fn_name == "signal_transition":
                        self.runtime_fsm.transition("tool_call")
                        target = fn_args.get("target_stage", "")

                        _write_tools = ("save_competence_batch", "delete_competences")
                        if (
                            current_stage == ConversationStage.PROVIDER_ONBOARDING
                            and target == ConversationStage.COMPLETED.value
                            and not any(n in _write_tools for n, _ in pending_tool_results)
                        ):
                            logger.info(
                                "signal_transition to 'completed' from PROVIDER_ONBOARDING "
                                "without a write tool — user likely chose no changes."
                            )

                        await self._apply_signal_transition_with_payload(
                            target, session_id, context, pending_tool_results,
                            user_input=user_input,
                        )
                        self.runtime_fsm.transition("tool_done")

                    else:
                        # FINALIZE-stage tools are intercepted here and never
                        # dispatched through the registry.
                        tool_result = None
                        if fn_name in ("accept_provider", "reject_and_fetch_next", "cancel_search"):
                            self.runtime_fsm.transition("tool_call")
                            await self._handle_finalize_tool(
                                fn_name, fn_args, session_id, context, pending_tool_results
                            )
                            self.runtime_fsm.transition("tool_done")

                        else:
                        # Regular tool call
                        # Guard: search_providers is redundant in FINALIZE when
                        # the auto-search already ran and found results.  If the
                        # cache is empty the first search may have been interrupted
                        # or used stale Weaviate data — re-fetch so a repaired
                        # dataset is picked up on the next turn.
                            self.runtime_fsm.transition("tool_call")
                            _cached_providers = self.conversation_service.context.get(
                                "providers_found", []
                            )
                            if (
                                fn_name == "search_providers"
                                and self.conversation_service.get_current_stage()
                                    == ConversationStage.FINALIZE
                                and _cached_providers
                            ):
                                tool_result = _cached_providers
                                logger.info(
                                    "Intercepted search_providers in FINALIZE — "
                                    "returning %d cached provider(s), skipping re-fetch.",
                                    len(tool_result),
                                )
                            else:
                                tool_result = None
                                async for tool_chunk in self.dispatch_tool(
                                    fn_name, fn_args, context or {}
                                ):
                                    tool_result = tool_chunk
                            self.runtime_fsm.transition("tool_done")

                        if tool_result is not None:
                            is_error = (
                                isinstance(tool_result, dict) and tool_result.get("error")
                            )
                            if not is_error:
                                pending_tool_results.append((fn_name, tool_result))
                                # Handle stage transition embedded in tool result.
                                # Guard: skip self-loop transitions (e.g. record_provider_interest
                                # called while already in PROVIDER_ONBOARDING returns
                                # {"signal_transition": "provider_onboarding"} — do not re-enter).
                                if isinstance(tool_result, dict) and "signal_transition" in tool_result:
                                    sig_target = tool_result["signal_transition"]
                                    try:
                                        _sig_stage = ConversationStage(sig_target)
                                    except ValueError:
                                        _sig_stage = None
                                    _cur_stage = self.conversation_service.get_current_stage()
                                    if _sig_stage is not None and _sig_stage == _cur_stage:
                                        logger.info(
                                            "Skipping same-stage signal_transition '%s' "
                                            "from tool result — already in this stage.",
                                            sig_target,
                                        )
                                    else:
                                        await self._apply_signal_transition_with_payload(
                                            sig_target, session_id, context, pending_tool_results
                                        )
                                # Surface provider list for stage-context use
                                if fn_name == "search_providers" and isinstance(tool_result, list):
                                    self.conversation_service.context["providers_found"] = tool_result
                                # Sync in-memory user_context after provider pitch response so
                                # _should_pitch_provider won't re-fire when stage hits COMPLETED.
                                if fn_name == "record_provider_interest" and isinstance(tool_result, dict):
                                    status = tool_result.get("status")
                                    if context and "user_context" in context:
                                        from datetime import datetime as _dt, timezone as _tz
                                        from ..firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL
                                        if status == "never":
                                            context["user_context"]["last_time_asked_being_provider"] = PROVIDER_PITCH_OPT_OUT_SENTINEL
                                        elif status in ("not_now", "accepted"):
                                            context["user_context"]["last_time_asked_being_provider"] = _dt.now(_tz.utc)
                                        if status == "accepted":
                                            context["user_context"]["is_service_provider"] = True
                                            # Also mirror into conversation context so the next
                                            # PROVIDER_ONBOARDING prompt renders with STEP 0 skipped.
                                            self.conversation_service.context["is_service_provider"] = True
                                # Link created service request to conversation
                                if fn_name == "create_service_request" and self.ai_conversation_service:
                                    req_id = (
                                        tool_result.get("id")
                                        or tool_result.get("service_request_id")
                                        if isinstance(tool_result, dict)
                                        else str(tool_result)
                                    )
                                    if req_id:
                                        await self.ai_conversation_service.set_request_id(req_id)
                                # Refresh competency list after a write so next prompt
                                # reflects the latest state
                                if (
                                    fn_name in ("save_competence_batch", "delete_competences")
                                    and self.tool_registry
                                ):
                                    try:
                                        refreshed = await self.tool_registry.execute(
                                            "get_my_competencies", {}, context or {}
                                        )
                                        self.conversation_service.context["current_competencies"] = (
                                            refreshed if isinstance(refreshed, list) else []
                                        )
                                        logger.debug(
                                            "Refreshed competencies after %r: %d items",
                                            fn_name,
                                            len(self.conversation_service.context["current_competencies"]),
                                        )
                                    except Exception as exc:  # pragma: no cover
                                        logger.warning(
                                            "Failed to refresh competencies after write: %s", exc
                                        )
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

            # ── Follow-up streams (bounded loop) ───────────────────────────────
            # Each iteration handles one batch of pending tool/transition results.
            # Iteration 0 carries the real user_input so the first follow-up LLM
            # call can use it when constructing the human turn.  Deeper iterations
            # use a neutral prompt instead: re-feeding user_input at depth ≥ 1
            # caused cascading misinterpretation (e.g. CONFIRMATION reading "try
            # again" as a refusal and oscillating back to TRIAGE, whose accumulated
            # problem context immediately bounced back to CONFIRMATION — dropping
            # all pending results from the third hop on the floor).
            MAX_FOLLOW_UP_DEPTH = 4
            current_pending = pending_tool_results
            for follow_up_iter in range(MAX_FOLLOW_UP_DEPTH):
                if not current_pending:
                    break
                next_pending: list[tuple[str, object]] = []
                # Only the first follow-up stream sees the real user utterance.
                follow_up_user_input = user_input if follow_up_iter == 0 else " "
                async for chunk in self._run_follow_up_stream(
                    current_pending, follow_up_user_input, session_id, context,
                    ai_response_parts, next_pending
                ):
                    yield chunk
                current_pending = next_pending

            if current_pending:
                logger.warning(
                    "Follow-up chain still had %d pending item(s) after %d iterations — "
                    "discarding to prevent unbounded recursion.",
                    len(current_pending), MAX_FOLLOW_UP_DEPTH,
                )

            # ── Safety fallback: stuck-in-FINALIZE guard ─────────────────────────
            # FINALIZE is a user-driven decision stage — the LLM awaits explicit
            # accept/reject/cancel input.  Forcing RECOVERY here would discard the
            # provider presentation mid-flow.  The fallback is therefore disabled:
            # the stage will persist until the next user utterance triggers one of
            # the three FINALIZE tools.  (§3.2)

            # ── Stream complete ──────────────────────────────────────────────────
            ai_text = "".join(ai_response_parts)

            # Safety net: if the entire orchestration produced no visible text
            # (e.g. the LLM exhausted its token budget on thinking tokens and
            # emitted nothing, or a transient Gemini API empty-stream), yield a
            # generic fallback so the user is not left in complete silence.
            if not ai_text.strip():
                logger.warning(
                    "generate_response_stream: empty response after all streams "
                    "(stage=%s, user_input=%r). Yielding fallback.",
                    self.conversation_service.get_current_stage(),
                    user_input[:80],
                )
                fallback = get_fallback_error_message(self.conversation_service.language)
                yield fallback
                ai_text = fallback

            self.conversation_service.record_ai_response(ai_text)

            if self.ai_conversation_service and ai_text.strip():
                final_stage = self.conversation_service.get_current_stage()
                await self.ai_conversation_service.save_message(
                    role="assistant", text=ai_text, stage=final_stage
                )

        except Exception as exc:
            logger.error("Error in response orchestration: %s", exc, exc_info=True)
            yield get_fallback_error_message(self.conversation_service.language)
        finally:
            # Always reset the FSM regardless of whether the stream yielded
            # content, returned empty, or raised an exception.  Without this,
            # a pure tool-call stream (no text chunks) or an error path would
            # leave the FSM stuck in THINKING or TOOL_EXECUTING forever.
            self.runtime_fsm.transition("stream_complete_text")
