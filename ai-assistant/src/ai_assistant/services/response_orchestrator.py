"""
Response Orchestration Service — Agentic Brain
Handles LLM response generation with conversation stage management,
signal_transition dispatch, tool dispatch, and FSM ownership.
"""
import asyncio
import re
import json
import math
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, TYPE_CHECKING, cast
from collections.abc import AsyncGenerator, AsyncIterator

if TYPE_CHECKING:
    from .ai_conversation_service import AIConversationService
    from .agent_profile import AgentProfile

from langchain_core.messages import AIMessage

from .conversation_service import ConversationService, ConversationStage
from .llm_service import LLMService, SIGNAL_TRANSITION_SCHEMA
from .agent_runtime_fsm import AgentRuntimeFSM
from .agent_tools import AgentToolRegistry, ToolContext, ToolPermissionError, FINALIZE_TOOL_SCHEMAS, BROWSE_TOOL_SCHEMAS
from ..prompts_templates import get_fallback_error_message
from ..data_provider import SearchUnavailableError  # noqa: F401 (used below)

logger = logging.getLogger(__name__)


def is_legal_transition(
    current: ConversationStage,
    target: ConversationStage,
    legal_transitions: dict,
) -> bool:
    """Return True when *target* is in the allowed transitions from *current*."""
    return target in legal_transitions.get(current, [])


def _extract_user_text_from_system_event(raw_text: str) -> str:
    """Extract user text from a buffered system-event wrapper when present."""
    clean = raw_text.strip()
    # Preferred format: [System Event: ... message: "<user text>"]
    msg_match = re.search(r'message:\s*"([^\"]*)"', clean)
    if msg_match:
        return msg_match.group(1).strip()
    # Fallback: remove only the leading wrapper and keep trailing user text.
    return re.sub(r'^\[System Event:[^\]]+\]\s*', '', clean).strip()

# Matches known tool-call names leaked as plain text — e.g. signal_transition(target_stage="finalize").
# Intentionally restricted to tool names registered in build_default_registry so that
# normal prose containing parentheses ("call me (555) 123-4567") is never stripped.
_KNOWN_TOOL_NAMES_RE = re.compile(
    r'\b(?:signal_transition|search_providers|get_favorites|get_open_requests'
    r'|create_service_request|cancel_service_request|record_provider_interest|get_my_competencies'
    r'|save_competence_batch|delete_competences'
    r'|accept_provider|reject_and_fetch_next|cancel_search|retry_search|generate_contact_template'
    r'|show_next_providers)\s*\([^)]*\)'
)

def _strip_tool_call_text(text: str) -> str:
    """Remove known tool-call name(...) patterns from a text chunk.

    Only strips the specific tool names registered in the default registry —
    not arbitrary identifiers — so normal prose with parentheses is preserved.
    Does NOT strip surrounding whitespace so inter-word spaces remain intact.
    """
    return _KNOWN_TOOL_NAMES_RE.sub("", text)


# Matches markdown heading markers at the start of a line (e.g. "## Heading").
_MARKDOWN_HEADING_RE = re.compile(r'^#{1,6}\s+', re.MULTILINE)
# Matches paired inline-code spans and unwraps the enclosed text.
_MARKDOWN_INLINE_CODE_RE = re.compile(r'(`+)([^`\n]+?)\1')
# Matches paired emphasis markers only when they are used as delimiters rather than
# appearing inside words or expressions such as snake_case or 3*5.
_MARKDOWN_BOLD_ITALIC_STAR_RE = re.compile(r'(?<!\w)\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*(?!\w)')
_MARKDOWN_BOLD_STAR_RE = re.compile(r'(?<!\w)\*\*(?=\S)(.+?)(?<=\S)\*\*(?!\w)')
_MARKDOWN_BOLD_UNDERSCORE_RE = re.compile(r'(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)')
_MARKDOWN_ITALIC_STAR_RE = re.compile(r'(?<!\w)\*(?=\S)(.+?)(?<=\S)\*(?!\w)')
_MARKDOWN_ITALIC_UNDERSCORE_RE = re.compile(r'(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)')


def _strip_markdown_formatting(text: str) -> str:
    """Remove common markdown formatting markers from a text chunk.

    Strips heading markers and unwraps paired inline markdown constructs while
    preserving literal ``*`` and ``_`` characters that are part of normal content
    such as identifiers, URLs, or arithmetic.
    """
    text = _MARKDOWN_HEADING_RE.sub("", text)
    text = _MARKDOWN_INLINE_CODE_RE.sub(r'\2', text)
    text = _MARKDOWN_BOLD_ITALIC_STAR_RE.sub(r'\1', text)
    text = _MARKDOWN_BOLD_STAR_RE.sub(r'\1', text)
    text = _MARKDOWN_BOLD_UNDERSCORE_RE.sub(r'\1', text)
    text = _MARKDOWN_ITALIC_STAR_RE.sub(r'\1', text)
    return _MARKDOWN_ITALIC_UNDERSCORE_RE.sub(r'\1', text)


