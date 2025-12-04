"""
WebRTC Peer Connection Handler: Manages individual WebRTC connections using service pattern.
"""
import asyncio
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaRelay
from aiortc.sdp import candidate_from_sdp

from .audio_processor import AudioProcessor
from .ai_assistant import AIAssistant

logger = logging.getLogger(__name__)


class WebRTCEventHandler:
    """Handles WebRTC peer connection events."""

    def __init__(self, connection_id: str, peer_connection, message_sender):
        """
        Initialize WebRTC event handler.
        
        Args:
            connection_id: Unique connection identifier
            peer_connection: RTCPeerConnection instance
            message_sender: Async callable to send messages to client
        """
        self.connection_id = connection_id
        self.pc = peer_connection
        self.send_message = message_sender
        self.audio_processor = None
        self.track_ready = asyncio.Event()

    def setup_handlers(self):
        """Set up all WebRTC event handlers."""
        self._setup_ice_candidate_handler()
        self._setup_track_handler()
        self._setup_connection_state_handler()
        logger.debug(f"Set up WebRTC event handlers for {self.connection_id}")

    def _setup_ice_candidate_handler(self):
        """Set up ICE (Interactive Connectivity Establishment) candidate event handler."""
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                logger.debug(f"ICE candidate generated for {self.connection_id}")
                await self.send_message({
                    'type': 'ice-candidate',
                    'candidate': {
                        'candidate': candidate.candidate,
                        'sdpMid': candidate.sdpMid,
                        'sdpMLineIndex': candidate.sdpMLineIndex
                    }
                })

    def _setup_track_handler(self):
        """Set up media track event handler."""
        @self.pc.on("track")
        async def on_track(track):
            logger.info(f"Received {track.kind} track for {self.connection_id}")

            if track.kind == "audio":
                await self._handle_audio_track(track)

    def _setup_connection_state_handler(self):
        """Set up connection state change handler."""
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(
                f"Connection {self.connection_id} state: {self.pc.connectionState}"
            )

            if self.pc.connectionState == "failed":
                logger.error(f"Connection {self.connection_id} failed")

    async def _handle_audio_track(self, track):
        """Handle incoming audio track."""
        logger.debug(f"Creating AudioProcessor for {self.connection_id}")
        # Audio processor will be set externally
        self.track_ready.set()

    async def wait_for_track(self, timeout: float = 5.0):
        """Wait for audio track to be ready."""
        await asyncio.wait_for(self.track_ready.wait(), timeout=timeout)


class PeerConnectionHandler:
    """
    WebRTC peer connection handler using service pattern.
    
    Manages:
    - WebRTC peer connection lifecycle
    - Media track handling
    - Audio processing coordination
    """

    def __init__(
        self,
        connection_id: str,
        ai_assistant: AIAssistant,
        websocket,
        user_id: str | None = None
    ):
        """
        Initialize peer connection handler.
        
        Args:
            connection_id: Unique connection identifier
            ai_assistant: AIAssistant instance for this connection
            websocket: WebSocket for signaling
            user_id: Firebase user ID (optional)
        """
        self.connection_id = connection_id
        self.user_id = user_id
        self.ai_assistant = ai_assistant
        self.websocket = websocket

        # WebRTC components
        self.peer_connection = RTCPeerConnection()
        self.relay = MediaRelay()
        self.audio_processor = None

        # Event handler
        self.event_handler = WebRTCEventHandler(
            connection_id,
            self.peer_connection,
            self._send_message
        )
        self.event_handler.setup_handlers()

        logger.info(f"PeerConnectionHandler created for {connection_id}")

    async def handle_offer(self, offer: RTCSessionDescription):
        """
        Handle WebRTC offer from client.
        
        Args:
            offer: RTCSessionDescription with client's offer
        """
        try:
            logger.debug(f"Handling offer from {self.connection_id}")

            # Set remote description
            await self.peer_connection.setRemoteDescription(offer)

            # Wait for audio track
            await self.event_handler.wait_for_track()

            # Create and add audio processor
            await self._setup_audio_processor()

            # Create and send answer
            await self._create_and_send_answer()

            logger.info(f"Sent answer to client {self.connection_id}")

        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for audio track from {self.connection_id}")
        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)

    async def _setup_audio_processor(self):
        """Set up audio processor with input track."""
        # Audio track is received via event handler
        # We need to get it from the PC's receivers
        for receiver in self.peer_connection.getReceivers():
            if receiver.track and receiver.track.kind == "audio":
                logger.debug(f"Creating AudioProcessor for {self.connection_id}")

                self.audio_processor = AudioProcessor(
                    connection_id=self.connection_id,
                    ai_assistant=self.ai_assistant,
                    input_track=receiver.track
                )

                # Store reference in event handler
                self.event_handler.audio_processor = self.audio_processor

                # Add output track to peer connection
                output_track = self.audio_processor.get_output_track()
                self.peer_connection.addTrack(output_track)
                logger.info(f"Added output track to {self.connection_id}")

                # Start audio processing
                asyncio.create_task(self.audio_processor.start())
                break

        if not self.audio_processor:
            logger.error(f"No audio track found for {self.connection_id}")

    async def _create_and_send_answer(self):
        """Create answer and send to client."""
        answer = await self.peer_connection.createAnswer()
        await self.peer_connection.setLocalDescription(answer)

        await self._send_message({
            'type': 'answer',
            'sdp': self.peer_connection.localDescription.sdp
        })

    async def handle_ice_candidate(self, candidate_data: dict):
        """
        Handle ICE candidate from client.
        
        Args:
            candidate_data: Dictionary with ICE candidate information
        """
        try:
            logger.debug(f"Handling ICE candidate for {self.connection_id}")

            # Extract candidate string from nested structure
            candidate_data = candidate_data['candidate']
            candidate_str = candidate_data['candidate']
            sdp_mid = candidate_data['sdpMid']
            sdp_mline_index = candidate_data['sdpMLineIndex']

            candidate = candidate_from_sdp(candidate_str)
            candidate.sdpMid = sdp_mid
            candidate.sdpMLineIndex = sdp_mline_index

            await self.peer_connection.addIceCandidate(candidate)
            logger.debug(f"ICE candidate added for {self.connection_id}")

        except Exception as e:
            logger.error(f"Error adding ICE candidate: {e}", exc_info=True)

    async def _send_message(self, message: dict):
        """Send message to client via WebSocket."""
        try:
            logger.debug(
                f"Sending {message.get('type')} to {self.connection_id}"
            )
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)

    async def close(self):
        """Close peer connection and cleanup resources."""
        logger.info(f"Closing peer connection {self.connection_id}")

        # Stop audio processor
        if self.audio_processor:
            try:
                await self.audio_processor.stop()
            except Exception as e:
                logger.warning(f"Error stopping audio processor: {e}")

        # Close peer connection
        if self.peer_connection:
            try:
                await self.peer_connection.close()
                logger.debug(f"Peer connection {self.connection_id} closed")
            except Exception as e:
                logger.warning(f"Error closing peer connection: {e}")
            finally:
                self.peer_connection = None
