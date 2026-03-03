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
    "availability": "Weekends, Tuesday 10am to 1pm",
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
        assert result["price_per_hour"] == 30.0
        # availability_text / availability_tags are no longer enricher outputs;
        # they are derived from the structured availability_time subcollection.
        assert "availability_text" not in result
        assert "availability_tags" not in result

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
# _availability_time_to_text
# ─────────────────────────────────────────────────────────────────────────────

class TestAvailabilityTimeToText:
    """Tests for CompetenceEnricher._availability_time_to_text."""

    def test_empty_dict_returns_empty_string(self):
        assert CompetenceEnricher._availability_time_to_text({}) == ""

    def test_single_day_single_range(self):
        avail = {"monday_time_ranges": [{"start_time": "09:00", "end_time": "12:00"}]}
        result = CompetenceEnricher._availability_time_to_text(avail)
        assert "Monday" in result
        assert "09:00" in result
        assert "12:00" in result

    def test_multiple_days(self):
        avail = {
            "monday_time_ranges": [{"start_time": "09:00", "end_time": "12:00"}],
            "wednesday_time_ranges": [{"start_time": "14:00", "end_time": "18:00"}],
        }
        result = CompetenceEnricher._availability_time_to_text(avail)
        assert "Monday" in result
        assert "Wednesday" in result

    def test_absence_days_included(self):
        avail = {"absence_days": ["2026-03-15", "2026-03-16"]}
        result = CompetenceEnricher._availability_time_to_text(avail)
        assert "2026-03-15" in result
        assert "absent" in result.lower()

    def test_days_without_ranges_are_skipped(self):
        avail = {
            "monday_time_ranges": [],
            "tuesday_time_ranges": [{"start_time": "10:00", "end_time": "13:00"}],
        }
        result = CompetenceEnricher._availability_time_to_text(avail)
        assert "Monday" not in result
        assert "Tuesday" in result

    def test_build_user_message_uses_availability_time_when_present(self):
        """When raw contains availability_time dict, it should be converted to text."""
        raw = {
            **_BASE_COMPETENCE,
            "availability_time": {
                "friday_time_ranges": [{"start_time": "08:00", "end_time": "16:00"}],
            },
        }
        # Remove plain 'availability' to confirm structured path is used
        raw.pop("availability", None)
        msg = CompetenceEnricher._build_user_message(raw)
        assert "Friday" in msg
        assert "08:00" in msg

    def test_build_user_message_falls_back_to_availability_string(self):
        """When availability_time is absent, falls back to plain 'availability' key."""
        raw = {**_BASE_COMPETENCE}  # has 'availability' key
        msg = CompetenceEnricher._build_user_message(raw)
        assert "Weekends" in msg


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
        assert "Weekends" in msg  # from 'availability' key in _BASE_COMPETENCE

    def test_missing_optional_fields_dont_crash(self):
        msg = CompetenceEnricher._build_user_message({"title": "Plumber"})
        assert "Plumber" in msg
