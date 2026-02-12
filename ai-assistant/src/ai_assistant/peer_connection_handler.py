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
    
    def __init__(self, connection_id: str, websocket, user_id: str = None, language: str = 'de'):
        self.connection_id = connection_id
        self.websocket = websocket
        self.user_id = user_id
        self.language = language
        self.pc = RTCPeerConnection()
        self.relay = MediaRelay()
        self.audio_processor = None
        self.track_ready = asyncio.Event()
        self.track_update_ready = asyncio.Event()
        
        logger.info(f"PeerConnectionHandler created for connection {connection_id} with language: {language}")
        
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
            logger.info(f"Received {track.kind} track: {track.id}")
            
            if track.kind == "audio":
                if self.audio_processor is not None:
                    logger.info("Track replacement detected (renegotiation)")
                    self.track_update_ready.clear()
                    await self.audio_processor.replace_input_track(track)
                    self.track_update_ready.set()
                else:
                    self.audio_processor = AudioProcessor(
                        connection_id=self.connection_id,
                        input_track=track,
                        user_id=self.user_id,
                        language=self.language
                    )
                    
                    if hasattr(self, 'data_channel') and self.data_channel:
                        self.audio_processor.set_data_channel(self.data_channel)

                    self.track_ready.set()
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
            if self.pc.connectionState == "failed":
                await self.close()
    
    async def handle_offer(self, offer: RTCSessionDescription):
        """Handle WebRTC offer from client."""
        try:
            is_renegotiation = len(self.pc.getSenders()) > 0
            logger.info(f"Handling {'renegotiation' if is_renegotiation else 'initial'} offer")
            
            await self.pc.setRemoteDescription(offer)
            
            if is_renegotiation:
                # Wait for track update to complete instead of fixed delay
                await asyncio.wait_for(self.track_update_ready.wait(), timeout=5.0)
            else:
                await asyncio.wait_for(self.track_ready.wait(), timeout=5.0)

            if not is_renegotiation:
                if self.audio_processor:
                    output_track = self.audio_processor.get_output_track()
                    logger.info(f"Adding output track: {output_track.id}")
                    self.pc.addTrack(output_track)
                else:
                    logger.error("Audio processor not ready")
            
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            await self._send_message({
                'type': 'answer',
                'sdp': self.pc.localDescription.sdp
            })
            
        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)
    
    async def handle_ice_candidate(self, candidate_data: dict):
        """Handle ICE candidate from client."""
        try:
            candidate_str = candidate_data.get('candidate', '')
            if candidate_str:
                candidate = candidate_from_sdp(candidate_str)
                candidate.sdpMid = candidate_data.get('sdpMid')
                candidate.sdpMLineIndex = candidate_data.get('sdpMLineIndex')
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
        logger.info(f"Closing connection {self.connection_id}")
        
        if self.audio_processor:
            await self.audio_processor.stop()
        
        await self.pc.close()
