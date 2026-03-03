"""CompetenceEnricher — LLM-powered enrichment of raw competence data.

Transforms the conversationally collected competence fields (title, description,
price_range, …) into a search-optimised representation:

  - ``skills_list``              explicit + implicit skills, normalised
  - ``search_optimized_summary`` LLM-rewritten profile for semantic vector search
  - ``price_per_hour``           numeric float extracted from price_range string
  - ``category``                 may be refined / inferred by the LLM

Availability is now structured in the ``availability_time`` subcollection and is
managed by ``derive_availability_tags()`` in ``firestore_schemas``.  The enricher
receives a human-readable summary of the availability (``availability`` key) for
context when writing ``search_optimized_summary`` — but no longer outputs
``availability_text`` or ``availability_tags``.

Design rules:
- Single non-streaming LLM call per competence (low latency, deterministic).
- Graceful degradation on LLM / parse failure: returns original dict unchanged.
- Constructor-injected ``llm`` (``ChatGoogleGenerativeAI`` or any LangChain chat
  model) — fully mockable at test boundary.
- No side effects: pure async function, no I/O beyond the LLM call.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


_ENRICHMENT_SYSTEM_PROMPT = """\
You are a structured-data extraction engine for a service-provider marketplace.
Given a service provider's raw competence data, output ONLY a single JSON object
— no markdown, no code fences, no commentary.

Rules:
1. skills_list: extract BOTH explicit skills (directly stated) AND implicit skills
   (strongly implied by the domain). Use lowercase English noun phrases.
   Example: "12 years as an electrician doing house wiring"
   → ["house wiring", "residential wiring", "lighting installation",
      "circuit breaker work", "electrical troubleshooting"]

2. search_optimized_summary: rewrite the profile in 2–4 sentences specifically
   optimised for semantic vector search by potential customers. Include domain
   keywords, key skills, experience level, and availability (if known). Write in English.

3. category: use the most appropriate single category from this list:
   Handwerk, IT, Reinigung, Garten, Pflege, Transport, Bildung, Küche, Sonstiges.
   Override the input category only if clearly wrong or empty.

4. price_per_hour: extract the representative hourly rate as a float.
   - For a range like "€20–€40/h" use the midpoint: 30.0
   - For a fixed rate like "€50/h" use: 50.0
   - If no price or non-hourly only, use null.
   Always represent as euros per hour.

Output schema (strict):
{
  "skills_list": ["string", ...],
  "search_optimized_summary": "string",
  "category": "string",
  "price_per_hour": <float | null>
}
"""


class CompetenceEnricher:
    """Enrich raw competence dicts with LLM-extracted, search-optimised fields.

    Args:
        llm: Any LangChain chat model (e.g. ``ChatGoogleGenerativeAI``).  Injected
             so the enricher can be mocked independently in unit tests.
    """

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    async def enrich(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Return *raw* merged with enriched fields.

        On any error (LLM failure, JSON parse, etc.) logs a warning and returns
        *raw* unchanged so the caller can still save to Firestore / Weaviate.

        Args:
            raw: Competence dict with at minimum ``title``.  Recognised keys:
                 title, description, category, price_range, year_of_experience,
                 availability (human-readable string, derived from availability_time
                 by the caller if structured data is available).

        Returns:
            Copy of *raw* with enriched keys added/overridden:
            skills_list, search_optimized_summary, price_per_hour, and
            optionally category.
        """
        user_content = self._build_user_message(raw)
        try:
            messages = [
                SystemMessage(content=_ENRICHMENT_SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ]
            # Non-streaming single-shot call — collect full response.
            full_text = ""
            async for chunk in self._llm.astream(messages):
                text = chunk.content if isinstance(chunk.content, str) else ""
                full_text += text

            enriched = self._parse_response(full_text)
            result = {**raw}
            result.update(enriched)
            logger.info(
                "Competence enriched — title=%r  skills=%d",
                raw.get("title"),
                len(enriched.get("skills_list", [])),
            )
            return result

        except Exception as exc:
            logger.warning(
                "CompetenceEnricher failed for title=%r, returning raw data: %s",
                raw.get("title"),
                exc,
                exc_info=True,
            )
            return dict(raw)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _availability_time_to_text(availability_time: Dict[str, Any]) -> str:
        """Derive a short human-readable availability string from a structured dict.

        Only used as context input to the LLM — not stored in Firestore.
        Example: "Monday 09:00–12:00, Wednesday 14:00–18:00, Friday 09:00–15:00"
        """
        _DAYS = [
            ("monday",    "Monday"),
            ("tuesday",   "Tuesday"),
            ("wednesday", "Wednesday"),
            ("thursday",  "Thursday"),
            ("friday",    "Friday"),
            ("saturday",  "Saturday"),
            ("sunday",    "Sunday"),
        ]
        parts = []
        for field_key, label in _DAYS:
            ranges = availability_time.get(f"{field_key}_time_ranges", []) or []
            if not ranges:
                continue
            slot_parts = []
            for r in ranges:
                if hasattr(r, "start_time"):
                    s, e = r.start_time, r.end_time
                else:
                    s = r.get("start_time", "")
                    e = r.get("end_time", "")
                if s and e:
                    slot_parts.append(f"{s}–{e}")
                elif s:
                    slot_parts.append(f"from {s}")
            if slot_parts:
                parts.append(f"{label} {', '.join(slot_parts)}")
        absence = availability_time.get("absence_days", []) or []
        if absence:
            parts.append(f"absent: {', '.join(absence)}")
        return "; ".join(parts) if parts else ""

    @staticmethod
    def _build_user_message(raw: Dict[str, Any]) -> str:
        # Derive availability text for context: prefer structured availability_time;
        # fall back to plain 'availability' or 'availability_text' string.
        avail_time = raw.get("availability_time")
        if avail_time and isinstance(avail_time, dict):
            avail_str = CompetenceEnricher._availability_time_to_text(avail_time)
        else:
            avail_str = raw.get("availability", "")
        lines = [
            f"title: {raw.get('title', '')}",
            f"description: {raw.get('description', '')}",
            f"category: {raw.get('category', '')}",
            f"price_range: {raw.get('price_range', '')}",
            f"year_of_experience: {raw.get('year_of_experience', 0)}",
            f"availability: {avail_str}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _parse_response(text: str) -> Dict[str, Any]:
        """Extract and validate the JSON payload from the LLM response."""
        # Strip markdown code fences if the model forgets the instruction.
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
        data = json.loads(cleaned)

        skills_list: List[str] = [
            s.strip().lower() for s in data.get("skills_list", []) if isinstance(s, str) and s.strip()
        ]
        summary: str = str(data.get("search_optimized_summary", "")).strip()
        category: str = str(data.get("category", "")).strip()
        price_raw = data.get("price_per_hour")
        price_per_hour: Optional[float] = float(price_raw) if price_raw is not None else None

        result: Dict[str, Any] = {
            "skills_list": skills_list,
            "search_optimized_summary": summary,
            "price_per_hour": price_per_hour,
        }
        if category:
            result["category"] = category
        return result
