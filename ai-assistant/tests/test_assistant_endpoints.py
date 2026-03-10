"""
Unit tests for /api/v1/assistant/* endpoints.
Covers the greet_warmup happy path and key failure cases.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, AsyncMock
from aiohttp import web

from ai_assistant.api.v1.endpoints import assistant


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_request(token: str = "valid_token") -> Mock:
    request = Mock(spec=web.Request)
    request.headers = {"Authorization": f"Bearer {token}"}
    return request


def _make_tts_transport():
    transport = MagicMock()
    transport.close = AsyncMock()
    return transport


def _make_tts_client(transport):
    client = MagicMock()
    client.transport = transport
    return client


def _make_tts_service(audio_bytes: bytes = b"\x00\x01" * 100):
    """Return a mock TextToSpeechService that yields one chunk."""

    async def _fake_stream(*_args, **_kwargs):
        yield audio_bytes

    transport = _make_tts_transport()
    tts = MagicMock()
    tts.synthesize_stream = _fake_stream
    tts.client = _make_tts_client(transport)
    return tts, transport


# ── tests ─────────────────────────────────────────────────────────────────────

class TestGreetWarmup:

    @pytest.fixture(autouse=True)
    def _mock_auth(self):
        with patch("ai_assistant.api.deps.auth.verify_id_token", return_value={"uid": "user_123"}):
            yield

    @pytest.fixture()
    def mock_firestore(self):
        with patch.object(assistant._firestore_service, "get_user", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture()
    def mock_greeting_cache(self):
        cache = MagicMock()
        cache.store = Mock()
        with patch("ai_assistant.api.v1.endpoints.assistant.get_greeting_cache", return_value=cache):
            yield cache

    async def test_happy_path_returns_ready_and_greeting(self, mock_firestore, mock_greeting_cache):
        """200 response with ready=True and greeting_text when everything succeeds."""
        mock_firestore.return_value = {
            "name": "Max Mustermann",
            "has_open_request": False,
            "user_app_settings": {"language": "de"},
        }

        tts_svc, transport = _make_tts_service()

        with (
            patch(
                "ai_assistant.api.v1.endpoints.assistant.ConversationService.generate_greeting_text",
                new_callable=AsyncMock,
                return_value="Hallo Max!",
            ),
            patch(
                "ai_assistant.api.v1.endpoints.assistant.TextToSpeechService",
                return_value=tts_svc,
            ),
        ):
            response = await assistant.greet_warmup(_make_request())

        import json
        body = json.loads(response.body)
        assert response.status == 200
        assert body["ready"] is True
        assert body["greeting_text"] == "Hallo Max!"

    async def test_tts_transport_close_is_awaited(self, mock_firestore, mock_greeting_cache):
        """TTS gRPC transport must be closed (awaited) even on success."""
        mock_firestore.return_value = {"name": "Anna", "has_open_request": False}

        tts_svc, transport = _make_tts_service()

        with (
            patch(
                "ai_assistant.api.v1.endpoints.assistant.ConversationService.generate_greeting_text",
                new_callable=AsyncMock,
                return_value="Hi Anna!",
            ),
            patch(
                "ai_assistant.api.v1.endpoints.assistant.TextToSpeechService",
                return_value=tts_svc,
            ),
        ):
            await assistant.greet_warmup(_make_request())

        transport.close.assert_awaited_once()

    async def test_tts_transport_closed_on_tts_failure(self, mock_firestore, mock_greeting_cache):
        """TTS gRPC transport must be closed even when TTS synthesis raises."""
        mock_firestore.return_value = {"name": "Tom"}

        async def _bad_stream(*_a, **_kw):
            raise RuntimeError("TTS failed")
            yield  # make it a generator

        transport = _make_tts_transport()
        tts_client = _make_tts_client(transport)
        tts_svc = MagicMock()
        tts_svc.synthesize_stream = _bad_stream
        tts_svc.client = tts_client

        with (
            patch(
                "ai_assistant.api.v1.endpoints.assistant.ConversationService.generate_greeting_text",
                new_callable=AsyncMock,
                return_value="Hallo!",
            ),
            patch(
                "ai_assistant.api.v1.endpoints.assistant.TextToSpeechService",
                return_value=tts_svc,
            ),
        ):
            response = await assistant.greet_warmup(_make_request())

        # Should return 500 but still close transport
        assert response.status == 500
        transport.close.assert_awaited_once()

    async def test_missing_auth_returns_401(self):
        """Missing Authorization header → 401 Unauthorized."""
        request = Mock(spec=web.Request)
        request.headers = {}
        with pytest.raises(web.HTTPUnauthorized):
            await assistant.greet_warmup(request)

    async def test_firestore_unavailable_returns_500(self, mock_greeting_cache):
        """Firestore failure → 500 Internal Server Error."""
        with patch.object(
            assistant._firestore_service, "get_user", new_callable=AsyncMock,
            side_effect=Exception("Firestore down"),
        ):
            response = await assistant.greet_warmup(_make_request())

        assert response.status == 500

    async def test_greeting_cached_with_user_id_and_language(self, mock_firestore, mock_greeting_cache):
        """The generated greeting is stored in the cache with correct keys."""
        mock_firestore.return_value = {
            "name": "Sophie",
            "has_open_request": True,
            "user_app_settings": {"language": "en"},
        }
        tts_svc, transport = _make_tts_service(b"\xff" * 200)

        with (
            patch(
                "ai_assistant.api.v1.endpoints.assistant.ConversationService.generate_greeting_text",
                new_callable=AsyncMock,
                return_value="Hello Sophie!",
            ),
            patch(
                "ai_assistant.api.v1.endpoints.assistant.TextToSpeechService",
                return_value=tts_svc,
            ),
        ):
            await assistant.greet_warmup(_make_request())

        mock_greeting_cache.store.assert_called_once()
        args = mock_greeting_cache.store.call_args[0]
        assert args[0] == "user_123"   # user_id
        assert args[1] == "en"         # language
        assert args[2] == "Hello Sophie!"  # greeting_text
        assert len(args[3]) == 200     # audio_bytes

    async def test_unknown_language_defaults_to_en(self, mock_firestore, mock_greeting_cache):
        """An unrecognised language value falls back to 'en'."""
        mock_firestore.return_value = {
            "name": "User",
            "user_app_settings": {"language": "fr"},  # unsupported
        }
        tts_svc, transport = _make_tts_service()

        with (
            patch(
                "ai_assistant.api.v1.endpoints.assistant.ConversationService.generate_greeting_text",
                new_callable=AsyncMock,
                return_value="Hello!",
            ),
            patch(
                "ai_assistant.api.v1.endpoints.assistant.TextToSpeechService",
                return_value=tts_svc,
            ),
        ):
            await assistant.greet_warmup(_make_request())

        # Language stored in cache should be the default 'en'
        args = mock_greeting_cache.store.call_args[0]
        assert args[1] == "en"
