#!/usr/bin/env python3
"""
Initialize Database (Firestore + Weaviate)
==========================================

This script initializes the Fides Platform databases with the Hub and Spoke schema.
It handles:
1. Firestore: Cleans collections and loads relational test data based on the defined schema.
2. Weaviate: Cleans schema/data and loads vector test data.

Collections initialized:
- Firestore: users, requests, reviews, chat_sessions
- Weaviate: UnifiedProfile, CompetenceEntry

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
import datetime
from datetime import timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Map custom env var to standard GOOGLE_APPLICATION_CREDENTIALS if not set
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")

# Google Cloud / Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
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
        # Use default credentials (GOOGLE_APPLICATION_CREDENTIALS)
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    except Exception as e:
        logger.warning(f"Could not initialize Firebase with ApplicationDefault: {e}")
        logger.warning("Attempting to initialize without credentials (for emulators or pre-configured env)...")
        firebase_admin.initialize_app()

try:
    db = firestore.client()
except Exception as e:
    logger.error(f"Failed to create Firestore client: {e}")
    db = None


def get_test_data():
    """Import test data dynamically."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests'))
    try:
        from test_hub_spoke_data import TEST_PERSONAS
        return TEST_PERSONAS
    except ImportError:
        logger.error("Could not import TEST_PERSONAS from tests/test_hub_spoke_data.py")
        return []


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


def datetime_from_days_ago(days):
    """Convert days ago integer to Firestore Timestamp (datetime)."""
    return datetime.datetime.now(timezone.utc) - datetime.timedelta(days=days)


def init_firestore(test_personas):
    """Initialize Firestore with schema and test data."""
    if not db:
        logger.error("Firestore client is not active. Skipping Firestore initialization.")
        return

    logger.info("Initializing Firestore...")
    
    # Collections to clean based on Diagram
    collections = ['users', 'requests', 'reviews', 'chat_sessions']
    
    # 1. Cleanup
    for coll_name in collections:
        logger.info(f"  Cleaning Firestore collection: {coll_name}")
        clean_firestore_collection(db.collection(coll_name))

    if not test_personas:
        logger.warning("  No test data provided. Firestore cleaned but empty.")
        return

    # 2. Populate Users & Competencies
    logger.info("  Populating Users and Competencies...")
    
    batch = db.batch()
    
    for persona in test_personas:
        p_data = persona['profile']
        c_data_list = persona['competences']
        
        user_id = p_data['user_id']
        user_ref = db.collection('users').document(user_id)
        
        # Transform profile data to match User schema
        user_doc = {
            'id': user_id,
            'name': p_data['name'],
            'email': p_data['email'],
            'introduction': f"I am {p_data['name']}, a professional on Fides.", # Placeholder
            'is_service_provider': p_data.get('is_service_provider', False),
            'fcm_token': p_data.get('fcm_token', ''),
            # 'competencies' is an Array of strings (titles) for quick access in the User object
            'competencies': [c['title'] for c in c_data_list],
            'favorites': [],
            'last_active': datetime_from_days_ago(p_data.get('last_active_date', 0)),
            'rating': 5.0, # Default start rating
            'review_count': 0,
            'positive_feedback': [],
            'negative_feedback': []
        }
        
        batch.set(user_ref, user_doc)
        
    batch.commit()
    logger.info("  ✓ User documents created")
    
    # Add Competencies Subcollection (Separate loop to avoid large batches)
    for persona in test_personas:
        user_id = persona['profile']['user_id']
        c_data_list = persona['competences']
        
        for i, comp in enumerate(c_data_list):
            comp_id = f"{user_id}_comp_{i+1}"
            # Subcollection 'competencies' under 'users'
            comp_ref = db.collection('users').document(user_id).collection('competencies').document(comp_id)
            
            comp_doc = {
                'id': comp_id,
                'title': comp['title'],
                'description': comp.get('description', ''),
                'price_range': comp.get('price_range', ''),
                'experience_years': 5, # Dummy data
                'certification': 'Certified Pro' # Dummy data
            }
            comp_ref.set(comp_doc)
            
    logger.info("  ✓ Competencies subcollections created")

    # 3. Create Dummy Service Request
    # Scenario: User E (Enthusiast/Seeker) asks User A (Pro)
    # Using 'requests' collection name to match previous code, Diagram says SERVICE_REQUEST but usually maps to lowercase plural in Firestore
    req_collection_name = 'requests' 
    req_id = "req_test_001"
    req_ref = db.collection(req_collection_name).document(req_id)
    req_doc = {
        'id': req_id,
        'seeker_user_id': "user_eva_005",
        'provider_user_id': "user_alice_001",
        'title': "Pot Light Installation",
        'price': 150.0,
        'description': "I need 5 pot lights installed in my living room. High ceilings.",
        'competencies': ["Installing Pot Lights"],
        'status': 'pending',
        'created_at': datetime.datetime.now(timezone.utc)
    }
    req_ref.set(req_doc)
    logger.info(f"  ✓ Dummy Service Request created in '{req_collection_name}'")
    
    # 4. Create Dummy Chat Session
    # Scenario: User E talks to AI
    chat_id = "chat_test_001"
    chat_ref = db.collection('chat_sessions').document(chat_id)
    chat_doc = {
        'id': chat_id,
        'session_id': chat_id,
        'sender_user_id': "user_eva_005",
        'receiver_user_id': "AI_ASSISTANT", 
        'title': "Pot Light Inquiry",
        'time': int(datetime.datetime.now(timezone.utc).timestamp() * 1000),
        'message': "Can you find someone to help with pot lights?"
    }
    chat_ref.set(chat_doc)
    logger.info("  ✓ Dummy Chat Session created")
    
    # 5. Create Dummy Review
    # Scenario: User A reviewed User E (maybe for a past job)
    review_id = "rev_test_001"
    review_ref = db.collection('reviews').document(review_id)
    review_doc = {
        'id': review_id,
        'request_id': "req_past_000",
        'provider_id': "user_alice_001",
        'reviewer_id': "user_eva_005",
        'rating': 5,
        'positive_feedback': ["Punctual", "Professional"],
        'negative_feedback': []
    }
    review_ref.set(review_doc)
    logger.info("  ✓ Dummy Review created")


