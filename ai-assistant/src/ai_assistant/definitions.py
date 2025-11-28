"""
Configuration Constants and Definitions
Centralized configuration values for the AI Assistant application.
"""

# ============================================================================
# Agent Identity
# ============================================================================
AGENT_NAME = "Elin"
COMPANY_NAME = "FidesConnect"
USER_NAME_PLACEHOLDER = "Wolfgang"

# ============================================================================
# Conversation Settings
# ============================================================================
MAX_PROVIDERS_TO_PRESENT = 3

# ============================================================================
# WebSocket & Connection Settings
# ============================================================================
# Heartbeat interval - send ping every N seconds
HEARTBEAT_INTERVAL = 10

# Connection timeout - max time without pong before closing connection (seconds)
CONNECTION_TIMEOUT = 30

# Idle timeout - cleanup AIAssistant after N seconds of inactivity (seconds)
IDLE_TIMEOUT = 60  # 5 minutes

# ============================================================================
# LLM Settings
# ============================================================================
LLM_MODEL = "gemini-2.0-flash-exp"
LLM_TEMPERATURE = 0.9
LLM_TOP_K = 8
LLM_TOP_P = 0.9
LLM_MAX_OUTPUT_TOKENS = 512

# ============================================================================
# Speech Recognition Settings
# ============================================================================
STT_ENCODING = "LINEAR16"
STT_SAMPLE_RATE_HZ = 48000
STT_AUDIO_CHANNEL_COUNT = 1
STT_MODEL = "latest_long"
STT_ENABLE_AUTOMATIC_PUNCTUATION = True
STT_USE_ENHANCED = True
STT_INTERIM_RESULTS = True
STT_SINGLE_UTTERANCE = False

# Audio processing timeouts
AUDIO_RECEIVE_TIMEOUT = 5.0  # Timeout for receiving audio frames (seconds)
AUDIO_STREAM_TIMEOUT = 3.0  # Timeout for Google STT stream (seconds)

# ============================================================================
# Text-to-Speech Settings
# ============================================================================
TTS_AUDIO_ENCODING = "LINEAR16"
TTS_SAMPLE_RATE_HZ = 48000
TTS_CHUNK_SIZE = 2048

# ============================================================================
# Conversation Stages
# ============================================================================
class ConversationStage:
    """Conversation stage identifiers."""
    GREETING = "greeting"
    TRIAGE = "triage"
    FINALIZE = "finalize"
    COMPLETED = "completed"
