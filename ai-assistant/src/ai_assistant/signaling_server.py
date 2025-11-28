"""
WebRTC Signaling Server
Handles WebSocket connections and WebRTC signaling between client and AI assistant.
"""
import asyncio
import json
import logging
import time
from typing import Dict
from aiohttp import web, WSMsgType
from aiortc import RTCSessionDescription

from .peer_connection_handler import PeerConnectionHandler
from .definitions import HEARTBEAT_INTERVAL, CONNECTION_TIMEOUT, IDLE_TIMEOUT

logger = logging.getLogger(__name__)


class SignalingServer:
    """Manages WebSocket connections and WebRTC signaling."""
    
    def __init__(self, gemini_api_key: str, language_code: str = 'de-DE', voice_name: str = 'de-DE-Chirp3-HD-Sulafat'):
        # Store config for creating per-user AI assistants
        self.gemini_api_key = gemini_api_key
        self.language_code = language_code
        self.voice_name = voice_name
        
        # Track active connections
        self.active_connections: Dict[str, PeerConnectionHandler] = {}
        
        # Track per-user AI assistant instances
        self.user_assistants: Dict[str, 'AIAssistant'] = {}
        
        # Heartbeat and idle timeout settings
        self.heartbeat_interval = HEARTBEAT_INTERVAL
        self.idle_timeout = IDLE_TIMEOUT
        self.connection_timeout = CONNECTION_TIMEOUT
        
        # Track last activity time per user
        self.user_last_activity: Dict[str, float] = {}
        
        # Background cleanup task
        self._cleanup_task = None
    
    async def start(self):
        """Start background tasks."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("Started periodic cleanup task")
    
    async def stop(self):
        """Stop background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped periodic cleanup task")
    
    async def _periodic_cleanup(self):
        """Periodically cleanup idle AIAssistant instances."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle_assistants()
            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
    
    async def _cleanup_idle_assistants(self):
        """Remove AIAssistant instances that have been idle too long."""
        current_time = time.time()
        idle_users = []
        
        for user_id, last_activity in list(self.user_last_activity.items()):
            # Check if user has no active connections and has been idle
            user_has_connections = any(
                conn.user_id == user_id 
                for conn in self.active_connections.values()
            )
            
            if not user_has_connections:
                idle_duration = current_time - last_activity
                if idle_duration > self.idle_timeout:
                    idle_users.append(user_id)
        
        for user_id in idle_users:
            logger.info(f"Cleaning up idle AIAssistant for user {user_id} (idle for {current_time - self.user_last_activity[user_id]:.0f}s)")
            self.cleanup_user_assistant(user_id, clear_persistent=False)
            del self.user_last_activity[user_id]
        
        if idle_users:
            logger.info(f"Cleaned up {len(idle_users)} idle AIAssistant instances")
    
    def _update_user_activity(self, user_id: str):
        """Update last activity timestamp for a user."""
        self.user_last_activity[user_id] = time.time()
    
    async def _heartbeat_loop(self, ws: web.WebSocketResponse, handler: PeerConnectionHandler, user_id: str):
        """Send periodic ping messages and check for stale connections."""
        try:
            while not ws.closed:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Check if connection is stale (no pong received)
                time_since_pong = time.time() - handler.last_pong
                if time_since_pong > self.connection_timeout:
                    logger.warning(f"Connection {handler.connection_id} is stale (no pong for {time_since_pong:.0f}s), closing")
                    await ws.close()
                    break
                
                # Send ping
                try:
                    await ws.send_json({'type': 'ping', 'timestamp': time.time()})
                    logger.debug(f"Sent ping to connection {handler.connection_id}")
                except Exception as e:
                    logger.error(f"Failed to send ping to {handler.connection_id}: {e}")
                    break
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat loop cancelled for {handler.connection_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop for {handler.connection_id}: {e}", exc_info=True)
    
    def cleanup_user_assistant(self, user_id: str, clear_persistent: bool = False) -> bool:
        """Clean up AIAssistant instance for a user.
        
        This removes the user's conversation history.
        Typically called on explicit logout or after prolonged inactivity.
        
        Returns True if assistant was removed, False if not found.
        """
        if user_id in self.user_assistants:
            logger.info(f"Cleaning up AIAssistant for user: {user_id}")
            assistant = self.user_assistants.pop(user_id)
            try:
                assistant.clear_conversation_history(clear_persistent=clear_persistent)
            except AttributeError:
                logger.debug("Assistant for %s does not expose clear_conversation_history", user_id)
            return True
        return False
        
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for signaling.
        
        Query params:
        - user_id: Firebase user ID (optional, for authenticated connections)
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = id(ws)
        client_ip = request.remote
        
        # Extract user_id from query params if provided
        user_id = request.query.get('user_id') or 'anonymous'
        
        if user_id != 'anonymous':
            logger.info(f"New authenticated WebSocket connection: {connection_id} from {client_ip} (user_id: {user_id})")
        else:
            logger.info(f"New anonymous WebSocket connection: {connection_id} from {client_ip}")
        
        # Get or create AI assistant for this user
        if user_id not in self.user_assistants:
            logger.info(f"Creating new AIAssistant instance for user: {user_id}")
            from .ai_assistant import AIAssistant
            self.user_assistants[user_id] = AIAssistant(
                gemini_api_key=self.gemini_api_key,
                language_code=self.language_code,
                voice_name=self.voice_name,
                user_id=user_id
            )
        else:
            logger.debug(f"Reusing existing AIAssistant instance for user: {user_id}")
        
        user_assistant = self.user_assistants[user_id]
        
        # Update user activity timestamp
        self._update_user_activity(user_id)
        
        # Create peer connection handler with user-specific AI assistant
        logger.debug(f"Creating PeerConnectionHandler for {connection_id}")
        handler = PeerConnectionHandler(
            connection_id=str(connection_id),
            ai_assistant=user_assistant,
            websocket=ws,
            user_id=user_id
        )
        self.active_connections[str(connection_id)] = handler
        handler.last_pong = time.time()  # Initialize pong timestamp
        logger.debug(f"Active connections: {len(self.active_connections)}, Unique users: {len(self.user_assistants)}")
        
        # Start heartbeat task for this connection
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws, handler, user_id))
        
        try:
            logger.debug(f"Starting message loop for connection {connection_id}")
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        logger.debug(f"Received text message from {connection_id}: {msg.data[:100]}...")
                        data = json.loads(msg.data)
                        msg_type = data.get('type')
                        logger.debug(f"Parsed message type: {msg_type}")
                        
                        # Update activity on any message
                        self._update_user_activity(user_id)
                        
                        # Handle pong responses
                        if msg_type == 'pong':
                            handler.last_pong = time.time()
                            logger.debug(f"Received pong from {connection_id}")
                        else:
                            await self._handle_message(handler, data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON received from {connection_id}: {e}")
                        logger.debug(f"Raw data: {msg.data}")
                    except Exception as e:
                        logger.error(f"Error handling message from {connection_id}: {e}", exc_info=True)
                        
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error for {connection_id}: {ws.exception()}")
                    
                elif msg.type == WSMsgType.CLOSE:
                    logger.info(f"Client {connection_id} initiated close")
                    
        finally:
            # Cancel heartbeat task
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            
            # Cleanup
            logger.info(f"WebSocket connection closed: {connection_id}")
            logger.debug(f"Cleaning up connection {connection_id}")
            await handler.close()
            
            # Remove connection
            if str(connection_id) in self.active_connections:
                del self.active_connections[str(connection_id)]
            
            # Check if user has any remaining connections
            if user_id != 'anonymous':
                user_has_connections = any(
                    conn.user_id == user_id 
                    for conn in self.active_connections.values()
                )
                
                # Optionally clean up user assistant if no connections remain
                # Comment out if you want to keep conversation history across reconnections
                # if not user_has_connections and user_id in self.user_assistants:
                #     logger.info(f"No remaining connections for user {user_id}, cleaning up AIAssistant")
                #     del self.user_assistants[user_id]
                
                if not user_has_connections:
                    logger.debug(f"User {user_id} has no remaining active connections (keeping AIAssistant for history)")
            
            logger.debug(f"Active connections after cleanup: {len(self.active_connections)}, Unique users: {len(self.user_assistants)}")
            
        return ws
    
    async def _handle_message(self, handler: PeerConnectionHandler, data: dict):
        """Handle signaling messages."""
        msg_type = data.get('type')
        logger.debug(f"Handling message type '{msg_type}' for connection {handler.connection_id}")
        
        if msg_type == 'offer':
            logger.debug(f"Processing offer (SDP length: {len(data.get('sdp', ''))})")
            # Receive WebRTC offer from client
            offer = RTCSessionDescription(
                sdp=data['sdp'],
                type=data['type']
            )
            await handler.handle_offer(offer)
            
        elif msg_type == 'ice-candidate':
            # Receive ICE candidate from client
            candidate = data.get('candidate')
            if candidate:
                logger.debug(f"Processing ICE candidate")
                await handler.handle_ice_candidate(candidate)
            else:
                logger.warning(f"Received ice-candidate message without candidate data")
                
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            'status': 'healthy',
            'active_connections': len(self.active_connections),
            'unique_users': len(self.user_assistants)
        })
    
    async def get_stats(self, request: web.Request) -> web.Response:
        """Get detailed server statistics."""
        # Group connections by user
        connections_by_user = {}
        for conn_id, handler in self.active_connections.items():
            user_id = handler.user_id or 'anonymous'
            if user_id not in connections_by_user:
                connections_by_user[user_id] = []
            connections_by_user[user_id].append(conn_id)
        
        return web.json_response({
            'total_connections': len(self.active_connections),
            'unique_users': len(self.user_assistants),
            'connections_by_user': {
                user_id: len(conns) 
                for user_id, conns in connections_by_user.items()
            },
            'authenticated_users': len([u for u in self.user_assistants.keys() if u != 'anonymous']),
            'anonymous_connections': len(connections_by_user.get('anonymous', []))
        })
