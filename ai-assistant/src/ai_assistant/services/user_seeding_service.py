import logging
import copy
from typing import Optional
from datetime import datetime, timezone

from ..firestore_service import FirestoreService
from ..seed_data import (
    USER_TEMPLATE, 
    USER_TEMPLATE_SERVICE_REQUESTS, 
    USER_TEMPLATE_COMPETENCIES, 
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
        user = {k: v for k, v in USER_TEMPLATE.items()}
        user['name'] = name
        user['email'] = email
        # Don't set created_at here - create_user handles timestamps
        if photo_url:
            user['photo_url'] = photo_url
        
        # Add user document in Firestore with the provided user_id and template data
        await self.firestore_service.create_user(user_id, user)
        
        # Get Weaviate UUID for syncing competencies
        weaviate_uuid = self._get_weaviate_user_uuid(user_id)
        
        # 1b. Add User Availability Times Subcollection
        for avail_time in USER_TEMPLATE_AVAILABILITY_TIMES:
            avail_doc = {
                'monday_time_ranges': avail_time.get('monday_time_ranges', []),
                'tuesday_time_ranges': avail_time.get('tuesday_time_ranges', []),
                'wednesday_time_ranges': avail_time.get('wednesday_time_ranges', []),
                'thursday_time_ranges': avail_time.get('thursday_time_ranges', []),
                'friday_time_ranges': avail_time.get('friday_time_ranges', []),
                'saturday_time_ranges': avail_time.get('saturday_time_ranges', []),
                'sunday_time_ranges': avail_time.get('sunday_time_ranges', []),
                'absence_days': avail_time.get('absence_days', []),
            }
            availability_time_id = await self.firestore_service.create_availability_time(user_id, avail_doc)
            if availability_time_id:
                logger.info(f"Created availability time {availability_time_id} for user {user_id}")
        
        # 1c. Add Competencies Subcollection
        for comp in USER_TEMPLATE_COMPETENCIES:
            comp_doc = {
                'title': comp.get('title', ''),
                'description': comp.get('description', ''),
                'category': comp.get('category', ''),
                'price_range': comp.get('price_range', ''),
                'year_of_experience': comp.get('year_of_experience', 0),
                'feedback_positive': comp.get('feedback_positive', []),
                'feedback_negative': comp.get('feedback_negative', []),
            }
            comp_result = await self.firestore_service.create_competence(user_id, comp_doc)
            if not comp_result:
                continue
            competence_id = comp_result.get('id')
            
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
            comp_key = f"competence_{{uid}}_{USER_TEMPLATE_COMPETENCIES.index(comp) + 1}"
            if comp_key in COMPETENCE_AVAILABILITY_TIMES:
                for comp_avail_time in COMPETENCE_AVAILABILITY_TIMES[comp_key]:
                    comp_avail_doc = {
                        'monday_time_ranges': comp_avail_time.get('monday_time_ranges', []),
                        'tuesday_time_ranges': comp_avail_time.get('tuesday_time_ranges', []),
                        'wednesday_time_ranges': comp_avail_time.get('wednesday_time_ranges', []),
                        'thursday_time_ranges': comp_avail_time.get('thursday_time_ranges', []),
                        'friday_time_ranges': comp_avail_time.get('friday_time_ranges', []),
                        'saturday_time_ranges': comp_avail_time.get('saturday_time_ranges', []),
                        'sunday_time_ranges': comp_avail_time.get('sunday_time_ranges', []),
                        'absence_days': comp_avail_time.get('absence_days', []),
                    }
                    comp_avail_id = await self.firestore_service.create_availability_time(
                        user_id, comp_avail_doc, competence_id=competence_id
                    )
                    if comp_avail_id:
                        logger.info(f"Created competence availability time {comp_avail_id} for competence {competence_id}")
        
        # 2. Create Sample Requests
        service_requests = USER_TEMPLATE_SERVICE_REQUESTS
        # Track which requests belong to which users for updating their open request arrays
        user_outgoing_requests = {}  # seeker_user_id -> [request_ids]
        user_incoming_requests = {}  # provider_user_id -> [request_ids]
        
        for idx, req in enumerate(service_requests):
            # Create a deep copy to modify
            req_data = copy.deepcopy(req)
            
            # Replace {uid} in seeker_user_id and selected_provider_user_id
            if "seeker_user_id" in req_data and "{uid}" in req_data["seeker_user_id"]:
                req_data["seeker_user_id"] = req_data["seeker_user_id"].format(uid=user_id)
            if "selected_provider_user_id" in req_data and "{uid}" in req_data["selected_provider_user_id"]:
                req_data["selected_provider_user_id"] = req_data["selected_provider_user_id"].format(uid=user_id)
            
            # Track the request for updating user open request arrays
            seeker_id = req_data.get("seeker_user_id")
            provider_id = req_data.get("selected_provider_user_id")
            
            try:
                # Create service request using service layer
                req_id = await self.firestore_service.create_service_request(req_data)
                if not req_id:
                    logger.error(f"Failed to create service request")
                    continue
                    
                logger.info(f"Created seed request: {req_id}")
                
                # Track for user arrays
                if seeker_id:
                    if seeker_id not in user_outgoing_requests:
                        user_outgoing_requests[seeker_id] = []
                    user_outgoing_requests[seeker_id].append(req_id)
                
                if provider_id:
                    if provider_id not in user_incoming_requests:
                        user_incoming_requests[provider_id] = []
                    user_incoming_requests[provider_id].append(req_id)
                
                # 2b. Add Provider Candidates as Subcollection
                if idx < len(USER_TEMPLATE_PROVIDER_CANDIDATES):
                    candidates = USER_TEMPLATE_PROVIDER_CANDIDATES[idx]
                    for candidate in candidates:
                        candidate_data = copy.deepcopy(candidate)
                        candidate_data["service_request_id"] = req_id
                        
                        if "{uid}" in candidate_data.get("provider_candidate_user_id", ""):
                            candidate_data["provider_candidate_user_id"] = candidate_data["provider_candidate_user_id"].format(uid=user_id)
                        
                        # Create provider candidate using service layer
                        candidate_id = await self.firestore_service.create_provider_candidate(
                            req_id, candidate_data
                        )
                        if candidate_id:
                            logger.info(f"Created provider candidate: {candidate_id} for request {req_id}")
                        
            except Exception as e:
                logger.error(f"Failed to seed request: {e}")

        # 2c. Update user documents with open incoming/outgoing service request arrays
        for user_id_to_update, outgoing_req_ids in user_outgoing_requests.items():
            try:
                success = await self.firestore_service.add_outgoing_service_requests(
                    user_id_to_update, outgoing_req_ids
                )
                if success:
                    logger.info(f"Updated user {user_id_to_update} with {len(outgoing_req_ids)} outgoing requests")
            except Exception as e:
                logger.error(f"Failed to update outgoing requests for user {user_id_to_update}: {e}")
        
        for user_id_to_update, incoming_req_ids in user_incoming_requests.items():
            try:
                success = await self.firestore_service.add_incoming_service_requests(
                    user_id_to_update, incoming_req_ids
                )
                if success:
                    logger.info(f"Updated user {user_id_to_update} with {len(incoming_req_ids)} incoming requests")
            except Exception as e:
                logger.error(f"Failed to update incoming requests for user {user_id_to_update}: {e}")

        # 3. Add Default Friend (Alice)
        # Ensure Alice exists first
        user_a_id = USER_A.get("id", "user_alice_001")
        try:
            # No need to filter out 'id' - update_user handles it internally
            await self.firestore_service.update_user(user_a_id, USER_A)
            
            # Add to user's favorites
            # Pass only the user_id, not the full dict
            await self.firestore_service.add_favorite(user_id, user_a_id)
            logger.info(f"Added default favorite {user_a_id} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to seed favorites for {user_id}: {e}")
            
        logger.info(f"Seeding complete for user {user_id}")