def load_weaviate_data(test_personas):
    """Load test personas into Weaviate."""
    logger.info("Loading Weaviate data...")
    
    for persona in test_personas:
        logger.info(f"  Processing {persona['name']}")
        result = HubSpokeIngestion.create_profile_with_competences(
            profile_data=persona['profile'],
            competences_data=persona['competences'],
            apply_sanitization=True,
            apply_enrichment=True
        )
        if result:
            logger.info(f"    ✓ Profile UUID: {result['profile_uuid']}")
            logger.info(f"    ✓ Competences: {len(result['competence_uuids'])}")
        else:
            logger.error(f"    ✗ Failed to create {persona['name']}")


def main():
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
    test_personas = get_test_data()
    
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
                 for c in ['users', 'requests', 'reviews', 'chat_sessions']:
                     clean_firestore_collection(db.collection(c))
             logger.info("✓ Firestore collections cleaned")
        else:
            # Clean and Populate
            if args.load_test_data and test_personas:
                init_firestore(test_personas)
                
                # Load Weaviate Data as well if requested
                logger.info("\n[Phase 3] Loading Vector Data (Weaviate)")
                logger.info("-" * 30)
                load_weaviate_data(test_personas)
            elif not args.load_test_data:
                 init_firestore([]) # Just clean if no data requested
                 logger.info("✓ Firestore cleaned (no data loaded)")

        logger.info("\n" + "=" * 80)
        logger.info("✓ Initialization Complete")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Close Weaviate connection
        HubSpokeConnection.close()


if __name__ == '__main__':
    sys.exit(main())
