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
    _extract_review_snippets,
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


def _make_review(text: str) -> dict:
    """Return a fake Places API (New) review object."""
    return {"text": {"text": text, "languageCode": "de"}, "rating": 5}


def _fake_place(
    place_id: str = "ChIJ_id1",
    name: str = "Test Plumber GmbH",
    rating: float = 4.5,
    types: list[str] | None = None,
    phone: str = "+49 89 0000",
    address: str = "Teststraße 1, Munich",
    website: str = "https://example.com",
    editorial_summary: str | None = "Professional plumbing in Munich.",
    reviews: list[dict] | None = None,
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
    if reviews is not None:
        place["reviews"] = reviews
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


# ---------------------------------------------------------------------------
# _extract_review_snippets()
# ---------------------------------------------------------------------------


class TestExtractReviewSnippets:
    def test_returns_empty_for_no_reviews(self) -> None:
        assert _extract_review_snippets([]) == []

    def test_extracts_text_from_review_objects(self) -> None:
        reviews = [_make_review("Great custom cakes!"), _make_review("Perfect wedding cake.")]
        result = _extract_review_snippets(reviews)
        assert result == ["Great custom cakes!", "Perfect wedding cake."]

    def test_truncates_at_word_boundary(self) -> None:
        long_text = "word " * 30  # 150 chars
        result = _extract_review_snippets([_make_review(long_text)], max_chars=50)
        assert len(result) == 1
        assert len(result[0]) <= 50
        assert not result[0].endswith(" ")

    def test_respects_max_count(self) -> None:
        reviews = [_make_review(f"Review {i}") for i in range(5)]
        result = _extract_review_snippets(reviews, max_count=2)
        assert len(result) == 2

    def test_skips_reviews_with_no_text(self) -> None:
        reviews = [{"text": {}, "rating": 5}, _make_review("Good service")]
        result = _extract_review_snippets(reviews)
        assert result == ["Good service"]


# ---------------------------------------------------------------------------
# Review enrichment in search_optimized_summary
# ---------------------------------------------------------------------------


class TestReviewEnrichment:
    async def test_search_optimized_summary_includes_review_snippets(self) -> None:
        """Reviews are passed to the LLM synthesiser as context; the output
        becomes the English search_optimized_summary."""
        svc = _make_service()
        # LLM returns something that proves review context was used
        svc._llm.generate = AsyncMock(
            return_value="Specialises in Harry Potter themed wedding cakes for large events."
        )
        place = _fake_place(
            editorial_summary="Professional wedding cake bakery in Berlin.",
            reviews=[
                _make_review("They crafted an amazing Harry Potter themed wedding cake!"),
                _make_review("Specialty: fantasy and fairy tale custom designs for large events."),
            ],
        )

        captured_competence: list[dict] = []

        def _capture(user_data: dict, competence_data: dict | None = None) -> str | None:
            if competence_data:
                captured_competence.append(competence_data)
            return user_data["uuid"]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[place])),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  side_effect=_capture),
        ):
            await svc.fetch_and_ingest("wedding cake bakery Berlin")

        assert len(captured_competence) == 1
        summary = captured_competence[0]["search_optimized_summary"]
        # summary is the English LLM synthesis result
        assert summary == "Specialises in Harry Potter themed wedding cakes for large events."
        # description remains the original GP editorial text (may be non-English)
        assert captured_competence[0]["description"] == "Professional wedding cake bakery in Berlin."
        # Old direct-concatenation format must NOT appear
        assert "Customer experiences:" not in summary

    async def test_search_optimized_summary_equals_description_when_no_reviews(self) -> None:
        """search_optimized_summary is always the English LLM synthesis result;
        description keeps the original editorial text."""
        svc = _make_service()
        svc._llm.generate = AsyncMock(
            return_value="Expert plumber offering emergency and installation services in Munich."
        )
        place = _fake_place(
            editorial_summary="Expert plumber in Munich.",
            reviews=[],
        )
        captured_competence: list[dict] = []

        def _capture(user_data: dict, competence_data: dict | None = None) -> str | None:
            if competence_data:
                captured_competence.append(competence_data)
            return user_data["uuid"]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[place])),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  side_effect=_capture),
        ):
            await svc.fetch_and_ingest("plumber Munich")

        assert len(captured_competence) == 1
        # search_optimized_summary is the English LLM output
        assert captured_competence[0]["search_optimized_summary"] == (
            "Expert plumber offering emergency and installation services in Munich."
        )
        # description is still the original editorial summary
        assert captured_competence[0]["description"] == "Expert plumber in Munich."

    async def test_synthesis_uses_review_context(self) -> None:
        """_synthesise_description must pass review snippets to the LLM prompt."""
        svc = _make_service()
        captured_prompts: list[str] = []

        async def _capture_generate(messages: list) -> str:
            captured_prompts.append(messages[0].content)
            return "Custom wedding cake specialist in Berlin."

        svc._llm.generate = _capture_generate

        place = _fake_place(
            editorial_summary=None,  # forces synthesis
            reviews=[_make_review("Amazing Harry Potter cake for our wedding!")],
            website="",  # no URL — crawler must not be invoked for this test
        )

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[place])),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  return_value="uuid-ok"),
        ):
            await svc.fetch_and_ingest("wedding cake")

        assert len(captured_prompts) == 1
        assert "Harry Potter" in captured_prompts[0]

    async def test_review_snippets_stored_in_competence_data(self) -> None:
        """review_snippets must be populated in competence_data when reviews are present."""
        svc = _make_service()
        svc._llm.generate = AsyncMock(return_value="Custom cake specialist.")
        place = _fake_place(
            editorial_summary="Custom cake shop.",
            reviews=[
                _make_review("Beautiful designs"),
                _make_review("Very punctual delivery"),
                _make_review("Will recommend to friends"),
            ],
        )
        captured_competence: list[dict] = []

        def _capture(user_data: dict, competence_data: dict | None = None) -> str | None:
            if competence_data:
                captured_competence.append(competence_data)
            return user_data["uuid"]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[place])),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  side_effect=_capture),
        ):
            await svc.fetch_and_ingest("cake shop")

        assert len(captured_competence) == 1
        snippets = captured_competence[0]["review_snippets"]
        assert isinstance(snippets, list)
        assert len(snippets) == 3
        assert "Beautiful designs" in snippets
        assert "Very punctual delivery" in snippets

    async def test_review_snippets_empty_when_no_reviews(self) -> None:
        """review_snippets must be an empty list when no reviews are available."""
        svc = _make_service()
        svc._llm.generate = AsyncMock(return_value="Plumber in Munich.")
        place = _fake_place(editorial_summary="Plumber in Munich.", reviews=[])
        captured_competence: list[dict] = []

        def _capture(user_data: dict, competence_data: dict | None = None) -> str | None:
            if competence_data:
                captured_competence.append(competence_data)
            return user_data["uuid"]

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[place])),
            patch("ai_assistant.hub_spoke_ingestion.HubSpokeIngestion.upsert_user",
                  side_effect=_capture),
        ):
            await svc.fetch_and_ingest("plumber")

        assert len(captured_competence) == 1
        assert captured_competence[0]["review_snippets"] == []


