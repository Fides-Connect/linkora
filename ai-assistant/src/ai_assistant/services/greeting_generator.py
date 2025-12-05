"""
Greeting Generator Service
Handles AI greeting generation with personalization.
"""
import logging
from typing import AsyncIterator, Optional

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate

from ..definitions import AGENT_NAME, COMPANY_NAME, USER_NAME_PLACEHOLDER
from ..prompts_templates import GREETING_PROMPT

logger = logging.getLogger(__name__)


class GreetingGenerator:
    """Generates personalized greetings using LLM."""

    def __init__(self, llm, data_provider):
        """
        Initialize greeting generator.
        
        Args:
            llm: LangChain LLM instance
            data_provider: Data provider for user information
        """
        self.llm = llm
        self.data_provider = data_provider

    async def generate_greeting_with_audio(
        self,
        user_id: Optional[str],
        tts_service,
        chat_history
    ) -> tuple[str, AsyncIterator[bytes]]:
        """
        Generate personalized greeting text and audio.
        
        Args:
            user_id: User ID for personalization
            tts_service: TTS service for audio generation
            chat_history: Chat history to store greeting
            
        Returns:
            Tuple of (greeting_text, audio_iterator)
        """
        # Fetch user data
        user_info = await self._fetch_user_info(user_id)

        # Generate greeting text
        greeting_text = await self._generate_greeting_text(user_info)

        # Add to chat history
        chat_history.add_message(AIMessage(content=greeting_text))

        # Generate audio
        logger.info(f"Generating greeting audio: '{greeting_text}'")
        audio_stream = tts_service.synthesize_speech(greeting_text)

        return greeting_text, audio_stream

    async def _fetch_user_info(self, user_id: Optional[str]) -> dict:
        """Fetch user information from data provider."""
        user_info = {
            'user_name': USER_NAME_PLACEHOLDER,
            'has_open_request': False
        }

        if not user_id:
            logger.debug("No user_id provided, using placeholder")
            return user_info

        user = await self.data_provider.get_user_by_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found, using placeholder")
            return user_info

        # Extract first name
        full_name = user.get("name", USER_NAME_PLACEHOLDER)
        if full_name and full_name != USER_NAME_PLACEHOLDER:
            user_info['user_name'] = full_name.split()[0] if full_name.split() else full_name
            logger.info(f"Using first name: '{user_info['user_name']}'")
        else:
            logger.debug(f"No valid name for user {user_id}")

        user_info['has_open_request'] = user.get("has_open_request", False)

        return user_info

    async def _generate_greeting_text(self, user_info: dict) -> str:
        """Generate greeting text using LLM."""
        try:
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(GREETING_PROMPT),
                HumanMessage(content=" ")  # Required for Gemini API
            ])

            greeting_message = prompt_template.format_messages(
                agent_name=AGENT_NAME,
                company_name=COMPANY_NAME,
                user_name=user_info['user_name'],
                has_open_request="YES" if user_info['has_open_request'] else "NO",
            )

            # Stream and collect full greeting
            full_greeting = ""
            async for chunk in self.llm.astream(greeting_message):
                if chunk.content:
                    full_greeting += chunk.content

            logger.info(f"Generated greeting: '{full_greeting}'")
            return full_greeting.strip()

        except Exception as e:
            logger.error(f"Error generating greeting: {e}", exc_info=True)
            return "Hallo! Wie kann ich dir heute helfen?"
