"""SessionMode — enum for the two conversation modes (voice / text)."""
from enum import Enum


class SessionMode(str, Enum):
    """The transport/interaction mode for a session.

    ``VOICE``: audio input via WebRTC track; greeting played on connect.
    ``TEXT``: no audio; DataChannel text-input only; greeting skipped.
    """
    VOICE = "voice"
    TEXT  = "text"
