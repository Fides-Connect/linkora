"""
Conversation Service
Handles conversation flow, stage management, and orchestration.
"""
import logging
import json
from typing import Optional, AsyncIterator, Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from ..prompts_templates import (
    GREETING_AND_TRIAGE_PROMPT,
    TRIAGE_CONVERSATION_PROMPT,
    FINALIZE_SERVICE_REQUEST_PROMPT,
    get_language_instruction
)
from ..test_data import detect_category
from ..data_provider import DataProvider

logger = logging.getLogger(__name__)


class ConversationStage:
    """Conversation stage constants."""
    GREETING = "greeting"
    TRIAGE = "triage"
    FINALIZE = "finalize"
    COMPLETED = "completed"


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
            "user_problem": "",
            "detected_category": None,
            "providers_found": [],
            "current_provider_index": 0,
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
            return ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT).format(
                    agent_name=self.agent_name,
                    company_name=self.company_name,
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
            provider_list_json = json.dumps(self.context["providers_found"], ensure_ascii=False)
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
        
        else:
            # Default to triage
            return self.create_prompt_for_stage(ConversationStage.TRIAGE)
    
    async def detect_stage_transition(self, user_input: str, ai_response: str) -> Optional[str]:
        """
        Detect if conversation should transition to a new stage.
        
        Args:
            user_input: User's input text
            ai_response: AI's response text
        
        Returns:
            New stage name if transition detected, None otherwise
        """
        user_lower = user_input.lower()
        response_lower = ai_response.lower()
        
        # Detect transition from TRIAGE to FINALIZE
        if self.current_stage == ConversationStage.TRIAGE:
            transition_keywords = [
                "database durchsuchen",
                "datenbank durchsuchen",
                "einen moment",
                "please hold",
                "bitte warten"
            ]
            if any(keyword in response_lower for keyword in transition_keywords):
                logger.info("Detected transition trigger to FINALIZE stage")
                await self.accumulate_problem_description(user_input)
                return ConversationStage.FINALIZE
        
        # Detect transition from FINALIZE to COMPLETED
        if self.current_stage == ConversationStage.FINALIZE:
            closing_keywords = [
                "schönen tag",
                "auf wiedersehen",
                "vielen dank",
                "thank you"
            ]
            if any(keyword in response_lower for keyword in closing_keywords):
                return ConversationStage.COMPLETED
        
        return None
    
    async def accumulate_problem_description(self, user_input: str):
        """
        Accumulate user's problem description and search for providers.
        
        Args:
            user_input: User's problem description
        """
        self.context["user_problem"] += " " + user_input
        
        # Detect category
        category = detect_category(self.context["user_problem"])
        if category:
            self.context["detected_category"] = category
            logger.info(f"Detected category: {category}")
        
        # Search for providers
        providers = await self.data_provider.search_providers(
            query_text=self.context["user_problem"],
            category=self.context["detected_category"],
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
            
            language_instruction = get_language_instruction(self.language)
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT),
                HumanMessage(content=" ")
            ])
            
            greeting_messages = prompt_template.format_messages(
                agent_name=self.agent_name,
                company_name=self.company_name,
                user_name=user_name,
                has_open_request="YES" if has_open_request else "NO",
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