# ---------------------------------------------------------------------------
# fetch_as_providers() — Weaviate-free lite path
# ---------------------------------------------------------------------------


class TestFetchAsProviders:
    """fetch_as_providers returns provider dicts shaped for the cross-encoder
    and FINALIZE prompt, without writing to or reading from Weaviate."""

    async def test_returns_provider_dicts_with_correct_shape(self) -> None:
        """Happy path: normalised places become properly shaped provider dicts."""
        svc = _make_service()
        places = [_fake_place(place_id="ChIJtest", name="Cake Studio")]

        with patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)):
            providers, result = await svc.fetch_as_providers(
                structured_query="cake maker Berlin",
                hyde_text="A professional cake studio in Berlin",
            )

        assert result.error is False
        assert result.providers_written == 1
        assert len(providers) == 1

        p = providers[0]
        # Must have the fields cross-encoder and FINALIZE expect
        assert "uuid" in p
        assert "title" in p
        assert "search_optimized_summary" in p
        assert "skills_list" in p
        assert "review_snippets" in p
        assert "user" in p
        assert p["user"]["source"] == "google_places"
        assert p["user"]["is_service_provider"] is True
        # Contact fields must be at top level too (for Flutter card rendering)
        assert "phone" in p
        assert "website" in p
        assert "address" in p

    async def test_zero_results_returns_empty_list(self) -> None:
        svc = _make_service()
        with patch.object(svc, "_fetch_places", new=AsyncMock(return_value=[])):
            providers, result = await svc.fetch_as_providers(
                structured_query="plumber Munich",
                hyde_text="",
            )

        assert providers == []
        assert result.error is False
        assert result.providers_written == 0

    async def test_rate_limit_returns_error(self) -> None:
        svc = _make_service()
        with patch.object(svc, "_fetch_places", new=AsyncMock(side_effect=_RateLimitError())):
            providers, result = await svc.fetch_as_providers("plumber Munich", hyde_text="")

        assert providers == []
        assert result.error is True
        assert result.error_code == "rate_limited"

    async def test_circuit_open_returns_error(self) -> None:
        svc = _make_service()
        import time
        svc._circuit_opened_at = time.monotonic()
        svc._consecutive_failures = _CIRCUIT_THRESHOLD

        providers, result = await svc.fetch_as_providers("plumber Munich", hyde_text="")

        assert providers == []
        assert result.error is True
        assert result.error_code == "circuit_open"