# Human-readable status labels sent to the client while a tool is executing.
_TOOL_STATUS_LABELS: dict[str, str] = {
    "search_providers": "Searching for providers",
    "get_favorites": "Loading your favorites",
    "get_open_requests": "Loading your requests",
    "create_service_request": "Submitting your request",
    "cancel_service_request": "Cancelling your request",
    "record_provider_interest": "Saving your preferences",
    "get_my_competencies": "Loading your skills",
    "save_competence_batch": "Saving your skills",
    "delete_competences": "Removing skills",
    "accept_provider": "Confirming your choice",
    "reject_and_fetch_next": "Finding the next match",
    "cancel_search": "Cancelling search",
    "retry_search": "Searching again",
    "generate_contact_template": "Preparing contact details",
    "show_next_providers": "Finding more results",
}


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
        runtime_fsm: AgentRuntimeFSM | None = None,
        tool_registry: AgentToolRegistry | None = None,
        ai_conversation_service: AIConversationService | None = None,
        profile: AgentProfile | None = None,
    ) -> None:
        from .agent_profile import FULL_PROFILE

        self.llm_service = llm_service
        self.conversation_service = conversation_service
        self.runtime_fsm: AgentRuntimeFSM = runtime_fsm or AgentRuntimeFSM()
        self.tool_registry = tool_registry
        self.ai_conversation_service = ai_conversation_service
        self._profile = profile if profile is not None else FULL_PROFILE

    # ── Stage helpers ──────────────────────────────────────────────────────────

    def handle_signal_transition(self, target_str: str) -> bool:
        """
        Validate and apply a stage transition requested by the LLM (sync).

        Uses the profile's ``legal_transitions`` table for validation so lite-mode
        restrictions are enforced even if the LLM requests a forbidden stage.

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
        if not is_legal_transition(current, target, self._profile.legal_transitions):
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
        context: dict[str, Any] | None,
        pending: list[tuple[str, Any]],
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
                providers: list[dict] = []
            else:
                await self.conversation_service.search_providers_for_request(session_id)
                # Divert to RECOVERY if Weaviate was unreachable. This prevents the
                # system from presenting zero results as if no provider matched.
                if self.conversation_service.context.pop("search_error", None) == "unavailable":
                    logger.warning(
                        "Weaviate unavailable during FINALIZE provider search — diverting to RECOVERY."
                    )
                    self.conversation_service.context["search_outage_pending"] = True
                    self.conversation_service.context["search_failure_count"] = (
                        self.conversation_service.context.get("search_failure_count", 0) + 1
                    )
                    self.handle_signal_transition("recovery")
                    pending.append(("signal_transition", {"stage": "recovery"}))
                    return True
                # Successful search: clear outage flags/counters so only
                # consecutive failures trigger the circuit-breaker behavior.
                self.conversation_service.context.pop("search_outage_pending", None)
                self.conversation_service.context.pop("search_failure_count", None)
                # Read providers stored by search_providers_for_request; avoids
                # the previous `await … or []` pattern that overwrote context.
                providers = self.conversation_service.context.get("providers_found", [])
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
            gp_context = self.conversation_service.context
            pending.append(("signal_transition", {
                "stage": "finalize",
                "current_provider": current_provider,
                "google_places_used": gp_context.get("google_places_used", False),
                "google_places_error": gp_context.get("google_places_error", False),
            }))

        elif target_stage == ConversationStage.PROVIDER_ONBOARDING:
            comps: list = []
            if self.tool_registry:
                try:
                    result = await self.tool_registry.execute(
                        "get_my_competencies", {}, cast(ToolContext, context or {})
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
            pitch_eligible = (
                self._profile.provider_pitch_enabled
                and await self._should_pitch_provider_async(context)
            )
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
                ConversationStage.BROWSE,
                ConversationStage.PROVIDER_ONBOARDING, ConversationStage.PROVIDER_PITCH,
            ):
                # B9: preserve the triggering utterance BEFORE wiping context so it
                # can be re-injected as the first problem entry of the new TRIAGE session.
                triggering_utterance = user_input.strip() if user_input else ""
                self.conversation_service.reset_request_context()
                if triggering_utterance:
                    self.conversation_service.context["user_problem"].append(triggering_utterance)
                    logger.debug(
                        "Preserved triggering utterance '%s...' for new TRIAGE session",
                        triggering_utterance[:50],
                    )
            # Clear outage flags whenever we settle into TRIAGE
            self.conversation_service.context.pop("search_outage_pending", None)
            self.conversation_service.context.pop("search_failure_count", None)
            pending.append(("signal_transition", {"stage": "triage"}))

        elif target_stage == ConversationStage.CONFIRMATION:
            if previous_stage == ConversationStage.RECOVERY:
                # RECOVERY → CONFIRMATION: outage-retry path.
                # The draft is already intact; just clear the outage flag so the
                # next FINALIZE attempt starts cleanly.
                self.conversation_service.context.pop("search_outage_pending", None)
                logger.info("RECOVERY → CONFIRMATION: outage retry path, draft preserved.")
            pending.append(("signal_transition", {"stage": "confirmation"}))

        elif target_stage == ConversationStage.BROWSE:
            # Reset browse_offset to 3 so the first show_next_providers call
            # starts from the 4th provider (first 3 were shown in FINALIZE).
            self.conversation_service.context["browse_offset"] = 3
            providers = self.conversation_service.context.get("providers_found", [])
            total_count = len(providers)
            remaining_count = max(0, total_count - 3)
            pending.append(("signal_transition", {
                "stage": "browse",
                "total_count": total_count,
                "shown_count": 3,
                "remaining_count": remaining_count,
                "has_more": remaining_count > 0,
            }))

        else:
            pending.append(("signal_transition", {"stage": target}))

        return True

    # ── Provider card helpers ─────────────────────────────────────────────────

    async def _localise_card_descriptions(
        self,
        gp_results: list[dict[str, Any]],
        user_query: str,
        language: str,
    ) -> list[str]:
        """Generate localised one-sentence descriptions for each GP card.

        Uses a single batched LLM call for efficiency.  Falls back to the stored
        description on any error so card display is never blocked.

        Only called for non-English sessions — English sessions display the
        stored description as-is.
        """
        from langchain_core.messages import HumanMessage
        from ..prompts_templates import PROVIDER_CARD_DESCRIPTION_LOCALISE_PROMPT

        language_name = "German" if language == "de" else language.capitalize()

        def _name(p: dict) -> str:
            return str((p.get("user") or {}).get("name") or p.get("title", ""))

        provider_items = "\n".join(
            f"{i + 1}. {_name(p)}: {p.get('search_optimized_summary') or p.get('description', '')[:200]}"
            for i, p in enumerate(gp_results)
        )
        prompt = PROVIDER_CARD_DESCRIPTION_LOCALISE_PROMPT.format(
            language_name=language_name,
            user_request=user_query or "service request",
            providers=provider_items,
            count=len(gp_results),
        )
        try:
            raw = await self.llm_service.generate([HumanMessage(content=prompt)])
            items = re.findall(r"(?m)^\s*\d+\.\s*(.+?)\s*$", raw)
            if len(items) == len(gp_results):
                return items
        except Exception as exc:
            logger.warning("Provider card description localisation failed: %s", exc)
        return [p.get("description", "") for p in gp_results]

    async def _generate_card_reasoning(
        self,
        gp_results: list[dict[str, Any]],
        user_query: str = "",
        language: str = "en",
    ) -> list[str]:
        """Generate a 1-sentence match justification for each GP result.

        Single LLM call returning a JSON array.  Falls back to empty strings on
        any error so card display is never blocked.
        """
        from langchain_core.messages import HumanMessage
        from ..prompts_templates import PROVIDER_CARD_REASONING_PROMPT

        def _provider_entry(idx: int, p: dict) -> str:
            name = (p.get("user") or {}).get("name") or p.get("title", "")
            primary_type = p.get("primary_type") or p.get("category") or ""
            address = p.get("address") or (p.get("user") or {}).get("address") or ""
            description = p.get("description", "")[:300]
            snippets = (p.get("review_snippets") or [])[:5]

            type_str = f" ({primary_type})" if primary_type else ""
            lines = [f"{idx + 1}. {name}{type_str}"]
            if address:
                lines.append(f"   Location: {address}")
            if description:
                lines.append(f"   Description: {description}")
            if snippets:
                lines.append("   Customer reviews: " + "; ".join(snippets))
            return "\n".join(lines)

        provider_items = "\n\n".join(
            _provider_entry(i, p) for i, p in enumerate(gp_results)
        )
        language_name = "German" if language == "de" else language.capitalize()
        prompt = PROVIDER_CARD_REASONING_PROMPT.format(
            query=user_query or "service request",
            providers=provider_items,
            count=len(gp_results),
            language_name=language_name,
        )
        try:
            raw = await self.llm_service.generate([HumanMessage(content=prompt)])
            items = re.findall(r"(?m)^\s*\d+\.\s*(.+?)\s*$", raw)
            if len(items) == len(gp_results):
                return items
        except Exception as exc:
            logger.warning("Provider card reasoning failed: %s", exc)
        return [""] * len(gp_results)

    async def _build_provider_cards(
        self,
        gp_results: list[dict[str, Any]],
        user_query: str = "",
    ) -> list[dict[str, Any]]:
        """Build card payloads for GP results with LLM-generated reasoning."""
        language = self.conversation_service.language
        reasoning = await self._generate_card_reasoning(gp_results, user_query, language)
        request_summary = self.conversation_service.context.get("request_summary", "") or user_query
        user_name = self.conversation_service.context.get("user_name", "")

        # Pre-compute per-card params.
        card_params = []
        for p in gp_results:
            user = p.get("user") or {}
            provider_name = user.get("name") or p.get("title", "")
            provider_address = p.get("address") or user.get("address") or ""
            card_params.append((provider_name, provider_address))

        # Generate email templates and localise card descriptions concurrently.
        email_tasks = [
            self._build_email_template(name, request_summary, language, user_name, addr)
            for name, addr in card_params
        ]
        if language != "en":
            localise_task = self._localise_card_descriptions(gp_results, user_query, language)
            *email_results_list, localised_descs = await asyncio.gather(*email_tasks, localise_task)
            email_results = list(email_results_list)
        else:
            email_results = list(await asyncio.gather(*email_tasks))
            localised_descs = [p.get("description", "") for p in gp_results]

        cards: list[dict[str, Any]] = []
        for i, p in enumerate(gp_results):
            user = p.get("user") or {}
            provider_name, provider_address = card_params[i]
            email_subject, email_body = email_results[i]
            card: dict[str, Any] = {
                "name": provider_name,
                "description": localised_descs[i] if i < len(localised_descs) else p.get("description", ""),
                "reasoning": reasoning[i] if i < len(reasoning) else "",
                "rating": user.get("average_rating"),
                "rating_count": user.get("rating_count"),
                "website": p.get("website") or user.get("website") or None,
                "phone": p.get("phone") or user.get("phone") or None,
                "address": provider_address or None,
                "email": p.get("email") or user.get("email") or None,
                "photo_url": p.get("photo_url") or None,
                "opening_hours": p.get("opening_hours") or None,
                "maps_url": p.get("maps_url") or None,
                "email_subject": email_subject,
                "email_body": email_body,
                "language": language,
                "source": user.get("source", "google_places"),
            }
            # Normalise empty strings to None for optional fields
            for field in ("website", "phone", "address", "email", "photo_url", "opening_hours", "maps_url"):
                if card[field] == "":
                    card[field] = None
            cards.append(card)
        return cards

    async def _build_email_template(
        self,
        provider_name: str,
        request_summary: str,
        language: str,
        user_name: str = "",
        provider_address: str = "",
    ) -> tuple[str, str]:
        """Return (subject, body) for a pre-filled enquiry email to a GP provider.

        Uses an LLM call to produce natural prose from the structured
        request_summary.  Falls back to a static template on any error.
        """
        from langchain_core.messages import HumanMessage
        from ..prompts_templates import PROVIDER_ENQUIRY_EMAIL_PROMPT

        prompt = PROVIDER_ENQUIRY_EMAIL_PROMPT.format(
            language="German" if language == "de" else "English",
            provider_name=provider_name,
            provider_address=provider_address or "—",
            user_name=user_name or "",
            request_summary=request_summary or "—",
        )
        try:
            raw = await self.llm_service.generate([HumanMessage(content=prompt)])
            # Strip optional markdown code fences
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
            raw = re.sub(r"\n?```$", "", raw.strip())
            parsed = json.loads(raw)
            subject = str(parsed.get("subject", "")).strip()
            body = str(parsed.get("body", "")).strip()
            if subject and body:
                return subject, body
        except Exception as exc:
            logger.warning("Email template LLM generation failed: %s", exc)

        # ── Static fallback ────────────────────────────────────────────────────
        return self._build_email_template_static(
            provider_name, request_summary, language, user_name, provider_address
        )

    @staticmethod
    @staticmethod
    def _format_request_summary(request_summary: str, language: str) -> str:
        """
        Convert a structured-query JSON string into a human-readable paragraph.

        If ``request_summary`` is a JSON object with ``category``, ``location``,
        ``criterions``, and/or ``available_time`` keys (as generated by the
        structured-query extractor), it is rendered as natural prose.  Plain
        strings are returned unchanged.
        """
        import json as _json

        try:
            data = _json.loads(request_summary)
        except Exception:
            return request_summary  # already plain text

        if not isinstance(data, dict):
            return request_summary

        category = str(data.get("category") or "").strip()
        location = str(data.get("location") or "").strip()
        criterions: list[str] = [str(c).strip() for c in (data.get("criterions") or []) if c]
        available_time = str(data.get("available_time") or "").strip()

        if language == "de":
            parts: list[str] = []
            if category and location:
                parts.append(f"Ich suche {category} in {location}.")
            elif category:
                parts.append(f"Ich suche {category}.")
            elif location:
                parts.append(f"Ich suche jemanden in {location}.")
            if criterions:
                parts.append(f"Anforderungen: {', '.join(criterions)}.")
            if available_time and available_time.lower() not in ("flexible", "flexibel", ""):
                parts.append(f"Verfügbarkeit: {available_time}.")
            elif available_time.lower() in ("flexible", "flexibel"):
                parts.append("Ich bin zeitlich flexibel.")
            return " ".join(parts) if parts else request_summary
        else:
            parts = []
            if category and location:
                parts.append(f"I am looking for {category} in {location}.")
            elif category:
                parts.append(f"I am looking for {category}.")
            elif location:
                parts.append(f"I am looking for someone in {location}.")
            if criterions:
                parts.append(f"Requirements: {', '.join(criterions)}.")
            if available_time and available_time.lower() not in ("flexible", ""):
                parts.append(f"Availability: {available_time}.")
            elif available_time.lower() == "flexible":
                parts.append("I am flexible regarding timing.")
            return " ".join(parts) if parts else request_summary

    @staticmethod
    def _build_email_template_static(
        provider_name: str,
        request_summary: str,
        language: str,
        user_name: str = "",
        provider_address: str = "",
    ) -> tuple[str, str]:
        """Static template with human-readable request prose."""
        formatted_request = ResponseOrchestrator._format_request_summary(
            request_summary, language
        )
        location_note = f" ({provider_address})" if provider_address else ""
        if language == "de":
            subject = f"Kontaktanfrage: {provider_name}"
            greeting = f"Sehr geehrte Damen und Herren von {provider_name}{location_note},"
            intro = "ich möchte gerne eine Anfrage bei Ihnen stellen."
            details_label = "Mein Anliegen"
            closing = "Ich freue mich über Ihre Rückmeldung und bin gespannt, von Ihnen zu hören."
            salutation = f"Mit freundlichen Grüßen,\n{user_name}" if user_name else "Mit freundlichen Grüßen"
        else:
            subject = f"Request: {provider_name}"
            greeting = f"Dear {provider_name}{location_note} team,"
            intro = "I would like to get in touch regarding a request."
            details_label = "My request"
            closing = "I look forward to hearing from you and discussing this further."
            salutation = f"Kind regards,\n{user_name}" if user_name else "Kind regards"

        body = (
            f"{greeting}\n\n"
            f"{intro}\n\n"
            f"{details_label}:\n{formatted_request}\n\n"
            f"{closing}\n\n"
            f"{salutation}"
        )
        return subject, body

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    @staticmethod
    def _should_pitch_provider(context: dict[str, Any] | None) -> bool:
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

        now = datetime.now(UTC)
        if last_asked.tzinfo is None:
            last_asked = last_asked.replace(tzinfo=UTC)
        return bool((now - last_asked) >= timedelta(days=30))

    async def _should_pitch_provider_async(self, context: dict[str, Any] | None) -> bool:
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
    ) -> AsyncIterator[str | dict]:
        """
        Dispatch a tool call through the registry.

        Yields the raw result dict on success, or an error dict on failure.
        The caller decides how to surface these to the client.
        """
        if self.tool_registry is None:
            yield {"error": "no_registry", "tool": name}
            return

        try:
            result = await self.tool_registry.execute(name, params, cast(ToolContext, context))
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
        pending: list[tuple[str, Any]],
        follow_up_input: str,
        session_id: str,
        context: dict[str, Any] | None,
        ai_response_parts: list[str],
        new_pending: list[tuple[str, Any]],
    ) -> AsyncIterator[str | dict]:
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

        # In lite mode (finalize_auto_advance_stage set) the FINALIZE stage is
        # purely mechanical: cards have already been sent and the auto-advance
        # guard will immediately transition to BROWSE, which generates the single
        # acknowledgement text.  Skip the FINALIZE LLM call entirely so only
        # one bubble reaches the user.
        if (
            follow_up_stage == ConversationStage.FINALIZE
            and self._profile.finalize_auto_advance_stage is not None
        ):
            logger.debug(
                "Skipping FINALIZE LLM call in lite mode — "
                "finalize_auto_advance_stage will handle the BROWSE transition."
            )
            return

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
        elif follow_up_stage == ConversationStage.BROWSE:
            self.llm_service.register_functions(
                session_id, [SIGNAL_TRANSITION_SCHEMA] + list(BROWSE_TOOL_SCHEMAS)
            )

        # ── Accumulate problem description on CONFIRMATION → TRIAGE bounce-back ──
        # When the user sends a correction from CONFIRMATION (e.g. "change the
        # location to Munich"), the main-stream body skips accumulation because
        # current_stage was CONFIRMATION.  Accumulate here so the Weaviate search
        # query used in the subsequent FINALIZE stage reflects the correction.
        # System-event wrappers (reconnection/dormant-UI buffered messages) are
        # stripped first so only the user's actual words are stored.
        if follow_up_stage == ConversationStage.TRIAGE and actual_input.strip():
            _clean_acc = _extract_user_text_from_system_event(actual_input)
            if _clean_acc and _clean_acc != " ":
                await self.conversation_service.accumulate_problem_description(_clean_acc)

        # Extract zero_result_event hint from any triage payload (set by reject_and_fetch_next
        # when the provider list is exhausted) so we can inject it into the human turn.
        _zero_event: str | None = None
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
                    if fu_name in ("accept_provider", "reject_and_fetch_next", "cancel_search", "retry_search", "generate_contact_template"):
                        await self._handle_finalize_tool(
                            fu_name, fu_args, session_id, context, new_pending
                        )
                    elif fu_name == "show_next_providers":
                        # BROWSE-stage tool in follow-up stream.
                        async for browse_chunk in self._handle_show_next_providers(
                            session_id, context, new_pending
                        ):
                            yield browse_chunk
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
                filtered = _strip_tool_call_text(_strip_markdown_formatting(chunk))
                if filtered.strip():
                    ai_response_parts.append(filtered)
                    yield filtered

    async def _handle_show_next_providers(
        self,
        session_id: str,
        context: dict[str, Any] | None,
        pending: list[tuple[str, Any]],
    ) -> AsyncGenerator[dict[str, Any]]:
        """Handle the BROWSE-stage ``show_next_providers`` tool call.

        Reads the next batch of 3 providers from ``providers_found`` starting
        at ``browse_offset``, yields a ``provider-cards`` message, advances
        the offset, and appends a follow-up payload to *pending* so the LLM
        can generate a brief narrative response.
        """
        providers: list[dict] = self.conversation_service.context.get("providers_found", [])
        offset: int = self.conversation_service.context.get("browse_offset", 3)
        batch = providers[offset:offset + 3]

        if not batch:
            pending.append(("show_next_providers", {
                "has_more": False,
                "batch_size": 0,
                "message": "No more providers available.",
            }))
            return

        cards = await self._build_provider_cards(batch, "")
        yield {"type": "provider-cards", "cards": cards}

        new_offset = offset + len(batch)
        self.conversation_service.context["browse_offset"] = new_offset
        remaining = max(0, len(providers) - new_offset)
        pending.append(("show_next_providers", {
            "has_more": remaining > 0,
            "batch_size": len(batch),
            "shown_count": new_offset,
            "total_count": len(providers),
        }))

    async def _handle_finalize_tool(
        self,
        fn_name: str,
        fn_args: dict,
        session_id: str,
        context: dict[str, Any] | None,
        pending: list[tuple[str, Any]],
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

            # GP guard: providers sourced from Google Maps do not have a
            # Linkora account — a service request cannot be created for them.
            # Instead, surface their contact details so the user can reach out
            # directly.
            accepted_provider_for_gp = next(
                (p for p in providers if p.get("user", {}).get("user_id") == provider_id),
                None,
            )
            if accepted_provider_for_gp is not None and accepted_provider_for_gp.get("source") == "google_places":
                contact_info: dict[str, str] = {}
                for _field in ("phone", "website", "address"):
                    _val = accepted_provider_for_gp.get(_field, "")
                    if _val:
                        contact_info[_field] = _val
                pending.append(("accept_provider", {
                    "error": "google_places_provider",
                    "message": "This provider is listed on Google Maps but is not registered on Linkora. They cannot be booked directly here, but you can contact them using the details below.",
                    "contact_info": contact_info,
                }))
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

            result: dict | None = None
            if self.tool_registry:
                try:
                    result = await self.tool_registry.execute(
                        "create_service_request", csr_args, cast(ToolContext, context or {})
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

        elif fn_name == "generate_contact_template":
            provider_name = fn_args.get("provider_name", "")
            request_summary = fn_args.get("request_summary", "")
            phone = fn_args.get("phone", "")
            website = fn_args.get("website", "")
            address = fn_args.get("address", "")
            logger.info(
                "generate_contact_template called for '%s' — injecting context for follow-up LLM.",
                provider_name,
            )
            template_context: dict[str, Any] = {
                "status": "contact_template_requested",
                "provider_name": provider_name,
                "request_summary": request_summary,
            }
            if phone:
                template_context["phone"] = phone
            if website:
                template_context["website"] = website
            if address:
                template_context["address"] = address
            pending.append(("generate_contact_template", template_context))

        elif fn_name == "retry_search":
            logger.info("retry_search called — clearing provider cache and re-running search.")
            # Clear the cached result set so the orchestrator performs a fresh query.
            self.conversation_service.context["providers_found"] = []
            self.conversation_service.context["current_provider_index"] = 0
            await self.conversation_service.search_providers_for_request(session_id)
            if self.conversation_service.context.pop("search_error", None) == "unavailable":
                logger.warning("retry_search: Weaviate unavailable — diverting to RECOVERY.")
                self.conversation_service.context["search_outage_pending"] = True
                self.conversation_service.context["search_failure_count"] = (
                    self.conversation_service.context.get("search_failure_count", 0) + 1
                )
                self.handle_signal_transition("recovery")
                pending.append(("signal_transition", {"stage": "recovery"}))
                return
            # Successful retry search: clear outage flags/counters.
            self.conversation_service.context.pop("search_outage_pending", None)
            self.conversation_service.context.pop("search_failure_count", None)
            fresh_providers = self.conversation_service.context.get("providers_found", [])
            if not fresh_providers:
                logger.info("retry_search: zero results — returning to TRIAGE.")
                await self._apply_signal_transition_with_payload(
                    "triage", session_id, context, pending, user_input=""
                )
                for _, ppayload in pending:
                    if (
                        isinstance(ppayload, dict)
                        and ppayload.get("stage") == "triage"
                        and "zero_result_event" not in ppayload
                    ):
                        ppayload["zero_result_event"] = (
                            "The search found no matching providers this time either. "
                            "Apologise briefly and invite the user to adjust their criteria."
                        )
                        break
            else:
                # Reset cursor and present the first result from the fresh list.
                self.conversation_service.context["current_provider_index"] = 0
                pending.append(("retry_search", {
                    "status": "results_refreshed",
                    "current_provider": fresh_providers[0],
                }))

    async def generate_response_stream(
        self,
        user_input: str,
        session_id: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[str | dict[str, Any]]:
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
            # In FINALIZE, restrict the LLM to only the FINALIZE tools so it
            # cannot call signal_transition, create_service_request, etc.
            # In BROWSE, offer signal_transition + show_next_providers only.
            if current_stage == ConversationStage.FINALIZE:
                tool_schemas = list(FINALIZE_TOOL_SCHEMAS)
            elif current_stage == ConversationStage.BROWSE:
                tool_schemas = [SIGNAL_TRANSITION_SCHEMA] + list(BROWSE_TOOL_SCHEMAS)
            else:
                tool_schemas = [SIGNAL_TRANSITION_SCHEMA]
                if self.tool_registry:
                    tool_schemas += self.tool_registry.all_schemas()
            self.llm_service.register_functions(session_id, tool_schemas)

            logger.debug(
                "Generating response for '%s...' [Stage: %s]",
                user_input[:50], current_stage,
            )

            # ── CONFIRMATION stuck-stage diagnostic counter ─────────────────────
            # Track how many consecutive turns the conversation has been in
            # CONFIRMATION without calling a transition tool.  A count > 1 with no
            # tool call means the LLM re-generated the summary instead of routing.
            if current_stage == ConversationStage.CONFIRMATION:
                self.conversation_service.context["confirmation_turns"] = (
                    self.conversation_service.context.get("confirmation_turns", 0) + 1
                )

            # Persist the user turn (fire-and-forget — don't block LLM start)
            if self.ai_conversation_service:
                asyncio.create_task(
                    self.ai_conversation_service.save_message(
                        role="user", text=user_input, stage=current_stage
                    )
                )

            # Accumulate problem description only during triage.
            # Strip any system-event wrapper (e.g. '[System Event: ... "msg"]')
            # before accumulating so buffered-message prefixes don't pollute the
            # Weaviate search query used in FINALIZE.
            if current_stage == ConversationStage.TRIAGE:
                clean_input = _extract_user_text_from_system_event(user_input)
                if clean_input:
                    await self.conversation_service.accumulate_problem_description(clean_input)

            # Pre-fetch competencies for ongoing PROVIDER_ONBOARDING turns so the
            # stage prompt always has the up-to-date list without the LLM calling
            # get_my_competencies.  (Freshly transitioned sessions are handled by
            # _apply_signal_transition_with_payload.)
            if current_stage == ConversationStage.PROVIDER_ONBOARDING and self.tool_registry:
                try:
                    competencies = await self.tool_registry.execute(
                        "get_my_competencies", {}, cast(ToolContext, context or {})
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
            tool_calls_seen = False  # True when ≥1 tool/signal was dispatched
            # In TRIAGE, the LLM may emit preamble text before calling
            # signal_transition — violating the single-acknowledgement rule.
            # Buffer text chunks while in TRIAGE and only flush them after the
            # main stream ends without a transition.  If a signal_transition fires,
            # discard the buffer so only the follow-up stage (CONFIRMATION) speaks.
            _triage_text_buffer: list[str] = []
            _triage_transition_fired = False

            async for chunk in self.llm_service.generate_stream(
                user_input, prompt_template, session_id
            ):
                if first_chunk:
                    self.runtime_fsm.transition("llm_stream_started")
                    first_chunk = False
                    # Clear first-message flag on the first successful LLM chunk so
                    # retries see the same greeting intent but the next distinct turn
                    # doesn't re-greet.  Only relevant for TRIAGE.
                    if current_stage == ConversationStage.TRIAGE:
                        self.conversation_service.context.pop("is_first_message", None)

                if isinstance(chunk, dict) and chunk.get("type") == "function_call":
                    fn_name = chunk.get("name", "")
                    fn_args = chunk.get("args", {})

                    if fn_name == "signal_transition":
                        self.runtime_fsm.transition("tool_call")
                        tool_calls_seen = True
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
                        # If TRIAGE generated preamble text before this transition,
                        # discard it — the follow-up stage will speak for itself.
                        if current_stage == ConversationStage.TRIAGE and _triage_text_buffer:
                            logger.debug(
                                "Suppressing %d TRIAGE text chunk(s) — "
                                "signal_transition fired in same turn.",
                                len(_triage_text_buffer),
                            )
                            for discarded in _triage_text_buffer:
                                # Remove from response parts so history is accurate.
                                try:
                                    ai_response_parts.remove(discarded)
                                except ValueError:
                                    pass
                            _triage_text_buffer.clear()
                            _triage_transition_fired = True

                    else:
                        # Notify the client which tool is running so the UI can
                        # show a descriptive status label instead of just "...".
                        yield {"type": "tool-status", "label": _TOOL_STATUS_LABELS.get(fn_name, "Working")}

                        # FINALIZE-stage tools are intercepted here and never
                        # dispatched through the registry.
                        tool_result = None
                        if fn_name in ("accept_provider", "reject_and_fetch_next", "cancel_search", "retry_search"):
                            self.runtime_fsm.transition("tool_call")
                            tool_calls_seen = True
                            await self._handle_finalize_tool(
                                fn_name, fn_args, session_id, context, pending_tool_results
                            )
                            self.runtime_fsm.transition("tool_done")

                        elif fn_name == "show_next_providers":
                            # BROWSE-stage tool: yield the next batch of provider cards.
                            self.runtime_fsm.transition("tool_call")
                            tool_calls_seen = True
                            async for browse_chunk in self._handle_show_next_providers(
                                session_id, context, pending_tool_results
                            ):
                                yield browse_chunk
                            self.runtime_fsm.transition("tool_done")

                        else:
                        # Regular tool call
                        # Guard: search_providers is redundant in FINALIZE when
                        # the auto-search already ran and found results.  If the
                        # cache is empty the first search may have been interrupted
                        # or used stale Weaviate data — re-fetch so a repaired
                        # dataset is picked up on the next turn.
                            self.runtime_fsm.transition("tool_call")
                            tool_calls_seen = True
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
                                    # Yield provider cards for GP results before the follow-up narrative
                                    _gp = [
                                        p for p in tool_result
                                        if (p.get("user") or {}).get("source") == "google_places"
                                    ][:3]  # cap at top 3
                                    if _gp:
                                        _cards = await self._build_provider_cards(_gp, user_input)
                                        yield {"type": "provider-cards", "cards": _cards}
                                # Sync in-memory user_context after provider pitch response so
                                # _should_pitch_provider won't re-fire when stage hits COMPLETED.
                                if fn_name == "record_provider_interest" and isinstance(tool_result, dict):
                                    status = tool_result.get("status")
                                    if context and "user_context" in context:
                                        from datetime import datetime as _dt
                                        from ..firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL
                                        if status == "never":
                                            context["user_context"]["last_time_asked_being_provider"] = PROVIDER_PITCH_OPT_OUT_SENTINEL
                                        elif status in ("not_now", "accepted"):
                                            context["user_context"]["last_time_asked_being_provider"] = _dt.now(UTC)
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
                                            "get_my_competencies", {}, cast(ToolContext, context or {})
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
                    # Plain text chunk — strip markdown first, then leaked tool-call patterns.
                    # Markdown is stripped first so that tool-call names wrapped in emphasis
                    # markers (e.g. "**signal_transition(...)**") are cleaned up in one pass
                    # rather than leaving bare delimiters behind.
                    md_stripped = _strip_markdown_formatting(chunk) if isinstance(chunk, str) else chunk
                    filtered = _strip_tool_call_text(md_stripped) if isinstance(md_stripped, str) else md_stripped
                    if filtered.strip() if isinstance(filtered, str) else filtered:
                        ai_response_parts.append(filtered)
                        # In TRIAGE, buffer text rather than yielding immediately.
                        # If a signal_transition fires in this same turn the buffer
                        # is discarded above, suppressing the preamble.
                        if current_stage == ConversationStage.TRIAGE and not _triage_transition_fired:
                            _triage_text_buffer.append(filtered)
                        else:
                            yield filtered
                    elif isinstance(chunk, str) and chunk.strip() and not (filtered.strip() if isinstance(filtered, str) else filtered) and (md_stripped.strip() if isinstance(md_stripped, str) else md_stripped):
                        # The chunk had content but was entirely removed by tool-call
                        # stripping (not markdown stripping).  Count it as an intentional
                        # signal so the empty-response fallback is not triggered.
                        tool_calls_seen = True

            # Flush any buffered TRIAGE text — only reached when no transition fired.
            for buffered_chunk in _triage_text_buffer:
                yield buffered_chunk
            _triage_text_buffer.clear()

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
                next_pending: list[tuple[str, Any]] = []
                # Only the first follow-up stream sees the real user utterance.
                follow_up_user_input = user_input if follow_up_iter == 0 else " "
                # Yield provider cards before the follow-up narrative whenever a
                # finalize transition is pending.  The guard is NOT limited to
                # follow_up_iter==0 because in the TRIAGE→CONFIRMATION→FINALIZE
                # path the finalize transition arrives at iter 1 (TRIAGE→CONFIRMATION
                # happens in the main stream; CONFIRMATION→FINALIZE happens inside
                # the first follow-up stream and lands in next_pending, which
                # becomes current_pending at iter 1).
                _has_finalize_transition = any(
                    name == "signal_transition"
                    and isinstance(res, dict)
                    and res.get("stage") == "finalize"
                    for name, res in current_pending
                )
                if _has_finalize_transition:
                    _providers = self.conversation_service.context.get("providers_found", [])
                    _gp_for_finalize = [
                        p for p in _providers
                        if (p.get("user") or {}).get("source") == "google_places"
                    ][:3]  # cap at top 3
                    if _gp_for_finalize:
                        _finalize_cards = await self._build_provider_cards(
                            _gp_for_finalize, user_input
                        )
                        yield {"type": "provider-cards", "cards": _finalize_cards}
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

            # ── Stuck-stage diagnostic: CONFIRMATION loop guard ──────────────────
            # If CONFIRMATION generated text on the second (or later) user turn
            # without calling any transition tool, the LLM ignored the Decision Gate
            # and re-summarised.  Log a warning so it surfaces in the backend logs.
            _conf_turns = self.conversation_service.context.get("confirmation_turns", 0)
            if (
                current_stage == ConversationStage.CONFIRMATION
                and _conf_turns > 1
                and not tool_calls_seen
            ):
                logger.warning(
                    "CONFIRMATION stuck-stage: turn %d produced text without a "
                    "signal_transition — LLM likely ignored the Decision Gate.",
                    _conf_turns,
                )

            # ── Safety fallback: stuck-in-FINALIZE guard ─────────────────────────
            # FINALIZE is a user-driven decision stage — the LLM awaits explicit
            # accept/reject/cancel input.  Forcing RECOVERY here would discard the
            # provider presentation mid-flow.  The fallback is therefore disabled:
            # the stage will persist until the next user utterance triggers one of
            # the three FINALIZE tools.  (§3.2)
            #
            # Exception: lite mode (finalize_auto_advance_stage is not None).  After
            # presenting the initial provider cards the orchestrator auto-transitions
            # to the configured target stage (BROWSE) without waiting for user input.  (§14.3)
            if (
                self._profile.finalize_auto_advance_stage is not None
                and self.conversation_service.get_current_stage() == ConversationStage.FINALIZE
            ):
                _auto_target = self._profile.finalize_auto_advance_stage
                logger.info(
                    "finalize_auto_advance_stage: auto-advancing FINALIZE → %s",
                    _auto_target.value,
                )
                auto_pending: list[tuple[str, Any]] = []
                await self._apply_signal_transition_with_payload(
                    _auto_target.value, session_id, context, auto_pending, user_input=""
                )
                if auto_pending:
                    async for chunk in self._run_follow_up_stream(
                        auto_pending, " ", session_id, context, ai_response_parts, []
                    ):
                        yield chunk

            # ── Stream complete ──────────────────────────────────────────────────
            ai_text = "".join(ai_response_parts)

            # Safety net: if the entire orchestration produced no visible text
            # (e.g. the LLM exhausted its token budget on thinking tokens and
            # emitted nothing, or a transient Gemini API empty-stream), yield a
            # generic fallback so the user is not left in complete silence.
            # Exception: pure tool-call streams (signal_transition, registry
            # tools) legitimately produce no text — do NOT fall back in that case.
            if not ai_text.strip() and not tool_calls_seen:
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
