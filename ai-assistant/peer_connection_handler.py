"""
WebRTC Peer Connection Handler
Manages individual WebRTC connections and media streams.
"""
import asyncio
import logging
import json
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    MediaStreamTrack
)
from aiortc.contrib.media import MediaRelay

from audio_processor import AudioProcessor

logger = logging.getLogger(__name__)


class PeerConnectionHandler:
    """Handles WebRTC peer connection for a single client."""
    
    def __init__(self, connection_id: str, ai_assistant, websocket):
        self.connection_id = connection_id
        self.ai_assistant = ai_assistant
        self.websocket = websocket
        self.pc = RTCPeerConnection()
        self.relay = MediaRelay()
        self.audio_processor = None
        
        # Set up event handlers
        self._setup_event_handlers()
        
    def _setup_event_handlers(self):
        """Set up WebRTC event handlers."""
        
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            """Send ICE candidates to client."""
            if candidate:
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
            
            if track.kind == "audio":
                # Create audio processor for this track
                self.audio_processor = AudioProcessor(
                    connection_id=self.connection_id,
                    ai_assistant=self.ai_assistant,
                    input_track=track
                )
                
                # Add output track to peer connection
                output_track = self.audio_processor.get_output_track()
                self.pc.addTrack(output_track)
                
                # Start processing
                asyncio.create_task(self.audio_processor.start())
        
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            """Handle connection state changes."""
            logger.info(f"Connection state: {self.pc.connectionState}")
            
            if self.pc.connectionState == "failed":
                await self.close()
    
    async def handle_offer(self, offer: RTCSessionDescription):
        """Handle WebRTC offer from client."""
        try:
            # Set remote description
            await self.pc.setRemoteDescription(offer)
            
            # Create answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            # Send answer to client
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
            candidate = RTCIceCandidate(
                candidate=candidate_data.get('candidate', ''),
                sdpMid=candidate_data.get('sdpMid'),
                sdpMLineIndex=candidate_data.get('sdpMLineIndex')
            )
            await self.pc.addIceCandidate(candidate)
            
        except Exception as e:
            logger.error(f"Error adding ICE candidate: {e}", exc_info=True)
    
    async def _send_message(self, message: dict):
        """Send message to client via WebSocket."""
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
    
    async def close(self):
        """Close peer connection and cleanup resources."""
        logger.info(f"Closing peer connection {self.connection_id}")
        
        if self.audio_processor:
            await self.audio_processor.stop()
        
        await self.pc.close()
