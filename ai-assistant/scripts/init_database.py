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
from datetime import datetime, timezone, timedelta
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
    try:
        from ai_assistant import seed_data
        return {
            'personas': seed_data.TEST_PERSONAS,
            'service_requests': getattr(seed_data, 'TEST_SERVICE_REQUESTS', []),
            'provider_candidates': getattr(seed_data, 'TEST_PROVIDER_CANDIDATES', []),
            'chats': getattr(seed_data, 'TEST_CHATS', []),
            'chat_messages': getattr(seed_data, 'TEST_CHAT_MESSAGES', []),
            'reviews': getattr(seed_data, 'TEST_REVIEWS', [])
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

def init_firestore(test_data):
    """Initialize Firestore with schema and test data."""
    if not db:
        logger.error("Firestore client is not active. Skipping Firestore initialization.")
        return

    logger.info("Initializing Firestore...")
    
    # Collections to clean based on Diagram
    collections = ['users', 'service_requests', 'reviews', 'chat_sessions', 'chats']
    
    # 1. Cleanup
    for coll_name in collections:
        logger.info(f"  Cleaning Firestore collection: {coll_name}")
        clean_firestore_collection(db.collection(coll_name))

    test_personas = test_data.get('personas', [])
    if not test_personas:
        logger.warning("  No test personas provided. Firestore users/competencies skipped.")
    else:
        # 2. Populate Users & Competencies
        logger.info("  Populating Users and Competencies...")
        
        batch = db.batch()
        
        for persona in test_personas:
            p_data = persona['user']
            
            user_id = p_data['user_id']
            user_ref = db.collection('users').document(user_id)
            
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
            user_doc = {
                'user_id': user_id,
                'name': p_data['name'],
                'email': p_data['email'],
                'photo_url': p_data.get('photo_url', ''),
                'location': p_data.get('location', ''),
                'self_introduction': p_data['self_introduction'],
                'is_service_provider': p_data.get('is_service_provider', False),
                'fcm_token': p_data.get('fcm_token', ''),
                'has_open_request': p_data.get('has_open_request', False),
                'favorites': p_data.get('favorites', []),
                'user_app_settings': p_data.get('user_app_settings', {}),
                'open_incoming_service_requests': p_data.get('open_incoming_service_requests', []),
                'open_outgoing_service_requests': p_data.get('open_outgoing_service_requests', []),
                'last_sign_in': last_sign_in,
                'feedback_positive': p_data.get('feedback_positive', []),
                'feedback_negative': p_data.get('feedback_negative', []),
                'average_rating': p_data.get('average_rating', 5.0),
                'review_count': p_data.get('review_count', 0),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
            }
            
            batch.set(user_ref, user_doc)
            
        batch.commit()
        logger.info("  ✓ User documents created")
        
        # Add Competencies Subcollection (Separate loop to avoid large batches)
        for persona in test_personas:
            user_id = persona['user']['user_id']
            c_data_list = persona['competencies']
            
            for i, comp in enumerate(c_data_list):
                comp_id = f"{user_id}_comp_{i+1}"
                # Subcollection 'competencies' under 'users'
                comp_ref = db.collection('users').document(user_id).collection('competencies').document(comp_id)
                
                comp_doc = {
                    'competence_id': comp_id,
                    'user_id': user_id,
                    'title': comp['title'],
                    'description': comp.get('description', ''),
                    'category': comp.get('category', ''),
                    'price_range': comp.get('price_range', ''),
                    'year_of_experience': comp.get('year_of_experience', 0),
                    'feedback_positive': comp.get('feedback_positive', []),
                    'feedback_negative': comp.get('feedback_negative', []),
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc),
                }
                comp_ref.set(comp_doc)
                
        logger.info("  ✓ Competencies subcollections created")
        
        # Add Availability Times Subcollection for Users
        for persona in test_personas:
            user_id = persona['user']['user_id']
            avail_times = persona.get('availability_times', [])
            
            for avail in avail_times:
                avail_id = avail.get('availability_time_id', f"avail_{user_id}_auto")
                avail_ref = db.collection('users').document(user_id).collection('availability_time').document(avail_id)
                
                avail_doc = {
                    'availability_time_id': avail_id,
                    'user_id': user_id,
                    'monday_time_ranges': avail.get('monday_time_ranges', []),
                    'tuesday_time_ranges': avail.get('tuesday_time_ranges', []),
                    'wednesday_time_ranges': avail.get('wednesday_time_ranges', []),
                    'thursday_time_ranges': avail.get('thursday_time_ranges', []),
                    'friday_time_ranges': avail.get('friday_time_ranges', []),
                    'saturday_time_ranges': avail.get('saturday_time_ranges', []),
                    'sunday_time_ranges': avail.get('sunday_time_ranges', []),
                    'absence_days': avail.get('absence_days', []),
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc),
                }
                avail_ref.set(avail_doc)
                
        logger.info("  ✓ User availability_time subcollections created")
        
        # Add Availability Times for specific competencies
        from ai_assistant.seed_data import COMPETENCE_AVAILABILITY_TIMES
        for comp_id, avail_times in COMPETENCE_AVAILABILITY_TIMES.items():
            # Skip template entries with {uid} placeholder (for seeding service only)
            if '{uid}' in comp_id:
                continue
                
            # Extract user_id from comp_id (format: user_xxx_comp_N)
            user_id = '_'.join(comp_id.split('_')[:-2])
            
            for avail in avail_times:
                avail_id = avail.get('availability_time_id', f"avail_{comp_id}_auto")
                avail_ref = (db.collection('users').document(user_id)
                           .collection('competencies').document(comp_id)
                           .collection('availability_time').document(avail_id))
                
                avail_doc = {
                    'availability_time_id': avail_id,
                    'monday_time_ranges': avail.get('monday_time_ranges', []),
                    'tuesday_time_ranges': avail.get('tuesday_time_ranges', []),
                    'wednesday_time_ranges': avail.get('wednesday_time_ranges', []),
                    'thursday_time_ranges': avail.get('thursday_time_ranges', []),
                    'friday_time_ranges': avail.get('friday_time_ranges', []),
                    'saturday_time_ranges': avail.get('saturday_time_ranges', []),
                    'sunday_time_ranges': avail.get('sunday_time_ranges', []),
                    'absence_days': avail.get('absence_days', []),
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc),
                }
                avail_ref.set(avail_doc)
                
        logger.info("  ✓ Competence availability_time subcollections created")

    # 3. Create Service Requests
    requests = test_data.get('service_requests', [])
    # Track which requests belong to which users for updating their open request arrays
    user_outgoing_requests = {}  # seeker_user_id -> [request_ids]
    user_incoming_requests = {}  # provider_user_id -> [request_ids]
    
    if requests:
        for req in requests:
            req_collection_name = 'service_requests'
            req_id = req.get('service_request_id', 'unknown_req')
            req_ref = db.collection(req_collection_name).document(req_id)
            
            # Track the request for updating user open request arrays
            seeker_id = req.get('seeker_user_id')
            provider_id = req.get('selected_provider_user_id')
            
            if seeker_id:
                if seeker_id not in user_outgoing_requests:
                    user_outgoing_requests[seeker_id] = []
                user_outgoing_requests[seeker_id].append(req_id)
            
            if provider_id:
                if provider_id not in user_incoming_requests:
                    user_incoming_requests[provider_id] = []
                user_incoming_requests[provider_id].append(req_id)
            
            # Add dynamic timestamps if missing
            if 'created_at' not in req:
                req['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in req:
                req['updated_at'] = datetime.now(timezone.utc)
                
            req_ref.set(req)
        logger.info(f"  ✓ {len(requests)} Service Requests created")
    
    # 3c. Update user documents with open incoming/outgoing service request arrays
    for user_id, outgoing_req_ids in user_outgoing_requests.items():
        user_ref = db.collection('users').document(user_id)
        user_ref.set({'open_outgoing_service_requests': outgoing_req_ids}, merge=True)
        logger.info(f"  ✓ Updated user {user_id} with {len(outgoing_req_ids)} outgoing requests")
    
    for user_id, incoming_req_ids in user_incoming_requests.items():
        user_ref = db.collection('users').document(user_id)
        user_ref.set({'open_incoming_service_requests': incoming_req_ids}, merge=True)
        logger.info(f"  ✓ Updated user {user_id} with {len(incoming_req_ids)} incoming requests")
    
    # 3b. Create Provider Candidates as subcollections
    provider_candidates = test_data.get('provider_candidates', [])
    if provider_candidates:
        for candidate in provider_candidates:
            req_id = candidate.get('service_request_id')
            cand_id = candidate.get('provider_candidate_id', 'unknown_candidate')
            
            if not req_id:
                continue
                
            cand_ref = db.collection('service_requests').document(req_id).collection('provider_candidates').document(cand_id)
            
            # Add dynamic timestamps if missing
            if 'created_at' not in candidate:
                candidate['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in candidate:
                candidate['updated_at'] = datetime.now(timezone.utc)
                
            cand_ref.set(candidate)
        logger.info(f"  ✓ {len(provider_candidates)} Provider Candidates created")
    
    # 4. Create Chat Sessions and Messages as subcollections under provider_candidates
    chats = test_data.get('chats', [])
    messages = test_data.get('chat_messages', [])
    
    if chats:
        for chat in chats:
            chat_id = chat.get('chat_id', 'unknown_chat')
            req_id = chat.get('service_request_id')
            cand_id = chat.get('provider_candidate_id')
            
            # Skip chats without proper hierarchy (general inquiries)
            if not req_id or not cand_id:
                logger.warning(f"Skipping chat {chat_id}: missing service_request_id or provider_candidate_id")
                continue
            
            # Chat is a subcollection under provider_candidate
            chat_ref = (db.collection('service_requests').document(req_id)
                       .collection('provider_candidates').document(cand_id)
                       .collection('chats').document(chat_id))
            
            # Add dynamic timestamps if missing
            if 'created_at' not in chat:
                chat['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in chat:
                chat['updated_at'] = datetime.now(timezone.utc)
                
            chat_ref.set(chat)
        logger.info(f"  ✓ {len(chats)} Chat Sessions created")
        
        # Add messages to subcollections
        if messages:
            count = 0
            for msg in messages:
                chat_id = msg.get('chat_id')
                if not chat_id:
                    continue
                
                # Find the chat to get its request_id and provider_candidate_id
                chat_data = next((c for c in chats if c.get('chat_id') == chat_id), None)
                if not chat_data:
                    logger.warning(f"No chat found for message in chat {chat_id}")
                    continue
                    
                req_id = chat_data.get('service_request_id')
                cand_id = chat_data.get('provider_candidate_id')
                
                if not req_id or not cand_id:
                    logger.warning(f"Skipping message in chat {chat_id}: missing hierarchy info")
                    continue
                    
                msg_id = msg.get('chat_message_id', f'msg_{count}')
                # Subcollection 'messages' under 'chats' document
                msg_ref = (db.collection('service_requests').document(req_id)
                          .collection('provider_candidates').document(cand_id)
                          .collection('chats').document(chat_id)
                          .collection('messages').document(msg_id))
                
                # Add dynamic timestamps if missing
                if 'created_at' not in msg:
                    msg['created_at'] = datetime.now(timezone.utc)
                if 'updated_at' not in msg:
                    msg['updated_at'] = datetime.now(timezone.utc)
                
                msg_ref.set(msg)
                count += 1
            logger.info(f"  ✓ {count} Chat Messages created")
    
    # 5. Create Reviews
    reviews = test_data.get('reviews', [])
    if reviews:
        for rev in reviews:
            rev_id = rev.get('review_id', 'unknown_rev')
            rev_ref = db.collection('reviews').document(rev_id)
            
            # Add dynamic timestamps if missing
            if 'created_at' not in rev:
                rev['created_at'] = datetime.now(timezone.utc)
            if 'updated_at' not in rev:
                rev['updated_at'] = datetime.now(timezone.utc)
            
            rev_ref.set(rev)
        logger.info(f"  ✓ {len(reviews)} Reviews created")


def load_weaviate_data(test_personas):
    """Load test personas into Weaviate."""
    logger.info("Loading Weaviate data...")
    
    for persona in test_personas:
        logger.info(f"  Processing {persona['name']}")
        
        # Inject competence_id to match Firestore logic
        user_id = persona['user']['user_id']
        competencies_data = persona['competencies']
        
        # We must iterate to inject IDs, replicating init_firestore logic:
        # comp_id = f"{user_id}_comp_{i+1}"
        for i, comp in enumerate(competencies_data):
            # Check if updated in place or if we need copy - safe to update in place for script
            comp['competence_id'] = f"{user_id}_comp_{i+1}"
            
        result = HubSpokeIngestion.add_user_with_competencies(
            user_data=persona['user'],
            competencies_data=competencies_data,
            apply_sanitization=True,
            apply_enrichment=True
        )
        if result:
            logger.info(f"    ✓ User UUID: {result['user_uuid']}")
            logger.info(f"    ✓ Competencies: {len(result['competence_uuids'])}")
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
                 for c in ['users', 'service_requests', 'reviews', 'chat_sessions', 'chats']:
                     clean_firestore_collection(db.collection(c))
             logger.info("✓ Firestore collections cleaned")
        else:
            # Clean and Populate
            if args.load_test_data and test_personas:
                init_firestore(test_data)
                
                # Load Weaviate Data as well if requested
                logger.info("\n[Phase 3] Loading Vector Data (Weaviate)")
                logger.info("-" * 30)
                load_weaviate_data(test_personas)
            elif not args.load_test_data:
                 # Create empty structure by passing empty dict
                 init_firestore({}) 
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
