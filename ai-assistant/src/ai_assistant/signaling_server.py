"""
Signaling Server: Manages WebSocket connections and WebRTC signaling using service pattern.
"""
import asyncio
import logging
from aiohttp import web

from .peer_connection_handler import PeerConnectionHandler
from .ai_assistant import AIAssistant
from .definitions import HEARTBEAT_INTERVAL, CONNECTION_TIMEOUT, IDLE_TIMEOUT, WATCHDOG_CHECK_INTERVAL

from .services.websocket_manager import WebSocketConnectionManager
from .services.user_session_manager import UserSessionManager
from .services.webrtc_signaling import WebRTCSignalingHandler
from .services.connection_registry import ConnectionRegistry

logger = logging.getLogger(__name__)


class SignalingServer:
    """
    WebRTC signaling server using service-oriented architecture.
    
    Coordinates between:
    - WebSocket connection management
    - User session management
    - Connection registry
    - WebRTC signaling
    """

    def __init__(
        self,
        gemini_api_key: str,
        language_code: str = 'de-DE',
        voice_name: str = 'de-DE-Chirp3-HD-Sulafat'
    ):
        """
        Initialize signaling server.
        
        Args:
            gemini_api_key: API key for Gemini LLM
            language_code: Language code for STT/TTS
            voice_name: Voice name for TTS
        """
        # Configuration for AI assistants
        self.gemini_api_key = gemini_api_key
        self.language_code = language_code
        self.voice_name = voice_name

        # Timeout settings
        self.heartbeat_interval = HEARTBEAT_INTERVAL
        self.idle_timeout = IDLE_TIMEOUT
        self.connection_timeout = CONNECTION_TIMEOUT

        # Initialize services
        self.connection_registry = ConnectionRegistry()
        self.user_session_manager = UserSessionManager(
            assistant_factory=self._create_assistant,
            idle_timeout=self.idle_timeout,
            cleanup_interval=WATCHDOG_CHECK_INTERVAL
        )

        # Background cleanup task
        self._cleanup_task = None

    # Compatibility properties for tests
    @property
    def active_connections(self):
        """Compatibility property for accessing connection registry."""
        return self.connection_registry.active_connections

    @property
    def user_assistants(self):
        """Compatibility property for accessing user session manager."""
        return self.user_session_manager.user_assistants

    def _create_assistant(self, user_id: str) -> AIAssistant:
        """Factory method to create AI assistant instances."""
        return AIAssistant(
            gemini_api_key=self.gemini_api_key,
            language_code=self.language_code,
            voice_name=self.voice_name,
            user_id=user_id
        )

    async def start(self):
        """Start background tasks."""
        await self.user_session_manager.start()

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("Started periodic cleanup task")

    async def stop(self):
        """Stop background tasks."""
        await self.user_session_manager.stop()

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped periodic cleanup task")

    async def _periodic_cleanup(self):
        """Periodically cleanup idle resources."""
        while True:
            try:
                await asyncio.sleep(WATCHDOG_CHECK_INTERVAL)
                self.user_session_manager.cleanup_idle_users(
                    self.connection_registry.has_user_connections
                )
            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}", exc_info=True)

    def cleanup_user_assistant(self, user_id: str, clear_persistent: bool = False) -> bool:
        """
        Clean up AIAssistant instance for a user.
        
        Args:
            user_id: User identifier
            clear_persistent: Whether to clear persistent history
            
        Returns:
            True if assistant was removed, False if not found
        """
        return self.user_session_manager.cleanup_user(user_id, clear_persistent)

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """
        Handle WebSocket connection for signaling.
        
        Args:
            request: aiohttp Request with optional user_id query param
            
        Returns:
            WebSocketResponse
        """
        # Prepare WebSocket
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        connection_id = str(id(ws))
        user_id = request.query.get('user_id') or 'anonymous'
        client_ip = request.remote

        logger.info(
            f"New WebSocket connection: {connection_id} from {client_ip} "
            f"(user: {user_id})"
        )

        # Create WebSocket manager
        ws_manager = WebSocketConnectionManager(
            ws,
            connection_id,
            self.heartbeat_interval,
            self.connection_timeout
        )

        # Get or create user assistant
        user_assistant = self.user_session_manager.get_or_create_assistant(user_id)

        # Create peer connection handler
        peer_handler = PeerConnectionHandler(
            connection_id=connection_id,
            ai_assistant=user_assistant,
            websocket=ws,
            user_id=user_id
        )

        # Register connection
        self.connection_registry.register(connection_id, peer_handler)

        # Start heartbeat
        await ws_manager.start_heartbeat()

        try:
            # Handle messages
            await ws_manager.receive_messages(
                lambda msg: self._handle_signaling_message(peer_handler, msg, user_id)
            )

        finally:
            # Cleanup
            await self._cleanup_connection(ws_manager, peer_handler, connection_id, user_id)

        return ws

    async def _handle_signaling_message(self, peer_handler, message: dict, user_id: str):
        """Handle signaling message and update user activity."""
        self.user_session_manager.update_activity(user_id)
        await WebRTCSignalingHandler.route_message(peer_handler, message)

    async def _cleanup_connection(
        self,
        ws_manager: WebSocketConnectionManager,
        peer_handler: PeerConnectionHandler,
        connection_id: str,
        user_id: str
    ):
        """Clean up connection resources."""
        logger.info(f"Cleaning up connection {connection_id}")

        # Stop heartbeat
        await ws_manager.stop_heartbeat()

        # Close peer connection
        await peer_handler.close()

        # Unregister connection
        self.connection_registry.unregister(connection_id)

        # Log status
        if user_id != 'anonymous':
            has_connections = self.connection_registry.has_user_connections(user_id)
            if not has_connections:
                logger.debug(
                    f"User {user_id} has no remaining connections "
                    f"(keeping assistant for history)"
                )

        logger.debug(
            f"Active connections: {self.connection_registry.count()}, "
            f"Unique users: {len(self.user_session_manager.user_assistants)}"
        )

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            'status': 'healthy',
            'active_connections': self.connection_registry.count(),
            'unique_users': len(self.user_session_manager.user_assistants)
        })

    async def get_stats(self, request: web.Request) -> web.Response:
        """Get detailed server statistics."""
        conn_stats = self.connection_registry.get_stats()
        session_stats = self.user_session_manager.get_stats()

        return web.json_response({
            **conn_stats,
            **session_stats
        })

    # Backward compatibility properties and methods for tests
    @property
    def active_connections(self):
        """Backward compatibility property for tests"""
        return self.connection_registry.active_connections
    
    @property
    def user_assistants(self):
        """Backward compatibility property for tests"""
        return self.user_session_manager.user_assistants
    
    @property
    def user_last_activity(self):
        """Backward compatibility property for tests"""
        return self.user_session_manager.user_last_activity
    
    def _update_user_activity(self, user_id: str):
        """Backward compatibility method for tests"""
        self.user_session_manager.update_activity(user_id)
