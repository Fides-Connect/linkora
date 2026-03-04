"""
Agent Tools
Defines tool adapters callable by the LLM agent via Gemini function-calling.

Each AgentTool carries:
- name / description  — for Gemini function schema registration
- schema              — Gemini function-calling declaration dict
- required_capability — ToolCapability the session user must hold
- execute             — async callable (params: dict, context: dict) -> Any

Context shape expected by all execute() functions::

    {
        "user_id":           str,
        "user_capabilities": list[ToolCapability],
        "data_provider":     DataProvider,
        "firestore_service": FirestoreService,
    }
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..hub_spoke_ingestion import HubSpokeIngestion
from ..firestore_schemas import AvailabilityTimeSchema, derive_availability_tags

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ToolCapability — explicit permission model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolCapability:
    """A capability grant expressed as (scope, action) pair."""
    scope: str
    action: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ToolCapability):
            return NotImplemented
        return self.scope == other.scope and self.action == other.action

    def __hash__(self) -> int:
        return hash((self.scope, self.action))

    def __repr__(self) -> str:
        return f"ToolCapability(scope={self.scope!r}, action={self.action!r})"


def check_capability(required: ToolCapability, caps: List[ToolCapability]) -> bool:
    """Return True when *required* is present in the user's *caps* list."""
    return required in caps


# ─────────────────────────────────────────────────────────────────────────────
# ToolPermissionError
# ─────────────────────────────────────────────────────────────────────────────

class ToolPermissionError(PermissionError):
    """Raised when the session user lacks the required capability for a tool."""

    def __init__(self, tool_name: str, required_capability: ToolCapability) -> None:
        self.tool_name = tool_name
        self.required_capability = required_capability
        super().__init__(
            f"Tool '{tool_name}' requires capability "
            f"{required_capability} which the session user does not hold."
        )


