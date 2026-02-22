"""
Conversation Service
Handles conversation flow, stage management, and orchestration.
"""
import logging
import json
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
    PROVIDER_PITCH_PROMPT,
    PROVIDER_ONBOARDING_PROMPT,
    get_language_instruction
)


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
    ConversationStage.FINALIZE:       [ConversationStage.COMPLETED, ConversationStage.RECOVERY],
    ConversationStage.RECOVERY:       [ConversationStage.TRIAGE],
    ConversationStage.COMPLETED:      [ConversationStage.PROVIDER_PITCH],
    ConversationStage.PROVIDER_PITCH: [ConversationStage.PROVIDER_ONBOARDING, ConversationStage.COMPLETED],
    ConversationStage.PROVIDER_ONBOARDING: [ConversationStage.COMPLETED],
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
                 max_providers: int = 3, language: str = 'de'):
        """
        Initialize Conversation service.
        
        Args:
            llm_service: LLM service instance
            data_provider: Data provider instance
            agent_name: Name of the AI agent
            company_name: Company name
            max_providers: Maximum number of providers to present
            language: Language code ('de' or 'en')
        """
        self.llm_service = llm_service
        self.data_provider = data_provider
        self.agent_name = agent_name
        self.company_name = company_name
        self.max_providers = max_providers
        self.language = language
        
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
    
    def create_prompt_for_stage(self, stage: str) -> ChatPromptTemplate:
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
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(TRIAGE_CONVERSATION_PROMPT).format(
                    agent_name=self.agent_name,
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
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(template).format(
                    agent_name=self.agent_name,
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
            onboarding_draft_json = json.dumps(
                self.context.get("onboarding_draft", []),
                ensure_ascii=False,
                default=json_serializer,
            )
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(PROVIDER_ONBOARDING_PROMPT).format(
                    agent_name=self.agent_name,
                    language_instruction=language_instruction,
                    onboarding_draft_json=onboarding_draft_json,
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])

        else:
            # Default to triage
            return self.create_prompt_for_stage(ConversationStage.TRIAGE)
    
    async def accumulate_problem_description(self, user_input: str):
        """
        Accumulate user's problem description.
        Note: Provider search is now performed in FINALIZE stage.
        
        Args:
            user_input: User's problem description
        """
        self.context["user_problem"].append(user_input)
    
    def _get_problem_summary(self) -> str:
        """Extract problem summary from conversation context."""
        ai_responses = self.context.get("ai_responses", [])
        if len(ai_responses) >= 2:
            return ai_responses[-2]
        elif len(ai_responses) == 1:
            return ai_responses[0]
        else:
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
    
    async def _generate_structured_query(self, problem_summary: str) -> str:
        """
        Generate structured JSON query from problem summary.
        
        Args:
            problem_summary: The user's problem description
            
        Returns:
            JSON string of structured query, or original summary on error
        """
        from ..prompts_templates import STRUCTURED_QUERY_EXTRACTION_PROMPT
        
        language_instruction = get_language_instruction(self.language)
        extraction_prompt = STRUCTURED_QUERY_EXTRACTION_PROMPT.format(
            problem_summary=problem_summary,
            language_instruction=language_instruction
        )
        
        try:
            json_response = await self.llm_service.generate([HumanMessage(content=extraction_prompt)])
            json_str = self._clean_json_response(json_response)
            
            # Validate JSON
            structured_query = json.loads(json_str)
            logger.info(f"Generated structured query: {json.dumps(structured_query, ensure_ascii=False)}")
            
            return json.dumps(structured_query, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error generating structured query: {e}", exc_info=True)
            logger.info("Falling back to original summary for search")
            return problem_summary
    
    async def search_providers_for_request(self):
        """
        Search for providers based on the agent's conversational summary.
        Called when entering FINALIZE stage.
        Generates a structured JSON query for hybrid search.
        """
        problem_summary = self._get_problem_summary()
        logger.info(f"Generating structured search query from summary: '{problem_summary[:100]}...'")
        
        # Generate structured query
        query_text = await self._generate_structured_query(problem_summary)
        
        # Search for providers
        self.context["request_summary"] = query_text
        providers = await self.data_provider.search_providers(
            query_text=query_text,
            limit=self.max_providers
        )
        
        self.context["providers_found"] = providers
        logger.info(f"Found {len(providers)} matching providers")
    
    async def generate_greeting(self, session_id: str, user_name: str = "",
                               has_open_request: bool = False) -> str:
        """
        Generate a natural, friendly greeting.
        
        Args:
            session_id: Session identifier
            user_name: User's name
            has_open_request: Whether user has an open request
        
        Returns:
            Greeting text
        """
        try:
            logger.info(f"🤖 generate_greeting called with user_name='{user_name}', has_open_request={has_open_request}")
            self.set_stage(ConversationStage.GREETING)
            # Persist so create_prompt_for_stage can use them if needed
            self.context["user_name"] = user_name
            self.context["has_open_request"] = has_open_request
            
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
            
            # Transition to triage after greeting
            self.set_stage(ConversationStage.TRIAGE)
            
            return greeting
            
        except Exception as e:
            logger.error(f"Error generating greeting: {e}", exc_info=True)
            self.set_stage(ConversationStage.TRIAGE)
            return "Hallo! Wie kann ich dir heute helfen?"
