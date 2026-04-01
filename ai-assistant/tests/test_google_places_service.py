"""
Unit tests for GooglePlacesService.

Covers:
- is_enabled() flag
- generate_query() — success and LLM error cases
- fetch_and_ingest() — success, zero results, circuit breaker, rate limit, 5xx
- _extract_location() static helper
- _run_gp_pipeline() in ConversationService
- Deterministic UUID behaviour
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from ai_assistant.services.google_places_service import (
    GooglePlacesService,
    GpResult,
    _CIRCUIT_THRESHOLD,
    _CIRCUIT_RESET_SECONDS,
    _extract_category,
    _RateLimitError,
    _HttpError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_service(api_key: str = "test-key") -> GooglePlacesService:
    """Return a GooglePlacesService instance with a mocked LLMService."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value="plumber Munich")
    with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": api_key}):
        svc = GooglePlacesService(llm_service=llm)
    return svc


def _fake_place(
    place_id: str = "ChIJ_id1",
    name: str = "Test Plumber GmbH",
    rating: float = 4.5,
    types: list[str] | None = None,
    phone: str = "+49 89 0000",
    address: str = "Teststraße 1, Munich",
    website: str = "https://example.com",
    editorial_summary: str | None = "Professional plumbing in Munich.",
) -> dict:
    """Return a fake Place object in Places API (New) response format."""
    place: dict = {
        "id": place_id,
        "displayName": {"text": name, "languageCode": "de"},
        "rating": rating,
        "types": types or ["plumber", "service_establishment"],
        "nationalPhoneNumber": phone,
        "formattedAddress": address,
        "websiteUri": website,
    }
    if editorial_summary:
        place["editorialSummary"] = {"text": editorial_summary, "languageCode": "de"}
    return place


# ---------------------------------------------------------------------------
# is_enabled()
# ---------------------------------------------------------------------------


class TestIsEnabled:
    def test_enabled_when_key_present(self) -> None:
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "abc123"}):
            assert GooglePlacesService.is_enabled() is True

    def test_disabled_when_key_empty(self) -> None:
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": ""}):
            assert GooglePlacesService.is_enabled() is False

    def test_disabled_when_key_missing(self) -> None:
        import os
        env = {k: v for k, v in os.environ.items() if k != "GOOGLE_PLACES_API_KEY"}
        with patch.dict("os.environ", env, clear=True):
            assert GooglePlacesService.is_enabled() is False


# ---------------------------------------------------------------------------
# generate_query()
# ---------------------------------------------------------------------------


class TestGenerateQuery:
    async def test_returns_phrase_on_success(self) -> None:
        svc = _make_service()
        svc._llm.generate = AsyncMock(return_value="  wedding photographer  ")
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "key"}):
            result = await svc.generate_query(
                structured_query='{"category": "Photography"}',
                hyde_text="professional wedding photographer",
                location="Berlin",
            )
        assert result == "wedding photographer"

    async def test_returns_none_on_llm_error(self) -> None:
        svc = _make_service()
        svc._llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "key"}):
            result = await svc.generate_query(
                structured_query='{}',
                hyde_text="",
                location="",
            )
        assert result is None

    async def test_returns_none_when_response_too_long(self) -> None:
        svc = _make_service()
        svc._llm.generate = AsyncMock(return_value="x" * 201)
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "key"}):
            result = await svc.generate_query(
                structured_query='{}',
                hyde_text="",
                location="",
            )
        assert result is None

    async def test_accepts_dict_as_structured_query(self) -> None:
        """generate_query should accept dict (not just str) without raising."""
        svc = _make_service()
        svc._llm.generate = AsyncMock(return_value="electrician Frankfurt")
        with patch.dict("os.environ", {"GOOGLE_PLACES_API_KEY": "key"}):
            result = await svc.generate_query(
                structured_query={"category": "Electrical"},
                hyde_text="",
                location="Frankfurt",
            )
        assert result == "electrician Frankfurt"


# ---------------------------------------------------------------------------
# fetch_and_ingest()
# ---------------------------------------------------------------------------


