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
    
    def __init__(self, connection_id: str, websocket, user_id: str = None, language: str = 'de', session_mode: str = 'voice'):
        self.connection_id = connection_id
        self.websocket = websocket
        self.user_id = user_id
        self.language = language
        self.session_mode = session_mode  # 'voice' or 'text'
        self.pc = RTCPeerConnection()
        self.relay = MediaRelay()
        self.audio_processor = None
        self.track_ready = asyncio.Event()
        self.track_update_ready = asyncio.Event()
        self.track_update_ready.set()  # Initially set - no update pending
        self._idle_task: asyncio.Task = None  # 10-minute idle timeout task
        
        logger.info(f"PeerConnectionHandler created for connection {connection_id} with language: {language}, mode: {session_mode}")
        
        # Set up event handlers
        self._setup_event_handlers()
        
    # ── Idle timer ────────────────────────────────────────────────────────────

    def _reset_idle_timer(self):
        """Cancel existing idle task and start a fresh 10-minute countdown."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_timeout_task())

    async def _idle_timeout_task(self):
        """Close the connection after 10 minutes of inactivity."""
        try:
            await asyncio.sleep(600)  # 10 minutes
            logger.info(f"Idle timeout reached for connection {self.connection_id} — closing")
            await self.close()
        except asyncio.CancelledError:
            pass  # Normal cancellation when activity is detected

    # ── Event handlers ────────────────────────────────────────────────────────

    def _setup_event_handlers(self):
        
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
                    # Event was already cleared in handle_offer before setRemoteDescription
                    await self.audio_processor.replace_input_track(track)
                    self.track_update_ready.set()
                else:
                    self.audio_processor = AudioProcessor(
                        connection_id=self.connection_id,
                        input_track=track,
                        user_id=self.user_id,
                        language=self.language,
                        skip_greeting=(self.session_mode == 'text'),
                    )
                    # Wire activity hook so STT transcripts reset the idle timer
                    self.audio_processor.on_activity = self._reset_idle_timer
                    
                    if hasattr(self, 'data_channel') and self.data_channel:
                        self.audio_processor.set_data_channel(self.data_channel)

                    self.track_ready.set()
                    asyncio.create_task(self.audio_processor.start())
                    # Start idle timer once the audio processor is up
                    self._reset_idle_timer()
        
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            """Handle incoming data channel."""
            logger.info(f"Data channel received: {channel.label}")
            self.data_channel = channel
            
            if self.audio_processor:
                self.audio_processor.set_data_channel(channel)
            
            @channel.on("message")
            def on_message(message):
                """Handle incoming data channel messages."""
                try:
                    import json
                    data = json.loads(message)
                    logger.info(f"Data channel message received: {data.get('type')}")
                    
                    if data.get('type') == 'text-input':
                        # Handle text input from client
                        text = data.get('text', '').strip()
                        if text and self.audio_processor:
                            preview = text[:50] + '…' if len(text) > 50 else text
                            logger.debug(f"Processing text input ({len(text)} chars): {preview}")
                            # Reset idle timer on any user activity
                            self._reset_idle_timer()
                            # Process text input through the public API
                            # This bypasses STT and goes directly to LLM -> TTS
                            asyncio.create_task(
                                self.audio_processor.process_text_input(text)
                            )
                        else:
                            logger.warning(f"Empty text or audio processor not ready")
                except Exception as e:
                    logger.error(f"Error handling data channel message: {e}", exc_info=True)
                
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
            
            # For renegotiation, clear the event before setRemoteDescription
            # This ensures we wait for the track replacement to complete
            if is_renegotiation:
                self.track_update_ready.clear()
            
            await self.pc.setRemoteDescription(offer)
            
            if is_renegotiation:
                # Wait for track update to complete (will be set by on_track handler)
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
        
        # Cancel idle timer
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        
        if self.audio_processor:
            await self.audio_processor.stop()
        
        await self.pc.close()
