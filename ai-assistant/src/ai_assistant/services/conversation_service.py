"""
Conversation Service
Handles conversation flow, stage management, and orchestration.
"""
import logging
import json
import asyncio
from enum import Enum
from datetime import datetime
from typing import Optional, AsyncIterator, Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from ..data_provider import DataProvider
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
    get_language_instruction
)
from .cross_encoder_service import CrossEncoderService


logger = logging.getLogger(__name__)


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class ConversationStage(str, Enum):
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
_LEGAL_TRANSITIONS: Dict["ConversationStage", List["ConversationStage"]] = {
    ConversationStage.GREETING:       [ConversationStage.TRIAGE],
    ConversationStage.TRIAGE:         [ConversationStage.FINALIZE, ConversationStage.CLARIFY,
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
    
    def __init__(self, llm_service, data_provider: DataProvider,
                 agent_name: str = "Elin", company_name: str = "Linkora",
                 max_providers: int = 5, language: str = 'de',
                 cross_encoder_service: Optional["CrossEncoderService"] = None):
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
        """
        self.llm_service = llm_service
        self.data_provider = data_provider
        self.agent_name = agent_name
        self.company_name = company_name
        self.max_providers = max_providers
        self.language = language
        self.cross_encoder_service = cross_encoder_service
        
        self.current_stage = ConversationStage.GREETING
        self.context: Dict[str, Any] = {
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
        }
        
        logger.info(f"Conversation service initialized: agent={agent_name}, company={company_name}")
    
    def get_current_stage(self) -> str:
        """Get current conversation stage."""
        return self.current_stage
    
    def set_stage(self, stage: str):
        """
        Set conversation stage.
        
        Args:
            stage: New stage to set
        """
        logger.info(f"Stage transition: {self.current_stage} -> {stage}")
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
            language_instruction = get_language_instruction(self.language)
            user_name = self.context.get("user_name", "")
            has_open_request = "Yes" if self.context.get("has_open_request", False) else "No"
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT).format(
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
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(TRIAGE_CONVERSATION_PROMPT).format(
                    agent_name=self.agent_name,
                    user_name=user_name,
                    language_instruction=language_instruction,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
        
        elif stage == ConversationStage.FINALIZE:
            provider_list_json = json.dumps(self.context["providers_found"], ensure_ascii=False, default=json_serializer)
            provider_count = len(self.context["providers_found"])
            language_instruction = get_language_instruction(self.language)
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(FINALIZE_SERVICE_REQUEST_PROMPT).format(
                    agent_name=self.agent_name,
                    provider_list_json=provider_list_json,
                    provider_count=provider_count,
                    language_instruction=language_instruction
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
            # Map each stage to its dedicated prompt template
            stage_prompt_map = {
                ConversationStage.CLARIFY: CLARIFY_PROMPT,
                ConversationStage.CONFIRMATION: CONFIRMATION_PROMPT,
                ConversationStage.RECOVERY: RECOVERY_PROMPT,
                # TOOL_EXECUTION: reuse triage until a dedicated template is needed
                ConversationStage.TOOL_EXECUTION: TRIAGE_CONVERSATION_PROMPT,
            }
            template = stage_prompt_map.get(stage, TRIAGE_CONVERSATION_PROMPT)
            # TRIAGE_CONVERSATION_PROMPT requires user_name; others only need agent_name
            fmt_kwargs: dict = {"agent_name": self.agent_name}
            if template is TRIAGE_CONVERSATION_PROMPT:
                fmt_kwargs["user_name"] = self.context.get("user_name", "")
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(template).format(
                    **fmt_kwargs
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.PROVIDER_PITCH:
            language_instruction = get_language_instruction(self.language)
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(PROVIDER_PITCH_PROMPT).format(
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
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(PROVIDER_ONBOARDING_PROMPT).format(
                    agent_name=self.agent_name,
                    language_instruction=language_instruction,
                    current_competencies_json=current_competencies_json,
                    is_service_provider=self.context.get("is_service_provider", False),
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        elif stage == ConversationStage.COMPLETED:
            language_instruction = get_language_instruction(self.language)
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(LOOP_BACK_PROMPT).format(
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
        # onboarding_draft and current_competencies are preserved across request
        # resets so a PROVIDER_ONBOARDING session isn't interrupted mid-flow.
        logger.info("Request context reset for new TRIAGE scoping session")

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
            return ai_responses[-1]
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

        # Build conversation excerpt — last 3 messages from LLM history.
        history_excerpt = ""
        if session_id:
            messages = self.llm_service.get_session_history(session_id).messages
            recent = messages[-3:] if len(messages) >= 3 else messages
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

        # Stages 1 + 2 run independently — fire both LLM calls concurrently.
        structured_query_task = asyncio.create_task(
            self._generate_structured_query(problem_summary, session_id)
        )
        hyde_task = asyncio.create_task(
            self._generate_hyde_text(problem_summary)
        )
        query_text, hyde_text = await asyncio.gather(structured_query_task, hyde_task)

        self.context["request_summary"] = query_text

        # Stage 3: wide-net retrieval (fetch_limit is computed inside
        # HubSpokeSearch as min(limit * 5, 30)).
        fetch_limit = min(self.max_providers * 5, 30)
        providers = await self.data_provider.search_providers(
            query_text=query_text,
            limit=fetch_limit,
            hyde_text=hyde_text,
        )

        # Stage 4: cross-encoder reranking.
        if self.cross_encoder_service and providers:
            logger.info(
                "Reranking %d candidates with cross-encoder (top %d)...",
                len(providers),
                self.max_providers,
            )
            providers = await self.cross_encoder_service.rerank(
                query=problem_summary,
                candidates=providers,
                top_k=self.max_providers,
            )
        else:
            providers = providers[: self.max_providers]

        self.context["providers_found"] = providers
        logger.info("Provider search complete — %d results", len(providers))
    
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
            logger.info(
                f"🤖 generate_greeting_text called with user_name='{user_name}', "
                f"has_open_request={has_open_request}"
            )
            language_instruction = get_language_instruction(self.language)
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT),
                HumanMessage(content=" ")
            ])

            greeting_messages = prompt_template.format_messages(
                agent_name=self.agent_name,
                company_name=self.company_name,
                user_name=user_name,
                has_open_request="Yes" if has_open_request else "No",
                language_instruction=language_instruction
            )

            logger.info(f"📨 Formatted prompt with user_name='{user_name}' for LLM")

            greeting = await self.llm_service.generate(greeting_messages)
            logger.info(f"Generated greeting: '{greeting}'")
            return greeting

        except Exception as e:
            logger.error(f"Error generating greeting text: {e}", exc_info=True)
            return "Hallo! Wie kann ich dir heute helfen?"
