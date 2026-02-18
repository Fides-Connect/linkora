"""
WebRTC Signaling Server
Handles WebSocket connections and WebRTC signaling between client and AI assistant.
"""
import json
import logging
from typing import Dict
from aiohttp import web, WSMsgType
from aiortc import RTCSessionDescription

from .peer_connection_handler import PeerConnectionHandler

logger = logging.getLogger(__name__)


class SignalingServer:
    """Manages WebSocket connections and WebRTC signaling."""
    
    def __init__(self):
        self.active_connections: Dict[str, PeerConnectionHandler] = {}
        
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for signaling."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = id(ws)
        client_ip = request.remote
        
        # Extract user_id, language, and session mode from query parameters
        user_id = request.query.get('user_id')
        language = request.query.get('language', 'de')  # Default to German
        raw_mode = request.query.get('mode', 'voice')
        if raw_mode not in ('voice', 'text'):
            logger.warning(
                f"Invalid session mode '{raw_mode}' from {client_ip}; defaulting to 'voice'"
            )
            session_mode = 'voice'
        else:
            session_mode = raw_mode
        
        if user_id:
            logger.info(f"New WebSocket connection: {connection_id} from {client_ip} (user: {user_id}, language: {language}, mode: {session_mode})")
        else:
            logger.info(f"New WebSocket connection: {connection_id} from {client_ip} (no user_id, language: {language}, mode: {session_mode})")
        
        # Create peer connection handler
        logger.debug(f"Creating PeerConnectionHandler for {connection_id}")
        handler = PeerConnectionHandler(
            connection_id=str(connection_id),
            websocket=ws,
            user_id=user_id,
            language=language,
            session_mode=session_mode,
        )
        self.active_connections[str(connection_id)] = handler
        logger.debug(f"Active connections: {len(self.active_connections)}")
        
        try:
            logger.debug(f"Starting message loop for connection {connection_id}")
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        logger.debug(f"Received text message from {connection_id}: {msg.data[:100]}...")
                        data = json.loads(msg.data)
                        logger.debug(f"Parsed message type: {data.get('type')}")
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
            # Cleanup
            logger.info(f"WebSocket connection closed: {connection_id}")
            logger.debug(f"Cleaning up connection {connection_id}")
            await handler.close()
            del self.active_connections[str(connection_id)]
            logger.debug(f"Active connections after cleanup: {len(self.active_connections)}")
            
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
            'active_connections': len(self.active_connections)
        })
