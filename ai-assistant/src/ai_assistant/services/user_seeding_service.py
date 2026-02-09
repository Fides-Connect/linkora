import logging
import copy
from typing import Optional
from datetime import datetime, timezone

from ..firestore_service import FirestoreService
from ..seed_data import (
    USER_TEMPLATE, 
    USER_TEMPLATE_SERVICE_REQUESTS, 
    USER_TEMPLATE_COMPETENCES, 
    USER_TEMPLATE_PROVIDER_CANDIDATES,
    USER_TEMPLATE_AVAILABILITY_TIMES,
    COMPETENCE_AVAILABILITY_TIMES,
    USER_A
)

# Weaviate imports
from ..hub_spoke_ingestion import HubSpokeIngestion
from ..hub_spoke_schema import get_user_collection
from weaviate.classes.query import Filter

logger = logging.getLogger(__name__)

class UserSeedingService:
    """Service to auto-seed data for new users."""

    def __init__(self, firestore_service: FirestoreService):
        self.firestore_service = firestore_service

    def _get_weaviate_user_uuid(self, user_id: str) -> Optional[str]:
        """Helper to get Weaviate UUID for a user."""
        try:
            coll = get_user_collection()
            res = coll.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )
            if res.objects:
                return str(res.objects[0].uuid)
        except Exception as e:
            logger.error(f"Failed to fetch Weaviate UUID for {user_id}: {e}")
        return None

    async def seed_new_user(self, user_id: str, name: str, email: str, photo_url: str = ""):
        """Seed initial data for a new user if not already present."""
        if not self.firestore_service.db:
            logger.warning("Firestore not initialized, skipping seeding.")
            return

        logger.info(f"Seeding data for new user: {user_id} ({name})")
        
        # 1. Update User with Template Defaults (intro, competencies, feedback)
        user_update = {k: v for k, v in USER_TEMPLATE.items()}
        user_update['user_id'] = user_id
        user_update['created_at'] = datetime.now(timezone.utc)
        if photo_url:
            user_update['photo_url'] = photo_url
        
        # We use the existing update_user_user method which does a set with merge=True
        await self.firestore_service.update_user(user_id, user_update)
        
        # Get Weaviate UUID for syncing competencies
        weaviate_uuid = self._get_weaviate_user_uuid(user_id)
        
        # 1b. Add User Availability Times Subcollection
        for avail_time in USER_TEMPLATE_AVAILABILITY_TIMES:
            # Generate prefixed availability_time ID
            availability_time_id = self.firestore_service._generate_prefixed_id('availability_time')
            avail_ref = self.firestore_service.db.collection('users').document(user_id).collection('availability_time').document(availability_time_id)
            
            avail_doc = {
                'availability_time_id': availability_time_id,
                'monday_time_ranges': avail_time.get('monday_time_ranges', []),
                'tuesday_time_ranges': avail_time.get('tuesday_time_ranges', []),
                'wednesday_time_ranges': avail_time.get('wednesday_time_ranges', []),
                'thursday_time_ranges': avail_time.get('thursday_time_ranges', []),
                'friday_time_ranges': avail_time.get('friday_time_ranges', []),
                'saturday_time_ranges': avail_time.get('saturday_time_ranges', []),
                'sunday_time_ranges': avail_time.get('sunday_time_ranges', []),
                'absence_days': avail_time.get('absence_days', []),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
            }
            avail_ref.set(avail_doc)
            logger.info(f"Created availability time {availability_time_id} for user {user_id}")
        
        # 1c. Add Competencies Subcollection
        for comp in USER_TEMPLATE_COMPETENCES:
            # Generate prefixed competence ID
            competence_id = self.firestore_service._generate_prefixed_id('competence')
            comp_ref = self.firestore_service.db.collection('users').document(user_id).collection('competencies').document(competence_id)
            
            comp_doc = {
                'competence_id': competence_id,
                'title': comp.get('title', ''),
                'description': comp.get('description', ''),
                'category': comp.get('category', ''),
                'price_range': comp.get('price_range', ''),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
            }
            comp_ref.set(comp_doc)
            
            # Sync to Weaviate
            if weaviate_uuid:
                try:
                    comp_data_weaviate = {
                        "competence_id": competence_id,
                        "title": comp_doc['title'],
                        "description": comp_doc['description'],
                        "category": comp_doc['category'],
                        "price_range": comp_doc['price_range']
                    }
                    HubSpokeIngestion.create_competence(comp_data_weaviate, weaviate_uuid)
                except Exception as e:
                    logger.error(f"Failed to sync seeded competence {competence_id} to Weaviate: {e}")
            
            # 1d. Add Competence Availability Times if available
            comp_key = f"{{uid}}_comp_{USER_TEMPLATE_COMPETENCES.index(comp) + 1}"
            if comp_key in COMPETENCE_AVAILABILITY_TIMES:
                for comp_avail_time in COMPETENCE_AVAILABILITY_TIMES[comp_key]:
                    comp_avail_id = self.firestore_service._generate_prefixed_id('availability_time')
                    comp_avail_ref = self.firestore_service.db.collection('users').document(user_id).collection('competencies').document(competence_id).collection('availability_time').document(comp_avail_id)
                    
                    comp_avail_doc = {
                        'availability_time_id': comp_avail_id,
                        'monday_time_ranges': comp_avail_time.get('monday_time_ranges', []),
                        'tuesday_time_ranges': comp_avail_time.get('tuesday_time_ranges', []),
                        'wednesday_time_ranges': comp_avail_time.get('wednesday_time_ranges', []),
                        'thursday_time_ranges': comp_avail_time.get('thursday_time_ranges', []),
                        'friday_time_ranges': comp_avail_time.get('friday_time_ranges', []),
                        'saturday_time_ranges': comp_avail_time.get('saturday_time_ranges', []),
                        'sunday_time_ranges': comp_avail_time.get('sunday_time_ranges', []),
                        'absence_days': comp_avail_time.get('absence_days', []),
                        'created_at': datetime.now(timezone.utc),
                        'updated_at': datetime.now(timezone.utc),
                    }
                    comp_avail_ref.set(comp_avail_doc)
                    logger.info(f"Created competence availability time {comp_avail_id} for competence {competence_id}")
        
        # 2. Create Sample Requests
        service_requests = USER_TEMPLATE_SERVICE_REQUESTS
        for idx, req in enumerate(service_requests):
            # Create a deep copy to modify
            req_data = copy.deepcopy(req)
            
            # Generate prefixed service request ID
            req_id = self.firestore_service._generate_prefixed_id('service_request')
            req_data["service_request_id"] = req_id
            
            # Replace {uid} in seeker_user_id and selected_provider_user_id
            if "seeker_user_id" in req_data and "{uid}" in req_data["seeker_user_id"]:
                req_data["seeker_user_id"] = req_data["seeker_user_id"].format(uid=user_id)
            if "selected_provider_user_id" in req_data and "{uid}" in req_data["selected_provider_user_id"]:
                req_data["selected_provider_user_id"] = req_data["selected_provider_user_id"].format(uid=user_id)
            
            # Add timestamps
            req_data['created_at'] = datetime.now(timezone.utc)
            req_data['updated_at'] = datetime.now(timezone.utc)
            
            try:
                requests_ref = self.firestore_service.db.collection('service_requests') # access public prop
                requests_ref.document(req_id).set(req_data, merge=True)
                logger.info(f"Created seed request: {req_id}")
                
                # 2b. Add Provider Candidates as Subcollection
                if idx < len(USER_TEMPLATE_PROVIDER_CANDIDATES):
                    candidates = USER_TEMPLATE_PROVIDER_CANDIDATES[idx]
                    for candidate in candidates:
                        candidate_data = copy.deepcopy(candidate)
                        
                        # Generate prefixed provider candidate ID
                        candidate_id = self.firestore_service._generate_prefixed_id('provider_candidate')
                        candidate_data["provider_candidate_id"] = candidate_id
                        candidate_data["service_request_id"] = req_id
                        
                        if "{uid}" in candidate_data.get("provider_candidate_user_id", ""):
                            candidate_data["provider_candidate_user_id"] = candidate_data["provider_candidate_user_id"].format(uid=user_id)
                        
                        # Store in provider_candidates subcollection using candidate_id as document ID
                        candidate_ref = requests_ref.document(req_id).collection('provider_candidates').document(candidate_id)
                        candidate_ref.set(candidate_data)
                        logger.info(f"Created provider candidate: {candidate_id} for request {req_id}")
                        
            except Exception as e:
                logger.error(f"Failed to seed request {req_id}: {e}")

        # 3. Add Default Friend (Alice)
        # Ensure Alice exists first
        user_a_id = USER_A["user_id"]
        try:
            alice_user_data = {k:v for k,v in USER_A.items() if k != "favorites"}
            await self.firestore_service.update_user(user_a_id, alice_user_data)
            
            # Add to user's favorites
            # Pass only the user_id, not the full dict
            await self.firestore_service.add_favorite(user_id, user_a_id)
            logger.info(f"Added default favorite {user_a_id} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to seed favorites for {user_id}: {e}")
            
        logger.info(f"Seeding complete for user {user_id}")