class TestFetchAndIngest:
    async def test_success_returns_written_count(self) -> None:
        svc = _make_service()
        places = [_fake_place(place_id=f"id{i}") for i in range(3)]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  return_value="uuid-ok"),
        ):
            result = await svc.fetch_and_ingest("plumber Munich")

        assert isinstance(result, GpResult)
        assert result.providers_written == 3
        assert result.error is False
        assert result.error_code == ""

    async def test_zero_results(self) -> None:
        svc = _make_service()
        with patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[])):
            result = await svc.fetch_and_ingest("nonsense query xyz")

        assert result.providers_written == 0
        assert result.error is False

    async def test_rate_limit_returns_error(self) -> None:
        svc = _make_service()
        with patch.object(svc, "_fetch_places", new=AsyncMock(side_effect=_RateLimitError())):
            result = await svc.fetch_and_ingest("plumber Munich")

        assert result.error is True
        assert result.error_code == "rate_limited"

    async def test_http_error_returns_error(self) -> None:
        svc = _make_service()
        with patch.object(svc, "_fetch_places", new=AsyncMock(side_effect=_HttpError(503))):
            result = await svc.fetch_and_ingest("test")

        assert result.error is True
        assert result.error_code == "http_error"

    async def test_timeout_returns_error(self) -> None:
        svc = _make_service()
        with patch.object(svc, "_fetch_places", new=AsyncMock(side_effect=asyncio.TimeoutError())):
            result = await svc.fetch_and_ingest("test")

        assert result.error is True
        assert result.error_code == "timeout"


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    async def test_circuit_opens_after_threshold_failures(self) -> None:
        svc = _make_service()
        places = [_fake_place()]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(side_effect=_HttpError(500))),
        ):
            for _ in range(_CIRCUIT_THRESHOLD):
                await svc.fetch_and_ingest("test")

        # Circuit should now be open
        assert svc._circuit_opened_at is not None

    async def test_circuit_open_returns_error_immediately(self) -> None:
        svc = _make_service()
        # Open the circuit manually
        import time
        svc._circuit_opened_at = time.monotonic()
        svc._consecutive_failures = _CIRCUIT_THRESHOLD

        result = await svc.fetch_and_ingest("test")

        assert result.error is True
        assert result.error_code == "circuit_open"

    async def test_circuit_resets_after_cooldown(self) -> None:
        svc = _make_service()
        import time
        # Set circuit opened well in the past
        svc._circuit_opened_at = time.monotonic() - (_CIRCUIT_RESET_SECONDS + 1)
        svc._consecutive_failures = _CIRCUIT_THRESHOLD

        places = [_fake_place()]
        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  return_value="uuid-ok"),
        ):
            result = await svc.fetch_and_ingest("plumber Munich")

        assert result.error is False
        assert svc._circuit_opened_at is None

    async def test_success_resets_failure_count(self) -> None:
        svc = _make_service()
        svc._consecutive_failures = 2  # almost at threshold

        places = [_fake_place()]
        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  return_value="uuid-ok"),
        ):
            await svc.fetch_and_ingest("plumber")

        assert svc._consecutive_failures == 0


# ---------------------------------------------------------------------------
# Deterministic UUID
# ---------------------------------------------------------------------------


class TestDeterministicUuids:
    async def test_same_place_id_produces_same_user_uuid(self) -> None:
        """Two ingest runs with the same place_id must call upsert with the same UUID."""
        svc = _make_service()
        places = [_fake_place(place_id="ChIJtest")]
        captured_uuids: list[str] = []

        def _capture_uuid(user_data: dict, competence_data: dict | None = None) -> str | None:
            captured_uuids.append(user_data["uuid"])
            return user_data["uuid"]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  side_effect=_capture_uuid),
        ):
            await svc.fetch_and_ingest("plumber Munich")
            await svc.fetch_and_ingest("plumber Munich")

        assert len(captured_uuids) == 2
        assert captured_uuids[0] == captured_uuids[1], "Same place_id must yield same UUID"

    async def test_different_place_ids_produce_different_uuids(self) -> None:
        svc = _make_service()
        places = [
            _fake_place(place_id="ChIJaaa"),
            _fake_place(place_id="ChIJbbb"),
        ]
        captured_uuids: list[str] = []

        def _capture_uuid(user_data: dict, competence_data: dict | None = None) -> str | None:
            captured_uuids.append(user_data["uuid"])
            return user_data["uuid"]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  side_effect=_capture_uuid),
        ):
            await svc.fetch_and_ingest("test")

        assert len(captured_uuids) == 2
        assert captured_uuids[0] != captured_uuids[1]


