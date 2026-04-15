"""
WebRTC Signaling Server
Handles WebSocket connections and WebRTC signaling between client and AI assistant.
"""
import asyncio
import json
import logging
import os
import time
from typing import Any
import aiohttp
from aiohttp import web, WSMsgType
from aiortc import RTCSessionDescription
from firebase_admin import auth as firebase_auth

from .peer_connection_handler import PeerConnectionHandler
from .chat_connection_handler import ChatConnectionHandler
from .firestore_service import FirestoreService
from .services.agent_profile import FULL_PROFILE, AgentProfile

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
# Languages the LLM prompts are tested and localised for.
# Any code outside this set falls back to English.
SUPPORTED_LANGUAGES = {"en", "de"}


class SignalingServer:
    """Manages WebSocket connections and WebRTC signaling."""

    def __init__(self, profile: AgentProfile | None = None) -> None:
        self.active_connections: dict[str, PeerConnectionHandler | ChatConnectionHandler] = {}
        self._firestore = FirestoreService()
        self._profile: AgentProfile = profile if profile is not None else FULL_PROFILE
        # Parked sessions: user_id → handler preserved after WS disconnect.
        # Kept alive for SESSION_SUSPENSION_TTL_MINUTES so the user can
        # reconnect and continue the exact same LLM session.
        self._suspended_sessions: dict[str, ChatConnectionHandler] = {}
        self._suspension_tasks: dict[str, asyncio.Task] = {}

    async def close_all_connections(self) -> None:
        """Close all active WebRTC/WebSocket connections for graceful shutdown.

        Must be called before ``AppRunner.cleanup()`` to prevent it from
        blocking indefinitely on open WebSocket handlers.
        """
        if not self.active_connections:
            return
        handlers = list(self.active_connections.values())
        # Close WebSockets first so the handle_websocket message-loops exit
        # promptly — this unblocks AppRunner.cleanup() regardless of how long
        # handler teardown takes.  The per-connection finally blocks then call
        # handler.close() as a safety net (idempotent).
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
        # Tear down audio processors and peer connections in parallel.  We do
        # this after closing websockets so no new tasks are spawned, but we
        # don't let slow teardown block the WS close above.
        await asyncio.gather(*(h.close() for h in handlers), return_exceptions=True)
        # Release all handler references now that teardown is complete.
        # The handle_websocket() finally blocks use pop(key, None) so they
        # are safe even if their entry has already been removed here.
        self.active_connections.clear()
        # Tear down any parked sessions that survived shutdown.
        for task in self._suspension_tasks.values():
            task.cancel()
        self._suspension_tasks.clear()
        suspended = list(self._suspended_sessions.values())
        self._suspended_sessions.clear()
        await asyncio.gather(*(h.close() for h in suspended), return_exceptions=True)
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for signaling."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        connection_id = id(ws)
        client_ip = request.remote

        # Extract language and session mode from query parameters.
        # user_id is always taken from the verified Firebase ID token — never trusted from the client.
        language = request.query.get('language', 'de')  # Default to German

        # Session mode: 'voice' or 'text', default to 'text' if invalid or absent
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
                logger.debug("Token verified for uid: %s", user_id)
            except Exception as e:
                logger.warning("WebSocket auth failed — invalid token: %s", e)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
        else:
            # No Authorization header — expect {"type": "auth", "token": "..."} as the
            # first message within 10 s (used by web browsers which cannot set WS headers).
            try:
                first_msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
            except Exception as e:
                logger.warning("WebSocket auth failed — no auth message from %s: %s", client_ip, e)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
            if first_msg.type != WSMsgType.TEXT:
                logger.warning("WebSocket auth failed — unexpected message type from %s", client_ip)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
            try:
                auth_data = json.loads(first_msg.data)
                if auth_data.get('type') != 'auth' or not auth_data.get('token'):
                    raise ValueError('First message is not an auth message')
                token = auth_data['token']
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
                user_id = decoded_token['uid']
                logger.info("WebSocket web-auth from %s for uid: %s", client_ip, user_id)
            except Exception as e:
                logger.warning("WebSocket auth failed — invalid web auth message from %s: %s", client_ip, e)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
        if raw_mode not in ('voice', 'text'):
            logger.warning("Invalid session mode '%s' from %s; defaulting to 'text'", raw_mode, client_ip)
            session_mode = 'text'
        else:
            session_mode = raw_mode

        # Lite mode: voice sessions are not supported — reject before creating any handler.
        if not self._profile.voice_enabled and session_mode == 'voice':
            logger.warning(
                "AGENT_MODE=%r does not support voice — rejecting voice session from %s",
                self._profile.name, client_ip,
            )
            await ws.close(code=4403, message=b"Voice not supported in this deployment")
            return ws

        # hold_start=true: complete ICE/DC handshake but defer AudioProcessor start
        # until a real voice offer (with audio track) arrives.  Used by the Flutter
        # client's hollow pre-warm so the server doesn't spin up STT/LLM until
        # the user actually taps the mic button.
        hold_start = request.query.get('hold_start', 'false').lower() == 'true'
        # Language selection logic:
        # 1. Check 'language' query parameter against SUPPORTED_LANGUAGES. If valid, use it.
        # 2. If query parameter is invalid or absent, and we have a user_id, look up the user's stored language in Firestore. If valid, use it.
        # 3. If both the query parameter and stored language are invalid or absent, fall back to 'en'.
        raw_language = request.query.get('language', '')
        stored_language = None  # populated below if a Firestore lookup is required
        if raw_language in SUPPORTED_LANGUAGES:
            language = raw_language
        else:
            # Attempt to read the user's stored language setting from Firestore
            # only when Firestore is enabled for this deployment mode.
            if user_id and self._profile.firestore_enabled:
                try:
                    user_doc = await self._firestore.get_user(user_id)
                    stored_language = (user_doc or {}).get('language')
                except Exception as lang_exc:
                    logger.warning(
                        "Could not fetch user language for %s: %s", user_id, lang_exc
                    )
            if stored_language in SUPPORTED_LANGUAGES:
                language = stored_language
                if raw_language:
                    logger.warning(
                        "Unsupported language '%s' from %s; using stored setting '%s'",
                        raw_language, client_ip, language,
                    )
            else:
                language = 'en'
                if raw_language:
                    logger.warning(
                        "Unsupported language '%s' from %s; falling back to 'en'",
                        raw_language, client_ip,
                    )
                elif not raw_language:
                    logger.debug("No language param; defaulting to 'en'")

        logger.info("New WebSocket connection: %s from %s (user: %s, language: %s, mode: %s)", connection_id, client_ip, user_id, language, session_mode)

        # Create peer connection handler
        logger.debug("Creating PeerConnectionHandler for %s", connection_id)
        ice_servers = await _fetch_ice_servers()
        # Compute fallback_from: non-empty when the client sent a language code that
        # is not in SUPPORTED_LANGUAGES so we fell all the way back to 'en'.
        language_fallback_from = (
            raw_language
            if (raw_language and raw_language not in SUPPORTED_LANGUAGES
                and language == 'en'
                and (not stored_language or stored_language not in SUPPORTED_LANGUAGES))
            else ""
        )
        handler = PeerConnectionHandler(
            connection_id=str(connection_id),
            websocket=ws,
            user_id=user_id,
            language=language,
            session_mode=session_mode,
            ice_servers=ice_servers,
            hold_start=hold_start,
            language_fallback_from=language_fallback_from,
            profile=self._profile,
        )
        self.active_connections[str(connection_id)] = handler
        logger.debug("Active connections: %s", len(self.active_connections))

        # Send ICE config to client immediately so it can configure its peer
        # connection with TURN credentials before sending the offer.
        await handler.send_ice_config(ice_servers)

        try:
            logger.debug("Starting message loop for connection %s", connection_id)
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        logger.debug("Received text message from %s: %s...", connection_id, msg.data[:100])
                        data = json.loads(msg.data)
                        logger.debug("Parsed message type: %s", data.get('type'))
                        await self._handle_message(handler, data)
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON received from %s: %s", connection_id, e)
                        logger.debug("Raw data: %s", msg.data)
                    except Exception as e:
                        logger.error("Error handling message from %s: %s", connection_id, e, exc_info=True)

                elif msg.type == WSMsgType.ERROR:
                    logger.error("WebSocket error for %s: %s", connection_id, ws.exception())

                elif msg.type == WSMsgType.CLOSE:
                    logger.info("Client %s initiated close", connection_id)

        finally:
            # Cleanup
            logger.info("WebSocket connection closed: %s", connection_id)
            logger.debug("Cleaning up connection %s", connection_id)
            await handler.close()
            self.active_connections.pop(str(connection_id), None)
            logger.debug("Active connections after cleanup: %s", len(self.active_connections))
        return ws

    async def _handle_message(self, handler: PeerConnectionHandler, data: dict[str, Any]) -> None:
        """Handle signaling messages."""
        msg_type = data.get('type')
        logger.debug("Handling message type '%s' for connection %s", msg_type, handler.connection_id)

        if msg_type == 'offer':
            logger.debug("Processing offer (SDP length: %s)", len(data.get('sdp', '')))
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
                logger.debug("Processing ICE candidate")
                await handler.handle_ice_candidate(candidate)
            else:
                logger.warning("Received ice-candidate message without candidate data")

        else:
            logger.warning("Unknown message type: %s", msg_type)

    async def handle_chat_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle a text-only lite-mode WebSocket connection (``GET /ws/chat``).

        No WebRTC, no ICE, no DataChannel.  After Firebase auth the connection
        is handed off to a ``ChatConnectionHandler`` which creates an
        ``AudioProcessor`` in text mode and forwards messages over the
        WebSocketBridge.
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        connection_id = str(id(ws))
        client_ip = request.remote

        # ── Authentication (identical two-path logic as handle_websocket) ────
        user_id: str | None = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[len('Bearer '):]
            try:
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
                user_id = decoded_token['uid']
                logger.debug("Chat WS token verified for uid: %s", user_id)
            except Exception as exc:
                logger.warning("Chat WS auth failed — invalid token: %s", exc)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
        else:
            try:
                first_msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
            except Exception as exc:
                logger.warning("Chat WS auth timeout from %s: %s", client_ip, exc)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
            if first_msg.type != WSMsgType.TEXT:
                await ws.close(code=4401, message=b'Unauthorized')
                return ws
            try:
                auth_data = json.loads(first_msg.data)
                if auth_data.get('type') != 'auth' or not auth_data.get('token'):
                    raise ValueError('First message is not an auth message')
                token = auth_data['token']
                decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
                user_id = decoded_token['uid']
                logger.info("Chat WS web-auth from %s for uid: %s", client_ip, user_id)
                # Acknowledge successful auth so the client knows the token
                # was accepted before the first chat frames arrive.
                await ws.send_str(json.dumps({"type": "auth-ok"}))
            except Exception as exc:
                logger.warning("Chat WS auth failed from %s: %s", client_ip, exc)
                await ws.close(code=4401, message=b'Unauthorized')
                return ws

        # ── Language resolution (same logic as handle_websocket) ─────────────
        raw_language = request.query.get('language', '')
        stored_language: str | None = None
        if raw_language in SUPPORTED_LANGUAGES:
            language = raw_language
        else:
            if user_id and self._profile.firestore_enabled:
                try:
                    user_doc = await self._firestore.get_user(user_id)
                    stored_language = (user_doc or {}).get('language')
                except Exception as exc:
                    logger.warning("Could not fetch user language for %s: %s", user_id, exc)
            if stored_language in SUPPORTED_LANGUAGES:
                language = stored_language
            else:
                language = 'en'
                if raw_language:
                    logger.warning(
                        "Chat WS unsupported language '%s' from %s; falling back to 'en'",
                        raw_language, client_ip,
                    )

        language_fallback_from = (
            raw_language
            if (raw_language and raw_language not in SUPPORTED_LANGUAGES
                and language == 'en'
                and (not stored_language or stored_language not in SUPPORTED_LANGUAGES))
            else ""
        )

        logger.info(
            "New chat WS connection: %s from %s (user: %s, language: %s)",
            connection_id, client_ip, user_id, language,
        )

        # Resume a parked session for this user if one exists, otherwise
        # create a fresh handler.
        parked = self._suspended_sessions.pop(user_id, None) if user_id else None
        if parked is not None:
            ttl_task = self._suspension_tasks.pop(user_id, None)
            if ttl_task and not ttl_task.done():
                ttl_task.cancel()
            handler = parked
            await handler.resume(ws)
        else:
            handler = ChatConnectionHandler(
                connection_id=connection_id,
                websocket=ws,
                user_id=user_id,
                language=language,
                language_fallback_from=language_fallback_from,
                profile=self._profile,
            )
        self.active_connections[connection_id] = handler

        try:
            if parked is None:
                await handler.start()

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get('type') == 'text-input':
                            text = data.get('text', '')
                            handler.handle_text_input(text)
                        elif data.get('type') == 'restore-history':
                            raw_messages = data.get('messages', [])
                            if isinstance(raw_messages, list):
                                handler.handle_restore_history(raw_messages)
                            else:
                                logger.warning(
                                    "Chat WS: restore-history from %s has invalid 'messages' field",
                                    connection_id,
                                )
                        else:
                            logger.debug(
                                "Chat WS: ignoring message type '%s' from %s",
                                data.get('type'), connection_id,
                            )
                    except json.JSONDecodeError as exc:
                        logger.error("Chat WS invalid JSON from %s: %s", connection_id, exc)
                    except Exception as exc:
                        logger.error("Chat WS message error from %s: %s", connection_id, exc, exc_info=True)
                elif msg.type == WSMsgType.ERROR:
                    logger.error("Chat WS error for %s: %s", connection_id, ws.exception())
                elif msg.type == WSMsgType.CLOSE:
                    logger.info("Chat WS client %s initiated close", connection_id)
        finally:
            logger.info("Chat WS connection closed: %s", connection_id)
            self.active_connections.pop(connection_id, None)
            if user_id and not handler._closed:
                # Park the session so the user can reconnect within the TTL.
                await handler.suspend()
                # Replace any previously parked session for this user.
                old_parked = self._suspended_sessions.pop(user_id, None)
                old_ttl = self._suspension_tasks.pop(user_id, None)
                if old_ttl and not old_ttl.done():
                    old_ttl.cancel()
                if old_parked is not None:
                    await old_parked.close()
                self._suspended_sessions[user_id] = handler
                self._suspension_tasks[user_id] = asyncio.create_task(
                    self._suspend_ttl_task(user_id)
                )
            else:
                await handler.close()
        return ws

    async def _suspend_ttl_task(self, user_id: str) -> None:
        """Tear down a parked session when the suspension TTL expires.

        Cancelled automatically when the user reconnects within the window.
        """
        ttl_minutes = int(os.getenv("SESSION_SUSPENSION_TTL_MINUTES", "10"))
        try:
            await asyncio.sleep(ttl_minutes * 60)
        except asyncio.CancelledError:
            return  # User reconnected — session was resumed, nothing to do.
        handler = self._suspended_sessions.pop(user_id, None)
        self._suspension_tasks.pop(user_id, None)
        if handler is not None:
            logger.info(
                "Suspension TTL expired for user %s — tearing down session %s",
                user_id, handler.connection_id,
            )
            await handler.close()

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            'status': 'healthy',
            'active_connections': len(self.active_connections)
        })