# ---------------------------------------------------------------------------
# TestWebEnrichment
# ---------------------------------------------------------------------------


class TestWebEnrichment:
    """Verify that WebPageCrawler results are merged into normalised place dicts."""

    async def test_skills_list_populated_from_crawl(self) -> None:
        """crawl.services propagates into skills_list."""
        from ai_assistant.services.webpage_crawler import WebCrawlResult

        svc = _make_service()
        places = [_fake_place()]
        crawl = WebCrawlResult(services=["Pipe repair", "Boiler install"])

        with (
            patch.object(svc, "_fetch_places", new=AsyncMock(return_value=places)),
            patch(
                "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
                new=AsyncMock(return_value=crawl),
            ),
        ):
            normalised = await svc._normalise_places(places, "plumber Munich")

        assert normalised[0]["skills_list"] == ["Pipe repair", "Boiler install"]

    async def test_search_summary_augmented_with_specialities(self) -> None:
        """crawl.specialities is appended to search_optimized_summary."""
        from ai_assistant.services.webpage_crawler import WebCrawlResult

        svc = _make_service()
        places = [_fake_place(editorial_summary="Plumbing in Munich.")]
        crawl = WebCrawlResult(specialities="Emergency specialist open 24/7")

        with (
            patch(
                "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
                new=AsyncMock(return_value=crawl),
            ),
        ):
            normalised = await svc._normalise_places(places, "plumber")

        assert "Emergency specialist open 24/7" in normalised[0]["search_optimized_summary"]

    async def test_search_summary_augmented_with_services(self) -> None:
        """crawl.services list is appended to search_optimized_summary for vectorization."""
        from ai_assistant.services.webpage_crawler import WebCrawlResult

        svc = _make_service()
        places = [_fake_place(editorial_summary="Cake studio in Berlin.")]
        crawl = WebCrawlResult(services=["Custom wedding cakes", "Gluten-free options", "City-wide delivery"])

        with (
            patch(
                "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
                new=AsyncMock(return_value=crawl),
            ),
        ):
            normalised = await svc._normalise_places(places, "cake")

        summary = normalised[0]["search_optimized_summary"]
        assert "Custom wedding cakes" in summary
        assert "Gluten-free options" in summary
        assert "City-wide delivery" in summary

    async def test_description_augmented_with_portfolio_and_coverage(self) -> None:
        """portfolio_highlights and coverage_area are appended to description."""
        from ai_assistant.services.webpage_crawler import WebCrawlResult

        svc = _make_service()
        places = [_fake_place(editorial_summary="Professional plumbers.")]
        crawl = WebCrawlResult(
            portfolio_highlights="Renovated 50+ bathrooms",
            coverage_area="Serving Munich and surroundings",
        )

        with (
            patch(
                "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
                new=AsyncMock(return_value=crawl),
            ),
        ):
            normalised = await svc._normalise_places(places, "plumber")

        desc = normalised[0]["description"]
        assert "Renovated 50+ bathrooms" in desc
        assert "Serving Munich and surroundings" in desc

    async def test_none_crawl_result_gracefully_skipped(self) -> None:
        """WebCrawlResult=None → skills_list=[], webpage_crawled=False, no error."""
        svc = _make_service()
        places = [_fake_place()]

        with patch(
            "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
            new=AsyncMock(return_value=None),
        ):
            normalised = await svc._normalise_places(places, "plumber")

        assert normalised[0]["skills_list"] == []
        assert normalised[0]["webpage_crawled"] is False

    async def test_webpage_crawled_flag_true_on_success(self) -> None:
        """A valid WebCrawlResult sets webpage_crawled=True."""
        from ai_assistant.services.webpage_crawler import WebCrawlResult

        svc = _make_service()
        places = [_fake_place()]
        crawl = WebCrawlResult(services=["Repair"])

        with patch(
            "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
            new=AsyncMock(return_value=crawl),
        ):
            normalised = await svc._normalise_places(places, "plumber")

        assert normalised[0]["webpage_crawled"] is True

    async def test_crawl_exception_treated_as_None(self) -> None:
        """If extract_provider_info raises, result is treated as missing enrichment."""
        svc = _make_service()
        places = [_fake_place()]

        with patch(
            "ai_assistant.services.google_places_service.WebPageCrawler.extract_provider_info",
            new=AsyncMock(side_effect=Exception("timeout")),
        ):
            # asyncio.gather with return_exceptions=True swallows the exception
            normalised = await svc._normalise_places(places, "plumber")

        assert normalised[0]["skills_list"] == []
        assert normalised[0]["webpage_crawled"] is False
