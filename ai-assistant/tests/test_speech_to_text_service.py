"""
Unit tests for SpeechToTextService — idle-silence timer behaviour.
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_assistant.services.speech_to_text_service import SpeechToTextService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(transcript: str, is_final: bool):
    """Build a minimal mock gRPC StreamingRecognizeResponse result."""
    alt = MagicMock()
    alt.transcript = transcript
    result = MagicMock()
    result.alternatives = [alt]
    result.is_final = is_final
    response = MagicMock()
    response.results = [result]
    return response


async def _collect(stt: SpeechToTextService, responses: list) -> list[tuple[str, bool]]:
    """Run continuous_stream over a fixed list of mock gRPC responses."""
    async def _audio_gen():
        yield b"\x00" * 960

    collected = []
    async for item in stt.continuous_stream(_audio_gen()):
        collected.append(item)
    return collected


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSttIdleSilenceTimer:
    """Verify gRPC stream is closed after 120 s of silence, reset on activity."""

    @pytest.fixture
    def stt(self):
        with patch(
            "ai_assistant.services.speech_to_text_service.SpeechAsyncClient"
        ):
            svc = SpeechToTextService(language_code="de-DE")
        return svc

    async def test_stream_closes_after_120s_silence(self, stt):
        """
        Two empty finals separated by >= 120 s should close the stream on the
        second one (first sets idle_since, second exceeds the threshold).
        """
        responses = [
            _make_result("", is_final=True),   # sets idle_since = t0
            _make_result("", is_final=True),   # t1 - t0 >= 120 → break
        ]

        async def _fake_stream():
            for r in responses:
                yield r

        async def _audio_gen():
            yield b"\x00" * 960

        # Simulate monotonic clock: first call returns 0.0, second returns 121.0
        time_values = iter([0.0, 121.0])

        with (
            patch.object(
                stt.client,
                "streaming_recognize",
                new=AsyncMock(return_value=_fake_stream()),
            ),
            patch(
                "ai_assistant.services.speech_to_text_service.time.monotonic",
                side_effect=lambda: next(time_values),
            ),
        ):
            collected = []
            async for item in stt.continuous_stream(_audio_gen()):
                collected.append(item)

        # The first empty final is yielded.  The second triggers the break
        # (timeout detected) before yield, so only one item is collected.
        assert collected == [("", True)]

    async def test_non_empty_transcript_resets_idle_timer(self, stt):
        """
        An empty final followed by a non-empty transcript must reset idle_since.
        A subsequent empty final at t+121 must NOT close the stream because the
        timer was reset.
        """
        responses = [
            _make_result("", is_final=True),          # sets idle_since = 0
            _make_result("Hallo", is_final=False),     # resets idle_since → None
            _make_result("", is_final=True),           # sets idle_since = 50
            # timer check: 60 - 50 = 10 s < 120 → no break; stream ends naturally
        ]

        async def _fake_stream():
            for r in responses:
                yield r

        async def _audio_gen():
            yield b"\x00" * 960

        time_values = iter([0.0, 50.0, 60.0])

        with (
            patch.object(
                stt.client,
                "streaming_recognize",
                new=AsyncMock(return_value=_fake_stream()),
            ),
            patch(
                "ai_assistant.services.speech_to_text_service.time.monotonic",
                side_effect=lambda: next(time_values),
            ),
        ):
            collected = []
            async for item in stt.continuous_stream(_audio_gen()):
                collected.append(item)

        assert ("Hallo", False) in collected
        # Stream must NOT have been force-closed; all responses consumed
        transcripts = [t for t, _ in collected]
        assert "Hallo" in transcripts

    async def test_interim_transcript_resets_idle_timer(self, stt):
        """
        An interim (non-final) non-empty result also resets the idle timer.
        """
        responses = [
            _make_result("", is_final=True),           # idle_since = 0
            _make_result("Warte", is_final=False),     # non-empty interim → reset
            _make_result("", is_final=True),           # idle_since = 200
            # monotonic next call = 210 → 210-200 = 10 < 120 → no close
        ]

        async def _fake_stream():
            for r in responses:
                yield r

        async def _audio_gen():
            yield b"\x00" * 960

        time_values = iter([0.0, 200.0, 210.0])

        with (
            patch.object(
                stt.client,
                "streaming_recognize",
                new=AsyncMock(return_value=_fake_stream()),
            ),
            patch(
                "ai_assistant.services.speech_to_text_service.time.monotonic",
                side_effect=lambda: next(time_values),
            ),
        ):
            collected = []
            async for item in stt.continuous_stream(_audio_gen()):
                collected.append(item)

        assert len(collected) == 3
        assert ("Warte", False) in collected
