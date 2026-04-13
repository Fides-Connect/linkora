#!/usr/bin/env python3
"""
Initialize Database (Firestore + Weaviate)
==========================================

This script initializes the Linkora Platform databases with the Hub and Spoke schema.
It handles:
1. Firestore: Cleans collections and loads relational test data based on the defined schema.
2. Weaviate: Cleans schema/data and loads vector test data.

Collections initialized:
- Firestore: users, requests, reviews, chat, chat_messages
- Weaviate: User, Competence

Usage:
    python scripts/init_database.py [--load-test-data]
    python scripts/init_database.py --sync-to-weaviate [--force]
    
Options:
    --load-test-data      Wipe and replace all data with test personas
    --clean-only          Delete all data from Firestore and Weaviate
    --sync-to-weaviate    Read all users + competencies from Firestore and
                          rebuild the Weaviate index from scratch.
                          Target instance is controlled by env vars:
                            Local:  WEAVIATE_URL (default http://localhost:8090)
                            Cloud:  WEAVIATE_CLUSTER_URL + WEAVIATE_API_KEY
    --force               Skip confirmation prompts for any destructive operation
    --add-service-request Add a single lawn mowing service request to Firestore.
                          Requires --seeker-user-id and --provider-user-id.
"""
import os
import sys
import argparse
import logging
import asyncio
import traceback
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Google Cloud / Firebase imports
try:
    import firebase_admin
    from firebase_admin import firestore
except ImportError:
    print("Error: firebase-admin module not found. Install it with: pip install firebase-admin")
    sys.exit(1)

# Weaviate / Internal imports
# Ensure we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from ai_assistant.hub_spoke_schema import (
    init_hub_spoke_schema,
    cleanup_hub_spoke_schema,
    HubSpokeConnection
)
from ai_assistant.firestore_service import FirestoreService
from ai_assistant.weaviate_sync import ingest_users_into_weaviate, rebuild_weaviate_from_firestore
from ai_assistant.seed_data import get_lawn_mowing_service_request
from ai_assistant.services.notification_service import notify_new_service_request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Initialize Firebase App
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
    except Exception as e:
        logger.error(
            "Failed to initialize Firebase app. This script requires Firestore access.\n"
            "Verify that one of the following is correctly configured:\n"
            "  - Application Default Credentials are set up (run `gcloud auth application-default login`),\n"
            "  - GOOGLE_APPLICATION_CREDENTIALS points to a valid service account JSON,\n"
            "  - or FIRESTORE_EMULATOR_HOST is set if you are using the Firestore emulator.\n"
            f"Underlying error: {e}"
        )
        raise SystemExit(1)

try:
    # Use the database specified in FIRESTORE_DATABASE_NAME env var, or default
    database_id = os.getenv('FIRESTORE_DATABASE_NAME', '(default)')
    db = firestore.client(database_id=database_id)
    firestore_service = FirestoreService()
    logger.info(f"Firestore client initialized with database: {database_id}")
except Exception as e:
    logger.error(f"Failed to create Firestore client: {e}")
    db = None
    firestore_service = None


def get_test_data():
    """Import test data dynamically."""
    try:
        from ai_assistant import seed_data
        return {
            'personas': seed_data.TEST_PERSONAS,
            # Service requests, provider candidates, chats, and reviews removed
            'service_requests': [],
            'provider_candidates': [],
            'chats': [],
            'chat_messages': [],
            'reviews': []
        }
    except ImportError as e:
        logger.error(f"Could not import test data from ai_assistant.seed_data: {e}")
        return {'personas': [], 'service_requests': [], 'provider_candidates': [], 'chats': [], 'reviews': []}


def clean_firestore_collection(coll_ref, batch_size=50):
    """Recursively delete a collection and its subcollections."""
    docs = list(coll_ref.limit(batch_size).stream())
    deleted = 0
    
    if len(docs) > 0:
        batch = db.batch()
        for doc in docs:
            # Recursively delete subcollections
            for subcoll in doc.reference.collections():
                clean_firestore_collection(subcoll, batch_size)
            batch.delete(doc.reference)
        batch.commit()
        deleted = len(docs)
        
        # Recurse if there are more
        if deleted >= batch_size:
            clean_firestore_collection(coll_ref, batch_size)


