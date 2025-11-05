"""
WebRTC Signaling Server
Handles WebSocket connections and WebRTC signaling between client and AI assistant.
"""
import asyncio
import json
import logging
from typing import Dict, Set
from aiohttp import web, WSMsgType
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaStreamTrack

from peer_connection_handler import PeerConnectionHandler

logger = logging.getLogger(__name__)


class SignalingServer:
    """Manages WebSocket connections and WebRTC signaling."""
    
    def __init__(self, ai_assistant):
        self.ai_assistant = ai_assistant
        self.active_connections: Dict[str, PeerConnectionHandler] = {}
        
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for signaling."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = id(ws)
        logger.info(f"New WebSocket connection: {connection_id}")
        
        # Create peer connection handler
        handler = PeerConnectionHandler(
            connection_id=str(connection_id),
            ai_assistant=self.ai_assistant,
            websocket=ws
        )
        self.active_connections[str(connection_id)] = handler
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(handler, data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {msg.data}")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}", exc_info=True)
                        
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    
        finally:
            # Cleanup
            logger.info(f"WebSocket connection closed: {connection_id}")
            await handler.close()
            del self.active_connections[str(connection_id)]
            
        return ws
    
    async def _handle_message(self, handler: PeerConnectionHandler, data: dict):
        """Handle signaling messages."""
        msg_type = data.get('type')
        
        if msg_type == 'offer':
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
                await handler.handle_ice_candidate(candidate)
                
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            'status': 'healthy',
            'active_connections': len(self.active_connections)
        })
