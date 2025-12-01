"""
AI Assistant: Core logic coordinating speech-to-text, LLM processing, and text-to-speech services.
"""
import asyncio
import logging
import os
from typing import AsyncIterator, Optional, Callable

from google.cloud.speech_v1 import SpeechAsyncClient
from google.cloud.texttospeech_v1 import TextToSpeechAsyncClient
from google.oauth2 import service_account

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from .data_provider import get_data_provider
from .weaviate_models import ChatMessageModelWeaviate
from .definitions import (
    ConversationStage,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TOP_K,
    LLM_TOP_P,
    LLM_MAX_OUTPUT_TOKENS,
)

# Import new service classes
from .services.conversation_stage_manager import ConversationStageManager
from .services.speech_to_text_service import SpeechToTextService
from .services.text_to_speech_service import TextToSpeechService
from .services.greeting_generator import GreetingGenerator
from .services.llm_response_processor import LLMResponseProcessor

logger = logging.getLogger(__name__)


class PersistentChatMessageHistory(BaseChatMessageHistory):
    """Chat history that automatically persists messages to Weaviate."""

    def __init__(self, user_id: str, session_id: str, stage_getter: Callable[[], str]):
        self._user_id = user_id
        self._session_id = session_id
        self._stage_getter = stage_getter
        self._is_loading = False
        self._loaded = False
        self._messages: list[BaseMessage] = []

    @property
    def messages(self) -> list[BaseMessage]:
        """Return the list of messages."""
        return self._messages

    def load_from_store(self):
        """Load previously persisted messages into memory once."""
        if self._loaded or not self._user_id:
            return
        
        messages = ChatMessageModelWeaviate.get_messages(self._user_id)
        if not messages:
            self._loaded = True
            return
        
        self._is_loading = True
        try:
            for msg in messages:
                content = msg.get("content")
                role = msg.get("role", "assistant")
                if not content:
                    continue
                
                if role == "human":
                    self._messages.append(HumanMessage(content=content))
                else:
                    self._messages.append(AIMessage(content=content))
        finally:
            self._is_loading = False
            self._loaded = True

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the history and persist it."""
        self._messages.append(message)
        
        if self._is_loading or not self._user_id:
            return

        role = "human" if isinstance(message, HumanMessage) else "assistant"
        content = getattr(message, "content", "")
        if not content:
            return

        ChatMessageModelWeaviate.save_message(
            user_id=self._user_id,
            session_id=self._session_id,
            role=role,
            content=content,
            stage=self._stage_getter(),
        )

    def clear(self) -> None:
        """Clear all messages from history."""
        self._messages = []


class AIAssistant:
    """
    AI Assistant using service-oriented architecture.
    
    Coordinates between:
    - Conversation stage management
    - Speech-to-text processing
    - LLM response generation
    - Text-to-speech synthesis
    - Greeting generation
    """

    def __init__(
        self,
        gemini_api_key: str,
        language_code: str = 'de-DE',
        voice_name: str = 'de-DE-Chirp3-HD-Sulafat',
        user_id: Optional[str] = None
    ):
        """
        Initialize AI Assistant with service dependencies.
        
        Args:
            gemini_api_key: API key for Google Gemini LLM
            language_code: Language code for STT/TTS
            voice_name: Voice name for TTS
            user_id: User ID for personalization and history
        """
        self.language_code = language_code
        self.voice_name = voice_name
        self.user_id = user_id or "anonymous"
        self.gemini_api_key = gemini_api_key

        # Initialize data provider
        self.data_provider = get_data_provider()

        # Initialize Google Cloud clients
        self._init_google_cloud_clients()

        # Initialize LLM
        self.llm = self._create_llm()

        # Initialize conversation stage manager
        self.stage_manager = ConversationStageManager(ConversationStage.GREETING)

        # Initialize chat history store
        self.store = {}

        # Create LangChain chain with history
        self._init_langchain_chain()

        # Initialize services
        self._init_services()

        logger.info(f"AI Assistant initialized for user: {self.user_id}")

    def _init_google_cloud_clients(self):
        """Initialize Google Cloud Speech and TTS clients."""
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using credentials from: {credentials_path}")
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.speech_client = SpeechAsyncClient(credentials=credentials)
            self.tts_client = TextToSpeechAsyncClient(credentials=credentials)
        else:
            logger.info("Using default credentials (Cloud Run environment)")
            self.speech_client = SpeechAsyncClient()
            self.tts_client = TextToSpeechAsyncClient()

    def _create_llm(self) -> ChatGoogleGenerativeAI:
        """Create LangChain LLM instance."""
        return ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=self.gemini_api_key,
            temperature=LLM_TEMPERATURE,
            top_k=LLM_TOP_K,
            top_p=LLM_TOP_P,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            streaming=True,
        )

    def _init_langchain_chain(self):
        """Initialize LangChain chain with message history."""
        current_prompt = self.stage_manager.create_prompt_for_stage(
            ConversationStage.TRIAGE
        )
        self.chain = current_prompt | self.llm
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def _init_services(self):
        """Initialize all service instances."""
        # Speech services
        self.stt_service = SpeechToTextService(
            self.speech_client,
            self.language_code
        )
        
        max_concurrency = int(os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5'))
        self.tts_service = TextToSpeechService(
            self.tts_client,
            self.language_code,
            self.voice_name,
            max_concurrency
        )

        # Greeting generator
        self.greeting_generator = GreetingGenerator(
            self.llm,
            self.data_provider
        )

        # LLM response processor
        self.llm_processor = LLMResponseProcessor(
            self.chain_with_history,
            self.stage_manager,
            self.data_provider,
            self.user_id
        )

    def _get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """Get or create chat message history for a session."""
        if session_id not in self.store:
            history = PersistentChatMessageHistory(
                user_id=self.user_id,
                session_id=session_id,
                stage_getter=lambda: self.stage_manager.current_stage,
            )
            history.load_from_store()
            self.store[session_id] = history
        return self.store[session_id]

    @property
    def current_stage(self) -> str:
        """Get current conversation stage."""
        return self.stage_manager.current_stage

    def clear_conversation_history(self, clear_persistent: bool = False):
        """Clear chat history from memory and optionally from Weaviate."""
        if self.user_id in self.store:
            del self.store[self.user_id]
        
        if clear_persistent and self.user_id:
            ChatMessageModelWeaviate.delete_messages(self.user_id)

    def update_chain_for_stage(self, stage: str):
        """Update the chain with new prompt for the given stage."""
        self.stage_manager.transition_to_stage(stage)
        current_prompt = self.stage_manager.create_prompt_for_stage(stage)
        self.chain = current_prompt | self.llm
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    # Public API methods using services

    async def speech_to_text_continuous_stream(
        self,
        audio_generator
    ) -> AsyncIterator[tuple[str, bool]]:
        """
        Stream audio to STT and yield (transcript, is_final) tuples.
        
        Args:
            audio_generator: Async generator yielding audio chunks
            
        Yields:
            Tuple of (transcript, is_final)
        """
        async for transcript, is_final in self.stt_service.stream_recognize(
            audio_generator
        ):
            yield transcript, is_final

    async def generate_llm_response_stream(self, prompt: str) -> AsyncIterator[str]:
        """
        Generate streaming LLM response with automatic stage management.
        
        Args:
            prompt: User's input prompt
            
        Yields:
            LLM response chunks
        """
        async for chunk in self.llm_processor.generate_response_stream(prompt):
            yield chunk

    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Convert text to speech and stream audio.
        
        Args:
            text: Text to convert
            
        Yields:
            Audio chunks as bytes
        """
        async for chunk in self.tts_service.synthesize_speech(text):
            yield chunk

    async def get_greeting_audio(
        self,
        user_id: Optional[str] = None
    ) -> tuple[str, AsyncIterator[bytes]]:
        """
        Generate personalized greeting and return text + audio.
        
        Args:
            user_id: Optional user ID for personalization
            
        Returns:
            Tuple of (greeting_text, audio_iterator)
        """
        # Transition to greeting stage
        self.update_chain_for_stage(ConversationStage.GREETING)

        # Get chat history
        history = self._get_session_history(self.user_id)

        # Generate greeting
        greeting_text, audio_stream = await self.greeting_generator.generate_greeting_with_audio(
            user_id or self.user_id,
            self.tts_service,
            history
        )

        # After greeting, transition to triage
        self.update_chain_for_stage(ConversationStage.TRIAGE)

        return greeting_text, audio_stream

    async def generate_greeting(
        self,
        user_name: str = "",
        has_open_request: bool = False
    ) -> str:
        """
        Generate greeting text (legacy method for compatibility).
        
        Args:
            user_name: User's name
            has_open_request: Whether user has open request
            
        Returns:
            Greeting text
        """
        # This method is kept for backwards compatibility
        # In practice, get_greeting_audio should be used
        greeting_text, _ = await self.get_greeting_audio(self.user_id)
        return greeting_text
