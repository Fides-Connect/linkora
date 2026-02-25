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

from .signaling_server import SignalingServer
from .common_endpoints import setup_cors
from .services.admin_service import AdminService
from .api.v1.router import register_v1_routes
from .weaviate_sync import run_startup_sync

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
    
    # Initialize Firebase Admin SDK using Application Default Credentials (WIF / Cloud Run ADC)
    logger.info("Initializing Firebase Admin SDK...")
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
            logger.info("Firebase Admin SDK initialized with Application Default Credentials")
        else:
            logger.info("Firebase Admin SDK already initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        logger.error("Firebase ID token verification will not work!")
        return
    
    # Log configuration
    logger.info("Configuration:")
    logger.info(f"  Firestore Database: {os.getenv('FIRESTORE_DATABASE_NAME', '(default)')}")
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
    
    # Sync Firestore → Weaviate (opt-in via WEAVIATE_SYNC_ON_STARTUP=true)
    await run_startup_sync()

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

    # Register v1 API routes
    register_v1_routes(app)
    
    # Register admin routes
    admin_service.register_routes(app)
    
    # Start server
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting AI Assistant server on {host}:{port}")
    logger.info(f"WebSocket endpoint: ws://{host}:{port}/ws")
    logger.info(f"Health check: http://{host}:{port}/health")
    logger.info(f"API v1: http://{host}:{port}/api/v1/")
    logger.info(f"Sign-In: http://{host}:{port}/api/v1/auth/sign-in-google")
    
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