# ─────────────────────────────────────────────────────────────────────────────
# AgentTool
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentTool:
    """A single tool callable by the LLM agent."""
    name: str
    description: str
    schema: Dict[str, Any]          # Gemini function-calling declaration
    required_capability: ToolCapability
    _execute: Callable              # async (params: dict, context: dict) -> Any

    async def execute(self, params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        return await self._execute(params, context)


# ─────────────────────────────────────────────────────────────────────────────
# AgentToolRegistry
# ─────────────────────────────────────────────────────────────────────────────

class AgentToolRegistry:
    """Registry of AgentTool instances; dispatches execute() with permission checks."""

    def __init__(self) -> None:
        self._tools: Dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[AgentTool]:
        return self._tools.get(name)

    async def execute(
        self,
        name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Any:
        """
        Execute the named tool after permission check.

        Raises:
            KeyError            — unknown tool name
            ToolPermissionError — user lacks required_capability
        """
        tool = self._tools[name]   # KeyError if not found

        user_caps: List[ToolCapability] = context.get("user_capabilities", [])
        if not check_capability(tool.required_capability, user_caps):
            raise ToolPermissionError(name, tool.required_capability)

        logger.info("Executing tool '%s' for user '%s'", name, context.get("user_id"))
        return await tool.execute(params, context)

    def all_schemas(self) -> List[Dict[str, Any]]:
        """Return all Gemini function-calling schemas for LLMService registration."""
        return [t.schema for t in self._tools.values()]


# ─────────────────────────────────────────────────────────────────────────────
# Context helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_fs(context: dict):
    """Extract firestore_service from context, raising a clear error if absent."""
    fs = context.get("firestore_service")
    if fs is None:
        raise RuntimeError(
            "firestore_service not injected into tool context — "
            "ensure _create_language_specific_assistant sets assistant.firestore_service"
        )
    return fs


# ─────────────────────────────────────────────────────────────────────────────
# Built-in tool implementations — service request / search
# ─────────────────────────────────────────────────────────────────────────────

async def _search_providers(params: dict, context: dict) -> Any:
    query = params.get("query", "")
    limit = int(params.get("limit", 5))
    dp = context["data_provider"]
    cross_encoder = context.get("cross_encoder_service")
    # For explicit mid-conversation tool calls, apply reranking when available.
    raw = await dp.search_providers(query_text=query, limit=min(limit * 5, 30))
    if cross_encoder and raw:
        from .cross_encoder_service import CrossEncoderService
        raw = await cross_encoder.rerank(query=query, candidates=raw, top_k=limit)
    else:
        raw = raw[:limit]
    return raw


async def _get_favorites(params: dict, context: dict) -> Any:
    fs = _require_fs(context)
    return await fs.get_user_favorites(context["user_id"])


async def _get_open_requests(params: dict, context: dict) -> Any:
    fs = _require_fs(context)
    return await fs.get_service_requests(user_id=context["user_id"])


async def _create_service_request(params: dict, context: dict) -> Any:
    fs = _require_fs(context)
    return await fs.create_service_request(
        user_id=context["user_id"],
        title=params.get("title", ""),
        description=params.get("description", ""),
    )


async def _cancel_service_request(params: dict, context: dict) -> Any:
    """Set a service request's status to 'cancelled'."""
    fs = context["firestore_service"]
    request_id = params.get("request_id", "")
    if not request_id:
        return {"error": "request_id is required"}
    await fs.update_service_request(request_id, {"status": "cancelled"})
    return {"cancelled": True, "request_id": request_id}


# ─────────────────────────────────────────────────────────────────────────────
# Provider onboarding tool implementations
# ─────────────────────────────────────────────────────────────────────────────

async def _record_provider_interest(params: dict, context: dict) -> Any:
    """
    Record the user's response to the provider pitch.

    decision values:
    - "accepted"  → set is_service_provider=True; return signal to enter PROVIDER_ONBOARDING
    - "not_now"   → reset last_time_asked_being_provider to now (re-check in 30 days)
    - "never"     → set last_time_asked_being_provider to PROVIDER_PITCH_OPT_OUT_SENTINEL
    """
    from ..firestore_schemas import PROVIDER_PITCH_OPT_OUT_SENTINEL

    fs = _require_fs(context)
    user_id = context["user_id"]
    decision = params.get("decision", "not_now")
    now = datetime.now(timezone.utc)

    if decision == "accepted":
        await fs.update_user(user_id, {
            "is_service_provider": True,
            "last_time_asked_being_provider": now,
        })
        # Immediately mirror the flag to Weaviate so the is_service_provider==True
        # filter in provider searches is visible before the next request.
        HubSpokeIngestion.update_user_hub_properties(user_id, {"is_service_provider": True})
        return {"signal_transition": "provider_onboarding", "status": "accepted"}
    elif decision == "never":
        await fs.update_user(user_id, {
            "last_time_asked_being_provider": PROVIDER_PITCH_OPT_OUT_SENTINEL,
        })
        return {"status": "never"}
    else:  # "not_now" and any other value
        await fs.update_user(user_id, {
            "last_time_asked_being_provider": now,
        })
        return {"status": "not_now"}


async def _get_my_competencies(params: dict, context: dict) -> Any:
    """Fetch the current user's competency list from Firestore."""
    fs = _require_fs(context)
    return await fs.get_competencies(context["user_id"])


async def _save_competence_batch(params: dict, context: dict) -> Any:
    """
    Create or update one or more competence entries for the user.

    Pipeline:
    1. Save each skill to Firestore (create or update).
    2. Run LLM enrichment via CompetenceEnricher (extracts skills_list,
       search_optimized_summary, availability_tags, price_per_hour, …).
    3. Write enriched fields back to Firestore.
    4. Mark user as service provider.
    5. Full re-sync all competencies to Weaviate with enriched data.

    params["skills"] is a list of dicts. Each dict may optionally contain
    "competence_id" to signal an update; otherwise a new entry is created.
    """
    from .competence_enricher import CompetenceEnricher  # local import avoids circular deps

    fs = _require_fs(context)
    user_id = context["user_id"]
    enricher: Optional[CompetenceEnricher] = context.get("competence_enricher")
    skills: List[dict] = params.get("skills", [])
    saved = []

    # Validate: price_range is mandatory for every NEW skill (no competence_id)
    missing_price = [
        skill.get("title", "(untitled)")
        for skill in skills
        if not skill.get("competence_id")
        and not skill.get("price_range", "").strip()
    ]
    if missing_price:
        return {
            "error": (
                f"price_range is required but was missing or empty for new entries: "
                f"{', '.join(missing_price)}. "
                "Ask the user for their pricing (e.g. hourly rate or fixed price) "
                "before calling save_competence_batch."
            )
        }

    # Load existing competencies once for the whole batch so we can do
    # server-side deduplication (title-collision → upgrade new → update).
    # Must happen BEFORE the availability_time check so deduplicated skills
    # (which become UPDATEs) are not incorrectly flagged as missing availability.
    try:
        existing_competencies: list[dict] = await fs.get_competencies(user_id) or []
    except Exception:  # pragma: no cover
        existing_competencies = []
    existing_by_title: dict[str, str] = {
        (c.get("title") or "").strip().lower(): c.get("competence_id", "")
        for c in existing_competencies
        if c.get("competence_id")
    }

    # Validate: availability_time is mandatory for every truly NEW skill.
    # A skill is "truly new" when it has no competence_id AND its title does not
    # match an existing competence (which would be deduplicated to an UPDATE).
    missing_availability = [
        skill.get("title", "(untitled)")
        for skill in skills
        if not skill.get("competence_id")
        and (skill.get("title") or "").strip().lower() not in existing_by_title
        and not skill.get("availability_time")
    ]
    if missing_availability:
        return {
            "error": (
                f"availability_time is required but was missing for new entries: "
                f"{', '.join(missing_availability)}. "
                "Ask the user when they are usually available (e.g. 'when are you usually free?') "
                "before calling save_competence_batch."
            )
        }

    for skill in skills:
        skill_copy = dict(skill)  # don't mutate caller's dict

        # Pop availability_time before hitting Firestore — it's written to the
        # 'availability_time' subcollection separately, not onto the competence doc.
        availability_time_data: Optional[dict] = skill_copy.pop("availability_time", None)

        # Legacy normalisation: if the LLM sent 'availability' as a plain string,
        # keep it in skill_copy so CompetenceEnricher can use it for context, but
        # do NOT store it in Firestore (CompetenceUpdateSchema has extra='ignore').
        # No 'availability_text' flat field exists on the schema any more.

        competence_id = skill_copy.pop("competence_id", None)

        # Server-side deduplication: if the LLM omitted competence_id but a
        # competence with the same title already exists, treat this as an update
        # to prevent duplicate entries.
        if not competence_id:
            lookup_title = (skill_copy.get("title") or "").strip().lower()
            if lookup_title and lookup_title in existing_by_title:
                competence_id = existing_by_title[lookup_title]
                logger.info(
                    "Deduplication: upgrading new-entry '%s' to update of %s",
                    skill_copy.get("title"), competence_id,
                )

        if competence_id:
            result = await fs.update_competence(user_id, competence_id, skill_copy)
        else:
            result = await fs.create_competence(user_id, skill_copy)
        saved.append(result)

        # ── Write availability_time subcollection ─────────────────────────────────
        saved_id = (
            (result.get("id") or result.get("competence_id") or competence_id)
            if result
            else None
        )
        if availability_time_data and saved_id:
            from pydantic import ValidationError as _ValidationError
            try:
                # Validate the structured time data before writing.
                fs._validate_data(availability_time_data, AvailabilityTimeSchema)
                # Check whether a doc already exists to decide create vs. update.
                existing_avail = await fs.get_availability_times(
                    user_id, competence_id=saved_id
                )
                if existing_avail:
                    avail_id = existing_avail[0].get("availability_time_id")
                    await fs.update_availability_time(
                        user_id, avail_id, availability_time_data, competence_id=saved_id
                    )
                else:
                    await fs.create_availability_time(
                        user_id, availability_time_data, competence_id=saved_id
                    )
                logger.info(
                    "Wrote availability_time for competence %s (user %s)", saved_id, user_id
                )
            except _ValidationError as avail_err:
                field_errors = fs._format_validation_errors(avail_err)
                return {
                    "error": (
                        "availability_time contains invalid data. "
                        "Fix the highlighted fields and retry."
                    ),
                    "field_errors": field_errors,
                    "hint": (
                        "time ranges: use HH:MM format (e.g. '09:00'), "
                        "absence_days: use YYYY-MM-DD (e.g. '2026-03-15')"
                    ),
                }

        # ── LLM enrichment ───────────────────────────────────────────────────
        if enricher is not None:
            # Resolve competence_id for the write-back.
            saved_id = (
                result.get("id")
                or result.get("competence_id")
                or competence_id
            )
            if saved_id:
                enriched = await enricher.enrich(skill_copy)
                enriched_fields = {
                    k: enriched[k]
                    for k in (
                        "skills_list",
                        "search_optimized_summary",
                        "availability_tags",
                        "availability_text",
                        "price_per_hour",
                        "category",
                    )
                    if k in enriched
                }
                if enriched_fields:
                    await fs.update_competence(user_id, saved_id, enriched_fields)
                    logger.info(
                        "Enriched competence %s for user %s", saved_id, user_id
                    )
        else:
            logger.warning(
                "competence_enricher not in context — skipping enrichment for user %s",
                user_id,
            )

    await fs.update_user(user_id, {"is_service_provider": True})
    # Immediately mirror the flag to the Weaviate User hub so that the
    # is_service_provider==True filter in provider searches becomes visible
    # before the next request.  (update_competencies_by_user_id only touches
    # Competence spokes — it does not rewrite User hub properties.)
    HubSpokeIngestion.update_user_hub_properties(user_id, {"is_service_provider": True})

    # Weaviate full re-sync: read ALL competencies from Firestore (ground truth) so
    # that skills saved in earlier sessions are preserved in Weaviate.
    # For each competence, fetch its availability_time subcollection and inject
    # derived availability_tags so Weaviate filtering stays accurate.
    all_competencies = await fs.get_competencies(user_id)
    if all_competencies:
        for comp in all_competencies:
            cid = comp.get("competence_id")
            if cid:
                avail_docs = await fs.get_availability_times(user_id, competence_id=cid)
                if avail_docs:
                    avail_data = avail_docs[0]  # one doc per competence
                    comp["availability_time"] = avail_data
                    comp["availability_tags"] = derive_availability_tags(avail_data)
        result = HubSpokeIngestion.update_competencies_by_user_id(user_id, all_competencies)
        if isinstance(result, dict) and not result.get("success") and result.get("error") == "User not found":
            logger.warning(
                "Weaviate user not found for %s — self-healing by creating from Firestore",
                user_id,
            )
            try:
                user_data = await fs.get_user(user_id) or {}
                user_data.setdefault("user_id", user_id)
                HubSpokeIngestion.create_user(user_data)
                # Re-sync with full competence dicts so all metadata is written.
                HubSpokeIngestion.update_competencies_by_user_id(user_id, all_competencies)
                logger.info("Weaviate self-heal complete for user %s", user_id)
            except Exception as heal_exc:
                logger.error(
                    "Weaviate self-heal failed for user %s: %s", user_id, heal_exc,
                    exc_info=True,
                )
                raise

    return {"saved": saved, "count": len(saved)}


async def _delete_competences(params: dict, context: dict) -> Any:
    """Delete competencies by their IDs and sync to Weaviate."""
    fs = _require_fs(context)
    user_id = context["user_id"]
    ids: List[str] = params.get("competence_ids", [])
    deleted = []

    for cid in ids:
        ok = await fs.remove_competence(user_id, cid)
        if ok:
            deleted.append(cid)

    # Weaviate sync: remove each deleted competence by its Firestore ID (required — errors propagate)
    for cid in deleted:
        HubSpokeIngestion.remove_competence_by_firestore_id(cid)

    return {"deleted_ids": deleted, "count": len(deleted)}


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def build_default_registry() -> AgentToolRegistry:
    """
    Build the default registry wiring all 8 built-in tools.
    Dependencies are injected per-call via the `context` dict passed to execute().
    """
    registry = AgentToolRegistry()

    registry.register(AgentTool(
        name="search_providers",
        description="Search for service providers matching a query.",
        schema={
            "name": "search_providers",
            "description": "Search for service providers matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of the required service.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
        required_capability=ToolCapability("providers", "read"),
        _execute=_search_providers,
    ))

    registry.register(AgentTool(
        name="get_favorites",
        description="Retrieve the user's saved favourite service providers.",
        schema={
            "name": "get_favorites",
            "description": "Retrieve the user's saved favourite service providers.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        required_capability=ToolCapability("favorites", "read"),
        _execute=_get_favorites,
    ))

    registry.register(AgentTool(
        name="get_open_requests",
        description="Retrieve all open service requests for the current user.",
        schema={
            "name": "get_open_requests",
            "description": "Retrieve all open service requests for the current user.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        required_capability=ToolCapability("service_requests", "read"),
        _execute=_get_open_requests,
    ))

    registry.register(AgentTool(
        name="create_service_request",
        description="Create a new service request on behalf of the user.",
        schema={
            "name": "create_service_request",
            "description": "Create a new service request on behalf of the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the service request.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Full description of the service needed.",
                    },
                },
                "required": ["title"],
            },
        },
        required_capability=ToolCapability("service_requests", "write"),
        _execute=_create_service_request,
    ))

    registry.register(AgentTool(
        name="cancel_service_request",
        description="Cancel an existing service request that was previously created.",
        schema={
            "name": "cancel_service_request",
            "description": "Cancel an existing service request that was previously created.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "The ID of the service request to cancel.",
                    },
                },
                "required": ["request_id"],
            },
        },
        required_capability=ToolCapability("service_requests", "write"),
        _execute=_cancel_service_request,
    ))

    # ── Provider onboarding tools ────────────────────────────────────────────
    _ONBOARDING_CAP = ToolCapability("provider_onboarding", "write")

    registry.register(AgentTool(
        name="record_provider_interest",
        description=(
            "Record the user's decision about becoming a service provider. "
            "Call with decision='accepted', 'not_now', or 'never'."
        ),
        schema={
            "name": "record_provider_interest",
            "description": "Record the user's decision about becoming a service provider.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["accepted", "not_now", "never"],
                        "description": "The user's decision: 'accepted', 'not_now', or 'never'.",
                    },
                },
                "required": ["decision"],
            },
        },
        required_capability=_ONBOARDING_CAP,
        _execute=_record_provider_interest,
    ))

    registry.register(AgentTool(
        name="get_my_competencies",
        description="Fetch the current user's list of registered competencies/skills.",
        schema={
            "name": "get_my_competencies",
            "description": "Fetch the current user's list of registered competencies/skills.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        required_capability=_ONBOARDING_CAP,
        _execute=_get_my_competencies,
    ))

    registry.register(AgentTool(
        name="save_competence_batch",
        description=(
            "Create or update one or more service competencies for the user. "
            "Each skill dict may include 'competence_id' for updates, or omit it for new entries. "
            "Required fields per skill: 'title' and 'price_range' (e.g. '€30–€50/h' or 'fixed price €200'). "
            "price_range is MANDATORY for new entries — never create a competence without it. "
            "For UPDATE (competence_id provided), price_range is optional. "
            "Optional fields: 'description', 'category', 'year_of_experience', "
            "'availability' (free-text string), 'availability_time' (structured weekly slots)."
        ),
        schema={
            "name": "save_competence_batch",
            "description": "Create or update one or more service competencies for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skills": {
                        "type": "array",
                        "description": "List of competence objects to save.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "competence_id": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "category": {"type": "string"},
                                "price_range": {
                                    "type": "string",
                                    "description": "Pricing information, e.g. '€30–€50/h' or 'fixed price €200'. REQUIRED for new entries.",
                                },
                                "availability": {
                                    "type": "string",
                                    "description": "Free-text description of when the provider is available, e.g. 'weekdays after 4pm'. Collected first. If the user confirms specific time slots, populate availability_time instead or alongside.",
                                },
                                "availability_time": {
                                    "type": "object",
                                    "description": (
                                        "Structured weekly availability derived from what the user said — no follow-up question needed. "
                                        "Each day key maps to a list of {start_time, end_time} objects in HH:MM (zero-padded). "
                                        "absence_days is an optional list of YYYY-MM-DD strings. "
                                        "Interpretation rules: "
                                        "'morning' → 08:00–12:00; "
                                        "'afternoon' → 12:00–17:00; "
                                        "'evening'/'after work' → 17:00–21:00; "
                                        "'from 14'/'after 2pm' → 14:00–21:00 (default end 21:00 when no end given); "
                                        "'from 9:15 to 12' → 09:15–12:00 (use exact numbers); "
                                        "'whole day'/'all day' → 08:00–20:00; "
                                        "'weekdays' (no time) → 08:00–20:00 on Mon–Fri; "
                                        "'at the weekend'/'weekends' → 08:00–20:00 on Sat+Sun; "
                                        "'flexible'/'anytime'/vague → omit this field entirely. "
                                        "Example for 'Monday morning and Tuesday from 14': "
                                        "{\"monday_time_ranges\": [{\"start_time\": \"08:00\", \"end_time\": \"12:00\"}], "
                                        "\"tuesday_time_ranges\": [{\"start_time\": \"14:00\", \"end_time\": \"21:00\"}]}"
                                    ),
                                    "properties": {
                                        "monday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "tuesday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "wednesday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "thursday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "friday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "saturday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "sunday_time_ranges": {"type": "array", "items": {"type": "object", "properties": {"start_time": {"type": "string"}, "end_time": {"type": "string"}}}},
                                        "absence_days": {"type": "array", "items": {"type": "string"}},
                                    },
                                },
                                "year_of_experience": {"type": "integer"},
                            },
                            "required": ["title", "price_range"],
                        },
                    },
                },
                "required": ["skills"],
            },
        },
        required_capability=_ONBOARDING_CAP,
        _execute=_save_competence_batch,
    ))

    registry.register(AgentTool(
        name="delete_competences",
        description="Delete one or more of the user's competencies by their IDs.",
        schema={
            "name": "delete_competences",
            "description": "Delete one or more of the user's competencies by their IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "competence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of competence IDs to delete.",
                    },
                },
                "required": ["competence_ids"],
            },
        },
        required_capability=_ONBOARDING_CAP,
        _execute=_delete_competences,
    ))

    return registry
