"""
LLM Response Processor
Handles LLM streaming, provider search, and stage transitions.
"""
import logging
from typing import AsyncIterator

from ..definitions import MAX_PROVIDERS_TO_PRESENT, ConversationStage, USER_NAME_PLACEHOLDER
from ..test_data import detect_category

logger = logging.getLogger(__name__)


class LLMResponseProcessor:
    """Processes LLM responses and handles stage transitions."""

    def __init__(
        self,
        ai_assistant,  # Reference to AIAssistant for chain updates
        stage_manager,
        data_provider,
        user_id: str
    ):
        """
        Initialize LLM response processor.
        
        Args:
            ai_assistant: AIAssistant instance (for accessing updated chain)
            stage_manager: Conversation stage manager
            data_provider: Data provider for searches
            user_id: User ID for session management
        """
        self.ai_assistant = ai_assistant
        self.stage_manager = stage_manager
        self.data_provider = data_provider
        self.user_id = user_id

    async def generate_response_stream(
        self,
        prompt: str
    ) -> AsyncIterator[str]:
        """
        Generate streaming LLM response with stage management.
        
        Args:
            prompt: User's input prompt
            
        Yields:
            LLM response chunks
        """
        try:
            logger.debug(
                f"Generating LLM response for: '{prompt[:50]}...' "
                f"[Stage: {self.stage_manager.current_stage}]"
            )

            # Fetch user info if in greeting stage
            if self.stage_manager.current_stage == ConversationStage.GREETING:
                await self._fetch_and_set_user_info()

            # Accumulate problem description during triage
            if self.stage_manager.current_stage == ConversationStage.TRIAGE:
                await self._accumulate_problem_description(prompt)

            # Prepare input with user variables if in greeting stage
            chain_input = {"input": prompt}
            if self.stage_manager.current_stage == ConversationStage.GREETING:
                chain_input.update(self.stage_manager.get_user_variables())

            # Stream response chunks
            full_response = ""
            async for chunk in self.ai_assistant.chain_with_history.astream(
                chain_input,
                config={"configurable": {"session_id": self.user_id}}
            ):
                if chunk.content:
                    logger.debug(f"LLM chunk: '{chunk.content}'")
                    full_response += chunk.content
                    yield chunk.content

            # Check for stage transitions
            await self._handle_stage_transitions(prompt, full_response)

        except Exception as e:
            logger.error(f"Streaming LLM error: {e}", exc_info=True)
            yield "Entschuldigung, ich konnte keine Antwort generieren."

    async def _fetch_and_set_user_info(self):
        """Fetch user information and set in stage manager."""
        try:
            user = await self.data_provider.get_user_by_id(self.user_id)
            if user:
                # Extract first name
                full_name = user.get("name", USER_NAME_PLACEHOLDER)
                user_name = full_name.split()[0] if full_name and full_name != USER_NAME_PLACEHOLDER and full_name.split() else "there"
                has_open_request = user.get("has_open_request", False)
                
                self.stage_manager.set_user_info(user_name, has_open_request)
                logger.info(f"Fetched user info: {user_name}, has_open_request={has_open_request}")
            else:
                # Use defaults
                self.stage_manager.set_user_info("there", False)
                logger.debug(f"No user found for {self.user_id}, using defaults")
        except Exception as e:
            logger.error(f"Error fetching user info: {e}", exc_info=True)
            self.stage_manager.set_user_info("there", False)

    async def _accumulate_problem_description(self, user_input: str):
        """Accumulate user's problem description without searching yet."""
        self.stage_manager.accumulate_user_problem(user_input)

        # Detect category for later use
        category = detect_category(self.stage_manager.get_user_problem())
        if category:
            self.stage_manager.set_detected_category(category)


    async def _handle_stage_transitions(self, user_input: str, ai_response: str):
        """Handle conversation stage transitions."""
        new_stage = self.stage_manager.detect_stage_transition(
            user_input,
            ai_response
        )

        if new_stage == ConversationStage.FINALIZE:
            await self._transition_to_finalize()
        elif new_stage:
            logger.info(
                f"Stage transition: {self.stage_manager.current_stage} -> {new_stage}"
            )
            # Update chain with new prompt for the stage
            self.ai_assistant.update_chain_for_stage(new_stage)

    async def _transition_to_finalize(self):
        """Handle transition to FINALIZE stage with provider search and auto-presentation."""
        logger.info(
            f"Transitioning: {self.stage_manager.current_stage} -> "
            f"{ConversationStage.FINALIZE}"
        )

        # Search for providers using accumulated problem description
        logger.info("Searching providers based on accumulated conversation")
        providers = await self.data_provider.search_providers(
            query_text=self.stage_manager.get_user_problem(),
            category=self.stage_manager.get_detected_category(),
            limit=MAX_PROVIDERS_TO_PRESENT
        )
        self.stage_manager.set_providers(providers)

        # Transition to FINALIZE stage
        self.stage_manager.transition_to_stage(ConversationStage.FINALIZE)

        # Auto-generate provider presentation
        logger.info("Auto-generating provider presentation")
        auto_prompt = " "  # Minimal prompt to trigger presentation

        async for chunk in self.ai_assistant.chain_with_history.astream(
            {"input": auto_prompt},
            config={"configurable": {"session_id": self.user_id}}
        ):
            if chunk.content:
                logger.debug(f"Auto-presentation chunk: '{chunk.content}'")
                yield chunk.content
