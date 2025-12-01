"""
LLM Response Processor
Handles LLM streaming, provider search, and stage transitions.
"""
import asyncio
import logging
from typing import AsyncIterator

from ..definitions import MAX_PROVIDERS_TO_PRESENT, ConversationStage
from ..test_data import detect_category

logger = logging.getLogger(__name__)


class LLMResponseProcessor:
    """Processes LLM responses and handles stage transitions."""

    def __init__(
        self,
        chain_with_history,
        stage_manager,
        data_provider,
        user_id: str
    ):
        """
        Initialize LLM response processor.
        
        Args:
            chain_with_history: LangChain runnable with message history
            stage_manager: Conversation stage manager
            data_provider: Data provider for searches
            user_id: User ID for session management
        """
        self.chain_with_history = chain_with_history
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

            # Accumulate problem description during triage
            if self.stage_manager.current_stage == ConversationStage.TRIAGE:
                await self._accumulate_problem_description(prompt)

            # Stream response chunks
            full_response = ""
            async for chunk in self.chain_with_history.astream(
                {"input": prompt},
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

    async def _accumulate_problem_description(self, user_input: str):
        """Accumulate user's problem for provider search."""
        self.stage_manager.accumulate_user_problem(user_input)

        # Detect category
        category = detect_category(self.stage_manager.get_user_problem())
        if category:
            self.stage_manager.set_detected_category(category)

        # Search for providers
        providers = await self.data_provider.search_providers(
            query_text=self.stage_manager.get_user_problem(),
            category=self.stage_manager.get_detected_category(),
            limit=MAX_PROVIDERS_TO_PRESENT
        )

        self.stage_manager.set_providers(providers)

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
            self.stage_manager.transition_to_stage(new_stage)

    async def _transition_to_finalize(self):
        """Handle transition to FINALIZE stage with auto-presentation."""
        logger.info(
            f"Transitioning: {self.stage_manager.current_stage} -> "
            f"{ConversationStage.FINALIZE}"
        )
        self.stage_manager.transition_to_stage(ConversationStage.FINALIZE)

        # Auto-generate provider presentation
        logger.info("Auto-generating provider presentation")
        auto_prompt = " "  # Minimal prompt to trigger presentation

        async for chunk in self.chain_with_history.astream(
            {"input": auto_prompt},
            config={"configurable": {"session_id": self.user_id}}
        ):
            if chunk.content:
                logger.debug(f"Auto-presentation chunk: '{chunk.content}'")
                yield chunk.content
