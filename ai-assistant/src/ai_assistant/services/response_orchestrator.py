"""
Response Orchestration Service
Handles LLM response generation with conversation stage management and transitions.
"""
import logging
from typing import AsyncIterator, Optional

from .conversation_service import ConversationService, ConversationStage
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class ResponseOrchestrator:
    """
    Orchestrates LLM response generation with stage-aware conversation flow.
    Handles stage transitions and automatic provider presentations.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        conversation_service: ConversationService
    ):
        """
        Initialize response orchestrator.
        
        Args:
            llm_service: LLM service instance
            conversation_service: Conversation service instance
        """
        self.llm_service = llm_service
        self.conversation_service = conversation_service
    
    async def generate_response_stream(
        self,
        user_input: str,
        session_id: str
    ) -> AsyncIterator[str]:
        """
        Generate streaming response with stage-aware conversation flow.
        
        This method:
        1. Accumulates problem descriptions during triage stage
        2. Generates LLM response for current stage
        3. Detects and handles stage transitions
        4. Auto-generates provider presentations when transitioning to finalize
        
        Args:
            user_input: User's input text
            session_id: Session identifier
            
        Yields:
            Response chunks as strings
        """
        try:
            current_stage = self.conversation_service.get_current_stage()
            logger.debug(
                f"Generating response for: '{user_input[:50]}...' [Stage: {current_stage}]"
            )
            
            # Accumulate problem description during triage stage
            if current_stage == ConversationStage.TRIAGE:
                await self.conversation_service.accumulate_problem_description(user_input)
            
            # Generate primary response
            full_response = ""
            async for chunk in self._generate_stage_response(user_input, session_id):
                full_response += chunk
                yield chunk
            
            # Check for and handle stage transitions
            new_stage = await self.conversation_service.detect_stage_transition(
                user_input,
                full_response
            )
            
            if new_stage:
                await self._handle_stage_transition(new_stage, session_id)
                
                # Perform provider search and generate presentation when entering finalize
                if new_stage == ConversationStage.FINALIZE:
                    # Search for providers based on the accumulated request summary
                    await self.conversation_service.search_providers_for_request()
                    
                    # Generate provider presentation
                    async for chunk in self._generate_finalize_presentation(session_id):
                        yield chunk
            
        except Exception as e:
            logger.error(f"Error in response orchestration: {e}", exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."
    
    async def _generate_stage_response(
        self,
        user_input: str,
        session_id: str
    ) -> AsyncIterator[str]:
        """
        Generate response for current conversation stage.
        
        Args:
            user_input: User's input text
            session_id: Session identifier
            
        Yields:
            Response chunks
        """
        current_stage = self.conversation_service.get_current_stage()
        prompt_template = self.conversation_service.create_prompt_for_stage(current_stage)
        
        async for chunk in self.llm_service.generate_stream(
            user_input,
            prompt_template,
            session_id
        ):
            yield chunk
    
    async def _handle_stage_transition(self, new_stage: str, session_id: str):
        """
        Handle conversation stage transition.
        
        Args:
            new_stage: New conversation stage
            session_id: Session identifier
        """
        old_stage = self.conversation_service.get_current_stage()
        logger.info(f"Stage transition: {old_stage} -> {new_stage}")
        
        self.conversation_service.set_stage(new_stage)
    
    async def _generate_finalize_presentation(
        self,
        session_id: str
    ) -> AsyncIterator[str]:
        """
        Auto-generate provider presentation for finalize stage.
        
        Args:
            session_id: Session identifier
            
        Yields:
            Response chunks
        """
        logger.info("Auto-generating provider presentation in FINALIZE stage")
        
        prompt_template = self.conversation_service.create_prompt_for_stage(
            ConversationStage.FINALIZE
        )
        
        # Use minimal prompt to trigger provider presentation
        auto_prompt = " "
        
        async for chunk in self.llm_service.generate_stream(
            auto_prompt,
            prompt_template,
            session_id
        ):
            yield chunk
