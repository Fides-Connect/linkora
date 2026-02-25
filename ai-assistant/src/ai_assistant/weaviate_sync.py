"""
Weaviate Sync Utilities
=======================

Provides reusable building blocks for synchronising Firestore data into the
Weaviate vector index.
"""
import logging
import os
from typing import List, Tuple, Dict, Any, NamedTuple

from .hub_spoke_ingestion import HubSpokeIngestion
from .hub_spoke_schema import init_hub_spoke_schema, cleanup_hub_spoke_schema
from .firestore_service import FirestoreService

logger = logging.getLogger(__name__)


class SyncResult(NamedTuple):
    """Counts returned by :func:`rebuild_weaviate_from_firestore`."""
    success_count: int
    failure_count: int
    total_users: int
    total_competencies: int


async def load_users_from_firestore() -> List[Tuple[Dict[str, Any], List]]:
    """Read all users and their competencies from Firestore.

    Returns:
        List of ``(user_data, competencies)`` tuples where *user_data* is the
        Firestore document dict (augmented with ``'user_id'``) and
        *competencies* is the list returned by
        :meth:`FirestoreService.get_competencies`.

    Raises:
        Exception: propagated if Firestore cannot be reached.
    """
    from firebase_admin import firestore as fs_admin

    firestore_service = FirestoreService()
    db = fs_admin.client()
    user_docs = list(db.collection("users").stream())

    users_payload: List[Tuple[Dict[str, Any], List]] = []
    for doc in user_docs:
        user_data = doc.to_dict()
        user_data["user_id"] = doc.id
        competencies = await firestore_service.get_competencies(doc.id)
        users_payload.append((user_data, competencies))
        logger.debug(f"  Loaded user {doc.id!r} with {len(competencies)} competence(s).")

    return users_payload


def ingest_users_into_weaviate(
    users_payload: List[Tuple[Dict[str, Any], List]],
) -> Tuple[int, int]:
    """Ingest ``(user_data, competencies)`` pairs into Weaviate.

    Args:
        users_payload: As returned by :func:`load_users_from_firestore` or
            built manually from test data.

    Returns:
        ``(success_count, failure_count)`` tuple.
    """
    success_count = 0
    failure_count = 0

    for user_data, competencies in users_payload:
        user_id = user_data.get("user_id", "<unknown>")
        try:
            result = HubSpokeIngestion.create_user_with_competencies(
                user_data=user_data,
                competencies_data=competencies,
                apply_sanitization=True,
                apply_enrichment=True,
            )
            if result:
                success_count += 1
                logger.info(
                    f"  ✓ {user_data.get('name', user_id)!r} "
                    f"({len(competencies)} competence(s))"
                )
            else:
                failure_count += 1
                logger.warning(f"  ✗ Failed to ingest user {user_id!r} (returned falsy).")
        except Exception as exc:
            failure_count += 1
            logger.error(f"  ✗ Exception ingesting user {user_id!r}: {exc}")

    return success_count, failure_count


async def rebuild_weaviate_from_firestore() -> SyncResult:
    """Full sync: read Firestore, wipe Weaviate, reinitialise schema, ingest.

    Reads Firestore *first* so that a transient Firestore outage does not
    leave the Weaviate index in an empty/broken state.

    Returns:
        :class:`SyncResult` with ingestion counts.  A Firestore read failure
        is reported as ``failure_count=1`` so callers can distinguish it from
        a successful (but empty) sync.

    Raises:
        Exception: if the Weaviate schema rebuild fails.
    """
    # ── Step 1: read users from Firestore ─────────────────────────────────────
    logger.info("[Sync 1/3] Reading users and competencies from Firestore...")
    try:
        users_payload = await load_users_from_firestore()
    except Exception as exc:
        logger.error(f"Could not read Firestore: {exc}. Weaviate was not modified.")
        return SyncResult(0, 1, 0, 0)

    total_users = len(users_payload)
    total_competencies = sum(len(c) for _, c in users_payload)
    logger.info(f"  Found {total_users} user(s) and {total_competencies} competence(s) to sync.")

    # ── Step 2: wipe and reinitialise Weaviate ────────────────────────────────
    logger.info("[Sync 2/3] Rebuilding Weaviate schema...")
    cleanup_hub_spoke_schema()
    logger.info("  ✓ Weaviate data cleared.")
    init_hub_spoke_schema()
    logger.info("  ✓ Weaviate schema initialised.")

    if not users_payload:
        logger.warning("No users found in Firestore; Weaviate schema reset but left empty.")
        return SyncResult(0, 0, 0, 0)

    # ── Step 3: ingest ────────────────────────────────────────────────────────
    logger.info("[Sync 3/3] Ingesting users and competencies...")
    success_count, failure_count = ingest_users_into_weaviate(users_payload)

    return SyncResult(success_count, failure_count, total_users, total_competencies)


async def run_startup_sync() -> None:
    """Rebuild the Weaviate index from the current Firestore state.

    Controlled by the ``WEAVIATE_SYNC_ON_STARTUP`` environment variable.
    When the variable is not set to ``"true"`` (case-insensitive) the function
    returns immediately without doing anything.

    If Weaviate is unavailable the error is logged and the function returns so
    that the rest of the server can still start.
    """
    if os.getenv("WEAVIATE_SYNC_ON_STARTUP", "false").lower() != "true":
        logger.info("Weaviate startup sync is disabled (set WEAVIATE_SYNC_ON_STARTUP=true to enable)")
        return

    logger.info("=" * 60)
    logger.info("Weaviate Startup Sync — begin")
    logger.info("=" * 60)

    try:
        result = await rebuild_weaviate_from_firestore()
    except Exception as exc:
        logger.error(f"Weaviate sync aborted — schema rebuild failed: {exc}")
        return

    logger.info("=" * 60)
    if result.failure_count > 0 and result.total_users == 0:
        logger.warning(
            "Weaviate Startup Sync — Firestore could not be read. "
            "Weaviate was not modified."
        )
    elif result.total_users == 0:
        logger.warning(
            "Weaviate Startup Sync — no users found in Firestore. "
            "Weaviate schema was reset but left empty."
        )
    elif result.failure_count == 0:
        logger.info(
            f"Weaviate Startup Sync — completed successfully "
            f"({result.success_count} user(s), {result.total_competencies} competence(s))."
        )
    else:
        logger.warning(
            f"Weaviate Startup Sync — completed with {result.failure_count} error(s) "
            f"({result.success_count}/{result.total_users} user(s) synced)."
        )
    logger.info("=" * 60)
