"""In-memory cache for pre-generated greeting text and TTS audio.

The warmup REST endpoint (``POST /api/v1/assistant/greet-warmup``) stores a
fully-synthesised greeting for a user.  When a voice session starts within the
TTL window, ``VoiceSessionStarter`` uses the cached data instead of making a
fresh LLM + TTS call — eliminating 1.5–2.5 s of tap-to-greeting latency.

Cache is keyed by ``(user_id, language)`` so multilingual users are handled
correctly.  Entries expire after ``TTL`` seconds (default 2 minutes) to
prevent stale ``has_open_request`` values from persisting too long.
"""
import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GreetingEntry:
    text: str
    audio_bytes: bytes
    language: str
    expires_at: float


class GreetingCache:
    """Thread-safe (asyncio-safe) in-memory greeting cache."""

    TTL: float = 120.0  # seconds

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], GreetingEntry] = {}

    def store(
        self,
        user_id: str,
        language: str,
        text: str,
        audio_bytes: bytes,
    ) -> None:
        """Cache a pre-generated greeting for *user_id* / *language*."""
        self._store[(user_id, language)] = GreetingEntry(
            text=text,
            audio_bytes=audio_bytes,
            language=language,
            expires_at=time.monotonic() + self.TTL,
        )
        logger.debug(
            "Greeting cached for user=%s lang=%s (%d bytes, TTL=%.0fs)",
            user_id,
            language,
            len(audio_bytes),
            self.TTL,
        )

    def get(self, user_id: str, language: str) -> GreetingEntry | None:
        """Return a non-expired entry or ``None``."""
        key = (user_id, language)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            logger.debug("Greeting cache expired for user=%s lang=%s", user_id, language)
            return None
        return entry

    def invalidate(self, user_id: str) -> None:
        """Remove all cached greetings for *user_id* (e.g. after profile change)."""
        keys = [k for k in self._store if k[0] == user_id]
        for k in keys:
            del self._store[k]
        if keys:
            logger.debug("Greeting cache invalidated for user=%s (%d entry/entries)", user_id, len(keys))


# Module-level singleton — shared across all connections in the process.
_cache = GreetingCache()


def get_greeting_cache() -> GreetingCache:
    """Return the process-wide ``GreetingCache`` singleton."""
    return _cache
