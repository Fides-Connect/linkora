"""
Google Places Service
=====================
Fetches external service-provider candidates from the Google Places Text Search
API, normalises them to the platform schema, and upserts them as User+Competence
nodes in Weaviate so the unified hybrid-search index can return them alongside
registered platform providers.

Key design decisions (from implementation plan):
- Serial write-first: this pipeline runs *before* the Weaviate search so GP nodes
  participate in the same ranking pass.
- Deterministic UUIDs: derived from ``place_id`` via ``weaviate.util.generate_uuid5``
  so re-ingestion performs an in-place update rather than creating duplicates.
- Circuit breaker: after 3 consecutive HTTP failures the pipeline is disabled for
  60 s then auto-resets.
- PII masking: phone / address are stored in Weaviate for functionality but are
  redacted in all log output.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from weaviate.util import generate_uuid5

from ..hub_spoke_ingestion import HubSpokeIngestion
from .llm_service import LLMService

logger = logging.getLogger(__name__)

_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
# Fields requested from Places API (New).
# Billing tiers for Text Search (New):
#   Basic:    id, displayName, formattedAddress, types, primaryTypeDisplayName
#   Advanced: rating, userRatingCount, nationalPhoneNumber, websiteUri
#   Preferred: editorialSummary, reviews  (same tier — one call, one charge)
_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.primaryTypeDisplayName,places.rating,places.userRatingCount,"
    "places.types,places.editorialSummary,places.reviews,"
    "places.nationalPhoneNumber,places.websiteUri"
)
_CIRCUIT_THRESHOLD = 3      # consecutive failures before opening
_CIRCUIT_RESET_SECONDS = 60  # cooldown before auto-reset


@dataclass
class GpResult:
    """Outcome of a single GP pipeline run."""
    providers_written: int = 0   # number of GP nodes written to Weaviate
    error: bool = False          # True when GP tried but failed
    query: str = ""              # Places query string used (empty on skip)
    duration_ms: int = 0         # wall-clock time for fetch_and_ingest()
    error_code: str = ""         # "rate_limited" | "timeout" | "http_error" | "circuit_open" | "llm_skip"


class GooglePlacesService:
    """
    Handles all Google Places API interactions for the provider search pipeline.

    One instance is created per ``AIAssistant`` (server-wide singleton pattern
    implicit in the constructor injection chain).  Circuit-breaker state is
    therefore per-process (not distributed — see deployment notes in the plan).
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        self._api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
        # Circuit breaker state
        self._consecutive_failures: int = 0
        self._circuit_opened_at: float | None = None

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def is_enabled() -> bool:
        """True when ``GOOGLE_PLACES_API_KEY`` env var is set and non-empty."""
        return bool(os.getenv("GOOGLE_PLACES_API_KEY", "").strip())

    async def generate_query(
        self,
        structured_query: str | dict[str, Any],
        hyde_text: str,
        location: str = "",
    ) -> str | None:
        """
        Generate a single Google Places search phrase via LLM.

        Uses ``GOOGLE_PLACES_QUERY_PROMPT`` from ``prompts_templates``.

        Args:
            structured_query: Structured request JSON string (or dict) from the
                              LLM extraction step.
            hyde_text: HyDE profile generated for vector search.
            location: City/region extracted from the structured query.  When set,
                      the LLM is encouraged to include it in the search phrase.

        Returns:
            A short English search phrase such as "wedding photographer Munich",
            or None on any LLM error (triggers silent GP skip in caller).
        """
        from ..prompts_templates import GOOGLE_PLACES_QUERY_PROMPT
        from langchain_core.messages import HumanMessage

        sq_str = structured_query if isinstance(structured_query, str) else str(structured_query)
        prompt_text = GOOGLE_PLACES_QUERY_PROMPT.format(
            structured_query=sq_str,
            hyde_text=hyde_text,
            location=location or "(not specified)",
        )
        try:
            result = await self._llm.generate([HumanMessage(content=prompt_text)])
            query = result.strip()
            # Basic sanity: reject empty or excessively long responses
            if not query or len(query) > 200:
                logger.warning(
                    "GooglePlacesService.generate_query: LLM returned unexpected response length=%d",
                    len(query),
                )
                return None
            logger.info("GP query generated: %r", query)
            return query
        except Exception as exc:
            logger.error(
                "GooglePlacesService.generate_query: LLM error (%s: %s) — GP silently skipped",
                type(exc).__name__,
                exc,
            )
            return None

    async def fetch_and_ingest(
        self,
        query: str,
        limit: int = 20,
    ) -> GpResult:
        """
        Fetch providers from the Places Text Search API and upsert to Weaviate.

        Applies the circuit breaker and retry policy defined in the plan.

        Returns:
            ``GpResult`` with ``providers_written`` count.  Records are NOT
            returned — the authoritative copy lives in Weaviate and is served
            by the Phase-3 unified search.
        """
        # ── Circuit breaker guard ─────────────────────────────────────────────
        if self._circuit_opened_at is not None:
            elapsed = time.monotonic() - self._circuit_opened_at
            if elapsed < _CIRCUIT_RESET_SECONDS:
                logger.warning(
                    "GP circuit open (%.0f s remaining) — skipping fetch.",
                    _CIRCUIT_RESET_SECONDS - elapsed,
                )
                return GpResult(error=True, error_code="circuit_open")
            # Auto-reset
            logger.info("GP circuit reset after %.0f s cooldown.", elapsed)
            self._circuit_opened_at = None
            self._consecutive_failures = 0

        t_start = time.monotonic()
        try:
            raw_results = await self._fetch_places(query, limit)
        except _RateLimitError as exc:
            self._record_failure()
            return GpResult(error=True, error_code="rate_limited", query=query)
        except _HttpError as exc:
            self._record_failure()
            return GpResult(error=True, error_code="http_error", query=query,
                            duration_ms=int((time.monotonic() - t_start) * 1000))
        except asyncio.TimeoutError:
            self._record_failure()
            return GpResult(error=True, error_code="timeout", query=query,
                            duration_ms=int((time.monotonic() - t_start) * 1000))
        except Exception as exc:
            logger.error("GP fetch unexpected error: %s", exc, exc_info=True)
            self._record_failure()
            return GpResult(error=True, error_code="http_error", query=query,
                            duration_ms=int((time.monotonic() - t_start) * 1000))

        duration_ms = int((time.monotonic() - t_start) * 1000)
        if not raw_results:
            logger.info(
                "GP fetch returned 0 results for query=%r (duration=%d ms)", query, duration_ms
            )
            self._reset_failures()
            return GpResult(providers_written=0, error=False, query=query, duration_ms=duration_ms)

        # Normalise and upsert
        count = await self._normalise_and_upsert(raw_results, query)
        self._reset_failures()

        logger.info(
            "GP pipeline complete: query=%r results=%d upserted=%d duration_ms=%d",
            query, len(raw_results), count, duration_ms,
        )
        return GpResult(providers_written=count, error=False, query=query, duration_ms=duration_ms)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _fetch_places(self, query: str, limit: int) -> list[dict[str, Any]]:
        """
        Call the Places Text Search (New) endpoint.

        Uses a POST request with JSON body and ``X-Goog-FieldMask`` header as
        required by the Places API (New).  The legacy ``textsearch/json`` GET
        endpoint is not used.

        Retry policy:
        - HTTP 429: no retry, raises ``_RateLimitError``
        - HTTP 5xx: 1 retry after 500 ms; second failure raises ``_HttpError``
        - Other HTTP 4xx / timeout: immediate failure
        """
        timeout = aiohttp.ClientTimeout(total=5)
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
        }
        body: dict[str, Any] = {
            "textQuery": query,
            "pageSize": min(limit, 20),
            # Include businesses that serve customers on-site or via delivery but
            # have no physical storefront (e.g. mobile cleaners, photographers).
            "includePureServiceAreaBusinesses": True,
        }

        async def _do_request() -> list[dict[str, Any]]:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    _PLACES_TEXT_SEARCH_URL,
                    json=body,
                    headers=headers,
                ) as resp:
                    if resp.status == 429:
                        raise _RateLimitError()
                    if resp.status >= 500:
                        raise _ServerError(resp.status)
                    if resp.status >= 400:
                        raise _HttpError(resp.status)
                    data = await resp.json()
                    # New API returns {"places": [...]} — empty array or missing
                    # key means zero results.
                    return data.get("places") or []

        try:
            return await _do_request()
        except _ServerError:
            # 1 retry after 500 ms for transient 5xx
            await asyncio.sleep(0.5)
            try:
                return await _do_request()
            except _ServerError as exc:
                raise _HttpError(exc.status) from exc

    async def _normalise_and_upsert(
        self, raw_results: list[dict[str, Any]], query: str
    ) -> int:
        """
        Normalise Places API results and upsert User+Competence pairs.

        Returns the number of nodes successfully written.
        """
        # Gather synthetic descriptions for results that lack editorialSummary
        desc_tasks = []
        desc_indices: list[int] = []
        for idx, place in enumerate(raw_results):
            if not (place.get("editorialSummary") or {}).get("text", "").strip():
                desc_indices.append(idx)
                reviews = place.get("reviews") or []
                desc_tasks.append(self._synthesise_description(place, query, reviews=reviews))

        synthetic_descs: list[str | None] = []
        if desc_tasks:
            synthetic_descs = list(await asyncio.gather(*desc_tasks, return_exceptions=True))

        count = 0
        for idx, place in enumerate(raw_results):
            try:
                place_id: str = place.get("id", "")
                if not place_id:
                    continue

                # Deterministic UUIDs — same place_id always → same UUID
                user_uuid = str(generate_uuid5(place_id))
                comp_uuid = str(generate_uuid5(f"{place_id}:competence"))

                # Description: editorialSummary first, then synthetic LLM result
                description: str = (
                    (place.get("editorialSummary") or {}).get("text", "").strip()
                )
                if not description:
                    pos = desc_indices.index(idx) if idx in desc_indices else -1
                    if pos >= 0 and pos < len(synthetic_descs):
                        synth = synthetic_descs[pos]
                        if isinstance(synth, str) and synth:
                            description = synth
                if not description:
                    # Final fallback: build from place type list
                    types = place.get("types", [])
                    display_name = (place.get("displayName") or {}).get("text", "")
                    description = f"{display_name} — {', '.join(types[:3])}"

                # Enrich search_optimized_summary with customer review snippets so the
                # cross-encoder and vector index can match on real service keywords.
                review_snippets = _extract_review_snippets(
                    place.get("reviews") or [], max_count=3, max_chars=100
                )
                if review_snippets:
                    search_optimized_summary = (
                        f"{description} Customer experiences: "
                        + " \u00b7 ".join(review_snippets)
                    )
                else:
                    search_optimized_summary = description

                # Phone / address — stored in Weaviate, masked in logs
                phone: str = place.get("nationalPhoneNumber") or ""
                address: str = place.get("formattedAddress") or ""
                name: str = (place.get("displayName") or {}).get("text", "")

                user_data: dict[str, Any] = {
                    "uuid": user_uuid,
                    "user_id": None,
                    "name": name,
                    "email": None,
                    "is_service_provider": True,
                    "source": "google_places",
                    "phone": phone,
                    "website": place.get("websiteUri") or "",
                    "address": address,
                    "average_rating": float(place.get("rating") or 0.0),
                }
                competence_data: dict[str, Any] = {
                    "uuid": comp_uuid,
                    "competence_id": f"gp:{place_id}",
                    "title": name,
                    "description": description,
                    "search_optimized_summary": search_optimized_summary,
                    "category": _extract_category(place.get("types", [])),
                }

                result_uuid = HubSpokeIngestion.upsert_user(user_data, competence_data)
                if result_uuid:
                    count += 1
                    logger.info(
                        "GP upserted: name=%r place_id=%r",
                        name, place_id,
                    )
                else:
                    logger.warning("GP upsert failed for place_id=%r", place_id)

            except Exception as exc:
                logger.error(
                    "GP normalise_and_upsert: error for place %r: %s",
                    place.get("place_id"), exc, exc_info=True,
                )

        return count

    async def _synthesise_description(
        self, place: dict[str, Any], query: str,
        reviews: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """
        Generate a single-sentence service description for a Place that has no
        editorial_summary.  Uses a lightweight single-shot LLM call.

        When ``reviews`` are provided, representative snippets are included in
        the prompt so the LLM can name real specialties instead of generic types.
        """
        from langchain_core.messages import HumanMessage

        name = (place.get("displayName") or {}).get("text", "")
        # Prefer the human-readable primaryTypeDisplayName over raw type codes
        primary_type = (place.get("primaryTypeDisplayName") or {}).get("text", "")
        types_phrase = primary_type or ", ".join(
            t.replace("_", " ") for t in (place.get("types") or [])[:4]
        )
        location = place.get("formattedAddress", "").split(",")[-1].strip()

        review_context = ""
        if reviews:
            snippets = _extract_review_snippets(reviews, max_count=3, max_chars=80)
            if snippets:
                review_context = f" Customers have mentioned: {'; '.join(snippets)}."

        prompt = (
            f"Write ONE short sentence describing the services offered by '{name}' "
            f"which provides {types_phrase} in {location}.{review_context} "
            "Focus on their specialties and unique offerings. "
            "Return only the sentence, no preamble."
        )
        try:
            result = await self._llm.generate([HumanMessage(content=prompt)])
            return result.strip()
        except Exception as exc:
            logger.warning(
                "GP synthetic description failed for %r: %s — using type fallback", name, exc
            )
            return None

    # ── Circuit breaker helpers ───────────────────────────────────────────────

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= _CIRCUIT_THRESHOLD:
            self._circuit_opened_at = time.monotonic()
            logger.warning(
                "GP circuit opened after %d consecutive failures.",
                self._consecutive_failures,
            )

    def _reset_failures(self) -> None:
        self._consecutive_failures = 0


# ──────────────────────────────────────────────────────────────────────────────
# Internal exceptions
# ──────────────────────────────────────────────────────────────────────────────

class _RateLimitError(Exception):
    """HTTP 429 from Places API."""


class _ServerError(Exception):
    """HTTP 5xx from Places API (retryable)."""
    def __init__(self, status: int) -> None:
        self.status = status


class _HttpError(Exception):
    """Non-retryable HTTP error from Places API."""
    def __init__(self, status: int) -> None:
        self.status = status


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_TYPE_CATEGORY_MAP: dict[str, str] = {
    "plumber": "Plumbing",
    "electrician": "Electrical",
    "locksmith": "Repair",
    "car_repair": "Repair",
    "painter": "Repair",
    "roofing_contractor": "Repair",
    "general_contractor": "Repair",
    "home_goods_store": "other",
    "beauty_salon": "Wellness",
    "hair_care": "Wellness",
    "spa": "Wellness",
    "gym": "Wellness",
    "physiotherapist": "Wellness",
    "doctor": "Wellness",
    "dentist": "Wellness",
    "restaurant": "Restaurant",
    "food": "Restaurant",
    "pet_store": "Pets",
    "veterinary_care": "Pets",
    "storage": "other",
    "moving_company": "Transport",
    "taxi_service": "Transport",
    "school": "Teaching",
    "university": "Teaching",
    "tutoring": "Teaching",
    "child_care_agency": "Childcare",
    "day_care_center": "Childcare",
    "garden_center": "Gardening",
    "landscaper": "Gardening",
    "cleaning_service": "Housekeeping",
    "laundry": "Housekeeping",
    "event_planner": "Events",
    "photographer": "Events",
    "florist": "Events",
}


def _extract_category(types: list[str]) -> str:
    """
    Map Google Places ``types`` list to a platform category string.
    Falls back to ``"other"`` when no mapping is found.
    """
    for t in types:
        mapped = _TYPE_CATEGORY_MAP.get(t.lower())
        if mapped:
            return mapped
    return "other"


def _extract_review_snippets(
    reviews: list[dict[str, Any]], max_count: int = 3, max_chars: int = 100
) -> list[str]:
    """
    Extract clean text snippets from Google Places review objects.

    Each review object from the Places API (New) has the shape
    ``{"text": {"text": "...", "languageCode": "..."}}``.  We extract the
    inner text, truncate at the nearest word boundary, and return up to
    ``max_count`` non-empty snippets.
    """
    snippets: list[str] = []
    for rv in reviews[:max_count]:
        text = (rv.get("text") or {}).get("text", "").strip()
        if not text:
            continue
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0]
        if text:
            snippets.append(text)
    return snippets
