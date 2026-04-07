"""
Agent Profile
=============
Defines the configurable personality/capability envelope for the AI assistant.

Two pre-built profiles ship with the platform:

- ``FULL_PROFILE`` — the standard multi-stage conversation engine with voice
  support, provider pitch, and the full tool set.
- ``LITE_PROFILE`` — a lighter, text-only variant aimed at stand-alone widget
  or web-embed deployments.  Google Places is always active; the stage machine
  is simplified; no pitch/onboarding; a single ``search_providers`` tool.

Usage
-----
Read ``AGENT_MODE`` once at startup and call ``get_profile(mode)``::

    import os
    from .services.agent_profile import get_profile

    profile = get_profile(os.getenv("AGENT_MODE", "full").lower().strip())

The profile is then injected into ``ConversationService``,
``ResponseOrchestrator`` / ``AgentToolRegistry``, ``SignalingServer``, and
``PeerConnectionHandler``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .conversation_service import ConversationStage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentProfile:
    """Immutable capability/configuration envelope for one deployment mode."""

    name: str
    """Human-readable label — ``"full"`` or ``"lite"``."""

    # ── Stage machine ──────────────────────────────────────────────────────
    legal_transitions: dict[ConversationStage, list[ConversationStage]]
    """Allowed stage transitions.  Used by ``ResponseOrchestrator`` to guard
    every ``signal_transition`` called by the LLM."""

    # ── Tools ──────────────────────────────────────────────────────────────
    available_tool_names: frozenset
    """Tool names that the LLM may call in this mode.  An extra gate inside
    ``AgentToolRegistry.execute()`` raises ``ToolPermissionError`` for any
    call outside this set."""

    # ── Behaviour flags ────────────────────────────────────────────────────
    provider_pitch_enabled: bool
    """When ``False`` the ``COMPLETED → PROVIDER_PITCH`` transition is never
    offered, regardless of user eligibility."""

    finalize_auto_complete: bool
    """Lite mode only.  After the FINALIZE provider list has been presented,
    automatically advance to ``COMPLETED`` without waiting for user input."""

    google_places_always_active: bool
    """When ``True`` the Google Places pipeline runs for every FINALIZE entry
    (subject to a location field being present in the structured query).
    When ``False`` GP is never queried regardless of ``GOOGLE_PLACES_API_KEY``."""

    voice_enabled: bool
    """When ``False`` the ``SignalingServer`` rejects ``?mode=voice`` connections
    with close code 4403 and ``PeerConnectionHandler`` skips all audio paths."""

    firestore_enabled: bool
    """When ``False`` all Firestore reads and writes are skipped for the
    lifetime of the session and its associated REST endpoints.  The AI session
    runs entirely in-memory; no conversation history is persisted and no user
    context is fetched from Firestore.  Intended for lite-mode deployments that
    serve anonymous or external users where data persistence is undesirable."""

    # ── Prompts ────────────────────────────────────────────────────────────
    prompt_key: str
    """Key into ``PROMPT_SETS`` in ``prompts_templates.py`` — ``"full"`` or ``"lite"``."""


# ─────────────────────────────────────────────────────────────────────────────
# Legal transition tables
# ─────────────────────────────────────────────────────────────────────────────

#: Full mode — identical to the historical ``_LEGAL_TRANSITIONS`` constant in
#: ``conversation_service.py``.  Kept in sync manually.
_FULL_TRANSITIONS: dict[ConversationStage, list[ConversationStage]] = {
    ConversationStage.GREETING:       [ConversationStage.TRIAGE],
    ConversationStage.TRIAGE:         [
        ConversationStage.CONFIRMATION,
        ConversationStage.CLARIFY,
        ConversationStage.TOOL_EXECUTION,
        ConversationStage.RECOVERY,
        ConversationStage.PROVIDER_ONBOARDING,
    ],
    ConversationStage.CLARIFY:        [ConversationStage.TRIAGE],
    ConversationStage.TOOL_EXECUTION: [
        ConversationStage.TRIAGE,
        ConversationStage.CONFIRMATION,
        ConversationStage.FINALIZE,
    ],
    ConversationStage.CONFIRMATION:   [ConversationStage.FINALIZE, ConversationStage.TRIAGE],
    ConversationStage.FINALIZE:       [
        ConversationStage.COMPLETED,
        ConversationStage.RECOVERY,
        ConversationStage.TRIAGE,
    ],
    ConversationStage.RECOVERY:       [ConversationStage.TRIAGE, ConversationStage.CONFIRMATION],
    ConversationStage.COMPLETED:      [
        ConversationStage.PROVIDER_PITCH,
        ConversationStage.TRIAGE,
    ],
    ConversationStage.PROVIDER_PITCH: [
        ConversationStage.PROVIDER_ONBOARDING,
        ConversationStage.COMPLETED,
        ConversationStage.TRIAGE,
    ],
    ConversationStage.PROVIDER_ONBOARDING: [
        ConversationStage.COMPLETED,
        ConversationStage.TRIAGE,
    ],
}

#: Lite mode — simplified stage set; no pitch, no onboarding, no TOOL_EXECUTION.
_LITE_TRANSITIONS: dict[ConversationStage, list[ConversationStage]] = {
    ConversationStage.GREETING:     [ConversationStage.TRIAGE],
    ConversationStage.TRIAGE:       [
        ConversationStage.CONFIRMATION,
        ConversationStage.CLARIFY,
        ConversationStage.RECOVERY,
    ],
    ConversationStage.CLARIFY:      [ConversationStage.TRIAGE],
    ConversationStage.CONFIRMATION: [ConversationStage.FINALIZE, ConversationStage.TRIAGE],
    ConversationStage.FINALIZE:     [
        ConversationStage.COMPLETED,
        ConversationStage.RECOVERY,
        ConversationStage.TRIAGE,
    ],
    ConversationStage.COMPLETED:    [ConversationStage.TRIAGE],
    ConversationStage.RECOVERY:     [ConversationStage.TRIAGE, ConversationStage.CONFIRMATION],
}


# ─────────────────────────────────────────────────────────────────────────────
# Pre-built profile singletons
# ─────────────────────────────────────────────────────────────────────────────

FULL_PROFILE = AgentProfile(
    name="full",
    legal_transitions=_FULL_TRANSITIONS,
    available_tool_names=frozenset({
        "search_providers",
        "get_favorites",
        "get_open_requests",
        "create_service_request",
        "record_provider_interest",
        "get_my_competencies",
        "save_competence_batch",
        "delete_competences",
    }),
    provider_pitch_enabled=True,
    finalize_auto_complete=False,
    google_places_always_active=False,
    voice_enabled=True,
    firestore_enabled=True,
    prompt_key="full",
)

LITE_PROFILE = AgentProfile(
    name="lite",
    legal_transitions=_LITE_TRANSITIONS,
    available_tool_names=frozenset({"search_providers"}),
    provider_pitch_enabled=False,
    finalize_auto_complete=True,
    google_places_always_active=True,
    voice_enabled=False,
    firestore_enabled=False,
    prompt_key="lite",
)


def get_profile(mode: str) -> AgentProfile:
    """Return the ``AgentProfile`` matching *mode*.

    Logs a warning and falls back to ``FULL_PROFILE`` for unrecognised values
    so a misconfigured ``AGENT_MODE`` env var degrades gracefully.

    Args:
        mode: ``"full"`` or ``"lite"`` (case-insensitive, already stripped).

    Returns:
        The matching :class:`AgentProfile` singleton.
    """
    if mode == "lite":
        return LITE_PROFILE
    if mode != "full":
        logger.warning(
            "Unknown AGENT_MODE=%r — defaulting to 'full'", mode
        )
    return FULL_PROFILE
