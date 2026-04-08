"""
AI Assistant
Core orchestration layer that coordinates services.
"""
import inspect
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from .services import (
    SpeechToTextService,
    TextToSpeechService,
    LLMService,
    ConversationService,
    AgentRuntimeFSM,
    build_default_registry,
)
from .services.agent_profile import get_profile
from .services.response_orchestrator import ResponseOrchestrator
from .services.competence_enricher import CompetenceEnricher
from .services.cross_encoder_service import CrossEncoderService
from .services.google_places_service import GooglePlacesService
from .data_provider import get_data_provider

logger = logging.getLogger(__name__)

# Constants
AGENT_NAME = "Elin"
COMPANY_NAME = "LinkoraConnect"
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
                 session_id: str | None = None) -> None:
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

        # Resolve agent profile from AGENT_MODE env var (default: full)
        mode = os.getenv("AGENT_MODE", "full").lower().strip()
        profile = get_profile(mode)
        self._profile = profile

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
            max_output_tokens=512,
            language=self.language,
        )

        # Cross-encoder reranker: lazy-loading sentence-transformers model.
        # Initialized before ConversationService so it can be injected.
        self.cross_encoder_service = CrossEncoderService()

        # Google Places enrichment — active only in lite mode (profile.google_places_always_active=True).
        # In full mode this is always None; Google Places is never queried.
        self.google_places_service = (
            GooglePlacesService(llm_service=self.llm_service)
            if profile.google_places_always_active and GooglePlacesService.is_enabled()
            else None
        )

        self.conversation_service = ConversationService(
            llm_service=self.llm_service,
            data_provider=self.data_provider,
            agent_name=AGENT_NAME,
            company_name=COMPANY_NAME,
            max_providers=profile.max_providers,
            language=self.language,
            cross_encoder_service=self.cross_encoder_service,
            google_places_service=self.google_places_service,
            profile=profile,
        )

        # Build agentic runtime FSM and tool registry
        self.runtime_fsm = AgentRuntimeFSM()
        self.firestore_service = None  # injected by PeerConnectionHandler after construction
        self.tool_registry = build_default_registry(allowed_tools=profile.available_tool_names)

        # Competence enricher: LLM-powered enrichment of provider competence data.
        # Uses the same underlying LLM instance (no extra API key needed).
        self.competence_enricher = CompetenceEnricher(llm=self.llm_service.llm)  # type: ignore[arg-type]

        # Initialize orchestration services
        self.response_orchestrator = ResponseOrchestrator(
            llm_service=self.llm_service,
            conversation_service=self.conversation_service,
            runtime_fsm=self.runtime_fsm,
            tool_registry=self.tool_registry,
            profile=profile,
        )

        logger.info("AI Assistant initialized with service-oriented architecture")

    async def aclose(self) -> None:
        """Close all underlying Google API connections for graceful shutdown."""
        await self.llm_service.aclose()
        # Google Cloud gapic-generated async clients (SpeechAsyncClient,
        # TextToSpeechAsyncClient) don't expose close() on the client itself —
        # it lives on client.transport.  We use getattr chains so this stays
        # correct if a future SDK version moves or adds a direct close().
        for label, client in [
            ("STT", self.stt_service.client),
            ("TTS", self.tts_service.client),
        ]:
            try:
                close_fn = getattr(client, "close", None)
                if close_fn is None:
                    transport = getattr(client, "transport", None)
                    close_fn = getattr(transport, "close", None) if transport is not None else None
                if not callable(close_fn):
                    logger.debug("AIAssistant.aclose: %s client has no close(); skipping.", label)
                    continue
                result = close_fn()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logger.warning(
                    "AIAssistant.aclose: error closing %s client: %s",
                    label, exc, exc_info=True,
                )

    async def generate_llm_response_stream(
        self, prompt: str, user_id: str | None = None
    ) -> AsyncIterator[str | dict[str, Any]]:
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
            "competence_enricher": self.competence_enricher,
            "cross_encoder_service": self.cross_encoder_service,
        }
        async for chunk in self.response_orchestrator.generate_response_stream(
            prompt, self.session_id, context=context
        ):
            yield chunk


