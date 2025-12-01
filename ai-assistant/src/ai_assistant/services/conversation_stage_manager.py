"""
Conversation Stage Manager
Manages conversation flow, stage transitions, and prompt templates.
"""
import logging
import json
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate

from ..definitions import (
    AGENT_NAME,
    COMPANY_NAME,
    ConversationStage,
)
from ..prompts_templates import (
    GREETING_AND_TRIAGE_PROMPT,
    TRIAGE_CONVERSATION_PROMPT,
    FINALIZE_SERVICE_REQUEST_PROMPT,
)

logger = logging.getLogger(__name__)


class ConversationStageManager:
    """Manages conversation stages, transitions, and prompt templates."""

    def __init__(self, initial_stage: str = ConversationStage.GREETING):
        """Initialize with an optional starting stage."""
        self.current_stage = initial_stage
        self.conversation_context = {
            "user_problem": "",
            "detected_category": None,
            "providers_found": [],
            "current_provider_index": 0,
        }

    def create_prompt_for_stage(self, stage: str) -> ChatPromptTemplate:
        """Create appropriate prompt template based on conversation stage."""
        if stage == ConversationStage.GREETING:
            return self._create_greeting_prompt()
        elif stage == ConversationStage.TRIAGE:
            return self._create_triage_prompt()
        elif stage == ConversationStage.FINALIZE:
            return self._create_finalize_prompt()
        else:
            # Default to triage
            return self._create_triage_prompt()

    def _create_greeting_prompt(self) -> ChatPromptTemplate:
        """Create greeting prompt template."""
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(GREETING_AND_TRIAGE_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

    def _create_triage_prompt(self) -> ChatPromptTemplate:
        """Create triage prompt template."""
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(TRIAGE_CONVERSATION_PROMPT).format(
                agent_name=AGENT_NAME,
            ),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

    def _create_finalize_prompt(self) -> ChatPromptTemplate:
        """Create finalize prompt template with provider data."""
        provider_list_json = json.dumps(
            self.conversation_context["providers_found"],
            ensure_ascii=False
        )
        provider_count = len(self.conversation_context["providers_found"])
        
        return ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(FINALIZE_SERVICE_REQUEST_PROMPT).format(
                agent_name=AGENT_NAME,
                provider_list_json=provider_list_json,
                provider_count=provider_count,
            ),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

    def detect_stage_transition(self, user_input: str, ai_response: str) -> Optional[str]:
        """
        Detect if conversation should transition to a new stage.
        
        Args:
            user_input: User's input text
            ai_response: AI's complete response
            
        Returns:
            New stage name if transition detected, None otherwise
        """
        user_lower = user_input.lower()
        response_lower = ai_response.lower()

        # Detect transition from TRIAGE to FINALIZE
        if self.current_stage == ConversationStage.TRIAGE:
            if self._should_transition_to_finalize(response_lower):
                logger.info("Detected transition trigger to FINALIZE stage")
                return ConversationStage.FINALIZE

        # Detect transition from FINALIZE to COMPLETED
        if self.current_stage == ConversationStage.FINALIZE:
            if self._should_transition_to_completed(response_lower):
                return ConversationStage.COMPLETED

        return None

    def _should_transition_to_finalize(self, response_lower: str) -> bool:
        """Check if response indicates transition to FINALIZE stage."""
        transition_keywords = [
            "database durchsuchen",
            "datenbank durchsuchen",
            "einen moment",
            "please hold",
            "bitte warten"
        ]
        return any(keyword in response_lower for keyword in transition_keywords)

    def _should_transition_to_completed(self, response_lower: str) -> bool:
        """Check if response indicates transition to COMPLETED stage."""
        closing_keywords = [
            "schönen tag",
            "auf wiedersehen",
            "vielen dank",
            "thank you"
        ]
        return any(keyword in response_lower for keyword in closing_keywords)

    def transition_to_stage(self, new_stage: str):
        """Transition to a new conversation stage."""
        old_stage = self.current_stage
        self.current_stage = new_stage
        logger.info(f"Conversation stage transitioned: {old_stage} -> {new_stage}")

    def accumulate_user_problem(self, user_input: str):
        """Accumulate user's problem description for provider search."""
        self.conversation_context["user_problem"] += " " + user_input

    def set_detected_category(self, category: str):
        """Set the detected service category."""
        self.conversation_context["detected_category"] = category
        logger.info(f"Detected category: {category}")

    def set_providers(self, providers: list):
        """Set the list of matching providers."""
        self.conversation_context["providers_found"] = providers
        logger.info(f"Found {len(providers)} matching providers")

    def get_user_problem(self) -> str:
        """Get accumulated user problem description."""
        return self.conversation_context["user_problem"]

    def get_detected_category(self) -> Optional[str]:
        """Get detected category."""
        return self.conversation_context["detected_category"]

    def get_providers(self) -> list:
        """Get list of found providers."""
        return self.conversation_context["providers_found"]
