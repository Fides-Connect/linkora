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
import urllib.parse
from dataclasses import dataclass
from typing import Any, cast
from collections.abc import Awaitable

import aiohttp
from weaviate.util import generate_uuid5

from ..hub_spoke_ingestion import HubSpokeIngestion
from .llm_service import LLMService
from .webpage_crawler import WebCrawlResult, WebPageCrawler

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
    "places.nationalPhoneNumber,places.websiteUri,"
    "places.regularOpeningHours,places.photos"
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
        # Configurable result limit (GP_MAX_RESULTS env var, default 60).
        # The Places API returns at most 20 results per page and supports up to
        # 3 pages (60 results total).  Values above 60 are clamped to 60.
        _raw_limit = os.getenv("GP_MAX_RESULTS", "60")
        try:
            self._max_results: int = max(1, min(int(_raw_limit), 60))
        except ValueError:
            logger.warning(
                "GP_MAX_RESULTS=%r is not a valid integer — using default of 60.", _raw_limit
            )
            self._max_results = 60
        # Webpage crawling enrichment (GP_WEBPAGE_CRAWL_ENABLED env var, default true).
        self._crawl_enabled: bool = (
            os.getenv("GP_WEBPAGE_CRAWL_ENABLED", "true").strip().lower() not in {"false", "0", "no"}
        )
        # Circuit breaker state
        self._consecutive_failures: int = 0
        self._circuit_opened_at: float | None = None
        # Persistent HTTP session — reused across Places API calls to avoid
        # repeated TCP connect + TLS handshake overhead.
        self._http_session: aiohttp.ClientSession | None = None

    def _get_http_session(self) -> aiohttp.ClientSession:
        """Return the shared HTTP session, creating it lazily on first call."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            )
        return self._http_session

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
        Generate a single Google Places search phrase.

        Fast path: extracts ``category`` and ``location`` from the structured
        query JSON and formats the phrase deterministically — no LLM call, no
        added latency.  This covers ~95 % of searches.

        LLM fallback: used only when ``category`` is absent or the structured
        query cannot be parsed as JSON.  The LLM path uses
        ``GOOGLE_PLACES_QUERY_PROMPT`` from ``prompts_templates``.

        Args:
            structured_query: Structured request JSON string (or dict) from the
                              LLM extraction step.
            hyde_text: HyDE profile generated for vector search (LLM path only).
            location: City/region pre-extracted from the structured query.

        Returns:
            A short English search phrase such as "wedding photographer Munich",
            or None on failure (triggers silent GP skip in caller).
        """
        import json as _json

        # ── Fast path: deterministic formatter ───────────────────────────────
        try:
            if isinstance(structured_query, dict):
                sq_data = structured_query
                sq_str = _json.dumps(sq_data)
            else:
                sq_str = str(structured_query)
                sq_data = _json.loads(sq_str)
            category = str(sq_data.get("category", "") or "").strip()
            sq_location = str(sq_data.get("location", "") or "").strip()
        except Exception:
            category = ""
            sq_location = ""

        loc = (location or sq_location).strip()
        if category:
            query = f"{category} {loc}".strip() if loc else category
            logger.debug("GP query (deterministic): %r", query)
            return query

        # ── LLM fallback: used only when category is missing ─────────────────
        logger.debug(
            "GP query: category missing from structured query — falling back to LLM"
        )
        from ..prompts_templates import GOOGLE_PLACES_QUERY_PROMPT
        from langchain_core.messages import HumanMessage

        prompt_text = GOOGLE_PLACES_QUERY_PROMPT.format(
            structured_query=sq_str,
            hyde_text=hyde_text,
            location=loc or "(not specified)",
        )
        try:
            result = await self._llm.generate([HumanMessage(content=prompt_text)])
            query = result.strip()
            if not query or len(query) > 200:
                logger.warning(
                    "GooglePlacesService.generate_query: LLM returned unexpected response length=%d",
                    len(query),
                )
                return None
            logger.debug("GP query (LLM fallback): %r", query)
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
        limit: int | None = None,
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

        _limit = limit if limit is not None else self._max_results
        t_start = time.monotonic()
        try:
            raw_results = await self._fetch_places(query, _limit)
        except _RateLimitError:
            self._record_failure()
            return GpResult(error=True, error_code="rate_limited", query=query)
        except _HttpError:
            self._record_failure()
            return GpResult(error=True, error_code="http_error", query=query,
                            duration_ms=int((time.monotonic() - t_start) * 1000))
        except TimeoutError:
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

    async def fetch_as_providers(
        self,
        structured_query: str,
        hyde_text: str,
        location: str = "",
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], GpResult]:
        """Fetch GP places and return them as provider dicts — no Weaviate write.

        Lite-mode entry point.  The returned provider dicts include all crawler
        enrichment (skills, specialities, email) and match the shape the
        cross-encoder, FINALIZE prompt, and Flutter card renderer expect.

        Returns:
            ``(providers, gp_result)`` where *providers* is ready for reranking.
        """
        if self._circuit_opened_at is not None:
            elapsed = time.monotonic() - self._circuit_opened_at
            if elapsed < _CIRCUIT_RESET_SECONDS:
                logger.warning(
                    "GP circuit open (%.0f s remaining) — skipping fetch.",
                    _CIRCUIT_RESET_SECONDS - elapsed,
                )
                return [], GpResult(error=True, error_code="circuit_open")
            logger.info("GP circuit reset after %.0f s cooldown.", elapsed)
            self._circuit_opened_at = None
            self._consecutive_failures = 0

        _limit = limit if limit is not None else self._max_results
        t_start = time.monotonic()
        query = await self.generate_query(
            structured_query=structured_query,
            hyde_text=hyde_text,
            location=location,
        )
        if not query:
            logger.info("GP fetch_as_providers skipped: generate_query returned None.")
            return [], GpResult(providers_written=0, error=False, error_code="llm_skip")

        try:
            raw_results = await self._fetch_places(query, _limit)
        except _RateLimitError:
            self._record_failure()
            return [], GpResult(error=True, error_code="rate_limited", query=query)
        except _HttpError:
            self._record_failure()
            return [], GpResult(error=True, error_code="http_error", query=query,
                                duration_ms=int((time.monotonic() - t_start) * 1000))
        except TimeoutError:
            self._record_failure()
            return [], GpResult(error=True, error_code="timeout", query=query,
                                duration_ms=int((time.monotonic() - t_start) * 1000))
        except Exception as exc:
            logger.error("GP fetch_as_providers unexpected error: %s", exc, exc_info=True)
            self._record_failure()
            return [], GpResult(error=True, error_code="http_error", query=query,
                                duration_ms=int((time.monotonic() - t_start) * 1000))

        duration_ms = int((time.monotonic() - t_start) * 1000)
        if not raw_results:
            logger.info(
                "GP fetch_as_providers 0 results for query=%r (duration=%d ms)", query, duration_ms
            )
            self._reset_failures()
            return [], GpResult(providers_written=0, error=False, query=query, duration_ms=duration_ms)

        normalised = await self._normalise_places(raw_results, query)
        providers = [_normalised_to_provider(p) for p in normalised]
        self._reset_failures()
        logger.info(
            "GP fetch_as_providers complete: query=%r providers=%d duration_ms=%d",
            query, len(providers), duration_ms,
        )
        return providers, GpResult(providers_written=len(providers), error=False,
                                   query=query, duration_ms=duration_ms)

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _fetch_places(self, query: str, limit: int) -> list[dict[str, Any]]:
        """
        Call the Places Text Search (New) endpoint.

        Uses a POST request with JSON body and ``X-Goog-FieldMask`` header as
        required by the Places API (New).  The legacy ``textsearch/json`` GET
        endpoint is not used.

        Pagination: the Places API caps each page at 20 results but returns a
        ``nextPageToken`` when more are available.  This method follows up to
        ``ceil(limit / 20)`` pages so callers can request up to 60 results
        (3 pages × 20) in a single call.

        Retry policy:
        - HTTP 429: no retry, raises ``_RateLimitError``
        - HTTP 5xx: 1 retry after 500 ms; second failure raises ``_HttpError``
        - Other HTTP 4xx / timeout: immediate failure
        """
        _PAGE_SIZE = 20  # Places API hard cap per page
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK + ",nextPageToken",
        }

        async def _do_request(body: dict[str, Any]) -> dict[str, Any]:
            """Make one POST and return the raw response dict."""
            session = self._get_http_session()
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
                return cast(dict[str, Any], await resp.json())

        async def _do_request_with_retry(body: dict[str, Any]) -> dict[str, Any]:
            try:
                return await _do_request(body)
            except _ServerError:
                # 1 retry after 500 ms for transient 5xx
                await asyncio.sleep(0.5)
                try:
                    return await _do_request(body)
                except _ServerError as exc:
                    raise _HttpError(exc.status) from exc

        all_places: list[dict[str, Any]] = []
        page_token: str | None = None
        pages_remaining = max(1, -(-limit // _PAGE_SIZE))  # ceil division

        while pages_remaining > 0 and len(all_places) < limit:
            need = limit - len(all_places)
            body: dict[str, Any] = {
                "textQuery": query,
                "pageSize": min(need, _PAGE_SIZE),
                # Include businesses that serve customers on-site or via delivery
                # but have no physical storefront (e.g. mobile cleaners, photographers).
                "includePureServiceAreaBusinesses": True,
            }
            if page_token:
                body["pageToken"] = page_token

            data = await _do_request_with_retry(body)
            batch = data.get("places") or []
            all_places.extend(batch)
            page_token = data.get("nextPageToken")
            pages_remaining -= 1

            if not page_token or not batch:
                break  # No more results available

            # Brief pause between pagination requests to stay within API rate limits.
            await asyncio.sleep(0.1)

        logger.info(
            "GP _fetch_places: query=%r requested=%d fetched=%d",
            query, limit, len(all_places),
        )
        return all_places[:limit]

    async def _normalise_and_upsert(
        self, raw_results: list[dict[str, Any]], query: str
    ) -> int:
        """
        Normalise Places API results and upsert User+Competence pairs (full mode).

        Returns the number of nodes successfully written.
        """
        normalised = await self._normalise_places(raw_results, query)
        count = 0
        for place in normalised:
            try:
                user_data: dict[str, Any] = {
                    "uuid": place["user_uuid"],
                    "user_id": None,
                    "name": place["name"],
                    "email": None,
                    "is_service_provider": True,
                    "source": "google_places",
                    "phone": place["phone"],
                    "website": place["website"],
                    "address": place["address"],
                    "average_rating": place["average_rating"],
                    "rating_count": place["rating_count"],
                    "photo_url": place["photo_url"],
                    "opening_hours": place["opening_hours"],
                    "maps_url": place["maps_url"],
                }
                competence_data: dict[str, Any] = {
                    "uuid": place["comp_uuid"],
                    "competence_id": f"gp:{place['place_id']}",
                    "title": place["title"],
                    "description": place["description"],
                    "search_optimized_summary": place["search_optimized_summary"],
                    "category": place["category"],
                    "primary_type": place["primary_type"],
                    "review_snippets": place["review_snippets"],
                }
                result_uuid = HubSpokeIngestion.upsert_user(user_data, competence_data)
                if result_uuid:
                    count += 1
                    logger.info("GP upserted: name=%r place_id=%r", place["name"], place["place_id"])
                else:
                    logger.warning("GP upsert failed for place_id=%r", place["place_id"])
            except Exception as exc:
                logger.error(
                    "GP normalise_and_upsert: error for place_id=%r: %s",
                    place.get("place_id"), exc, exc_info=True,
                )
        return count

    async def _normalise_places(
        self, raw_results: list[dict[str, Any]], query: str
    ) -> list[dict[str, Any]]:
        """
        Normalise raw Places API results into flat dicts.

        Returns one dict per place containing all fields used by both the
        full-mode hub-spoke upsert path and the lite-mode fetch_as_providers path.

        The ``search_optimized_summary`` field is always generated in English
        (via an LLM synthesis call) regardless of the language returned by the
        Places API.  This is required because the cross-encoder model
        (ms-marco-MiniLM-L-6-v2) is English-only and produces unreliable scores
        against non-English candidate text.

        The user-facing ``description`` field continues to use the raw
        editorialSummary (in whatever language GP returns it) so that the
        provider card shows the authentic GP text.
        """
        # Two separate concurrency budgets:
        #   - Summary synthesis: cheap calls (~500 tokens each), safe to parallelise widely.
        #   - Webpage crawl+extraction: heavy calls (up to 15k token input each), kept low.
        _summary_sem = asyncio.Semaphore(15)
        _crawl_sem = asyncio.Semaphore(3)

        async def _throttled_summary(coro: Awaitable[Any]) -> Any:
            async with _summary_sem:
                return await coro

        async def _throttled_crawl(coro: Awaitable[Any]) -> Any:
            async with _crawl_sem:
                return await coro

        # Build English search_optimized_summaries for all places concurrently.
        summary_tasks = [
            _throttled_summary(self._synthesise_description(
                place,
                query,
                reviews=place.get("reviews") or [],
                editorial_summary=(
                    (place.get("editorialSummary") or {}).get("text", "").strip() or None
                ),
            ))
            for place in raw_results
        ]
        english_summaries: list[str | None]
        crawl_results: list[Any]

        if self._crawl_enabled:
            crawler = WebPageCrawler(self._llm)
            crawl_tasks = [
                _throttled_crawl(crawler.extract_provider_info(
                    url=(place.get("websiteUri") or ""),
                    provider_name=(place.get("displayName") or {}).get("text", ""),
                    query=query,
                ))
                for place in raw_results
            ]
            raw_summaries, raw_crawl_results = await asyncio.gather(
                asyncio.gather(*summary_tasks, return_exceptions=True),
                asyncio.gather(*crawl_tasks, return_exceptions=True),
            )
            english_summaries = [r if isinstance(r, str) else None for r in raw_summaries]
            crawl_results = list(raw_crawl_results)
            crawl_successes = sum(1 for r in crawl_results if isinstance(r, WebCrawlResult))
            logger.info(
                "Webpage enrichment: %d/%d providers crawled successfully",
                crawl_successes, len(crawl_results),
            )
        else:
            raw_summaries = await asyncio.gather(*summary_tasks, return_exceptions=True)
            english_summaries = [r if isinstance(r, str) else None for r in raw_summaries]
            crawl_results = [None] * len(raw_results)
            logger.info("Webpage enrichment disabled (GP_WEBPAGE_CRAWL_ENABLED=false).")

        results: list[dict[str, Any]] = []
        for idx, place in enumerate(raw_results):
            place_id: str = place.get("id", "")
            if not place_id:
                continue

            # Deterministic UUIDs — same place_id always → same UUID
            user_uuid = str(generate_uuid5(place_id))
            comp_uuid = str(generate_uuid5(f"{place_id}:competence"))

            # User-facing description: editorialSummary first (in original
            # language), synthetic fallback, then name+types as last resort.
            description: str = (
                (place.get("editorialSummary") or {}).get("text", "").strip()
            )
            if not description:
                synth = english_summaries[idx]
                if isinstance(synth, str) and synth:
                    description = synth
            if not description:
                types = place.get("types", [])
                display_name = (place.get("displayName") or {}).get("text", "")
                description = f"{display_name} — {', '.join(types[:3])}"

            # search_optimized_summary: always English (for cross-encoder +
            # vector index compatibility). Fall back to the (possibly non-English)
            # description only if synthesis failed entirely.
            synth_summary = english_summaries[idx]
            search_optimized_summary = (
                synth_summary
                if isinstance(synth_summary, str) and synth_summary
                else description
            )

            # Phone / address — stored in Weaviate, masked in logs
            phone: str = place.get("nationalPhoneNumber") or ""
            address: str = place.get("formattedAddress") or ""
            name: str = (place.get("displayName") or {}).get("text", "")

            # Photo URL — first photo from Places API
            photo: str = ""
            raw_photos = place.get("photos") or []
            if raw_photos and self._api_key:
                photo_name = raw_photos[0].get("name", "")
                if photo_name:
                    photo = (
                        f"https://places.googleapis.com/v1/{photo_name}"
                        f"/media?maxWidthPx=400&key={self._api_key}"
                    )

            # Opening hours — human-readable weekday strings
            opening_hours: str = ""
            raw_hours = (place.get("regularOpeningHours") or {}).get(
                "weekdayDescriptions", []
            )
            if raw_hours:
                opening_hours = "\n".join(raw_hours)

            # Merge crawl enrichment into description / summary fields.
            crawl = crawl_results[idx] if idx < len(crawl_results) else None
            if crawl is not None and not isinstance(crawl, Exception):
                if isinstance(crawl, WebCrawlResult):
                    if crawl.specialities:
                        search_optimized_summary = f"{search_optimized_summary} {crawl.specialities}".strip()
                    if crawl.services:
                        services_text = ", ".join(crawl.services[:10])
                        search_optimized_summary = f"{search_optimized_summary} Services: {services_text}".strip()
                    extra = " ".join(filter(None, [crawl.portfolio_highlights, crawl.coverage_area])).strip()
                    if extra:
                        description = f"{description} {extra}".strip()

            results.append({
                "place_id": place_id,
                "user_uuid": user_uuid,
                "comp_uuid": comp_uuid,
                "name": name,
                "title": name,
                "description": description,
                "search_optimized_summary": search_optimized_summary,
                "phone": phone,
                "website": place.get("websiteUri") or "",
                "address": address,
                "average_rating": float(place.get("rating") or 0.0),
                "rating_count": int(place.get("userRatingCount") or 0),
                "photo_url": photo,
                "opening_hours": opening_hours,
                # Deep link that opens the Google Maps place card directly.
                "maps_url": (
                    "https://www.google.com/maps/search/?api=1"
                    f"&query={urllib.parse.quote(name)}"
                    f"&query_place_id={place_id}"
                ),
                "category": _extract_category(place.get("types", [])),
                "primary_type": (place.get("primaryTypeDisplayName") or {}).get("text", ""),
                "review_snippets": _extract_review_snippets(
                    place.get("reviews") or [], max_count=5, max_chars=120
                ),
                "skills_list": _merge_crawl_skills(crawl_results, idx),
                "webpage_crawled": _crawl_succeeded(crawl_results, idx),
                "email": crawl.email if isinstance(crawl, WebCrawlResult) else "",
            })

        return results

    async def _synthesise_description(
        self,
        place: dict[str, Any],
        query: str,
        reviews: list[dict[str, Any]] | None = None,
        editorial_summary: str | None = None,
    ) -> str | None:
        """
        Generate a short English-language service summary for a Place.

        This is used exclusively as the ``search_optimized_summary`` fed to the
        ms-marco cross-encoder and (in full mode) to the Weaviate vector index —
        both of which are English-only.  Always outputs English regardless of the session language
        or the language of the editorial_summary / reviews provided.

        ``editorial_summary`` — when provided (e.g. from editorialSummary in the
        GP API, which may be in the local language), its content is passed as
        context so the LLM can capture real specialties rather than generic types.
        """
        from langchain_core.messages import HumanMessage

        name = (place.get("displayName") or {}).get("text", "")
        primary_type = (place.get("primaryTypeDisplayName") or {}).get("text", "")
        types_phrase = primary_type or ", ".join(
            t.replace("_", " ") for t in (place.get("types") or [])[:4]
        )
        location = place.get("formattedAddress", "").split(",")[-1].strip()

        extra_context = ""
        if editorial_summary:
            extra_context += f" Official description: {editorial_summary}."
        if reviews:
            snippets = _extract_review_snippets(reviews, max_count=5, max_chars=120)
            if snippets:
                extra_context += f" Customers have mentioned: {'; '.join(snippets)}."

        # Include all available type tags for richer vocabulary in the summary.
        all_types = ", ".join(
            t.replace("_", " ") for t in (place.get("types") or [])[:6]
        )
        type_context = (
            f" Also classified as: {all_types}." if all_types and all_types != types_phrase else ""
        )
        prompt = (
            f"Write ONE short English sentence describing the services offered by '{name}' "
            f"which provides {types_phrase} in {location}.{extra_context}{type_context} "
            "Focus on their specialties and unique offerings. "
            "The sentence MUST be in English regardless of any non-English text above. "
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


def _normalised_to_provider(place: dict[str, Any]) -> dict[str, Any]:
    """Convert a ``_normalise_places()`` dict to the provider shape expected by
    the cross-encoder, FINALIZE prompt, and Flutter card renderer.
    """
    return {
        "uuid": place["comp_uuid"],
        "score": 0.0,  # no retrieval score; cross-encoder supplies rerank_score
        "title": place["title"],
        "description": place.get("description", ""),
        "search_optimized_summary": place.get("search_optimized_summary", ""),
        "primary_type": place.get("primary_type", ""),
        "category": place.get("category", ""),
        "skills_list": place.get("skills_list") or [],
        "review_snippets": place.get("review_snippets") or [],
        "user": {
            "uuid": place["user_uuid"],
            "user_id": None,
            "name": place["name"],
            "source": "google_places",
            "is_service_provider": True,
            "phone": place.get("phone", ""),
            "website": place.get("website", ""),
            "address": place.get("address", ""),
            "average_rating": place.get("average_rating", 0.0),
            "rating_count": place.get("rating_count", 0),
            "photo_url": place.get("photo_url", ""),
            "opening_hours": place.get("opening_hours", ""),
            "maps_url": place.get("maps_url", ""),
            "email": place.get("email", ""),
        },
        "phone": place.get("phone", ""),
        "website": place.get("website", ""),
        "address": place.get("address", ""),
        "photo_url": place.get("photo_url", ""),
        "opening_hours": place.get("opening_hours", ""),
        "maps_url": place.get("maps_url", ""),
        "email": place.get("email", ""),
        "average_rating": place.get("average_rating", 0.0),
        "rating_count": place.get("rating_count", 0),
    }


def _merge_crawl_skills(crawl_results: list[Any], idx: int) -> list[str]:
    """Return de-duplicated service list from the crawl result at *idx*.

    Returns an empty list if the result is absent, an exception, or not a
    ``WebCrawlResult`` instance.
    """
    if idx >= len(crawl_results):
        return []
    crawl = crawl_results[idx]
    if crawl is None or isinstance(crawl, Exception):
        return []
    if not isinstance(crawl, WebCrawlResult):
        return []
    return list(dict.fromkeys(s for s in crawl.services if s))[:20]


def _crawl_succeeded(crawl_results: list[Any], idx: int) -> bool:
    """Return ``True`` if the crawl result at *idx* is a valid ``WebCrawlResult``."""
    if idx >= len(crawl_results):
        return False
    crawl = crawl_results[idx]
    return isinstance(crawl, WebCrawlResult)


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
