"""
Greeting Service
Handles greeting generation with user data integration.
"""
import logging
from typing import AsyncIterator, Optional, Tuple
from langchain_core.messages import AIMessage

from .conversation_service import ConversationService
from .text_to_speech_service import TextToSpeechService
from .llm_service import LLMService
from ..data_provider import DataProvider

logger = logging.getLogger(__name__)


class GreetingService:
    """
    Generates personalized greetings with audio synthesis.
    Integrates user data from data provider.
    """
    
    def __init__(
        self,
        conversation_service: ConversationService,
        tts_service: TextToSpeechService,
        llm_service: LLMService,
        data_provider: DataProvider,
        default_user_name: str = "Wolfgang"
    ):
        """
        Initialize greeting service.
        
        Args:
            conversation_service: Conversation service instance
            tts_service: Text-to-speech service instance
            llm_service: LLM service instance
            data_provider: Data provider instance
            default_user_name: Default user name if not found
        """
        self.conversation_service = conversation_service
        self.tts_service = tts_service
        self.llm_service = llm_service
        self.data_provider = data_provider
        self.default_user_name = default_user_name
    
    async def get_greeting_with_audio(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[str, AsyncIterator[bytes]]:
        """
        Generate personalized greeting with audio.
        
        This method:
        1. Fetches user data from data provider if user_id provided
        2. Generates personalized greeting text using LLM
        3. Adds greeting to conversation history
        4. Synthesizes audio from greeting text
        
        Args:
            session_id: Session identifier
            user_id: Optional user ID to fetch user data
            
        Returns:
            Tuple of (greeting_text, audio_iterator)
        """
        logger.info(f"🎯 get_greeting_with_audio called with user_id={user_id}")
        
        # Fetch user data
        user_name, has_open_request = await self._fetch_user_data(user_id)
        logger.info(f"📝 Resolved user_name='{user_name}', has_open_request={has_open_request}")
        
        # Generate greeting text
        greeting_text = await self.conversation_service.generate_greeting(
            session_id=session_id,
            user_name=user_name,
            has_open_request=has_open_request
        )
        
        # Add to conversation history
        self._add_to_history(session_id, greeting_text)
        
        # Generate audio stream
        logger.info(f"Generating greeting audio: '{greeting_text}'")
        audio_stream = self.tts_service.synthesize_stream(greeting_text, chunk_size=2048)
        
        return greeting_text, audio_stream
    
    async def _fetch_user_data(self, user_id: Optional[str]) -> Tuple[str, bool]:
        """
        Fetch user data from data provider.
        
        Args:
            user_id: Optional user ID
            
        Returns:
            Tuple of (user_name, has_open_request)
        """
        user_name = self.default_user_name
        has_open_request = False
        
        if user_id:
            logger.info(f"🔍 Fetching user data for user_id={user_id}...")
            try:
                user = await self.data_provider.get_user_by_id(user_id)
                logger.info(f"📦 Data provider returned: {user}")
                if user:
                    user_name = user.get("name", self.default_user_name)
                    has_open_request = user.get("has_open_request", False)
                    logger.info(f"✅ Successfully fetched user data: name='{user_name}', open_request={has_open_request}")
                else:
                    logger.warning(f"❌ Data provider returned None/empty for user_id={user_id}")
            except Exception as e:
                logger.error(f"❌ Failed to fetch user data for {user_id}: {e}", exc_info=True)
        else:
            logger.info(f"⚠️  No user_id provided, using default name='{self.default_user_name}'")
        
        return user_name, has_open_request
    
    def _add_to_history(self, session_id: str, greeting_text: str):
        """
        Add greeting to conversation history.
        
        Args:
            session_id: Session identifier
            greeting_text: Greeting text
        """
        history = self.llm_service.get_session_history(session_id)
        history.add_message(AIMessage(content=greeting_text))
        logger.debug(f"Added greeting to history for session {session_id}")
