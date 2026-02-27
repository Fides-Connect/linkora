"""Unit tests for CompetenceEnricher.

All LLM calls are mocked — no network access required.
asyncio_mode = "auto" (set in pyproject.toml) so no @pytest.mark.asyncio needed.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_assistant.services.competence_enricher import CompetenceEnricher


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_llm_mock(json_payload: dict):
    """Return a mock LLM whose astream() yields a single chunk with the JSON."""
    chunk = MagicMock()
    chunk.content = json.dumps(json_payload)

    async def _astream(messages):
        yield chunk

    llm = MagicMock()
    llm.astream = _astream
    return llm


def _make_llm_mock_text(text: str):
    """Return a mock LLM whose astream() yields raw text (for error-parsing tests)."""
    chunk = MagicMock()
    chunk.content = text

    async def _astream(messages):
        yield chunk

    llm = MagicMock()
    llm.astream = _astream
    return llm


def _make_failing_llm():
    """Return a mock LLM whose astream() raises an exception."""
    async def _astream(messages):
        raise RuntimeError("LLM unavailable")
        yield  # make it a generator

    llm = MagicMock()
    llm.astream = _astream
    return llm


_BASE_COMPETENCE = {
    "title": "Electrician",
    "description": "12 years as a residential electrician. Does house wiring, lighting.",
    "category": "Handwerk",
    "price_range": "€20–€40/h",
    "year_of_experience": 12,
    "availability_text": "Weekends, Tuesday 10am to 1pm",
}

_ENRICHED_PAYLOAD = {
    "skills_list": ["house wiring", "lighting installation", "circuit breaker work", "residential wiring"],
    "search_optimized_summary": (
        "Residential electrician with 12 years of experience. "
        "Specialises in house wiring, lighting installations, and home electrical systems. "
        "Available on weekends and Tuesday mornings."
    ),
    "category": "Handwerk",
    "price_per_hour": 30.0,
    "availability_text": "Weekends and Tuesday 10am–1pm",
    "availability_tags": ["weekend", "tuesday", "morning"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Core enrichment
# ─────────────────────────────────────────────────────────────────────────────

class TestCompetenceEnricherEnrich:

    async def test_enriched_fields_added_to_result(self):
        enricher = CompetenceEnricher(llm=_make_llm_mock(_ENRICHED_PAYLOAD))
        result = await enricher.enrich(_BASE_COMPETENCE)

        assert result["skills_list"] == _ENRICHED_PAYLOAD["skills_list"]
        assert result["search_optimized_summary"] == _ENRICHED_PAYLOAD["search_optimized_summary"]
        assert result["availability_tags"] == ["weekend", "tuesday", "morning"]
        assert result["price_per_hour"] == 30.0
        assert result["availability_text"] == "Weekends and Tuesday 10am–1pm"

    async def test_original_fields_preserved(self):
        enricher = CompetenceEnricher(llm=_make_llm_mock(_ENRICHED_PAYLOAD))
        result = await enricher.enrich(_BASE_COMPETENCE)

        assert result["title"] == "Electrician"
        assert result["year_of_experience"] == 12
        assert result["price_range"] == "€20–€40/h"  # display field kept

    async def test_category_overridden_when_llm_provides_it(self):
        payload = {**_ENRICHED_PAYLOAD, "category": "IT"}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich({**_BASE_COMPETENCE, "category": "Handwerk"})
        assert result["category"] == "IT"

    async def test_category_not_overridden_when_llm_returns_empty(self):
        payload = {**_ENRICHED_PAYLOAD, "category": ""}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich({**_BASE_COMPETENCE, "category": "Handwerk"})
        # Empty string from LLM → should not override
        assert result["category"] == "Handwerk"


# ─────────────────────────────────────────────────────────────────────────────
# Graceful degradation
# ─────────────────────────────────────────────────────────────────────────────

class TestCompetenceEnricherGracefulDegradation:

    async def test_llm_error_returns_original(self):
        enricher = CompetenceEnricher(llm=_make_failing_llm())
        result = await enricher.enrich(_BASE_COMPETENCE)

        # Must be a copy of the original, not mutated
        assert result["title"] == "Electrician"
        assert result["description"] == _BASE_COMPETENCE["description"]
        # Enriched fields absent (no side-effect)
        assert "search_optimized_summary" not in result or result.get("search_optimized_summary") == ""

    async def test_json_parse_error_returns_original(self):
        enricher = CompetenceEnricher(llm=_make_llm_mock_text("not-json {{ broken"))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert result["title"] == "Electrician"

    async def test_original_dict_not_mutated_on_error(self):
        original = dict(_BASE_COMPETENCE)
        enricher = CompetenceEnricher(llm=_make_failing_llm())
        await enricher.enrich(original)
        # Original dict is unmodified
        assert original == _BASE_COMPETENCE


# ─────────────────────────────────────────────────────────────────────────────
# Price extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestPriceExtraction:

    async def test_midpoint_of_range(self):
        """€20–€40/h → 30.0"""
        payload = {**_ENRICHED_PAYLOAD, "price_per_hour": 30.0}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert result["price_per_hour"] == 30.0

    async def test_fixed_rate(self):
        payload = {**_ENRICHED_PAYLOAD, "price_per_hour": 50.0}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert result["price_per_hour"] == 50.0

    async def test_null_price_when_no_hourly_rate(self):
        payload = {**_ENRICHED_PAYLOAD, "price_per_hour": None}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert result["price_per_hour"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Availability tag normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestAvailabilityTags:

    async def test_weekend_tag_present(self):
        payload = {**_ENRICHED_PAYLOAD, "availability_tags": ["weekend", "saturday", "sunday"]}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert "weekend" in result["availability_tags"]

    async def test_weekday_tag_inferred(self):
        payload = {**_ENRICHED_PAYLOAD, "availability_tags": ["weekday", "monday", "tuesday"]}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert "weekday" in result["availability_tags"]
        assert "monday" in result["availability_tags"]

    async def test_time_bucket_morning(self):
        payload = {**_ENRICHED_PAYLOAD, "availability_tags": ["tuesday", "morning"]}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert "morning" in result["availability_tags"]

    async def test_tags_are_lowercase(self):
        payload = {**_ENRICHED_PAYLOAD, "availability_tags": ["Weekend", "TUESDAY", "Morning"]}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        for tag in result["availability_tags"]:
            assert tag == tag.lower(), f"Tag not lowercase: {tag!r}"

    async def test_empty_tags_on_no_availability(self):
        payload = {**_ENRICHED_PAYLOAD, "availability_tags": []}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert result["availability_tags"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Skills list
# ─────────────────────────────────────────────────────────────────────────────

class TestSkillsList:

    async def test_skills_lowercased_and_stripped(self):
        payload = {**_ENRICHED_PAYLOAD, "skills_list": ["  House Wiring  ", "LIGHTING Installation"]}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert "house wiring" in result["skills_list"]
        assert "lighting installation" in result["skills_list"]

    async def test_empty_strings_in_skills_list_dropped(self):
        payload = {**_ENRICHED_PAYLOAD, "skills_list": ["valid skill", "", "  "]}
        enricher = CompetenceEnricher(llm=_make_llm_mock(payload))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert "" not in result["skills_list"]


# ─────────────────────────────────────────────────────────────────────────────
# Markdown code-fence stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestMarkdownStripping:

    async def test_strips_json_code_fences(self):
        raw_payload = _ENRICHED_PAYLOAD
        fenced_text = f"```json\n{json.dumps(raw_payload)}\n```"
        enricher = CompetenceEnricher(llm=_make_llm_mock_text(fenced_text))
        result = await enricher.enrich(_BASE_COMPETENCE)
        # Should parse successfully despite code fences
        assert result["price_per_hour"] == 30.0

    async def test_strips_plain_code_fences(self):
        raw_payload = _ENRICHED_PAYLOAD
        fenced_text = f"```\n{json.dumps(raw_payload)}\n```"
        enricher = CompetenceEnricher(llm=_make_llm_mock_text(fenced_text))
        result = await enricher.enrich(_BASE_COMPETENCE)
        assert result["skills_list"] == _ENRICHED_PAYLOAD["skills_list"]


# ─────────────────────────────────────────────────────────────────────────────
# _build_user_message
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildUserMessage:

    def test_all_fields_included(self):
        msg = CompetenceEnricher._build_user_message(_BASE_COMPETENCE)
        assert "Electrician" in msg
        assert "12" in msg
        assert "€20–€40/h" in msg
        assert "Weekends" in msg

    def test_missing_optional_fields_dont_crash(self):
        msg = CompetenceEnricher._build_user_message({"title": "Plumber"})
        assert "Plumber" in msg
