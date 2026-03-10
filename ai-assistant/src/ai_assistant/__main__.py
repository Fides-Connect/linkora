#!/usr/bin/env python3
"""
AI Assistant Service
Provides WebRTC-based voice assistant functionality using Google Cloud services.
"""
import asyncio
import inspect
import logging
import os
import sys
import warnings

# ── Python 3.14 compatibility patches (applied before any third-party imports) ─
#
# LangChain calls asyncio.iscoroutinefunction() on every streaming request.
# In Python 3.14 that function is a deprecated wrapper around
# inspect.iscoroutinefunction() that emits a DeprecationWarning on every
# invocation.  Replacing it process-wide with the non-deprecated equivalent
# eliminates the per-call warning overhead for all LLMService instances.
# The guard ensures no-op on Python 3.11/3.12/3.13 where the two functions
# are already equivalent and asyncio does not yet emit the warning.
if sys.version_info >= (3, 14):
    asyncio.iscoroutinefunction = inspect.iscoroutinefunction  # type: ignore[attr-defined]

# google-genai re-defines AiohttpClientSession (an aiohttp.ClientSession
# subclass) inside a factory function, so aiohttp emits its "Inheritance …
# is discouraged" warning on each new API-client creation.  This is purely
# cosmetic — suppress it.
warnings.filterwarnings(
    "ignore",
    message=r"Inheritance class .+ from ClientSession is discouraged",
    category=DeprecationWarning,
)

from aiohttp import web
from dotenv import load_dotenv
import firebase_admin

from .signaling_server import SignalingServer
from .common_endpoints import setup_cors
from .services.admin_service import AdminService
from .api.v1.router import register_v1_routes
from .weaviate_sync import run_startup_sync
from .services.llm_service import LLMService
from .hub_spoke_schema import HubSpokeConnection

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
    logger.info(f"  LLM Model: {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite')}")
    
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

    # Suppress the expected aiortc background-task ConnectionError that fires
    # when RTCSctpTransport._data_channel_flush tries to send after the DTLS
    # transport is already torn down.  This is a benign race inside aiortc
    # during WebRTC teardown and does not affect correctness.
    # We narrow suppression to the known aiortc message to avoid hiding real
    # connection failures (e.g. outbound HTTP, Weaviate).
    _orig_exc_handler = asyncio.get_running_loop().get_exception_handler()
    _AIORTC_CONN_ERR_MSG = "Cannot send encrypted data, not connected"

    def _task_exc_handler(lp: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if isinstance(exc, ConnectionError) and _AIORTC_CONN_ERR_MSG in str(exc):
            return
        if _orig_exc_handler is not None:
            _orig_exc_handler(lp, context)
        else:
            lp.default_exception_handler(context)

    asyncio.get_running_loop().set_exception_handler(_task_exc_handler)

    # Fire-and-forget: prime LangChain internals so the first real user
    # utterance doesn't pay the one-time initialisation cost.
    prewarm_llm = LLMService(
        api_key=os.getenv('GEMINI_API_KEY', ''),
        model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite'),
    )
    prewarm_task = asyncio.create_task(prewarm_llm.prewarm())

    def _on_prewarm_done(task: asyncio.Task) -> None:
        """Consume the result so unhandled-exception warnings are never emitted."""
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logger.warning(
                    "LLM prewarm failed: %s",
                    exc,
                    exc_info=(type(exc), exc, exc.__traceback__),
                )

    prewarm_task.add_done_callback(_on_prewarm_done)

    # Keep running until cancelled (Ctrl+C via asyncio.run triggers CancelledError,
    # not KeyboardInterrupt, so we catch both defensively).
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Cleanup started")
        # Cancel prewarm if it never finished (e.g. Ctrl+C during startup).
        if not prewarm_task.done():
            prewarm_task.cancel()
            try:
                await prewarm_task
            except asyncio.CancelledError:
                pass
        # Close all active WebRTC/WebSocket connections before stopping the
        # HTTP server.  Without this, runner.cleanup() blocks indefinitely
        # waiting for open WebSocket handlers to finish, requiring the user
        # to press Ctrl+C multiple times.
        try:
            await asyncio.wait_for(signaling_server.close_all_connections(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out waiting for close_all_connections(); "
                "some WebSocket connections may still be open."
            )
        # Close the Weaviate connection before stopping the HTTP server.
        try:
            HubSpokeConnection.close()
        except Exception:
            logger.warning(
                "Failed to close HubSpokeConnection; continuing shutdown anyway.",
                exc_info=True,
            )
        try:
            await asyncio.wait_for(runner.cleanup(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.error(
                "Timed out waiting for runner.cleanup(); "
                "aborting to prevent hanging indefinitely."
            )
            raise
        # Close the google-genai async HTTP connection pool opened by the prewarm call
        await prewarm_llm.aclose()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
