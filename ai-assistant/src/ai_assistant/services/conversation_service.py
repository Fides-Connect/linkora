"""
Conversation Service
Handles conversation flow, stage management, and orchestration.
"""
import logging
import json
import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from datetime import datetime
from typing import Any, TYPE_CHECKING
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.messages import HumanMessage

if TYPE_CHECKING:
    from .google_places_service import GooglePlacesService
    from .agent_profile import AgentProfile

from ..data_provider import DataProvider, SearchUnavailableError
from ..prompts_templates import (
    GREETING_AND_TRIAGE_PROMPT,
    TRIAGE_CONVERSATION_PROMPT,
    FINALIZE_SERVICE_REQUEST_PROMPT,
    CLARIFY_PROMPT,
    CONFIRMATION_PROMPT,
    RECOVERY_PROMPT,
    LOOP_BACK_PROMPT,
    PROVIDER_PITCH_PROMPT,
    PROVIDER_ONBOARDING_PROMPT,
    get_language_instruction,
    get_greeting_fallback,
    get_prompt,
)
from .cross_encoder_service import CrossEncoderService
from .llm_service import LLMService


logger = logging.getLogger(__name__)


@dataclass
class GpResult:
    """Outcome of a single GP pipeline run inside search_providers_for_request."""
    providers_written: int = 0   # number of GP nodes written to Weaviate
    error: bool = False          # True when GP tried but failed
    query: str = ""              # Places query string used (empty on LLM skip)
    duration_ms: int = 0         # wall-clock time for fetch_and_ingest()
    error_code: str = ""         # e.g. "rate_limited", "timeout", "llm_skip"


def json_serializer(obj: object) -> str:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class ConversationStage(StrEnum):
    """External conversation stage — owned exclusively by ResponseOrchestrator."""
    GREETING      = "greeting"
    TRIAGE        = "triage"
    CLARIFY       = "clarify"
    TOOL_EXECUTION = "tool_execution"
    CONFIRMATION  = "confirmation"
    FINALIZE      = "finalize"
    RECOVERY      = "recovery"
    COMPLETED     = "completed"
    PROVIDER_PITCH      = "provider_pitch"
    PROVIDER_ONBOARDING = "provider_onboarding"


# Legal stage transitions: { from_stage: { allowed_to_stages } }
_LEGAL_TRANSITIONS: dict[ConversationStage, list[ConversationStage]] = {
    ConversationStage.GREETING:       [ConversationStage.TRIAGE],
    ConversationStage.TRIAGE:         [ConversationStage.CONFIRMATION, ConversationStage.CLARIFY,
                                       ConversationStage.TOOL_EXECUTION, ConversationStage.RECOVERY,
                                       ConversationStage.PROVIDER_ONBOARDING],
    ConversationStage.CLARIFY:        [ConversationStage.TRIAGE],
    ConversationStage.TOOL_EXECUTION: [ConversationStage.TRIAGE, ConversationStage.CONFIRMATION,
                                       ConversationStage.FINALIZE],
    ConversationStage.CONFIRMATION:   [ConversationStage.FINALIZE, ConversationStage.TRIAGE],
    ConversationStage.FINALIZE:       [ConversationStage.COMPLETED, ConversationStage.RECOVERY, ConversationStage.TRIAGE],
    ConversationStage.RECOVERY:       [ConversationStage.TRIAGE],
    ConversationStage.COMPLETED:      [ConversationStage.PROVIDER_PITCH, ConversationStage.TRIAGE],
    ConversationStage.PROVIDER_PITCH: [ConversationStage.PROVIDER_ONBOARDING, ConversationStage.COMPLETED,
                                       ConversationStage.TRIAGE],
    ConversationStage.PROVIDER_ONBOARDING: [ConversationStage.COMPLETED, ConversationStage.TRIAGE],
}


