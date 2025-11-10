"""
AI Assistant Package
Real-time voice AI service using WebRTC and Google Cloud APIs.
"""
__version__ = "0.1.0"

from .ai_assistant import AIAssistant
from .audio_processor import AudioProcessor
from .audio_track import AudioOutputTrack
from .peer_connection_handler import PeerConnectionHandler
from .signaling_server import SignalingServer

__all__ = [
    "AIAssistant",
    "AudioProcessor",
    "AudioOutputTrack",
    "PeerConnectionHandler",
    "SignalingServer",
]
