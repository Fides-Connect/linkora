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
from .hub_spoke_schema import init_hub_spoke_schema
__all__ = [
    "AIAssistant",
    "AudioProcessor",
    "AudioOutputTrack",
    "PeerConnectionHandler",
    "SignalingServer",
    "init_hub_spoke_schema",
]
