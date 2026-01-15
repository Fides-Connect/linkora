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
)
from .services.response_orchestrator import ResponseOrchestrator
from .services.greeting_service import GreetingService
from .data_provider import get_data_provider

logger = logging.getLogger(__name__)

# Constants
AGENT_NAME = "Elin"
COMPANY_NAME = "FidesConnect"
USER_NAME_PLACEHOLDER = ""

class AIAssistant:
    """
    AI Assistant orchestrator that coordinates services.
    This class acts as a facade, delegating work to specialized services.
    """
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', 
                 voice_name: str = 'de-DE-Chirp3-HD-Sulafat',
                 session_id: Optional[str] = None):
        """
        Initialize AI Assistant with all required services.
        
        Args:
            gemini_api_key: API key for Gemini LLM
            language_code: Language code for STT/TTS
            voice_name: Voice name for TTS
            session_id: Session identifier
        """
        self.language_code = language_code
        self.voice_name = voice_name
        self.session_id = session_id or "default"
        
        # Initialize data provider
        self.data_provider = get_data_provider()
        
        # Initialize Google Cloud credentials
        credentials = self._get_google_credentials()
        
        # Initialize services
        self.stt_service = SpeechToTextService(
            language_code=language_code,
            credentials=credentials
        )
        
        max_concurrency = int(os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5'))
        self.tts_service = TextToSpeechService(
            language_code=language_code,
            voice_name=voice_name,
            max_concurrent_requests=max_concurrency,
            credentials=credentials
        )
        
        self.llm_service = LLMService(
            api_key=gemini_api_key,
            model="gemini-2.0-flash-exp",
            temperature=0.9,
            max_output_tokens=512
        )
        
        self.conversation_service = ConversationService(
            llm_service=self.llm_service,
            data_provider=self.data_provider,
            agent_name=AGENT_NAME,
            company_name=COMPANY_NAME,
            max_providers=3
        )
        
        # Initialize orchestration services
        self.response_orchestrator = ResponseOrchestrator(
            llm_service=self.llm_service,
            conversation_service=self.conversation_service
        )
        
        self.greeting_service = GreetingService(
            conversation_service=self.conversation_service,
            tts_service=self.tts_service,
            llm_service=self.llm_service,
            data_provider=self.data_provider,
            default_user_name=USER_NAME_PLACEHOLDER
        )
        
        logger.info("AI Assistant initialized with service-oriented architecture")
    
    def _get_google_credentials(self):
        """Get Google Cloud credentials if available."""
        credentials_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_PATH')
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Using credentials from: {credentials_path}")
            from google.oauth2 import service_account
            return service_account.Credentials.from_service_account_file(credentials_path)
        else:
            logger.info("Using default credentials (Cloud Run environment)")
            return None
    
    @property
    def current_stage(self) -> str:
        """Get current conversation stage."""
        return self.conversation_service.get_current_stage()
    
    @property
    def conversation_context(self):
        """Get conversation context."""
        return self.conversation_service.context
    
    def _get_session_history(self, session_id: str):
        """Get session history from LLM service."""
        return self.llm_service.get_session_history(session_id)
    
    def _create_prompt_for_stage(self, stage: str):
        """Create prompt template for stage."""
        return self.conversation_service.create_prompt_for_stage(stage)
    
    def _update_chain_for_stage(self, stage: str):
        """Update conversation stage."""
        self.conversation_service.set_stage(stage)
        logger.info(f"Updated conversation stage to: {stage}")
    
    async def _detect_stage_transition(self, user_input: str, ai_response: str) -> Optional[str]:
        """Detect stage transition."""
        return await self.conversation_service.detect_stage_transition(user_input, ai_response)
    
    async def _accumulate_problem_description(self, user_input: str):
        """Accumulate problem description."""
        await self.conversation_service.accumulate_problem_description(user_input)
    
    async def speech_to_text_continuous_stream(self, audio_generator) -> AsyncIterator[Tuple[str, bool]]:
        """
        Continuously stream audio to STT.
        Delegates to SpeechToTextService.
        
        Args:
            audio_generator: Async generator yielding audio chunks
        
        Yields:
            Tuple of (transcript, is_final)
        """
        async for transcript, is_final in self.stt_service.continuous_stream(audio_generator):
            yield (transcript, is_final)
    
    async def generate_llm_response_stream(self, prompt: str) -> AsyncIterator[str]:
        """
        Generate streaming response using LLM.
        Delegates to ResponseOrchestrator for stage-aware conversation flow.
        
        Args:
            prompt: User input prompt
        
        Yields:
            Response chunks as strings
        """
        async for chunk in self.response_orchestrator.generate_response_stream(
            prompt,
            self.session_id
        ):
            yield chunk
    
    async def text_to_speech_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Convert text to speech.
        Delegates to TextToSpeechService.
        
        Args:
            text: Text to synthesize
        
        Yields:
            Audio data chunks as bytes
        """
        async for chunk in self.tts_service.synthesize_stream(text, chunk_size=2048):
            yield chunk
    
    async def generate_greeting(self, user_name: str = "", has_open_request: bool = False) -> str:
        """
        Generate a natural, friendly greeting.
        Delegates to ConversationService.
        
        Args:
            user_name: User's name
            has_open_request: Whether user has an open request
        
        Returns:
            Greeting text
        """
        return await self.conversation_service.generate_greeting(
            session_id=self.session_id,
            user_name=user_name or USER_NAME_PLACEHOLDER,
            has_open_request=has_open_request
        )
    
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
