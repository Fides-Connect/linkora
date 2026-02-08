#!/usr/bin/env python3
"""
AI Assistant Service
Provides WebRTC-based voice assistant functionality using Google Cloud services.
"""
import asyncio
import logging
import os
from aiohttp import web
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials

from .signaling_server import SignalingServer
from .common_endpoints import sign_in_google, setup_cors
from .user_endpoints import user_sync, user_logout
from .services.admin_service import AdminService
from . import app_endpoints

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""
    # Load environment variables
    load_dotenv()

    # Set log level from environment
    logging.getLogger().setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())
    
    logger.info("=" * 60)
    logger.info("AI Assistant Service Starting")
    logger.info("=" * 60)
    
    # Verify required environment variables
    required_vars = [
        'GEMINI_API_KEY'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    # GOOGLE_SERVICE_ACCOUNT_JSON_PATH is optional in Cloud Run
    credentials_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_PATH')
    if credentials_path and not os.path.exists(credentials_path):
        logger.warning(f"Credentials file not found: {credentials_path}, will use default credentials")
    
    # Initialize Firebase Admin SDK
    logger.info("Initializing Firebase Admin SDK...")
    try:
        if not firebase_admin._apps:
            # Use the same service account credentials for Firebase
            if credentials_path and os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin SDK initialized with credentials from {credentials_path}")
            else:
                # Use default credentials (works in Cloud Run)
                firebase_admin.initialize_app()
                logger.info("Firebase Admin SDK initialized with default credentials")
        else:
            logger.info("Firebase Admin SDK already initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        logger.error("Firebase ID token verification will not work!")
        return
    
    # Log configuration
    logger.info("Configuration:")
    logger.info(f"  Language DE: {os.getenv('LANGUAGE_CODE_DE', 'de-DE')}")
    logger.info(f"  Voice DE: {os.getenv('VOICE_NAME_DE', 'de-DE-Chirp3-HD-Sulafat')}")
    logger.info(f"  Language EN: {os.getenv('LANGUAGE_CODE_EN', 'en-US')}")
    logger.info(f"  Voice EN: {os.getenv('VOICE_NAME_EN', 'en-US-Chirp3-HD-Sulafat')}")
    logger.info(f"  Host: {os.getenv('HOST', '0.0.0.0')}")
    logger.info(f"  Port: {os.getenv('PORT', 8080)}")
    logger.info(f"  Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info(f"  Google TTS API Concurrency: {os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5')}")
    logger.info(f"  Debug Audio Record: {os.getenv('DEBUG_RECORD_AUDIO', 'false')}")
    logger.info(f"  LLM Model: {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}")
    logger.debug(f"  Credentials: {os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_PATH')}")
    
    # Initialize signaling server
    logger.info("Initializing signaling server...")
    signaling_server = SignalingServer()
    
    # Initialize admin service
    logger.info("Initializing admin service...")
    admin_service = AdminService(signaling_server=signaling_server)
    
    # Create web application
    app = web.Application()
    app.router.add_get('/ws', signaling_server.handle_websocket)
    app.router.add_get('/health', signaling_server.health_check)
    app.router.add_post('/sign_in_google', sign_in_google)
    app.router.add_post('/user/sync', user_sync)
    app.router.add_post('/user/logout', user_logout)

    # Register app endpoints
    app.router.add_get('/service_requests', app_endpoints.get_service_requests)
    app.router.add_post('/service_requests', app_endpoints.add_service_request)
    app.router.add_put('/service_requests/{service_request_id}/status', app_endpoints.update_service_request_status)
    app.router.add_get('/favorites', app_endpoints.get_favorites)
    app.router.add_post('/favorites/{user_id}', app_endpoints.add_favorite)
    app.router.add_delete('/favorites/{user_id}', app_endpoints.remove_favorite)
    app.router.add_get('/user', app_endpoints.get_user)
    app.router.add_put('/user', app_endpoints.update_user)
    app.router.add_post('/user/competencies', app_endpoints.add_competence)
    app.router.add_delete('/user/competencies/{competence_id}', app_endpoints.remove_competence)
    app.router.add_get('/users/{user_id}/user', app_endpoints.get_other_user)
    
    # Review routes
    app.router.add_post('/reviews', app_endpoints.create_review)
    app.router.add_get('/reviews/{review_id}', app_endpoints.get_review)
    app.router.add_get('/reviews/user/{user_id}', app_endpoints.get_reviews_for_user)
    app.router.add_get('/reviews/reviewer/{reviewer_user_id}', app_endpoints.get_reviews_by_reviewer)
    app.router.add_get('/reviews/service_request/{service_request_id}', app_endpoints.get_reviews_for_service_request)
    app.router.add_patch('/reviews/{review_id}', app_endpoints.update_review)
    app.router.add_delete('/reviews/{review_id}', app_endpoints.delete_review)
    
    # Chat routes
    app.router.add_post('/provider_candidates/{provider_candidate_id}/chats', app_endpoints.create_chat)
    app.router.add_get('/provider_candidates/{provider_candidate_id}/chats/{chat_id}', app_endpoints.get_chat)
    app.router.add_get('/service_requests/{service_request_id}/chats', app_endpoints.get_chats_for_service_request)
    app.router.add_get('/provider_candidates/{provider_candidate_id}/chats', app_endpoints.get_chats_for_provider_candidate)
    app.router.add_patch('/provider_candidates/{provider_candidate_id}/chats/{chat_id}', app_endpoints.update_chat)
    app.router.add_delete('/provider_candidates/{provider_candidate_id}/chats/{chat_id}', app_endpoints.delete_chat)
    
    # Chat message routes
    app.router.add_post('/provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages', app_endpoints.create_chat_message)
    app.router.add_get('/provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages', app_endpoints.get_chat_messages)
    app.router.add_get('/provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages/{chat_message_id}', app_endpoints.get_chat_message)
    app.router.add_patch('/provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages/{chat_message_id}', app_endpoints.update_chat_message)
    app.router.add_delete('/provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages/{chat_message_id}', app_endpoints.delete_chat_message)
    
    # Register admin routes
    admin_service.register_routes(app)
    
    # Start server
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting AI Assistant server on {host}:{port}")
    logger.info(f"WebSocket endpoint: ws://{host}:{port}/ws")
    logger.info(f"Health check: http://{host}:{port}/health")
    logger.info(f"Sign-In Google: http://{host}:{port}/sign_in_google")
    
    runner = web.AppRunner(app)
    setup_cors(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info("=" * 60)
    logger.info("AI Assistant server is running")
    logger.info("=" * 60)
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        logger.info("Cleanup started")
        await runner.cleanup()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
