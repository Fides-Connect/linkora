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
from .ai_assistant import AIAssistant
from .common_endpoints import sign_in_google, user_sync, user_logout, set_signaling_server, setup_cors

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
    
    # GOOGLE_APPLICATION_CREDENTIALS is optional in Cloud Run
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
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
    logger.info(f"  Language: {os.getenv('LANGUAGE_CODE', 'de-DE')}")
    logger.info(f"  Voice: {os.getenv('VOICE_NAME', 'de-DE-Chirp3-HD-Sulafat')}")
    logger.info(f"  Host: {os.getenv('HOST', '0.0.0.0')}")
    logger.info(f"  Port: {os.getenv('PORT', 8080)}")
    logger.info(f"  Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info(f"  Google TTS API Concurrency: {os.getenv('GOOGLE_TTS_API_CONCURRENCY', '5')}")
    logger.info(f"  Debug Audio Record: {os.getenv('DEBUG_RECORD_AUDIO', 'false')}")
    logger.debug(f"  Credentials: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
    
    # Initialize signaling server (creates AI assistants per user)
    logger.info("Initializing signaling server...")
    signaling_server = SignalingServer(
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        language_code=os.getenv('LANGUAGE_CODE', 'de-DE'),
        voice_name=os.getenv('VOICE_NAME', 'de-DE-Chirp3-HD-Sulafat')
    )
    
    # Set signaling server reference for logout cleanup
    set_signaling_server(signaling_server)
    
    # Start background cleanup task
    await signaling_server.start()
    
    # Create web application
    app = web.Application()
    app.router.add_get('/ws', signaling_server.handle_websocket)
    app.router.add_get('/health', signaling_server.health_check)
    app.router.add_get('/stats', signaling_server.get_stats)
    app.router.add_post('/sign_in_google', sign_in_google)
    app.router.add_post('/user/sync', user_sync)
    app.router.add_post('/user/logout', user_logout)
    
    # Start server
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting AI Assistant server on {host}:{port}")
    logger.info(f"WebSocket endpoint: ws://{host}:{port}/ws")
    logger.info(f"Health check: http://{host}:{port}/health")
    logger.info(f"Stats: http://{host}:{port}/stats")
    logger.info(f"Sign-In Google: http://{host}:{port}/sign_in_google")
    logger.info(f"User Sync: http://{host}:{port}/user/sync")
    logger.info(f"User Logout: http://{host}:{port}/user/logout")
    
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
        await signaling_server.stop()
        await runner.cleanup()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