# ---------------------------------------------------------------------------
# _extract_category()
# ---------------------------------------------------------------------------


class TestExtractCategory:
    def test_maps_known_type(self) -> None:
        assert _extract_category(["plumber", "service_establishment"]) == "Plumbing"

    def test_falls_back_to_other(self) -> None:
        assert _extract_category(["unknown_type_xyz"]) == "other"

    def test_empty_list_returns_other(self) -> None:
        assert _extract_category([]) == "other"

    def test_first_matching_type_wins(self) -> None:
        # "plumber" appears before "photographer" in _TYPE_CATEGORY_MAP
        assert _extract_category(["plumber", "photographer"]) == "Plumbing"


# ---------------------------------------------------------------------------
# ConversationService._extract_location()
# ---------------------------------------------------------------------------


class TestExtractLocation:
    def test_extracts_location_from_json(self) -> None:
        from ai_assistant.services.conversation_service import ConversationService
        query_text = json.dumps({"location": "Berlin", "category": "Plumbing"})
        assert ConversationService._extract_location(query_text) == "Berlin"

    def test_returns_empty_when_missing(self) -> None:
        from ai_assistant.services.conversation_service import ConversationService
        query_text = json.dumps({"category": "Plumbing"})
        assert ConversationService._extract_location(query_text) == ""

    def test_returns_empty_on_invalid_json(self) -> None:
        from ai_assistant.services.conversation_service import ConversationService
        assert ConversationService._extract_location("not json at all") == ""

    def test_returns_empty_when_location_none(self) -> None:
        from ai_assistant.services.conversation_service import ConversationService
        query_text = json.dumps({"location": None})
        assert ConversationService._extract_location(query_text) == ""


# ---------------------------------------------------------------------------
# ConversationService._run_gp_pipeline()
# ---------------------------------------------------------------------------


class TestRunGpPipeline:
    def _make_conversation_service(self, gp_service: GooglePlacesService):
        from ai_assistant.services.conversation_service import ConversationService
        from unittest.mock import MagicMock
        llm = MagicMock()
        dp = MagicMock()
        cs = ConversationService.__new__(ConversationService)
        cs._llm = llm
        cs.google_places_service = gp_service
        cs.language = "de"
        return cs

    async def test_run_gp_pipeline_success(self) -> None:
        svc = _make_service()
        svc.generate_query = AsyncMock(return_value="plumber Munich")
        svc.fetch_and_ingest = AsyncMock(return_value=GpResult(providers_written=3))

        from ai_assistant.services.conversation_service import ConversationService, GpResult as CsGpResult
        cs = self._make_conversation_service(svc)
        result = await ConversationService._run_gp_pipeline(
            cs,
            gp_service=svc,
            query_text='{"location": "Munich", "category": "Plumbing"}',
            hyde_text="professional plumber",
        )

        assert result.providers_written == 3
        assert result.error is False

    async def test_run_gp_pipeline_skips_when_query_is_none(self) -> None:
        svc = _make_service()
        svc.generate_query = AsyncMock(return_value=None)
        svc.fetch_and_ingest = AsyncMock(return_value=GpResult(providers_written=0))

        from ai_assistant.services.conversation_service import ConversationService
        cs = self._make_conversation_service(svc)
        result = await ConversationService._run_gp_pipeline(
            cs,
            gp_service=svc,
            query_text='{"location": "Munich"}',
            hyde_text="",
        )

        assert result.providers_written == 0
        assert result.error is False
        assert result.error_code == "llm_skip"
        svc.fetch_and_ingest.assert_not_called()

    async def test_run_gp_pipeline_propagates_gp_error(self) -> None:
        svc = _make_service()
        svc.generate_query = AsyncMock(return_value="plumber Munich")
        svc.fetch_and_ingest = AsyncMock(return_value=GpResult(error=True, error_code="timeout"))

        from ai_assistant.services.conversation_service import ConversationService
        cs = self._make_conversation_service(svc)
        result = await ConversationService._run_gp_pipeline(
            cs,
            gp_service=svc,
            query_text='{"location": "Munich"}',
            hyde_text="",
        )

        assert result.error is True
        assert result.error_code == "timeout"
