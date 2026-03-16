#!/usr/bin/env python3
"""
Repair script: re-sync a single user's Weaviate data from Firestore.

Usage:
    python scripts/repair_weaviate_user.py <firebase_user_id>

What it does:
1. Reads the user doc from Firestore (ground truth).
1b. Auto-upgrades is_service_provider=True in Firestore if the flag is False but
    the user already has competencies (self-healing guard).
2. Creates or updates the Weaviate User hub node (incl. is_service_provider flag).
3. Enriches all competencies with availability_time from Firestore.
4. Performs a full Weaviate competency re-sync via HubSpokeIngestion.update_competencies_by_user_id.

Run this against any user who is not appearing in provider search results.
"""
import asyncio
import logging
import sys
import os

# Ensure the ai_assistant package is importable from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("repair_weaviate_user")


async def repair(user_id: str) -> None:
    import firebase_admin
    from firebase_admin import credentials as fb_credentials
    from ai_assistant.firestore_service import FirestoreService
    from ai_assistant.hub_spoke_ingestion import HubSpokeIngestion
    from ai_assistant.firestore_schemas import derive_availability_tags

    # Initialize Firebase Admin SDK if not already done.
    if not firebase_admin._apps:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path:
            cred = fb_credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()  # ADC fallback
        logger.info("Firebase Admin SDK initialized.")

    fs = FirestoreService()

    # ── 1. Load user from Firestore ───────────────────────────────────────────
    user_data = await fs.get_user(user_id)
    if not user_data:
        logger.error("User %s not found in Firestore. Aborting.", user_id)
        sys.exit(1)

    logger.info(
        "Firestore user: name=%s  is_service_provider=%s",
        user_data.get("name"),
        user_data.get("is_service_provider"),
    )

    user_data.setdefault("user_id", user_id)

    # ── 1b. Load competencies early to check auto-upgrade eligibility ─────────
    # Do this before the Weaviate writes so the correct flag is used throughout.
    all_competencies = await fs.get_competencies(user_id) or []
    if not user_data.get("is_service_provider") and all_competencies:
        logger.warning(
            "Auto-upgrading is_service_provider=True for %s: Firestore flag was False "
            "but user has %d competencies.",
            user_id,
            len(all_competencies),
        )
        user_data["is_service_provider"] = True
        await fs.update_user(user_id, {"is_service_provider": True})

    # ── 2. Create or update Weaviate User hub ─────────────────────────────────
    from ai_assistant.hub_spoke_schema import get_user_collection
    from weaviate.classes.query import Filter

    coll = get_user_collection()
    res = coll.query.fetch_objects(
        filters=Filter.by_property("user_id").equal(user_id),
        limit=1,
    )

    if res.objects:
        logger.info("Weaviate User hub found — updating hub properties.")
        ok = HubSpokeIngestion.update_user_hub_properties(
            user_id,
            {
                "is_service_provider": user_data.get("is_service_provider", False),
                "name": user_data.get("name", ""),
                "email": user_data.get("email", ""),
            },
        )
        logger.info("update_user_hub_properties: %s", "OK" if ok else "FAILED")
    else:
        logger.info("Weaviate User hub NOT found — creating from Firestore data.")
        uuid = HubSpokeIngestion.create_user(user_data)
        if uuid:
            logger.info("Created Weaviate User hub: uuid=%s", uuid)
        else:
            logger.error("Failed to create Weaviate User hub. Aborting.")
            sys.exit(1)

    # ── 3. Enrich competencies with availability_time from Firestore ─────────
    # (list was already fetched in step 1b above)
    logger.info("Found %d competencies in Firestore.", len(all_competencies))

    for comp in all_competencies:
        cid = comp.get("competence_id")
        if cid:
            avail_docs = await fs.get_availability_times(user_id, competence_id=cid)
            if avail_docs:
                avail_data = avail_docs[0]
                comp["availability_time"] = avail_data
                comp["availability_tags"] = derive_availability_tags(avail_data)
                logger.info(
                    "  competence '%s' → availability_tags=%s",
                    comp.get("title"),
                    comp["availability_tags"],
                )
            else:
                logger.info("  competence '%s' → no availability_time doc", comp.get("title"))

    # ── 4. Full Weaviate competency re-sync ───────────────────────────────────
    result = HubSpokeIngestion.update_competencies_by_user_id(user_id, all_competencies)
    if result.get("success"):
        logger.info(
            "Weaviate re-sync complete: %d competencies written.", result.get("count", 0)
        )
    else:
        logger.error("Weaviate re-sync failed: %s", result.get("error"))
        sys.exit(1)

    logger.info("Repair complete for user %s.", user_id)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/repair_weaviate_user.py <firebase_user_id>")
        sys.exit(1)

    asyncio.run(repair(sys.argv[1]))
