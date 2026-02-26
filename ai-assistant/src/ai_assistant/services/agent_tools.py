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
# Built-in tool implementations — service request / search
# ─────────────────────────────────────────────────────────────────────────────

async def _search_providers(params: dict, context: dict) -> Any:
    query = params.get("query", "")
    limit = int(params.get("limit", 3))
    dp = context["data_provider"]
    return await dp.search_providers(query_text=query, limit=limit)


async def _get_favorites(params: dict, context: dict) -> Any:
    fs = context["firestore_service"]
    return await fs.get_user_favorites(context["user_id"])


async def _get_open_requests(params: dict, context: dict) -> Any:
    fs = context["firestore_service"]
    return await fs.get_service_requests(user_id=context["user_id"])


async def _create_service_request(params: dict, context: dict) -> Any:
    fs = context["firestore_service"]
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

    fs = context["firestore_service"]
    user_id = context["user_id"]
    decision = params.get("decision", "not_now")
    now = datetime.now(timezone.utc)

    if decision == "accepted":
        await fs.update_user(user_id, {
            "is_service_provider": True,
            "last_time_asked_being_provider": now,
        })
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
    return await context["firestore_service"].get_competencies(context["user_id"])


async def _save_competence_batch(params: dict, context: dict) -> Any:
    """
    Create or update one or more competence entries for the user.

    params["skills"] is a list of dicts. Each dict may optionally contain
    "competence_id" to signal an update; otherwise a new entry is created.
    After saving, marks the user as a service provider and syncs to Weaviate.
    """
    fs = context["firestore_service"]
    user_id = context["user_id"]
    skills: List[dict] = params.get("skills", [])
    saved = []

    for skill in skills:
        skill_copy = dict(skill)  # don't mutate caller's dict
        competence_id = skill_copy.pop("competence_id", None)
        if competence_id:
            result = await fs.update_competence(user_id, competence_id, skill_copy)
        else:
            result = await fs.create_competence(user_id, skill_copy)
        saved.append(result)

    await fs.update_user(user_id, {"is_service_provider": True})

    # Weaviate re-sync using skill titles (required — errors propagate)
    titles = [s.get("title", "") for s in skills if s.get("title")]
    if titles:
        HubSpokeIngestion.update_competencies_by_user_id(user_id, titles)

    return {"saved": saved, "count": len(saved)}


async def _delete_competences(params: dict, context: dict) -> Any:
    """Delete competencies by their IDs and sync to Weaviate."""
    fs = context["firestore_service"]
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
                        "description": "Maximum number of results to return (default 3).",
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
            "Required field per skill: 'title'. Optional: 'description', 'category', "
            "'price_range', 'year_of_experience'."
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
                                "price_range": {"type": "string"},
                                "year_of_experience": {"type": "integer"},
                            },
                            "required": ["title"],
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