def is_legal_transition(from_stage: ConversationStage, to_stage: ConversationStage) -> bool:
    """
    Return True when transitioning from_stage → to_stage is allowed.
    Used by ResponseOrchestrator to guard signal_transition() calls.
    """
    return to_stage in _LEGAL_TRANSITIONS.get(from_stage, [])


class ConversationService:
    """Service for managing conversation flow and state."""

    def __init__(self, llm_service: LLMService, data_provider: DataProvider,
                 agent_name: str = "Elin", company_name: str = "Linkora",
                 max_providers: int = 5, language: str = 'de',
                 cross_encoder_service: CrossEncoderService | None = None,
                 google_places_service: "GooglePlacesService | None" = None,
                 profile: "AgentProfile | None" = None) -> None:
        """
        Initialize Conversation service.

        Args:
            llm_service: LLM service instance
            data_provider: Data provider instance
            agent_name: Name of the AI agent
            company_name: Company name
            max_providers: Maximum number of providers to present
            language: Language code ('de' or 'en')
            cross_encoder_service: Optional cross-encoder reranker.  When
                provided, providers returned by Weaviate are reranked before
                being stored in ``context["providers_found"]``.
            google_places_service: Optional Google Places service.  When
                provided and the profile has ``google_places_always_active=True``,
                GP results are fetched and upserted before the Weaviate search.
            profile: Agent capability profile.  Defaults to ``FULL_PROFILE`` when
                ``None``.
        """
        from .agent_profile import FULL_PROFILE

        self.llm_service = llm_service
        self.data_provider = data_provider
        self.agent_name = agent_name
        self.company_name = company_name
        self.max_providers = max_providers
        self.language = language
        self.cross_encoder_service = cross_encoder_service
        self.google_places_service = google_places_service
        self._profile = profile if profile is not None else FULL_PROFILE

        self.current_stage: ConversationStage = ConversationStage.GREETING
        self.context: dict[str, Any] = {
            "user_problem": [],
            "ai_responses": [],
            "request_summary": "",
            "providers_found": [],
            "current_provider_index": 0,
            "user_name": "",
            "has_open_request": False,
            # Holds partial skill data during PROVIDER_ONBOARDING (in-memory MVP).
            # List of dicts, each representing one competence being assembled.
            "onboarding_draft": [],
            # Holds the fetched competencies for PROVIDER_ONBOARDING.
            # Populated by ResponseOrchestrator before each LLM call in that stage;
            # refreshed after every successful write tool.
            "current_competencies": [],
            # Mirrored from user_context by ResponseOrchestrator on every
            # PROVIDER_ONBOARDING turn so the prompt can render STEP 0 correctly.
            "is_service_provider": False,
            # Google Places integration flags (reset per FINALIZE session)
            "google_places_used": False,
            "google_places_error": False,
            "google_places_announced": False,
        }

        logger.info("Conversation service initialized: agent=%s, company=%s", agent_name, company_name)

    def get_current_stage(self) -> ConversationStage:
        """Get current conversation stage."""
        return self.current_stage

    def set_stage(self, stage: ConversationStage) -> None:
        """
        Set conversation stage.

        Args:
            stage: New stage to set
        """
        logger.info("Stage transition: %s -> %s", self.current_stage, stage)
        self.current_stage = stage

    def create_prompt_for_stage(self, stage: ConversationStage) -> ChatPromptTemplate:
        """
        Create appropriate prompt template based on conversation stage.

        Args:
            stage: Conversation stage

        Returns:
            ChatPromptTemplate for the stage
        """
        if stage == ConversationStage.GREETING:
            # B2: Pass any unsupported-language fallback note on the first turn only,
            # then clear it so subsequent prompts don't repeat it.
            fallback_from = self.context.pop("language_fallback_from", "")
            language_instruction = get_language_instruction(self.language, fallback_from=fallback_from)
            user_name = self.context.get("user_name", "")
            has_open_request = "Yes" if self.context.get("has_open_request", False) else "No"
            prompt_str = get_prompt(self._profile.prompt_key, stage)
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(prompt_str).format(
                    agent_name=self.agent_name,
                    company_name=self.company_name,
                    user_name=user_name,
                    has_open_request=has_open_request,
                    language_instruction=language_instruction
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.TRIAGE:
            user_name = self.context.get("user_name", "")
            language_instruction = get_language_instruction(self.language)
            # GP enabled: location becomes mandatory — inject the MRI instruction.
            gp_active = (
                self._profile.google_places_always_active
                and self.google_places_service is not None
            )
            location_mri_instruction = (
                "IMPORTANT: Location is a MANDATORY requirement before you may proceed to "
                "CONFIRMATION. You MUST ask for a city or region before any other "
                "extended-context field. Do not call "
                'signal_transition(target_stage=\"confirmation\") until the user has '
                "provided a location."
                if gp_active else ""
            )
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(get_prompt(self._profile.prompt_key, stage)).format(
                    agent_name=self.agent_name,
                    user_name=user_name,
                    language_instruction=language_instruction,
                    location_mri_instruction=location_mri_instruction,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.FINALIZE:
            providers = self.context.get("providers_found", [])
            idx = self.context.get("current_provider_index", 0)
            current_provider = providers[idx] if providers and idx < len(providers) else {}
            provider_json = json.dumps(current_provider, ensure_ascii=False, default=json_serializer)
            language_instruction = get_language_instruction(self.language)
            language_name = "German" if self.language == "de" else "English"

            # GP announcement — controls first-entry vs. already-announced behaviour
            gp_active = (
                self._profile.google_places_always_active
                and self.google_places_service is not None
            )
            gp_used = self.context.get("google_places_used", False)
            gp_error = self.context.get("google_places_error", False)
            gp_announced = self.context.get("google_places_announced", False)

            if not gp_active:
                google_places_announcement = ""
            elif gp_error:
                google_places_announcement = (
                    "The Google Maps search was temporarily unavailable. "
                    "Briefly inform the user (once only) that results are sourced from "
                    "registered providers only."
                )
            elif gp_used and not gp_announced:
                google_places_announcement = (
                    "Begin your response with a single natural sentence informing the user "
                    "that you are also searching Google Maps for nearby providers — "
                    "exactly once."
                )
                self.context["google_places_announced"] = True
            elif gp_used and gp_announced:
                google_places_announcement = (
                    "NOTE: You already informed the user at the start of this FINALIZE "
                    "session that you also searched Google Maps. "
                    "Do NOT repeat this announcement."
                )
            else:
                google_places_announcement = ""

            contact_template_instruction = (
                f"CONTACT TEMPLATE:\n"
                f"If the user explicitly asks you to write a contact message or email "
                f"template for the currently presented provider, call "
                f"generate_contact_template() immediately.\n"
                f"Never generate a contact template unprompted.\n"
                f"Do NOT narrate the tool call or announce that you are generating a "
                f"template — the tool execution is silent. Your next response after the "
                f"tool result IS the template itself, written directly in {language_name}."
            )

            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(get_prompt(self._profile.prompt_key, stage)).format(
                    agent_name=self.agent_name,
                    provider_json=provider_json,
                    language_instruction=language_instruction,
                    google_places_announcement=google_places_announcement,
                    contact_template_instruction=contact_template_instruction,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage in (
            ConversationStage.CLARIFY,
            ConversationStage.TOOL_EXECUTION,
            ConversationStage.CONFIRMATION,
            ConversationStage.RECOVERY,
        ):
            # Resolve prompt template string via profile key.
            # TOOL_EXECUTION falls back to "triage" when not in the profile's prompt set.
            _stage_key = str(stage)
            try:
                template_str = get_prompt(self._profile.prompt_key, _stage_key)
            except KeyError:
                # Lite profile has no tool_execution entry — fall back to triage
                template_str = get_prompt(self._profile.prompt_key, "triage")

            # Determine whether this template needs TRIAGE-level format args.
            # We detect this by checking whether the template string references
            # {location_mri_instruction} which only triage-style templates use.
            _is_triage_template = "{location_mri_instruction}" in template_str
            fmt_kwargs: dict = {"agent_name": self.agent_name}
            if _is_triage_template:
                fmt_kwargs["user_name"] = self.context.get("user_name", "")
                fmt_kwargs["language_instruction"] = get_language_instruction(self.language)
                # GP flag: pass empty or active MRI instruction
                gp_active = (
                    self._profile.google_places_always_active
                    and self.google_places_service is not None
                )
                fmt_kwargs["location_mri_instruction"] = (
                    "IMPORTANT: Location is a MANDATORY requirement before you may proceed to "
                    "CONFIRMATION. You MUST ask for a city or region before any other "
                    "extended-context field. Do not call "
                    'signal_transition(target_stage=\"confirmation\") until the user has '
                    "provided a location."
                    if gp_active else ""
                )
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(template_str).format(
                    **fmt_kwargs
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.PROVIDER_PITCH:
            language_instruction = get_language_instruction(self.language)
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(get_prompt(self._profile.prompt_key, stage)).format(
                    agent_name=self.agent_name,
                    language_instruction=language_instruction,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.PROVIDER_ONBOARDING:
            language_instruction = get_language_instruction(self.language)
            current_competencies_json = json.dumps(
                self.context.get("current_competencies", []),
                ensure_ascii=False,
                default=json_serializer,
            )
            draft_invalidated = self.context.pop("onboarding_draft_invalidated", False)
            draft_invalidated_notice = (
                "\n**NOTICE:** Your competency list was updated from another session "
                "since this conversation started. The previous draft has been discarded "
                "and the list above reflects the current saved state. "
                "Inform the user briefly before continuing.\n"
                if draft_invalidated
                else ""
            )
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(get_prompt(self._profile.prompt_key, stage)).format(
                    agent_name=self.agent_name,
                    language_instruction=language_instruction,
                    current_competencies_json=current_competencies_json,
                    is_service_provider=self.context.get("is_service_provider", False),
                    draft_invalidated_notice=draft_invalidated_notice,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.COMPLETED:
            language_instruction = get_language_instruction(self.language)
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(get_prompt(self._profile.prompt_key, stage)).format(
                    agent_name=self.agent_name,
                    language_instruction=language_instruction,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        else:
            # Default to triage
            return self.create_prompt_for_stage(ConversationStage.TRIAGE)

    async def accumulate_problem_description(self, user_input: str) -> None:
        """Accumulate user's problem description during TRIAGE.

        Note: Provider search is performed in FINALIZE stage via
        search_providers_for_request().
        """
        self.context["user_problem"].append(user_input)

    def reset_request_context(self) -> None:
        """Clear per-request fields so a new scoping conversation starts clean.

        Called when looping back from COMPLETED → TRIAGE so the new request
        scope does not bleed into the previous one. Preserves user_name,
        has_open_request, and onboarding_draft.
        """
        self.context["user_problem"] = []
        self.context["ai_responses"] = []
        self.context["request_summary"] = ""
        self.context["providers_found"] = []
        self.context["current_provider_index"] = 0
        self.context["google_places_used"] = False
        self.context["google_places_error"] = False
        self.context["google_places_announced"] = False
        # onboarding_draft and current_competencies are preserved across request
        # resets so a PROVIDER_ONBOARDING session isn't interrupted mid-flow.
        logger.info("Request context reset for new TRIAGE scoping session")

    def restore_from_summary(self, summary: dict) -> None:
        """Hydrate conversation context from a previous session summary.

        Seeds the context with the prior request summary and topic title so the
        LLM has the necessary background on session connect.  Only restores the
        stage when the prior final_stage is an auto-resumable mid-flow stage
        (TRIAGE, CLARIFY, CONFIRMATION).  Terminal stages are ignored — the
        session boots fresh from GREETING/TRIAGE instead.

        Assigns to ``self.current_stage`` directly (bypasses legal-transition
        FSM) since this is a restore, not a runtime transition.
        """
        _MID_FLOW_STAGES = {
            ConversationStage.TRIAGE,
            ConversationStage.CLARIFY,
            ConversationStage.CONFIRMATION,
        }
        final_stage = summary.get("final_stage")
        topic_title = summary.get("topic_title", "")
        request_summary_text = summary.get("request_summary", "")

        if request_summary_text:
            self.context["request_summary"] = request_summary_text
        if topic_title:
            self.context["user_problem"] = [topic_title]

        if isinstance(final_stage, ConversationStage) and final_stage in _MID_FLOW_STAGES:
            self.current_stage = final_stage
            logger.info("Session restored to stage %s from previous session summary", final_stage)
        else:
            logger.info(
                "Session summary present but stage %s is terminal — booting fresh.", final_stage
            )

    def record_ai_response(self, text: str) -> None:
        """Append an assembled AI response to the context history.

        Called by ResponseOrchestrator at the end of each generate_response_stream()
        so get_problem_summary() returns the LLM's confirmed job summary instead
        of raw joined user inputs.
        """
        if text.strip():
            self.context["ai_responses"].append(text)

    def get_problem_summary(self) -> str:
        """Return the most recent AI response as the job summary.

        Falls back to raw joined user inputs when no AI responses have been
        recorded yet (e.g., first turn or session reset).
        """
        ai_responses = self.context.get("ai_responses", [])
        if ai_responses:
            return str(ai_responses[-1])
        return " ".join(self.context["user_problem"])

    def _clean_json_response(self, json_str: str) -> str:
        """Clean up JSON response by removing markdown code blocks."""
        json_str = json_str.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        return json_str.strip()

    async def _generate_structured_query(
        self, problem_summary: str, session_id: str = ""
    ) -> str:
        """Generate structured JSON query from the problem summary.

        Passes the last 3 messages from conversation history (when a
        session_id is provided) alongside the summary so the LLM has
        richer context for field extraction.

        Returns:
            JSON string of structured query, or original summary on error.
        """
        from ..prompts_templates import STRUCTURED_QUERY_EXTRACTION_PROMPT

        # Build conversation excerpt — last 6 messages from LLM history.
        # Using 6 instead of 3 ensures early-conversation context (e.g. a
        # location mentioned by the user several turns ago) is not lost when
        # extraction fires late in the flow at FINALIZE.
        history_excerpt = ""
        if session_id:
            messages = self.llm_service.get_session_history(session_id).messages
            recent = messages[-6:] if len(messages) >= 6 else messages
            if recent:
                lines = []
                for msg in recent:
                    role = "User" if msg.type == "human" else "Assistant"
                    lines.append(f"{role}: {msg.content}")
                history_excerpt = "\n".join(lines)

        language_instruction = get_language_instruction(self.language)
        extraction_prompt = STRUCTURED_QUERY_EXTRACTION_PROMPT.format(
            problem_summary=problem_summary,
            history_excerpt=history_excerpt,
            language_instruction=language_instruction,
        )

        try:
            json_response = await self.llm_service.generate(
                [HumanMessage(content=extraction_prompt)]
            )
            json_str = self._clean_json_response(json_response)
            structured_query = json.loads(json_str)
            logger.info(
                "Generated structured query: %s",
                json.dumps(structured_query, ensure_ascii=False),
            )
            return json.dumps(structured_query, ensure_ascii=False)
        except Exception as exc:
            logger.error("Error generating structured query: %s", exc, exc_info=True)
            logger.info("Falling back to original summary for search")
            return problem_summary

    async def _generate_hyde_text(self, problem_summary: str) -> str:
        """Generate a hypothetical provider profile (HyDE) from the problem summary.

        Calls the LLM with ``HYDE_GENERATION_PROMPT`` to produce a short
        prose description of a *perfect* service provider for the user's need.
        The resulting text is used as the Weaviate vector query to bridge the
        vocabulary gap between user language and stored competency bios.

        Args:
            problem_summary: Plain-language description of the user's request.

        Returns:
            Hypothetical provider profile string, or empty string on error.
        """
        from ..prompts_templates import HYDE_GENERATION_PROMPT

        try:
            hyde_prompt = HYDE_GENERATION_PROMPT.format(problem_summary=problem_summary)
            hyde_text = await self.llm_service.generate(
                [HumanMessage(content=hyde_prompt)]
            )
            hyde_text = hyde_text.strip()
            logger.info("Generated HyDE profile (%d chars): '%s...'" , len(hyde_text), hyde_text[:80])
            return hyde_text
        except Exception as exc:
            logger.error("Error generating HyDE text: %s", exc, exc_info=True)
            return ""

    async def search_providers_for_request(self, session_id: str = "") -> None:
        """Search for providers based on the confirmed TRIAGE summary.

        Multi-stage retrieval pipeline:

        1. **Structured query extraction** — LLM parses the problem summary
           into ``{available_time, category, criterions}`` JSON for hard
           filters and BM25 matching.
        2. **HyDE** — LLM writes a hypothetical provider profile that bridges
           the vocabulary gap between the user's language and stored bios.  The
           profile is used as the Weaviate vector query.
        3. **Wide-net hybrid retrieval** — Weaviate returns up to 25 candidates
           using both vector (HyDE) and BM25 (structured fields) signals.
        4. **Cross-encoder reranking** — if a ``CrossEncoderService`` is
           injected, it rescores each candidate against the original problem
           summary using a joint (query, document) encoder, returning the top
           ``max_providers`` most relevant results.

        Args:
            session_id: Active LLM session — last 3 history messages are
                        included in the extraction prompt for richer context.
        """
        problem_summary = self.get_problem_summary()
        logger.info(
            "Starting multi-stage provider search from summary: '%s...'",
            problem_summary[:100],
        )

        # Stage 1+2: structured query extraction and HyDE run concurrently.
        structured_query_task = asyncio.create_task(
            self._generate_structured_query(problem_summary, session_id)
        )
        hyde_task = asyncio.create_task(
            self._generate_hyde_text(problem_summary)
        )
        query_text, hyde_text = await asyncio.gather(structured_query_task, hyde_task)

        self.context["request_summary"] = query_text

        # Stage 2 (GP): fetch & ingest Google Places providers while the
        # Weaviate hot path is reading the index.  GP writes happen before
        # the Weaviate read so new nodes are visible in Stage 3.
        gp_active = (
            self._profile.google_places_always_active
            and self.google_places_service is not None
        )
        if gp_active:
            gp_result = await self._run_gp_pipeline(
                self.google_places_service,  # type: ignore[arg-type]
                query_text=query_text,
                hyde_text=hyde_text,
            )
            self.context["google_places_used"] = gp_result.providers_written > 0
            self.context["google_places_error"] = gp_result.error
            if gp_result.error:
                logger.warning(
                    "GP pipeline error (%s): %s",
                    gp_result.error_code,
                    gp_result.error,
                )

        # Stage 3: wide-net retrieval — now includes any freshly upserted GP
        # nodes.  Pass max_providers directly; HubSpokeSearch applies its own
        # expansion internally.
        try:
            providers = await self.data_provider.search_providers(
                query_text=query_text,
                limit=self.max_providers,
                hyde_text=hyde_text,
            )
        except SearchUnavailableError as exc:
            logger.warning(
                "Search index unreachable during provider search — routing to RECOVERY. (%s)", exc
            )
            self.context["search_error"] = "unavailable"
            return

        # Stage 4: cross-encoder reranking.
        if self.cross_encoder_service and providers:
            logger.info(
                "Reranking %d candidates with cross-encoder (top %d)...",
                len(providers),
                self.max_providers,
            )
            providers = await self.cross_encoder_service.rerank(
                query=hyde_text,
                candidates=providers,
                top_k=self.max_providers,
            )
        else:
            providers = providers[: self.max_providers]

        # Stage 5 (lite mode only): restrict the final result set to Google
        # Places-sourced providers.  Skipped when GP encountered an error so
        # the degradation path (§2.7) can still return internal-index results.
        if self._profile.google_places_always_active and not self.context.get("google_places_error"):
            providers = [
                p for p in providers
                if p.get("user", {}).get("source") == "google_places"
            ]
            logger.info(
                "Lite mode: GP-source filter applied — %d Google Places results remain",
                len(providers),
            )

        self.context["providers_found"] = providers
        logger.info("Provider search complete — %d results", len(providers))

    # ------------------------------------------------------------------
    # GP pipeline helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_location(query_text: str) -> str:
        """Return the ``location`` field from a structured-query JSON string.

        ``query_text`` is either the raw JSON produced by
        ``_generate_structured_query`` or a plain-text fallback.  Returns an
        empty string when missing or when parsing fails.
        """
        import json as _json
        try:
            data = _json.loads(query_text)
            return str(data.get("location", "") or "")
        except Exception:
            return ""

    async def _run_gp_pipeline(
        self,
        gp_service: "GooglePlacesService",
        query_text: str,
        hyde_text: str,
    ) -> "GpResult":
        """Drive the Google Places enrichment phase (Stage 2).

        1. Generates a Places search phrase via the LLM.
        2. Fetches up to 5 places from the Places API.
        3. Upserts each place as a User+Competence node in Weaviate.

        Returns a :class:`GpResult` describing what happened.
        """
        location = self._extract_location(query_text)
        try:
            query = await gp_service.generate_query(
                structured_query=query_text,
                hyde_text=hyde_text,
                location=location,
            )
            if not query:
                logger.info("GP pipeline skipped: generate_query returned None.")
                return GpResult(providers_written=0, error=False, error_code="llm_skip")
            gp_result = await gp_service.fetch_and_ingest(query)
            # fetch_and_ingest returns a GpResult from google_places_service;
            # re-wrap into the local GpResult to keep types consistent.
            return GpResult(
                providers_written=gp_result.providers_written,
                error=bool(gp_result.error),
                query=gp_result.query,
                duration_ms=gp_result.duration_ms,
                error_code=gp_result.error_code,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Unexpected GP pipeline error: %s", exc, exc_info=True)
            return GpResult(providers_written=0, error=True, error_code="unexpected")

    async def generate_greeting_text(
        self,
        user_name: str = "",
        has_open_request: bool = False,
    ) -> str:
        """Generate a natural, friendly greeting text via LLM.

        Pure LLM call — stage management and context seeding are the
        responsibility of the caller (SessionStarter).

        Args:
            user_name: User's first name
            has_open_request: Whether user has an open service request

        Returns:
            Greeting text
        """
        try:
            logger.info("🤖 generate_greeting_text called with user_name='%s', has_open_request=%s", user_name, has_open_request)
            language_instruction = get_language_instruction(self.language)
            resume_ctx = self.context.get("session_resume_context", "")
            system_prefix = f"{resume_ctx}\n\n" if resume_ctx else ""
            greeting_prompt = get_prompt(self._profile.prompt_key, "greeting")
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(system_prefix + greeting_prompt),
                HumanMessage(content=" ")
            ])

            greeting_messages = prompt_template.format_messages(
                agent_name=self.agent_name,
                company_name=self.company_name,
                user_name=user_name,
                has_open_request="Yes" if has_open_request else "No",
                language_instruction=language_instruction
            )

            logger.info("📨 Formatted prompt with user_name='%s' for LLM", user_name)

            greeting = await self.llm_service.generate(greeting_messages)
            logger.info("Generated greeting: '%s'", greeting)
            return greeting

        except Exception as e:
            logger.error("Error generating greeting text: %s", e, exc_info=True)
            return get_greeting_fallback(self.language)
