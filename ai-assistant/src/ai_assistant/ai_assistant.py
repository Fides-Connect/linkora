"""
AI Assistant
Core orchestration layer that coordinates services.
"""
import logging
import os
from typing import AsyncIterator, Optional, Tuple

from .services import (
    SpeechToTextService,
    TextToSpeechService,
    LLMService,
    ConversationService,
    AgentRuntimeFSM,
    build_default_registry,
)
from .services.response_orchestrator import ResponseOrchestrator
from .services.greeting_service import GreetingService
from .data_provider import get_data_provider

logger = logging.getLogger(__name__)

# Constants
AGENT_NAME = "Elin"
COMPANY_NAME = "FidesConnect"
USER_NAME_PLACEHOLDER = ""


def get_language_config(language: str) -> tuple[str, str]:
    """Get language code and voice name based on language."""
    if language == 'en':
        # English configuration - using Chirp3-HD voice with full identifier
        language_code = os.getenv('LANGUAGE_CODE_EN', 'en-US')
        voice_name = os.getenv('VOICE_NAME_EN', 'en-US-Chirp3-HD-Sulafat')
    else:
        # German configuration (default)
        language_code = os.getenv('LANGUAGE_CODE_DE', 'de-DE')
        voice_name = os.getenv('VOICE_NAME_DE', 'de-DE-Chirp3-HD-Sulafat')
    
    return language_code, voice_name

class AIAssistant:
    """
    AI Assistant orchestrator that coordinates services.
    This class acts as a facade, delegating work to specialized services.
    """
    
    def __init__(self, gemini_api_key: str, language: str = 'de',
                 llm_model: str = 'gemini-2.5-flash',
                 session_id: Optional[str] = None):
        """
        Initialize AI Assistant with all required services.
        
        Args:
            gemini_api_key: API key for Gemini LLM
            language: Language code ('de' or 'en')
            llm_model: LLM model name
            session_id: Session identifier
        """
        self.language = language
        self.session_id = session_id or "default"
        
        # Get language-specific configuration
        self.language_code, self.voice_name = get_language_config(language)
        
        # Initialize data provider
        self.data_provider = get_data_provider()
        
        # Initialize services
        self.stt_service = SpeechToTextService(
            language_code=self.language_code
        )
        
        max_concurrency = int(os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5'))
        self.tts_service = TextToSpeechService(
            language_code=self.language_code,
            voice_name=self.voice_name,
            max_concurrent_requests=max_concurrency
        )
        
        self.llm_service = LLMService(
            api_key=gemini_api_key,
            model=llm_model,
            temperature=0.2,
            max_output_tokens=2048
        )
        
        self.conversation_service = ConversationService(
            llm_service=self.llm_service,
            data_provider=self.data_provider,
            agent_name=AGENT_NAME,
            company_name=COMPANY_NAME,
            max_providers=3,
            language=self.language
        )
        
        # Build agentic runtime FSM and tool registry
        self.runtime_fsm = AgentRuntimeFSM()
        self.firestore_service = None  # injected by PeerConnectionHandler after construction
        self.tool_registry = build_default_registry(
            data_provider=self.data_provider,
            firestore_service=None,  # placeholder — real value set via self.firestore_service
        )

        # Initialize orchestration services
        self.response_orchestrator = ResponseOrchestrator(
            llm_service=self.llm_service,
            conversation_service=self.conversation_service,
            runtime_fsm=self.runtime_fsm,
            tool_registry=self.tool_registry,
        )
        
        self.greeting_service = GreetingService(
            conversation_service=self.conversation_service,
            tts_service=self.tts_service,
            llm_service=self.llm_service,
            data_provider=self.data_provider,
            default_user_name=USER_NAME_PLACEHOLDER
        )
        
        logger.info("AI Assistant initialized with service-oriented architecture")
    
    async def generate_llm_response_stream(
        self, prompt: str, user_id: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response using LLM.
        Delegates to ResponseOrchestrator for stage-aware conversation flow.

        Args:
            prompt: User input prompt
            user_id: Authenticated user ID — forwarded to tools that need it

        Yields:
            Response chunks as strings
        """
        from .services.agent_tools import ToolCapability

        # Fetch user_context for provider pitch eligibility check (best-effort)
        user_ctx: dict = {}
        if self.firestore_service and user_id:
            try:
                user_ctx = await self.firestore_service.get_user(user_id) or {}
            except Exception:
                pass

        context = {
            "user_id": user_id or "",
            "user_capabilities": [
                ToolCapability("providers", "read"),
                ToolCapability("favorites", "read"),
                ToolCapability("service_requests", "read"),
                ToolCapability("service_requests", "write"),
                ToolCapability("provider_onboarding", "write"),
            ],
            "data_provider": self.data_provider,
            "firestore_service": self.firestore_service,
            "user_context": user_ctx,
        }
        async for chunk in self.response_orchestrator.generate_response_stream(
            prompt, self.session_id, context=context
        ):
            yield chunk
    
    async def get_greeting_audio(self, user_id: Optional[str] = None) -> Tuple[str, AsyncIterator[bytes]]:
        """
        Generate a natural greeting and return both text and TTS audio.
        Delegates to GreetingService.
        
        Args:
            user_id: Optional user ID to fetch user data from data provider
        
        Returns:
            Tuple of (greeting_text, audio_iterator)
        """
        return await self.greeting_service.get_greeting_with_audio(
            session_id=self.session_id,
            user_id=user_id
        )
