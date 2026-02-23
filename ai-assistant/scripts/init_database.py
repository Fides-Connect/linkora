#!/usr/bin/env python3
"""
Initialize Database (Firestore + Weaviate)
==========================================

This script initializes the Fides Platform databases with the Hub and Spoke schema.
It handles:
1. Firestore: Cleans collections and loads relational test data based on the defined schema.
2. Weaviate: Cleans schema/data and loads vector test data.

Collections initialized:
- Firestore: users, requests, reviews, chat, chat_messages
- Weaviate: User, Competence

Usage:
    python scripts/init_database.py [--load-test-data]
    
Options:
    --load-test-data    Load test personas after initialization
    --clean-only        Only clean up databases without creating new data
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
from ai_assistant.hub_spoke_ingestion import HubSpokeIngestion
from ai_assistant.firestore_service import FirestoreService

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
    
    Args:
        test_personas: List of persona dictionaries
    """
    logger.info("Loading Weaviate data...")
    
    for i, persona in enumerate(test_personas):
        persona_name = persona.get('name', f'Persona {i}')
        logger.info(f"  Processing {persona_name}")
        
        # Get user_id from persona data
        user_id = persona['user'].get('user_id')
        if not user_id:
            logger.warning(f"Skipping Weaviate ingestion for {persona_name}: missing 'user_id' field")
            continue
            
        competencies_data = persona['competencies']
        
        # We must iterate to inject IDs, replicating init_firestore logic:
        # comp_id = f"competence_{user_id}_{i+1}"
        for j, comp in enumerate(competencies_data):
            # Check if updated in place or if we need copy - safe to update in place for script
            comp['competence_id'] = f"competence_{user_id}_{j+1}"
        
        # HubSpokeIngestion expects 'user_id' field
        user_data_for_weaviate = {**persona['user'], 'user_id': user_id}
        
        result = HubSpokeIngestion.create_user_with_competencies(
            user_data=user_data_for_weaviate,
            competencies_data=competencies_data,
            apply_sanitization=True,
            apply_enrichment=True
        )
        if result:
            logger.info(f"    ✓ User UUID: {result['user_uuid']}")
            logger.info(f"    ✓ Competencies: {len(result['competence_uuids'])}")
        else:
            logger.error(f"    ✗ Failed to create {persona_name}")


async def main():
    parser = argparse.ArgumentParser(
        description='Initialize Fides Database (Firestore + Weaviate)'
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
    
    args = parser.parse_args()
    test_data = get_test_data()
    test_personas = test_data.get('personas', [])
    
    try:
        logger.info("=" * 80)
        logger.info("Fides Database Initialization")
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
                
                # Load Weaviate Data as well if requested
                logger.info("\n[Phase 3] Loading Vector Data (Weaviate)")
                logger.info("-" * 30)
                load_weaviate_data(test_personas)
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
