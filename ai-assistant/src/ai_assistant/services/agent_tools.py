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
from typing import Any, Callable, Dict, List, Optional

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
# Built-in tool implementations
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


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def build_default_registry(data_provider: Any, firestore_service: Any) -> AgentToolRegistry:
    """
    Build the default registry wiring the 4 built-in tools to the given
    data_provider and firestore_service instances.
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

    return registry