async def init_firestore(test_data):
    """Initialize Firestore with schema and test data."""
    if not db or not firestore_service:
        logger.error("Firestore client is not active. Skipping Firestore initialization.")
        return

    logger.info("Initializing Firestore...")
    
    # Collections to clean based on Diagram
    collections = ['users', 'service_requests', 'reviews', 'chats']
    
    # 1. Cleanup
    for coll_name in collections:
        logger.info(f"  Cleaning Firestore collection: {coll_name}")
        clean_firestore_collection(db.collection(coll_name))

    test_personas = test_data.get('personas', [])
    if not test_personas:
        logger.warning("  No test personas provided. Firestore users/competencies skipped.")
        return
    
    # 2. Populate Users & Competencies using firestore_service
    logger.info("  Populating Users and Competencies...")
    
    for i, persona in enumerate(test_personas):
        p_data = persona['user']
        persona_name = persona.get('name', f'Persona {i}')
        user_id = p_data.get('user_id')
        
        if not user_id:
            logger.error(f"Skipping {persona_name}: missing 'user_id' field in persona data")
            continue
        
        # Convert last_sign_in from relative (days) to absolute datetime if needed
        last_sign_in = p_data.get('last_sign_in', 0)
        if isinstance(last_sign_in, int):
            # Convert days ago to absolute datetime
            last_sign_in = datetime.now(timezone.utc) - timedelta(days=last_sign_in)
        elif isinstance(last_sign_in, str):
            # Parse ISO format string if provided
            try:
                last_sign_in = datetime.fromisoformat(last_sign_in.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                last_sign_in = datetime.now(timezone.utc)
        elif not isinstance(last_sign_in, datetime):
            last_sign_in = datetime.now(timezone.utc)
        
        # Transform user data to match User schema
        user_data = {
            'name': p_data['name'],
            'email': p_data['email'],
            'photo_url': p_data.get('photo_url', ''),
            'location': p_data.get('location', ''),
            'self_introduction': p_data['self_introduction'],
            'is_service_provider': p_data.get('is_service_provider', False),
            'fcm_token': p_data.get('fcm_token', ''),
            'has_open_request': p_data.get('has_open_request', False),
            'user_app_settings': p_data.get('user_app_settings', {}),
            'last_sign_in': last_sign_in,
            'feedback_positive': p_data.get('feedback_positive', []),
            'feedback_negative': p_data.get('feedback_negative', []),
            'average_rating': p_data.get('average_rating', 5.0),
            'review_count': p_data.get('review_count', 0),
        }
        
        # Create user with the ID from persona data
        success = await firestore_service.create_user(user_id=user_id, user_data=user_data)
        if not success:
            logger.error(f"Failed to create user {persona_name}")
            continue
        
        logger.info(f"  Created user: {persona_name} -> {user_id}")
        
        # Create favorites subcollection
        favorites = p_data.get('favorites', [])
        if favorites:
            for fav_id in favorites:
                await firestore_service.add_favorite(user_id, fav_id)
        
        # Create outgoing service requests subcollection
        outgoing = p_data.get('outgoing_service_requests', [])
        if outgoing:
            await firestore_service.add_outgoing_service_requests(user_id, outgoing)
        
        # Create incoming service requests subcollection
        incoming = p_data.get('incoming_service_requests', [])
        if incoming:
            await firestore_service.add_incoming_service_requests(user_id, incoming)
    
    logger.info("  ✓ User documents created")
    
    # Add Competencies Subcollection
    for i, persona in enumerate(test_personas):
        persona_name = persona.get('name', f'Persona {i}')
        user_id = persona['user'].get('user_id')
        if not user_id:
            logger.warning(f"Skipping competencies for {persona_name}: missing 'user_id' field")
            continue
            
        c_data_list = persona['competencies']
        
        for j, comp in enumerate(c_data_list):
            comp_id = f"competence_{user_id}_{j+1}"
            
            # Remove competence_id from data - it's the document ID, not stored data
            comp_data = {
                'title': comp['title'],
                'description': comp.get('description', ''),
                'category': comp.get('category', ''),
                'price_range': comp.get('price_range', ''),
                'year_of_experience': comp.get('year_of_experience', 0),
                'feedback_positive': comp.get('feedback_positive', []),
                'feedback_negative': comp.get('feedback_negative', []),
            }
            
            # Create competence via firestore_service manually (need to set specific ID)
            # Since create_competence generates IDs, we'll write directly but through validation
            competencies_ref = db.collection('users').document(user_id).collection('competencies')
            
            # Validate using Pydantic schema
            from ai_assistant.firestore_schemas import CompetenceSchema
            try:
                validated = CompetenceSchema(**comp_data)
                validated_dict = validated.model_dump(mode='python', exclude_none=False)
                competencies_ref.document(comp_id).set(validated_dict)
            except Exception as e:
                logger.error(f"Failed to create competence {comp_id}: {e}")
                continue
    
    logger.info("  ✓ Competencies subcollections created")
    
    # Add Availability Times Subcollection for Users
    for i, persona in enumerate(test_personas):
        persona_name = persona.get('name', f'Persona {i}')
        user_id = persona['user'].get('user_id')
        if not user_id:
            logger.warning(f"Skipping availability times for {persona_name}: missing 'user_id' field")
            continue
            
        avail_times = persona.get('availability_times', [])
        
        for j, avail in enumerate(avail_times):
            avail_id = f"availability_time_{user_id}_{j+1}"
            
            # Remove ID fields - they are document IDs, not stored data
            avail_data = {
                'monday_time_ranges': avail.get('monday_time_ranges', []),
                'tuesday_time_ranges': avail.get('tuesday_time_ranges', []),
                'wednesday_time_ranges': avail.get('wednesday_time_ranges', []),
                'thursday_time_ranges': avail.get('thursday_time_ranges', []),
                'friday_time_ranges': avail.get('friday_time_ranges', []),
                'saturday_time_ranges': avail.get('saturday_time_ranges', []),
                'sunday_time_ranges': avail.get('sunday_time_ranges', []),
                'absence_days': avail.get('absence_days', []),
            }
            
            # Validate using Pydantic schema
            from ai_assistant.firestore_schemas import AvailabilityTimeSchema
            try:
                validated = AvailabilityTimeSchema(**avail_data)
                validated_dict = validated.model_dump(mode='python', exclude_none=False)
                validated_dict['created_at'] = datetime.now(timezone.utc)
                validated_dict['updated_at'] = datetime.now(timezone.utc)
                
                avail_ref = db.collection('users').document(user_id).collection('availability_time').document(avail_id)
                avail_ref.set(validated_dict)
            except Exception as e:
                logger.error(f"Failed to create availability time {avail_id}: {e}")
                continue
    
    logger.info("  ✓ User availability_time subcollections created")
    
    # Add Availability Times for specific competencies
    from ai_assistant.seed_data import COMPETENCE_AVAILABILITY_TIMES
    for comp_id, avail_times in COMPETENCE_AVAILABILITY_TIMES.items():
        # Skip template entries with {uid} placeholder (for seeding service only)
        if '{uid}' in comp_id:
            continue
            
        # Extract user_id from comp_id (format: competence_user_xxx_N)
        user_id = '_'.join(comp_id.split('_')[1:-1])
        
        for j, avail in enumerate(avail_times):
            avail_id = f"availability_time_{comp_id}_{j+1}"
            
            # Remove ID fields - they are document IDs, not stored data
            avail_data = {
                'monday_time_ranges': avail.get('monday_time_ranges', []),
                'tuesday_time_ranges': avail.get('tuesday_time_ranges', []),
                'wednesday_time_ranges': avail.get('wednesday_time_ranges', []),
                'thursday_time_ranges': avail.get('thursday_time_ranges', []),
                'friday_time_ranges': avail.get('friday_time_ranges', []),
                'saturday_time_ranges': avail.get('saturday_time_ranges', []),
                'sunday_time_ranges': avail.get('sunday_time_ranges', []),
                'absence_days': avail.get('absence_days', []),
            }
            
            # Validate using Pydantic schema
            from ai_assistant.firestore_schemas import AvailabilityTimeSchema
            try:
                validated = AvailabilityTimeSchema(**avail_data)
                validated_dict = validated.model_dump(mode='python', exclude_none=False)
                validated_dict['created_at'] = datetime.now(timezone.utc)
                validated_dict['updated_at'] = datetime.now(timezone.utc)
                
                avail_ref = (db.collection('users').document(user_id)
                           .collection('competencies').document(comp_id)
                           .collection('availability_time').document(avail_id))
                avail_ref.set(validated_dict)
            except Exception as e:
                logger.error(f"Failed to create competence availability time {avail_id}: {e}")
                continue
    
    logger.info("  ✓ Competence availability_time subcollections created")

    # Note: Service requests, provider candidates, chats, and reviews have been removed from test data
    



def load_weaviate_data(test_personas):
    """Load test personas into Weaviate.

    Builds a ``(user_data, competencies)`` payload from *test_personas* and
    delegates to :func:`~ai_assistant.weaviate_sync.ingest_users_into_weaviate`.

    Args:
        test_personas: List of persona dictionaries (as returned by
            :func:`get_test_data`).
    """
    logger.info("Loading Weaviate data...")

    users_payload = []
    for i, persona in enumerate(test_personas):
        persona_name = persona.get('name', f'Persona {i}')
        user_id = persona['user'].get('user_id')
        if not user_id:
            logger.warning(f"Skipping Weaviate ingestion for {persona_name}: missing 'user_id' field")
            continue

        competencies_data = persona['competencies']
        # Inject document IDs to match the IDs written by init_firestore.
        for j, comp in enumerate(competencies_data):
            comp['competence_id'] = f"competence_{user_id}_{j + 1}"

        user_data_for_weaviate = {**persona['user'], 'user_id': user_id}
        users_payload.append((user_data_for_weaviate, competencies_data))

    success_count, failure_count = ingest_users_into_weaviate(users_payload)
    logger.info(f"  ✓ {success_count} user(s) ingested, {failure_count} failure(s).")


def _confirm(prompt: str, force: bool) -> bool:
    """Print *prompt* and return True if the user confirms (or force=True)."""
    if force:
        return True
    try:
        answer = input(f"\n{prompt} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    return answer in ("y", "yes")


async def sync_firestore_to_weaviate(force: bool = False) -> int:
    """Read all users and competencies from Firestore and rebuild Weaviate from scratch.

    Args:
        force: If True, skip the interactive confirmation prompt.

    Returns:
        0 on success, 1 on failure.
    """
    if not db or not firestore_service:
        logger.error("Firestore client is not active. Cannot run sync.")
        return 1

    # Determine and display the target Weaviate instance so the user knows
    # exactly what will be wiped.
    cluster_url = os.getenv('WEAVIATE_CLUSTER_URL')
    weaviate_target = (
        f"Weaviate Cloud: {cluster_url}"
        if cluster_url
        else f"Local Weaviate: {os.getenv('WEAVIATE_URL', 'http://localhost:8090')}"
    )

    logger.info("=" * 80)
    logger.info("Firestore → Weaviate Sync")
    logger.info("=" * 80)
    logger.info(f"  Target : {weaviate_target}")
    logger.info("  Action : ALL existing Weaviate data will be deleted and replaced")
    logger.info("           with the current users/competencies from Firestore.")

    if not _confirm(
        "ALL existing Weaviate data will be deleted and replaced with Firestore data. Continue?",
        force=force,
    ):
        logger.info("Sync cancelled.")
        return 0

    try:
        result = await rebuild_weaviate_from_firestore()
    except Exception as e:
        logger.error(f"  ✗ Weaviate schema rebuild failed: {e}")
        return 1

    logger.info("\n" + "=" * 80)
    logger.info("Sync Summary")
    logger.info("=" * 80)
    logger.info(f"  Target        : {weaviate_target}")
    logger.info(f"  Users synced  : {result.success_count} / {result.total_users}")
    logger.info(f"  Failures      : {result.failure_count}")
    success = result.failure_count == 0 and result.total_users > 0
    if result.total_users == 0 and result.failure_count > 0:
        logger.warning("  ⚠ Firestore could not be read. No data was synced to Weaviate.")
    elif result.total_users == 0:
        logger.warning("  ⚠ No users found in Firestore. No data was synced to Weaviate.")
    elif result.failure_count == 0:
        logger.info("  ✓ Sync completed successfully.")
    else:
        logger.warning("  ⚠ Sync completed with errors — check logs above.")

    return 0 if success else 1


async def main():
    parser = argparse.ArgumentParser(
        description='Initialize Linkora Database (Firestore + Weaviate)'
    )
    parser.add_argument(
        '--load-test-data',
        action='store_true',
        help='Load test personas after schema initialization'
    )
    parser.add_argument(
        '--clean-only',
        action='store_true',
        help='Only clean up existing collections without creating new ones'
    )
    parser.add_argument(
        '--sync-to-weaviate',
        action='store_true',
        help=(
            'Read all users and competencies from Firestore and rebuild the '
            'Weaviate index from scratch. Target instance is controlled by '
            'WEAVIATE_URL (local) or WEAVIATE_CLUSTER_URL + WEAVIATE_API_KEY (cloud).'
        )
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts for any destructive operation (--clean-only, --load-test-data, --sync-to-weaviate)'
    )
    parser.add_argument(
        '--add-service-request',
        action='store_true',
        help='Add a single lawn mowing service request to Firestore. Requires --seeker-user-id and --provider-user-id.'
    )
    parser.add_argument(
        '--seeker-user-id',
        type=str,
        help='User ID of the service seeker (required with --add-service-request).'
    )
    parser.add_argument(
        '--provider-user-id',
        type=str,
        help='User ID of the selected service provider (required with --add-service-request).'
    )

    args = parser.parse_args()

    # ── Add single service request ──────────────────────────────────────────
    if args.add_service_request:
        if not args.seeker_user_id or not args.provider_user_id:
            logger.error(
                "--add-service-request requires both --seeker-user-id and --provider-user-id."
            )
            return 1
        if not firestore_service:
            logger.error("Firestore client is not active. Cannot create service request.")
            return 1
        request_data = get_lawn_mowing_service_request(
            seeker_user_id=args.seeker_user_id,
            selected_provider_user_id=args.provider_user_id,
        )
        result = await firestore_service.create_service_request(request_data)
        try:
            if result:
                service_request_id = result.get('service_request_id', '')
                logger.info(
                    f"✓ Service request created: {service_request_id} "
                    f"(seeker={args.seeker_user_id}, provider={args.provider_user_id})"
                )
                await notify_new_service_request(
                    provider_id=args.provider_user_id,
                    service_request_id=service_request_id,
                    category=request_data.get('category', ''),
                )
                return 0
            else:
                logger.error("✗ Failed to create service request.")
                return 1
        finally:
            HubSpokeConnection.close()

    # ── Sync path: independent of the normal init flow ─────────────────────
    if args.sync_to_weaviate:
        try:
            return await sync_firestore_to_weaviate(force=args.force)
        finally:
            HubSpokeConnection.close()

    # ── Confirmation prompts for destructive init operations ─────────────────
    if args.clean_only:
        if not _confirm(
            "--clean-only will DELETE all data from Firestore and Weaviate. Continue?",
            force=args.force,
        ):
            logger.info("Aborted.")
            return 0

    if args.load_test_data:
        if not _confirm(
            "--load-test-data will WIPE and REPLACE all Firestore + Weaviate data "
            "with test personas. Continue?",
            force=args.force,
        ):
            logger.info("Aborted.")
            return 0

    test_data = get_test_data()
    test_personas = test_data.get('personas', [])
    
    try:
        logger.info("=" * 80)
        logger.info("Linkora Database Initialization")
        logger.info("=" * 80)
        
        # --- Weaviate Operations ---
        logger.info("\n[Phase 1] Weaviate Initialization")
        logger.info("-" * 30)
        try:
            cleanup_hub_spoke_schema()
            logger.info("✓ Weaviate schema cleaned")
        except Exception as e:
            logger.warning(f"Weaviate cleanup warning: {e}")
            
        if not args.clean_only:
            init_hub_spoke_schema()
            logger.info("✓ Weaviate schema initialized (Hub & Spoke)")
        
        # --- Firestore Operations ---
        logger.info("\n[Phase 2] Firestore Initialization")
        logger.info("-" * 30)
        if args.clean_only:
             # Just clean firestore
             if db:
                 for c in ['users', 'service_requests', 'reviews', 'chats']:
                     clean_firestore_collection(db.collection(c))
             logger.info("✓ Firestore collections cleaned")
        else:
            # Clean and Populate
            if args.load_test_data and test_personas:
                await init_firestore(test_data)

                # Rebuild Weaviate from Firestore — includes all live accounts,
                # not just the static test personas loaded above.
                logger.info("\n[Phase 3] Loading Vector Data (Weaviate)")
                logger.info("-" * 30)
                result = await rebuild_weaviate_from_firestore()
                logger.info(
                    f"  ✓ {result.success_count} user(s) ingested, "
                    f"{result.failure_count} failure(s)."
                )
            elif not args.load_test_data:
                # Create empty structure by passing empty dict
                await init_firestore({}) 
                logger.info("✓ Firestore cleaned (no data loaded)")
                
        logger.info("\n" + "=" * 80)
        logger.info("✓ Database Initialization Complete")
        logger.info("=" * 80)
        return 0
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ Database Initialization Failed")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        traceback.print_exc()
        return 1
        
    finally:
        # Close Weaviate connection
        HubSpokeConnection.close()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
