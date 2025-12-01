"""
WebSocket Connection Manager
Manages WebSocket lifecycle, heartbeat, and message handling.
"""
import asyncio
import json
import logging
import time
from typing import Optional
from aiohttp import web, WSMsgType

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages individual WebSocket connection lifecycle."""

    def __init__(
        self,
        websocket: web.WebSocketResponse,
        connection_id: str,
        heartbeat_interval: float = 30.0,
        connection_timeout: float = 90.0
    ):
        """
        Initialize WebSocket connection manager.
        
        Args:
            websocket: WebSocket response object
            connection_id: Unique connection identifier
            heartbeat_interval: Seconds between heartbeat pings
            connection_timeout: Seconds before marking connection stale
        """
        self.websocket = websocket
        self.connection_id = connection_id
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout
        self.last_pong = time.time()
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def send_json(self, message: dict):
        """Send JSON message to client."""
        try:
            await self.websocket.send_json(message)
            logger.debug(f"Sent message to {self.connection_id}: {message.get('type')}")
        except Exception as e:
            logger.error(f"Error sending message to {self.connection_id}: {e}")
            raise

    async def start_heartbeat(self):
        """Start heartbeat monitoring task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.debug(f"Started heartbeat for connection {self.connection_id}")

    async def stop_heartbeat(self):
        """Stop heartbeat monitoring task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Stopped heartbeat for connection {self.connection_id}")

    async def _heartbeat_loop(self):
        """Send periodic pings and check for stale connections."""
        try:
            while not self.websocket.closed:
                await asyncio.sleep(self.heartbeat_interval)

                # Check if connection is stale
                time_since_pong = time.time() - self.last_pong
                if time_since_pong > self.connection_timeout:
                    logger.warning(
                        f"Connection {self.connection_id} stale "
                        f"(no pong for {time_since_pong:.0f}s), closing"
                    )
                    await self.websocket.close()
                    break

                # Send ping
                try:
                    await self.websocket.send_json({
                        'type': 'ping',
                        'timestamp': time.time()
                    })
                    logger.debug(f"Sent ping to {self.connection_id}")
                except Exception as e:
                    logger.error(f"Failed to send ping to {self.connection_id}: {e}")
                    break

        except asyncio.CancelledError:
            logger.debug(f"Heartbeat loop cancelled for {self.connection_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop for {self.connection_id}: {e}", exc_info=True)

    def update_pong_timestamp(self):
        """Update last pong timestamp."""
        self.last_pong = time.time()
        logger.debug(f"Updated pong timestamp for {self.connection_id}")

    async def receive_messages(self, message_handler):
        """
        Receive and process messages from WebSocket.
        
        Args:
            message_handler: Async function to handle parsed messages
        """
        try:
            async for msg in self.websocket:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get('type')

                        if msg_type == 'pong':
                            self.update_pong_timestamp()
                        else:
                            await message_handler(data)

                    except json.JSONDecodeError as e:
                        logger.error(
                            f"Invalid JSON from {self.connection_id}: {e}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error handling message from {self.connection_id}: {e}",
                            exc_info=True
                        )

                elif msg.type == WSMsgType.ERROR:
                    logger.error(
                        f"WebSocket error for {self.connection_id}: "
                        f"{self.websocket.exception()}"
                    )

                elif msg.type == WSMsgType.CLOSE:
                    logger.info(f"Client {self.connection_id} initiated close")
                    break

        except Exception as e:
            logger.error(
                f"Error in receive loop for {self.connection_id}: {e}",
                exc_info=True
            )

    @property
    def is_closed(self) -> bool:
        """Check if WebSocket is closed."""
        return self.websocket.closed
