"""Session mode enum shared across AudioProcessor and PeerConnectionHandler."""
from enum import Enum


class SessionMode(str, Enum):
    """Transport mode for a peer-connection session.

    Inherits from ``str`` so that legacy ``== "voice"`` / ``== "text"``
    comparisons continue to work without any change at call sites.
    """

    VOICE = "voice"
    TEXT = "text"
