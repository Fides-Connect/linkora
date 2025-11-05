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

from .signaling_server import SignalingServer
from .ai_assistant import AIAssistant

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
    
    # Verify required environment variables
    required_vars = [
        'GOOGLE_APPLICATION_CREDENTIALS',
        'GEMINI_API_KEY'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    # Initialize AI Assistant
    ai_assistant = AIAssistant(
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        language_code=os.getenv('LANGUAGE_CODE', 'de-DE'),
        voice_name=os.getenv('VOICE_NAME', 'de-DE-Wavenet-F')
    )
    
    # Initialize signaling server
    signaling_server = SignalingServer(ai_assistant)
    
    # Create web application
    app = web.Application()
    app.router.add_get('/ws', signaling_server.handle_websocket)
    app.router.add_get('/health', signaling_server.health_check)
    
    # Start server
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting AI Assistant server on {host}:{port}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info("AI Assistant server is running")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
