#!/usr/bin/env python3
"""
Simple WebRTC Client Test
This script tests the AI Assistant service by establishing a WebRTC connection
and sending a test audio file.
"""
import asyncio
import json
import wave
import logging
from fractions import Fraction
from pathlib import Path

import websockets
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack
)
from aiortc.contrib.media import MediaRecorder
from av import AudioFrame
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioFileTrack(MediaStreamTrack):
    """
    A media track that reads audio from a WAV file.
    """
    kind = "audio"

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.samples_per_frame = 320  # 20ms at 16kHz
        self.sample_rate = 16000
        self._timestamp = 0
        self._wav_file = None
        self._load_audio()

    def _load_audio(self):
        """Load audio from WAV file."""
        with wave.open(self.file_path, 'rb') as wav_file:
            # Verify format
            assert wav_file.getnchannels() == 1, "Audio must be mono"
            assert wav_file.getsampwidth() == 2, "Audio must be 16-bit"
            assert wav_file.getframerate() == 16000, "Sample rate must be 16kHz"
            
            # Read all frames
            frames = wav_file.readframes(wav_file.getnframes())
            self.audio_data = np.frombuffer(frames, dtype=np.int16)
            self.position = 0

    async def recv(self) -> AudioFrame:
        """Receive next audio frame."""       
        # Get next chunk
        end_pos = min(self.position + self.samples_per_frame, len(self.audio_data))
        chunk = self.audio_data[self.position:end_pos]
        
        # Pad with silence if needed
        if len(chunk) < self.samples_per_frame:
            chunk = np.pad(chunk, (0, self.samples_per_frame - len(chunk)), mode='constant')
        
        # Log every 50th frame to avoid spam
        if self.position % (self.samples_per_frame * 50) == 0:
            chunk_min, chunk_max = chunk.min(), chunk.max()
            chunk_rms = np.sqrt(np.mean(chunk.astype(float) ** 2))
            logger.debug(f"Sending frame at position {self.position}: min={chunk_min}, max={chunk_max}, RMS={chunk_rms:.2f}")
        
        # Create audio frame
        frame = AudioFrame(
            format='s16',
            layout='mono',
            samples=self.samples_per_frame
        )
        frame.planes[0].update(chunk.tobytes())
        frame.sample_rate = self.sample_rate
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, self.sample_rate)
        
        self._timestamp += self.samples_per_frame
        self.position = end_pos
        
        # Delay for exactly 20ms to match WebRTC frame timing
        await asyncio.sleep(0.02) 
        
        return frame


class TestClient:
    """Test client for AI Assistant service."""
    
    def __init__(self, server_url: str = "localhost:8080"):
        self.server_url = f"ws://{server_url}/ws"
        self.pc = None
        self.websocket = None
        self.audio_track = None
        self.recorder = None
        
    async def connect(self):
        """Connect to the signaling server."""
        logger.info(f"Connecting to {self.server_url}")
        self.websocket = await websockets.connect(self.server_url)
        logger.info("Connected to signaling server")
        
    async def setup_peer_connection(self, audio_file: str = None):
        """Set up WebRTC peer connection."""
        self.pc = RTCPeerConnection()
        
        # Set up event handlers
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
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
            logger.info(f"Received {track.kind} track from server")
            
            if track.kind == "audio":
                # Record received audio
                logger.info("Starting recorder for received audio")
                # MediaRecorder should auto-detect the sample rate from the track
                # But we can also wrap it to ensure correct format
                self.recorder = MediaRecorder("output.wav", format="wav")
                self.recorder.addTrack(track)
                await self.recorder.start()
                logger.info("Recorder started - saving to output.wav at track's native sample rate")
                logger.info(f"Track sample rate will be: {track.kind} track (48kHz expected from TTS)")
        
        # Add audio track
        if audio_file and Path(audio_file).exists():
            logger.info(f"Adding audio track from {audio_file}")
            self.audio_track = AudioFileTrack(audio_file)
            self.pc.addTrack(self.audio_track)
        else:
            logger.warning("No audio file specified, using microphone")
            # You could add microphone input here
        
    async def start_call(self):
        """Initiate WebRTC call."""
        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        # Send offer to server
        await self._send_message({
            'type': 'offer',
            'sdp': self.pc.localDescription.sdp
        })
        
        logger.info("Sent offer to server")
        
        # Wait for answer
        message = await self._receive_message()
        
        if message['type'] == 'answer':
            answer = RTCSessionDescription(
                sdp=message['sdp'],
                type='answer'
            )
            await self.pc.setRemoteDescription(answer)
            logger.info("Received answer from server")
        
    async def _send_message(self, message: dict):
        """Send message to server."""
        await self.websocket.send(json.dumps(message))
        
    async def _receive_message(self) -> dict:
        """Receive message from server."""
        message = await self.websocket.recv()
        return json.loads(message)
    
    async def run(self, audio_file: str = None, duration: int = 30):
        """Run the test client."""
        try:
            await self.connect()
            await self.setup_peer_connection(audio_file)
            await self.start_call()
            
            logger.info(f"Call established, running for {duration} seconds...")
            await asyncio.sleep(duration)
            
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
        finally:
            await self.close()
    
    async def close(self):
        """Close connections."""
        # Stop recorder first
        if self.recorder:
            logger.info("Stopping recorder...")
            await self.recorder.stop()
            logger.info("Recording saved to output.wav")
            
            # Verify the output file
            try:
                with wave.open("output.wav", 'rb') as wav:
                    logger.info(f"Output WAV file info:")
                    logger.info(f"  Sample rate: {wav.getframerate()} Hz")
                    logger.info(f"  Channels: {wav.getnchannels()}")
                    logger.info(f"  Sample width: {wav.getsampwidth()} bytes")
                    logger.info(f"  Duration: {wav.getnframes() / wav.getframerate():.2f} seconds")
                    
                    if wav.getframerate() != 48000:
                        logger.warning(f"WARNING: Expected 48kHz but got {wav.getframerate()} Hz!")
                        logger.warning("This will cause playback speed issues!")
            except Exception as e:
                logger.error(f"Could not verify output file: {e}")

        if self.pc:
            await self.pc.close()
        if self.websocket:
            await self.websocket.close()
        logger.info("Closed connections")


async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test AI Assistant WebRTC service')
    parser.add_argument('--server', default='localhost:8080',
                        help='WebSocket server URL')
    parser.add_argument('--audio-file', help='Path to WAV file (16kHz, mono, 16-bit)')
    parser.add_argument('--duration', type=int, default=30,
                        help='Test duration in seconds')
    
    args = parser.parse_args()
    
    client = TestClient(args.server)
    await client.run(args.audio_file, args.duration)


if __name__ == '__main__':
    asyncio.run(main())
