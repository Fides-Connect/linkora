import logging
import copy
from datetime import datetime, UTC
from typing import Any, cast

from ..firestore_service import FirestoreService
from ..seed_data import (
    USER_TEMPLATE,
    USER_TEMPLATE_SERVICE_REQUESTS,
    USER_TEMPLATE_COMPETENCIES,
    USER_TEMPLATE_PROVIDER_CANDIDATES,
    USER_TEMPLATE_CHATS,
    USER_TEMPLATE_CHAT_MESSAGES,
    USER_TEMPLATE_REVIEWS,
    USER_TEMPLATE_AVAILABILITY_TIMES,
    COMPETENCE_AVAILABILITY_TIMES,
    USER_A
)

# Weaviate imports
from ..hub_spoke_ingestion import HubSpokeIngestion

logger = logging.getLogger(__name__)

class UserSeedingService:
    """Service to auto-seed data for new users."""

    def __init__(self, firestore_service: FirestoreService) -> None:
        self.firestore_service = firestore_service

    async def seed_new_user(self, user_id: str, name: str, email: str, photo_url: str = "", enricher: Any | None = None) -> None:
        """Seed initial data for a new user if not already present."""
        if not self.firestore_service.db:
            logger.warning("Firestore not initialized, skipping seeding.")
            return

        logger.info("Seeding data for new user: %s (%s)", user_id, name)

        # 1. Update User with Template Defaults (intro, competencies, feedback)
        user = {k: v for k, v in USER_TEMPLATE.items()}
        user['name'] = name
        user['email'] = email
        # Don't set created_at here - create_user handles timestamps
        if photo_url:
            user['photo_url'] = photo_url

        # Add user document in Firestore with the provided user_id and template data
        await self.firestore_service.create_user(user_id, user)

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
                logger.info("Created availability time %s for user %s", availability_time_id, user_id)

        # 1c. Add Competencies Subcollection in Firestore and collect data for Weaviate
        competencies_for_weaviate = []
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
            competence_id = comp_result.get('competence_id')
            if competence_id is None:
                continue

            # Enrich competency with LLM if enricher is available
            enriched_doc = dict(comp_doc)
            if enricher is not None:
                try:
                    enriched_doc = await enricher.enrich(comp_doc)
                    # Persist enriched fields back to Firestore so future
                    # --sync-to-weaviate rebuilds retain the quality summary.
                    enrich_update = {
                        k: enriched_doc[k]
                        for k in ("search_optimized_summary", "skills_list", "price_per_hour")
                        if k in enriched_doc and enriched_doc.get(k)
                    }
                    if enrich_update:
                        await self.firestore_service.update_competence(user_id, competence_id, enrich_update)
                        logger.info("Enriched competency %r for user %s", competence_id, user_id)
                except Exception as e:
                    logger.warning("Enrichment failed for competency %r: %s", competence_id, e)

            # Collect competency data for Weaviate sync
            comp_data_weaviate = {
                "competence_id": competence_id,
                "title": enriched_doc.get('title', comp_doc['title']),
                "description": enriched_doc.get('description', comp_doc['description']),
                "category": enriched_doc.get('category', comp_doc['category']),
                "price_range": enriched_doc.get('price_range', comp_doc['price_range']),
                "search_optimized_summary": enriched_doc.get('search_optimized_summary', ''),
                "skills_list": enriched_doc.get('skills_list', []),
            }
            competencies_for_weaviate.append(comp_data_weaviate)

            # 1d. Add Competence Availability Times if available
            comp_key = f"competence_{{uid}}_{USER_TEMPLATE_COMPETENCIES.index(comp) + 1}"
            if comp_key in COMPETENCE_AVAILABILITY_TIMES:
                for comp_avail_time in cast(list, COMPETENCE_AVAILABILITY_TIMES[comp_key]):
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
                        logger.info("Created competence availability time %s for competence %s", comp_avail_id, competence_id)

        # 1e. Sync user and competencies to Weaviate using HubSpokeIngestion
        try:
            # HubSpokeIngestion.create_user expects 'user_id' field
            user_data_for_weaviate = {**user, 'user_id': user_id, 'created_at': datetime.now(UTC)}
            result = HubSpokeIngestion.create_user_with_competencies(
                user_data=user_data_for_weaviate,
                competencies_data=competencies_for_weaviate,
                apply_sanitization=True,
                apply_enrichment=True
            )
            if result:
                logger.info("✓ Synced user %s to Weaviate with %s competencies", user_id, len(result['competence_uuids']))
            else:
                logger.error("Failed to sync user %s to Weaviate", user_id)
        except Exception as e:
            logger.error("Failed to sync user %s to Weaviate: %s", user_id, e)

        # 2. Create Sample Requests
        service_requests = USER_TEMPLATE_SERVICE_REQUESTS
        # Track which requests belong to which users for updating their open request arrays
        user_outgoing_requests: dict[str, Any] = {}  # seeker_user_id -> [request_ids]
        user_incoming_requests: dict[str, Any] = {}  # provider_user_id -> [request_ids]
        # Track created service request IDs and provider candidate IDs for chat creation
        created_request_ids = []  # List of created service request IDs
        created_provider_candidate_ids = []  # List of lists: [[req0_cand_ids], [req1_cand_ids], ...]

        for idx, req in enumerate(service_requests):
            # Create a deep copy to modify
            req_data = copy.deepcopy(req)

            # Replace {uid} in seeker_user_id and selected_provider_user_id
            if "seeker_user_id" in req_data and "{uid}" in cast(str, req_data["seeker_user_id"]):
                req_data["seeker_user_id"] = cast(str, req_data["seeker_user_id"]).format(uid=user_id)
            if "selected_provider_user_id" in req_data and "{uid}" in cast(str, req_data["selected_provider_user_id"]):
                req_data["selected_provider_user_id"] = cast(str, req_data["selected_provider_user_id"]).format(uid=user_id)

            # Track the request for updating user open request arrays
            seeker_id = cast(str, req_data.get("seeker_user_id"))
            provider_id = cast(str, req_data.get("selected_provider_user_id"))

            try:
                # Create service request using service layer
                req_result = await self.firestore_service.create_service_request(req_data)
                if not req_result:
                    logger.error("Failed to create service request")
                    continue

                # Extract the service_request_id from the result
                req_id = req_result.get('service_request_id')
                if not req_id:
                    logger.error("Service request created but missing service_request_id")
                    continue

                logger.info("Created seed request: %s", req_id)

                # Track the created request ID
                created_request_ids.append(req_id)

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
                request_candidate_ids = []  # Track candidates for this specific request
                if idx < len(USER_TEMPLATE_PROVIDER_CANDIDATES):
                    candidates = USER_TEMPLATE_PROVIDER_CANDIDATES[idx]
                    for candidate in candidates:
                        candidate_data = copy.deepcopy(candidate)
                        candidate_data["service_request_id"] = req_id

                        _candidate_uid = cast(str, candidate_data.get("provider_candidate_user_id", ""))
                        if "{uid}" in _candidate_uid:
                            candidate_data["provider_candidate_user_id"] = _candidate_uid.format(uid=user_id)

                        # Create provider candidate using service layer
                        candidate_result = await self.firestore_service.create_provider_candidate(
                            req_id, candidate_data
                        )
                        if candidate_result:
                            candidate_id = candidate_result.get('candidate_id')
                            if candidate_id:
                                logger.info("Created provider candidate: %s for request %s", candidate_id, req_id)
                                request_candidate_ids.append(candidate_id)
                            else:
                                logger.error("Provider candidate created but missing candidate_id")
                        else:
                            logger.error("Failed to create provider candidate for request %s", req_id)

                # Store the candidate IDs for this request (even if empty list)
                created_provider_candidate_ids.append(request_candidate_ids)

            except Exception as e:
                logger.error("Failed to seed request: %s", e)

        # 2c. Update user documents with open incoming/outgoing service request arrays
        for user_id_to_update, outgoing_req_ids in user_outgoing_requests.items():
            try:
                success = await self.firestore_service.add_outgoing_service_requests(
                    user_id_to_update, outgoing_req_ids
                )
                if success:
                    logger.info("Updated user %s with %s outgoing requests", user_id_to_update, len(outgoing_req_ids))
            except Exception as e:
                logger.error("Failed to update outgoing requests for user %s: %s", user_id_to_update, e)

        for user_id_to_update, incoming_req_ids in user_incoming_requests.items():
            try:
                success = await self.firestore_service.add_incoming_service_requests(
                    user_id_to_update, incoming_req_ids
                )
                if success:
                    logger.info("Updated user %s with %s incoming requests", user_id_to_update, len(incoming_req_ids))
            except Exception as e:
                logger.error("Failed to update incoming requests for user %s: %s", user_id_to_update, e)

        # 3. Create Sample Chats and Messages
        for chat_idx, chat_template in enumerate(USER_TEMPLATE_CHATS):
            try:
                # Get the request index from the template
                req_idx = chat_template.get("request_index")
                if req_idx is None or not isinstance(req_idx, int) or req_idx >= len(created_request_ids):
                    logger.warning("Skipping chat %s: invalid request index %s", chat_idx, req_idx)
                    continue

                # Get the service request ID and provider candidate ID
                service_request_id = created_request_ids[req_idx]

                # Get the first provider candidate for this request (usually the selected one)
                if req_idx < len(created_provider_candidate_ids) and created_provider_candidate_ids[req_idx]:
                    provider_candidate_id = created_provider_candidate_ids[req_idx][0]
                else:
                    logger.warning("Skipping chat %s: no provider candidates found for request %s", chat_idx, req_idx)
                    continue

                # Prepare chat data
                _seeker = cast(str, chat_template["seeker_user_id"])
                _provider_user = cast(str, chat_template["provider_user_id"])
                chat_data = {
                    "service_request_id": service_request_id,
                    "provider_candidate_id": provider_candidate_id,
                    "seeker_user_id": _seeker.format(uid=user_id) if "{uid}" in _seeker else _seeker,
                    "provider_user_id": _provider_user.format(uid=user_id) if "{uid}" in _provider_user else _provider_user,
                    "title": chat_template["title"],
                }

                # Create chat using service layer
                chat_result = await self.firestore_service.create_chat(chat_data)
                if not chat_result:
                    logger.error("Failed to create chat for request %s", service_request_id)
                    continue

                chat_id = chat_result.get('chat_id')
                if not chat_id:
                    logger.error("Chat created but missing chat_id for request %s", service_request_id)
                    continue
                logger.info("Created seed chat: %s", chat_id)

                # 3b. Add Chat Messages as Subcollection
                if chat_idx < len(USER_TEMPLATE_CHAT_MESSAGES):
                    messages = USER_TEMPLATE_CHAT_MESSAGES[chat_idx]
                    for msg_template in messages:
                        msg_data = copy.deepcopy(msg_template)
                        msg_data["chat_id"] = chat_id

                        # Replace {uid} placeholders in sender and receiver
                        if "{uid}" in cast(str, msg_data["sender_user_id"]):
                            msg_data["sender_user_id"] = cast(str, msg_data["sender_user_id"]).format(uid=user_id)
                        if "{uid}" in cast(str, msg_data["receiver_user_id"]):
                            msg_data["receiver_user_id"] = cast(str, msg_data["receiver_user_id"]).format(uid=user_id)

                        # Create chat message using service layer
                        msg_result = await self.firestore_service.create_chat_message(chat_id, msg_data)
                        if msg_result:
                            msg_id = msg_result.get('chat_message_id')
                            logger.info("Created chat message: %s for chat %s", msg_id, chat_id)
                        else:
                            logger.error("Failed to create chat message for chat %s", chat_id)

            except Exception as e:
                logger.error("Failed to seed chat %s: %s", chat_idx, e)

        # 4. Add Default Reviews
        for review_template in USER_TEMPLATE_REVIEWS:
            try:
                review_data = copy.deepcopy(review_template)

                # Get the service request ID from the request_index
                request_index = cast(int, review_data.pop("request_index"))
                if request_index < len(created_request_ids):
                    service_request_id = created_request_ids[request_index]
                    review_data["service_request_id"] = service_request_id

                    # Replace {uid} placeholders
                    if "{uid}" in cast(str, review_data["user_id"]):
                        review_data["user_id"] = cast(str, review_data["user_id"]).format(uid=user_id)

                    # Create review using service layer
                    review_result = await self.firestore_service.create_review(review_data)
                    if review_result:
                        review_id = review_result.get('review_id')
                        logger.info("Created seed review: %s for request %s", review_id, service_request_id)
                    else:
                        logger.error("Failed to create review for request %s", service_request_id)
                else:
                    logger.error("Request index %s out of range for reviews", request_index)

            except Exception as e:
                logger.error("Failed to seed review: %s", e)

        # 5. Add Default Friend (Alice)
        # Ensure Alice exists first
        user_a_id = cast(str, USER_A.get("id", "user_alice_001"))
        try:
            # No need to filter out 'id' - update_user handles it internally
            await self.firestore_service.update_user(user_a_id, USER_A)

            # Add to user's favorites
            # Pass only the user_id, not the full dict
            await self.firestore_service.add_favorite(user_id, user_a_id)
            logger.info("Added default favorite %s for user %s", user_a_id, user_id)

        except Exception as e:
            logger.error("Failed to seed favorites for %s: %s", user_id, e)

        logger.info("Seeding complete for user %s", user_id)
