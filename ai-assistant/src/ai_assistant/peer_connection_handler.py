"""
WebRTC Peer Connection Handler
Manages individual WebRTC connections and media streams.
"""
import asyncio
import logging
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaRelay
from aiortc.sdp import candidate_from_sdp

from .audio_processor import AudioProcessor

logger = logging.getLogger(__name__)


class PeerConnectionHandler:
    """Handles WebRTC peer connection for a single client."""
    
    def __init__(self, connection_id: str, ai_assistant, websocket, user_id: str = None, language: str = 'de'):
        self.connection_id = connection_id
        self.ai_assistant = ai_assistant
        self.websocket = websocket
        self.user_id = user_id
        self.language = language
        self.pc = RTCPeerConnection()
        self.relay = MediaRelay()
        self.audio_processor = None
        self.track_ready = asyncio.Event()
        
        logger.info(f"PeerConnectionHandler created for connection {connection_id} with language: {language}")
        
        # Set up event handlers
        self._setup_event_handlers()
        
    def _setup_event_handlers(self):
        """Set up WebRTC event handlers."""
        
        logger.debug(f"Setting up WebRTC event handlers for connection {self.connection_id}")
        
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            """Send ICE candidates to client."""
            if candidate:
                logger.debug(f"ICE candidate generated: {candidate.candidate}")
                await self._send_message({
                    'type': 'ice-candidate',
                    'candidate': {
                        'candidate': candidate.candidate,
                        'sdpMid': candidate.sdpMid,
                        'sdpMLineIndex': candidate.sdpMLineIndex
                    }
                })
        
        @self.pc.on("track")
        async def on_track(track):
            """Handle incoming media track from client."""
            logger.info(f"Received track: {track.kind}")
            logger.debug(f"Track details - id={track.id}, kind={track.kind}, readyState={track.readyState}")
            
            if track.kind == "audio":
                logger.debug("Creating AudioProcessor for incoming audio track")
                # Create audio processor for this track
                self.audio_processor = AudioProcessor(
                    connection_id=self.connection_id,
                    ai_assistant=self.ai_assistant,
                    input_track=track,
                    user_id=self.user_id,
                    language=self.language
                )
                
                # If we already have a data channel, pass it to the audio processor
                if hasattr(self, 'data_channel') and self.data_channel:
                    self.audio_processor.set_data_channel(self.data_channel)

                # Signal that the track is ready
                self.track_ready.set()
                logger.debug("Audio processor created and ready")
                
                # Start processing
                logger.debug("Starting audio processor")
                asyncio.create_task(self.audio_processor.start())
        
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            """Handle incoming data channel."""
            logger.info(f"Data channel received: {channel.label}")
            self.data_channel = channel
            
            if self.audio_processor:
                self.audio_processor.set_data_channel(channel)
                
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            """Handle connection state changes."""
            logger.info(f"Connection state: {self.pc.connectionState}")
            logger.debug(f"Connection {self.connection_id} state details - ice={self.pc.iceConnectionState}, gathering={self.pc.iceGatheringState}")
            
            if self.pc.connectionState == "failed":
                logger.error(f"Connection {self.connection_id} failed")
                await self.close()
    
    async def handle_offer(self, offer: RTCSessionDescription):
        """Handle WebRTC offer from client."""
        try:
            logger.debug(f"Handling offer from client {self.connection_id}")
            logger.debug(f"Offer SDP length: {len(offer.sdp)} chars")
            
            # Set remote description
            logger.debug("Setting remote description")
            await self.pc.setRemoteDescription(offer)

            # Wait for audio processor to be ready
            logger.debug("Waiting for audio track to be ready...")
            await asyncio.wait_for(self.track_ready.wait(), timeout=5.0)
            logger.debug("Audio track is ready")

            # Add output track before creating answer
            if self.audio_processor:
                output_track = self.audio_processor.get_output_track()
                logger.info(f"Adding output track to peer connection: {output_track.id}")
                self.pc.addTrack(output_track)
            else:
                logger.error("Audio processor not ready after waiting!")
            
            # Create answer
            logger.debug("Creating answer")
            answer = await self.pc.createAnswer()
            logger.debug(f"Answer SDP length: {len(answer.sdp)} chars")
            
            logger.debug("Setting local description")
            await self.pc.setLocalDescription(answer)
            
            # Send answer to client
            logger.debug("Sending answer to client")
            await self._send_message({
                'type': 'answer',
                'sdp': self.pc.localDescription.sdp
            })
            
            logger.info(f"Sent answer to client {self.connection_id}")
            
        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)
    
    async def handle_ice_candidate(self, candidate_data: dict):
        """Handle ICE candidate from client."""
        try:
            logger.debug(f"Handling ICE candidate from client {self.connection_id}")
            logger.debug(f"Candidate: {candidate_data.get('candidate', '')[:100]}...")
            
            # Parse the SDP candidate string into an RTCIceCandidate object
            candidate_str = candidate_data.get('candidate', '')
            if candidate_str:
                candidate = candidate_from_sdp(candidate_str)
                candidate.sdpMid = candidate_data.get('sdpMid')
                candidate.sdpMLineIndex = candidate_data.get('sdpMLineIndex')
                await self.pc.addIceCandidate(candidate)
                logger.debug("ICE candidate added successfully")
            
        except Exception as e:
            logger.error(f"Error adding ICE candidate: {e}", exc_info=True)
    
    async def _send_message(self, message: dict):
        """Send message to client via WebSocket."""
        try:
            logger.debug(f"Sending message to client {self.connection_id}: type={message.get('type')}")
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
    
    async def close(self):
        """Close peer connection and cleanup resources."""
        logger.info(f"Closing peer connection {self.connection_id}")
        
        if self.audio_processor:
            logger.debug("Stopping audio processor")
            await self.audio_processor.stop()
        
        logger.debug("Closing RTCPeerConnection")
        await self.pc.close()
        logger.debug(f"Peer connection {self.connection_id} closed successfully")
