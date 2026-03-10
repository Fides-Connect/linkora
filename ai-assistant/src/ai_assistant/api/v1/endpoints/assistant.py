"""
/api/v1/assistant/* endpoints
AI Assistant utility endpoints (e.g. greeting pre-generation / warmup).
"""
import logging
import os
from aiohttp import web

from ai_assistant.api.deps import get_current_user_id
from ai_assistant.firestore_service import FirestoreService
from ai_assistant.ai_assistant import get_language_config, AGENT_NAME, COMPANY_NAME
from ai_assistant.data_provider import get_data_provider
from ai_assistant.services.greeting_cache import get_greeting_cache
from ai_assistant.services.conversation_service import ConversationService
from ai_assistant.services.llm_service import LLMService
from ai_assistant.services.text_to_speech_service import TextToSpeechService

logger = logging.getLogger(__name__)
_firestore_service = FirestoreService()


async def greet_warmup(request: web.Request) -> web.Response:
    """POST /api/v1/assistant/greet-warmup

    Pre-generates the personalised greeting for the authenticated user and
    caches the LLM text + TTS audio for up to 2 minutes.

    When a voice session starts within this window, ``VoiceSessionStarter``
    uses the cached audio immediately — eliminating the LLM + TTS latency
    (~1.5–2.5 s) from the tap-to-greeting path.

    The user's language is read from Firestore (``user_app_settings.language``)
    so no request body is needed.

    Response:
        {"ready": true, "greeting_text": "..."}
    """
    try:
        user_id = await get_current_user_id(request)

        # Fetch user profile from Firestore.
        user = await _firestore_service.get_user(user_id)
        user_name = ""
        has_open_request = False
        language = "en"
        if user:
            raw_name = user.get("name", "")
            user_name = raw_name.split()[0] if raw_name else ""
            has_open_request = bool(user.get("has_open_request", False))
            stored_lang = user.get("user_app_settings", {}).get("language", "en")
            if isinstance(stored_lang, str) and stored_lang.strip().lower() in ("de", "en"):
                language = stored_lang.strip().lower()

        # Build language-specific service instances (lightweight, no shared state).
        language_code, voice_name = get_language_config(language)
        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

        llm_service = LLMService(
            api_key=gemini_api_key,
            model=gemini_model,
            temperature=0.2,
            max_output_tokens=512,
        )
        conv_service = ConversationService(
            llm_service=llm_service,
            data_provider=get_data_provider(),
            agent_name=AGENT_NAME,
            company_name=COMPANY_NAME,
            language=language,
        )

        # Generate greeting text via LLM.
        greeting_text = await conv_service.generate_greeting_text(
            user_name=user_name,
            has_open_request=has_open_request,
        )

        # Synthesise TTS audio.  Build a short-lived service and always close
        # its gRPC transport afterwards to avoid leaking open channels.
        max_concurrency = int(os.getenv("GOOGLE_TTS_API_CONCURRENCY", "5"))
        tts_service = TextToSpeechService(
            language_code=language_code,
            voice_name=voice_name,
            max_concurrent_requests=max_concurrency,
        )
        audio_bytes = b""
        try:
            audio_chunks: list[bytes] = []
            async for chunk in tts_service.synthesize_stream(greeting_text, chunk_size=2048):
                if chunk:
                    audio_chunks.append(chunk)
            audio_bytes = b"".join(audio_chunks)
        finally:
            await tts_service.client.transport.close()

        # Store in the process-wide cache.
        get_greeting_cache().store(user_id, language, greeting_text, audio_bytes)

        logger.info(
            "Greeting pre-generated for user=%s lang=%s (%d audio bytes)",
            user_id,
            language,
            len(audio_bytes),
        )
        return web.json_response({"ready": True, "greeting_text": greeting_text})

    except web.HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in greet_warmup: %s", exc, exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)
