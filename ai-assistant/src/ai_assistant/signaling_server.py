"""
WebRTC Signaling Server
Handles WebSocket connections and WebRTC signaling between client and AI assistant.
"""
import asyncio
import json
import logging
import os
import time
from typing import Dict
import aiohttp
from aiohttp import web, WSMsgType
from aiortc import RTCSessionDescription
from firebase_admin import auth as firebase_auth

from .peer_connection_handler import PeerConnectionHandler

logger = logging.getLogger(__name__)

_DEFAULT_ICE_SERVERS: list[dict] = [{"urls": "stun:stun.l.google.com:19302"}]

# Module-level TTL cache for ICE servers — Metered.ca credentials are valid
# for ~1 day, so we cache for 5 minutes to amortise per-connection latency.
_ICE_CACHE: list[dict] | None = None
_ICE_CACHE_TIMESTAMP: float = 0.0
_ICE_CACHE_TTL: float = 300.0  # seconds
_ICE_CACHE_LOCK: asyncio.Lock | None = None


def _get_ice_cache_lock() -> asyncio.Lock:
    """Return (creating if needed) the module-level asyncio.Lock for the ICE cache."""
    global _ICE_CACHE_LOCK
    if _ICE_CACHE_LOCK is None:
        _ICE_CACHE_LOCK = asyncio.Lock()
    return _ICE_CACHE_LOCK


async def _fetch_ice_servers() -> list[dict]:
    """Fetch ephemeral TURN credentials from Metered.ca with a 5-minute TTL cache.

    Requires ``METERED_APP_NAME`` and ``METERED_API_KEY`` environment variables.
    Falls back to a plain STUN server when either is absent or the request
    fails, so the service degrades gracefully in development.
    """
    global _ICE_CACHE, _ICE_CACHE_TIMESTAMP
    async with _get_ice_cache_lock():
        if _ICE_CACHE is not None and (time.monotonic() - _ICE_CACHE_TIMESTAMP) < _ICE_CACHE_TTL:
            logger.debug("Returning cached ICE servers (%d entry(s))", len(_ICE_CACHE))
            return _ICE_CACHE

        app_name = os.getenv("METERED_APP_NAME")
        api_key = os.getenv("METERED_API_KEY")
        if not app_name or not api_key:
            logger.debug("METERED_APP_NAME/METERED_API_KEY not set — using default STUN server")
            return _DEFAULT_ICE_SERVERS
        url = f"https://{app_name}.metered.live/api/v1/turn/credentials?apiKey={api_key}"
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        servers = await resp.json()
                        if servers:
                            logger.debug("Fetched %d ICE server(s) from Metered.ca", len(servers))
                            _ICE_CACHE = servers
                            _ICE_CACHE_TIMESTAMP = time.monotonic()
                            return _ICE_CACHE
                    else:
                        logger.warning(
                            "Metered.ca returned status %d — using default STUN", resp.status
                        )
        except Exception as exc:
            logger.warning("Failed to fetch TURN credentials: %s — using default STUN", exc)
        return _DEFAULT_ICE_SERVERS


class SignalingServer:
    """Manages WebSocket connections and WebRTC signaling."""
    
    def __init__(self):
        self.active_connections: Dict[str, PeerConnectionHandler] = {}

    async def close_all_connections(self) -> None:
        """Close all active WebRTC/WebSocket connections for graceful shutdown.

        Must be called before ``AppRunner.cleanup()`` to prevent it from
        blocking indefinitely on open WebSocket handlers.
        """
        if not self.active_connections:
            return
        handlers = list(self.active_connections.values())
        # Tear down audio processors and peer connections first so no new
        # tasks are spawned after we close the WebSockets.
        # PeerConnectionHandler.close() is idempotent, so the handle_websocket()
        # finally block calling it again is a safe no-op.
        await asyncio.gather(*(h.close() for h in handlers), return_exceptions=True)
        # Close each open WebSocket so the handle_websocket message-loop exits
        # and its finally block can run.
        await asyncio.gather(
            *(
                h.websocket.close()
                for h in handlers
                if hasattr(h, "websocket")
                and h.websocket is not None
                and not h.websocket.closed
            ),
            return_exceptions=True,
        )

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for signaling."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = id(ws)
        client_ip = request.remote
        
        # Extract language and session mode from query parameters.
        # user_id is always taken from the verified Firebase ID token — never trusted from the client.
        language = request.query.get('language', 'de')  # Default to German
        raw_mode = request.query.get('mode', 'voice')

        # Authenticate the connection. Non-web clients send the Firebase ID token in the
        # Authorization: Bearer header. Web browsers cannot set WebSocket upgrade headers
        # (browser security restriction), so they send {"type": "auth", "token": "..."} as the
        # first WebSocket message instead.
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[len('Bearer '):]
            try:
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
                user_id = decoded_token['uid']
                logger.debug(f"Token verified for uid: {user_id}")
            except Exception as e:
                logger.warning(f"WebSocket auth failed — invalid token: {e}")
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
        else:
            # No Authorization header — expect {"type": "auth", "token": "..."} as the
            # first message within 10 s (used by web browsers which cannot set WS headers).
            try:
                first_msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
            except Exception as e:
                logger.warning(f"WebSocket auth failed — no auth message from {client_ip}: {e}")
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
            if first_msg.type != WSMsgType.TEXT:
                logger.warning(f"WebSocket auth failed — unexpected message type from {client_ip}")
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
            try:
                auth_data = json.loads(first_msg.data)
                if auth_data.get('type') != 'auth' or not auth_data.get('token'):
                    raise ValueError('First message is not an auth message')
                token = auth_data['token']
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
                user_id = decoded_token['uid']
                logger.info(f"WebSocket web-auth from {client_ip} for uid: {user_id}")
            except Exception as e:
                logger.warning(f"WebSocket auth failed — invalid web auth message from {client_ip}: {e}")
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
        if raw_mode not in ('voice', 'text'):
            logger.warning(
                f"Invalid session mode '{raw_mode}' from {client_ip}; defaulting to 'voice'"
            )
            session_mode = 'voice'
        else:
            session_mode = raw_mode

        # hold_start=true: complete ICE/DC handshake but defer AudioProcessor start
        # until a real voice offer (with audio track) arrives.  Used by the Flutter
        # client's hollow pre-warm so the server doesn't spin up STT/LLM until
        # the user actually taps the mic button.
        hold_start = request.query.get('hold_start', 'false').lower() == 'true'
        
        logger.info(f"New WebSocket connection: {connection_id} from {client_ip} (user: {user_id}, language: {language}, mode: {session_mode})")
        
        # Create peer connection handler
        logger.debug(f"Creating PeerConnectionHandler for {connection_id}")
        ice_servers = await _fetch_ice_servers()
        handler = PeerConnectionHandler(
            connection_id=str(connection_id),
            websocket=ws,
            user_id=user_id,
            language=language,
            session_mode=session_mode,
            ice_servers=ice_servers,
            hold_start=hold_start,
        )
        self.active_connections[str(connection_id)] = handler
        logger.debug(f"Active connections: {len(self.active_connections)}")

        # Send ICE config to client immediately so it can configure its peer
        # connection with TURN credentials before sending the offer.
        await handler.send_ice_config(ice_servers)
        
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
