import logging
import os
from typing import Any
from datetime import datetime, timedelta, UTC
from firebase_admin import firestore
from google.cloud.firestore_v1.base_collection import BaseCollectionReference
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.transforms import Increment
from pydantic import BaseModel, ValidationError

from .services.conversation_service import ConversationStage
from .firestore_schemas import (
    UserSchema,
    UserUpdateSchema,
    CompetenceSchema,
    CompetenceUpdateSchema,
    ServiceRequestSchema,
    ServiceRequestUpdateSchema,
    ReviewSchema,
    ReviewUpdateSchema,
    ChatSchema,
    ChatUpdateSchema,
    ChatMessageSchema,
    ChatMessageUpdateSchema,
    ProviderCandidateSchema,
    ProviderCandidateUpdateSchema,
    AvailabilityTimeSchema,
    AvailabilityTimeUpdateSchema,
    AIConversationSchema,
    AIConversationUpdateSchema,
    AIConversationMessageSchema,
)

logger = logging.getLogger(__name__)

class FirestoreService:
    """Service to interact with Firestore database."""

    def __init__(self) -> None:
        """Initialize Firestore client lazily."""
        self._db: Client | None = None

    @property
    def db(self) -> Client | None:
        if self._db is None:
            try:
                # Initialization should have happened in main.py
                # This call will work if the default app is initialized.
                # Use the database specified in FIRESTORE_DATABASE_NAME env var, or default
                database_id = os.getenv('FIRESTORE_DATABASE_NAME', '(default)')
                self._db = firestore.client(database_id=database_id)
                logger.info("Firestore client initialized with database: %s", database_id)
            except Exception as e:
                # If app is not initialized yet (e.g. during imports), log it but don't crash
                # It will retry on next access
                logger.debug("Firestore client not initialized (yet): %s", e)
                return None
        return self._db

    def _get_collection(self, collection_name: str) -> BaseCollectionReference:
        if self.db is None:
            raise RuntimeError("Firestore client is not initialized")
        return self.db.collection(collection_name)

    def _generate_prefixed_id(self, prefix: str) -> str:
        """Generate a Firestore auto-ID with a prefix.

        Args:
            prefix: The prefix to add (e.g., 'user', 'competence', 'service_request')

        Returns:
            A prefixed ID like 'user_abc123def456'
        """
        # Generate a Firestore-style auto ID
        assert self.db is not None
        doc_ref = self.db.collection('_temp').document()
        auto_id = doc_ref.id
        return f"{prefix}_{auto_id}"

    def _validate_data(
        self,
        data: dict[str, Any],
        schema_class: type[BaseModel],
        exclude_unset: bool = False,
    ) -> dict[str, Any]:
        """Validate data against a Pydantic schema.

        Args:
            data: The data to validate
            schema_class: The Pydantic model class to validate against
            exclude_unset: If True, only include fields that were explicitly set (for updates)

        Returns:
            Validated data as a dictionary

        Raises:
            ValidationError: If validation fails with detailed error messages
        """
        try:
            # Validate and convert to dict
            validated = schema_class(**data)
            # For updates (exclude_unset=True), only include explicitly set fields
            # For creates (exclude_unset=False), include all fields with defaults
            return validated.model_dump(
                mode='python',
                exclude_none=False,
                exclude_defaults=False,
                exclude_unset=exclude_unset
            )
        except ValidationError as e:
            logger.error("Validation error for %s: %s", schema_class.__name__, e)
            raise

    @staticmethod
    def _format_validation_errors(error: ValidationError) -> dict[str, str]:
        """Convert a Pydantic ValidationError into a flat {field: message} dict.

        The returned dict is intended to be included verbatim in a tool-call error
        result so that the LLM can self-correct without a re-prompt cycle.

        Example output::

            {
                "monday_time_ranges[0].end_time": "String should match pattern '^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'",
                "absence_days[0]": "absence_days entries must be ISO-8601 date strings (YYYY-MM-DD), got: '15-03-2026'",
            }
        """
        result: dict[str, str] = {}
        for err in error.errors():
            # Build a human-readable field path, e.g. "monday_time_ranges[0].end_time"
            parts = []
            for loc_part in err.get("loc", ()):
                if isinstance(loc_part, int):
                    if parts:
                        parts[-1] = f"{parts[-1]}[{loc_part}]"
                    else:
                        parts.append(f"[{loc_part}]")
                else:
                    parts.append(str(loc_part))
            field_path = ".".join(parts) if parts else "(unknown)"
            result[field_path] = err.get("msg", "invalid value")
        return result

    # --- Service Request Operations ---

    async def _enrich_service_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Enrich a service request with user names and initials.

        Args:
            request: The service request dict

        Returns:
            The enriched request dict
        """
        # Add seeker user info
        if 'seeker_user_id' in request:
            seeker = await self.get_user(request['seeker_user_id'])
            if seeker and 'name' in seeker:
                request['seeker_user_name'] = seeker['name']
                request['seeker_user_initials'] = "".join([n[0] for n in seeker['name'].split() if n]).upper()[:2]
            else:
                request['seeker_user_name'] = ''
                request['seeker_user_initials'] = ''

        # Add provider user info
        if request.get('selected_provider_user_id'):
            provider = await self.get_user(request['selected_provider_user_id'])
            if provider and 'name' in provider:
                request['selected_provider_user_name'] = provider['name']
                request['selected_provider_user_initials'] = "".join([n[0] for n in provider['name'].split() if n]).upper()[:2]
            else:
                request['selected_provider_user_name'] = ''
                request['selected_provider_user_initials'] = ''

        return request

    async def get_service_requests(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch incoming and outgoing service requests involving the user."""
        if not self.db:
            return []

        requests = []
        try:
            requests_ref = self._get_collection('service_requests')

            # Fetch requests where user is seeker or provider
            query1 = requests_ref.where(filter=FieldFilter("seeker_user_id", "==", user_id)).stream()
            for doc in query1:
                data = doc.to_dict()
                data['service_request_id'] = doc.id
                requests.append(data)

            query2 = requests_ref.where(filter=FieldFilter("selected_provider_user_id", "==", user_id)).stream()
            for doc in query2:
                data = doc.to_dict()
                data['service_request_id'] = doc.id
                # Avoid duplicates
                if not any(r['service_request_id'] == data['service_request_id'] for r in requests):
                    requests.append(data)

            # Enrich requests with user names and initials
            for i, req in enumerate(requests):
                requests[i] = await self._enrich_service_request(req)
            return requests

        except Exception as e:
            logger.error("Error fetching requests for user %s: %s", user_id, e)
            return []

    async def create_service_request(self, request_data: dict[str, Any]) -> dict[str, Any] | None:
        """Create a new service request.

        Returns:
            The created service request object with service_request_id, or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed service request ID
            service_request_id = self._generate_prefixed_id('service_request')

            # Add timestamps before validation (they will be validated as well)
            request_data['created_at'] = datetime.now(UTC)
            request_data['updated_at'] = datetime.now(UTC)

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(request_data, ServiceRequestSchema)

            # Create document with the prefixed ID
            ref = self._get_collection('service_requests').document(service_request_id)
            ref.set(validated_data)

            # Add to seeker's outgoing service requests
            seeker_user_id = validated_data.get('seeker_user_id')
            if seeker_user_id:
                await self.add_outgoing_service_requests(seeker_user_id, [service_request_id])

            # Add to provider's incoming service requests if provider is selected
            selected_provider_user_id = validated_data.get('selected_provider_user_id')
            if selected_provider_user_id:
                await self.add_incoming_service_requests(selected_provider_user_id, [service_request_id])

            # Return full object
            result = validated_data.copy()
            result['service_request_id'] = service_request_id
            return result
        except Exception as e:
            logger.error("Error creating request: %s", e)
            return None

    async def get_service_request(self, request_id: str) -> dict[str, Any] | None:
        """Fetch a single service request by ID."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('service_requests').document(request_id).get()
            if doc.exists:
                data = doc.to_dict()
                if data is None:
                    return None
                data['service_request_id'] = doc.id
                return await self._enrich_service_request(data)
            return None
        except Exception as e:
            logger.error("Error fetching request %s: %s", request_id, e)
            return None

    async def update_service_request_status(self, request_id: str, status: str) -> dict[str, Any] | None:
        """Update service request status.

        Returns:
            The full updated service request object, or None if failed
        """
        if not self.db:
            return None
        try:
            # Validate status value using the update schema
            update_data = {'status': status}
            validated_data = self._validate_data(update_data, ServiceRequestUpdateSchema, exclude_unset=True)

            ref = self._get_collection('service_requests').document(request_id)
            ref.update({
                'status': validated_data['status'],
                'updated_at': datetime.now(UTC)
            })

            # Fetch and return the updated object
            return await self.get_service_request(request_id)
        except Exception as e:
            logger.error("Error updating request status %s: %s", request_id, e)
            return None

    async def update_service_request(self, request_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a service request with full data.

        Args:
            request_id: The service request ID to update
            update_data: Data to update

        Returns:
            The full updated service request object, or None if failed
        """
        if not self.db:
            return None
        try:
            # Check if service request exists and get current data
            ref = self._get_collection('service_requests').document(request_id)
            doc = ref.get()
            if not doc.exists:
                logger.warning("Cannot update service request %s: service request does not exist", request_id)
                return None

            current_data = doc.to_dict() or {}
            old_provider_id = current_data.get('selected_provider_user_id', '')

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ServiceRequestUpdateSchema, exclude_unset=True)

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Check if selected_provider_user_id is being updated
            new_provider_id = validated_data.get('selected_provider_user_id')
            if new_provider_id is not None and new_provider_id != old_provider_id:
                # Remove from old provider's incoming list (if any)
                if old_provider_id:
                    await self.remove_incoming_service_requests(old_provider_id, [request_id])

                # Add to new provider's incoming list (if any)
                if new_provider_id:
                    await self.add_incoming_service_requests(new_provider_id, [request_id])

            # Update the document
            ref.update(validated_data)

            # Fetch and return the updated object
            return await self.get_service_request(request_id)
        except Exception as e:
            logger.error("Error updating service request %s: %s", request_id, e)
            return None

    async def delete_service_request(self, request_id: str) -> bool:
        """Delete a service request and all its subcollections, plus related chats from root collection.

        Args:
            request_id: The service request ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            service_request_ref = self._get_collection('service_requests').document(request_id)

            # Get the service request data to know which users to update
            doc = service_request_ref.get()
            if doc.exists:
                request_data = doc.to_dict() or {}
                seeker_user_id = request_data.get('seeker_user_id')
                selected_provider_user_id = request_data.get('selected_provider_user_id')

                # Remove from seeker's outgoing list
                if seeker_user_id:
                    await self.remove_outgoing_service_requests(seeker_user_id, [request_id])

                # Remove from provider's incoming list
                if selected_provider_user_id:
                    await self.remove_incoming_service_requests(selected_provider_user_id, [request_id])

            # Delete all chats related to this service request from root chats collection
            chats_query = self._get_collection('chats').where('service_request_id', '==', request_id)
            chats = chats_query.stream()
            for chat in chats:
                # Delete all messages in each chat
                messages_ref = chat.reference.collection('messages')
                messages = messages_ref.stream()
                for message in messages:
                    message.reference.delete()
                # Delete the chat
                chat.reference.delete()

            # Delete all provider_candidates subcollection
            providers_ref = service_request_ref.collection('provider_candidates')
            providers = providers_ref.stream()
            for provider in providers:
                provider.reference.delete()

            # Delete the service request document
            service_request_ref.delete()
            return True
        except Exception as e:
            logger.error("Error deleting service request %s: %s", request_id, e)
            return False

    # --- Provider Candidate Operations ---

    async def create_provider_candidate(
        self,
        service_request_id: str,
        candidate_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Create a new provider candidate for a service request.

        Args:
            service_request_id: The service request ID
            candidate_data: Provider candidate data

        Returns:
            The created provider candidate object with candidate_id, or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed provider candidate ID
            provider_candidate_id = self._generate_prefixed_id('provider_candidate')
            candidate_data['service_request_id'] = service_request_id

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(candidate_data, ProviderCandidateSchema)

            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(UTC)
            validated_data['updated_at'] = datetime.now(UTC)

            # Create document as subcollection under service_request
            ref = (self._get_collection('service_requests')
                  .document(service_request_id)
                  .collection('provider_candidates')
                  .document(provider_candidate_id))
            ref.set(validated_data)

            # Add service request to provider candidate's incoming list
            provider_user_id = validated_data.get('provider_candidate_user_id')
            if provider_user_id:
                await self.add_incoming_service_requests(provider_user_id, [service_request_id])

            # Return full object
            result = validated_data.copy()
            result['candidate_id'] = provider_candidate_id
            return result
        except Exception as e:
            logger.error("Error creating provider candidate for request %s: %s", service_request_id, e)
            return None

    async def get_provider_candidates(
        self,
        service_request_id: str
    ) -> list[dict[str, Any]]:
        """Fetch all provider candidates for a service request.

        Args:
            service_request_id: The service request ID

        Returns:
            List of provider candidate dictionaries
        """
        if not self.db:
            return []
        try:
            candidates_ref = (self._get_collection('service_requests')
                             .document(service_request_id)
                             .collection('provider_candidates'))
            docs = candidates_ref.stream()

            candidates = []
            for doc in docs:
                data = doc.to_dict()
                data['candidate_id'] = doc.id
                candidates.append(data)
            return candidates
        except Exception as e:
            logger.error("Error fetching provider candidates for request %s: %s", service_request_id, e)
            return []

    async def get_provider_candidate(
        self,
        service_request_id: str,
        provider_candidate_id: str
    ) -> dict[str, Any] | None:
        """Fetch a single provider candidate.

        Args:
            service_request_id: The service request ID
            provider_candidate_id: The provider candidate ID

        Returns:
            Provider candidate dictionary or None if not found
        """
        if not self.db:
            return None
        try:
            doc = (self._get_collection('service_requests')
                  .document(service_request_id)
                  .collection('provider_candidates')
                  .document(provider_candidate_id)
                  .get())
            if doc.exists:
                data = doc.to_dict()
                data['candidate_id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error("Error fetching provider candidate %s: %s", provider_candidate_id, e)
            return None

    async def update_provider_candidate(
        self,
        service_request_id: str,
        provider_candidate_id: str,
        update_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update a provider candidate.

        Args:
            service_request_id: The service request ID
            provider_candidate_id: The provider candidate ID
            update_data: Data to update

        Returns:
            Full updated provider candidate object, or None if failed
        """
        if not self.db:
            return None
        try:
            # Check if provider candidate exists and get current data
            ref = (self._get_collection('service_requests')
                  .document(service_request_id)
                  .collection('provider_candidates')
                  .document(provider_candidate_id))

            doc = ref.get()
            if not doc.exists:
                logger.warning("Cannot update provider candidate %s: does not exist", provider_candidate_id)
                return None

            current_data = doc.to_dict()
            old_provider_user_id = current_data.get('provider_candidate_user_id')

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(
                update_data,
                ProviderCandidateUpdateSchema,
                exclude_unset=True
            )

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Check if provider_candidate_user_id is being updated
            new_provider_user_id = validated_data.get('provider_candidate_user_id')
            if new_provider_user_id is not None and new_provider_user_id != old_provider_user_id:
                # Remove from old provider's incoming list (if not the selected provider)
                if old_provider_user_id:
                    service_request = await self.get_service_request(service_request_id)
                    if service_request and service_request.get('selected_provider_user_id') != old_provider_user_id:
                        await self.remove_incoming_service_requests(old_provider_user_id, [service_request_id])

                # Add to new provider's incoming list
                if new_provider_user_id:
                    await self.add_incoming_service_requests(new_provider_user_id, [service_request_id])

            # Update document
            ref.update(validated_data)
            return await self.get_provider_candidate(service_request_id, provider_candidate_id)
        except Exception as e:
            logger.error("Error updating provider candidate %s: %s", provider_candidate_id, e)
            return None

    async def delete_provider_candidate(
        self,
        service_request_id: str,
        provider_candidate_id: str
    ) -> bool:
        """Delete a provider candidate and related chats from root collection.

        Args:
            service_request_id: The service request ID
            provider_candidate_id: The provider candidate ID

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            candidate_ref = (self._get_collection('service_requests')
                            .document(service_request_id)
                            .collection('provider_candidates')
                            .document(provider_candidate_id))

            # Get the provider candidate data to know which user to update
            doc = candidate_ref.get()
            if doc.exists:
                candidate_data = doc.to_dict()
                provider_user_id = candidate_data.get('provider_candidate_user_id')

                # Remove from provider's incoming list only if they're not the selected provider
                if provider_user_id:
                    service_request = await self.get_service_request(service_request_id)
                    if service_request and service_request.get('selected_provider_user_id') != provider_user_id:
                        await self.remove_incoming_service_requests(provider_user_id, [service_request_id])

            # Delete all chats related to this provider candidate from root chats collection
            chats_query = self._get_collection('chats').where('provider_candidate_id', '==', provider_candidate_id)
            chats = chats_query.stream()
            for chat in chats:
                # Delete all messages in each chat
                messages_ref = chat.reference.collection('messages')
                messages = messages_ref.stream()
                for message in messages:
                    message.reference.delete()
                # Delete the chat
                chat.reference.delete()

            # Delete the provider candidate
            candidate_ref.delete()
            return True
        except Exception as e:
            logger.error("Error deleting provider candidate %s: %s", provider_candidate_id, e)
            return False

    # --- Favorites Operations ---

    async def get_favorites(self, user_id: str) -> list[dict[str, Any]]:
        """Fetch user's favorite users with full user data from favorites subcollection."""
        if not self.db:
            return []
        try:
            # Query favorites subcollection
            favorites_ref = self._get_collection('users').document(user_id).collection('favorites')
            favorite_docs = favorites_ref.stream()

            # Fetch full user data for each favorite
            favorite_users = []
            for fav_doc in favorite_docs:
                favorite_user_id = fav_doc.id
                user_data = await self.get_user(favorite_user_id)
                if user_data:
                    # Transform to match the User model expected by Flutter
                    favorite_users.append({
                        'user_id': favorite_user_id,
                        'name': user_data.get('name', ''),
                        'self_introduction': user_data.get('self_introduction', ''),
                        'competencies': user_data.get('competencies', []),
                        'average_rating': user_data.get('average_rating', 0.0),
                        'review_count': user_data.get('review_count', 0),
                        'feedback_positive': user_data.get('feedback_positive', []),
                        'feedback_negative': user_data.get('feedback_negative', [])
                    })
            return favorite_users
        except Exception as e:
            logger.error("Error fetching favorites for %s: %s", user_id, e)
            return []

    async def add_favorite(self, user_id: str, favorite_user_id: str) -> bool:
        """Add a user to favorites subcollection."""
        if not self.db:
            return False
        try:
            # Create document in favorites subcollection with favorite_user_id as doc ID
            ref = (self._get_collection('users')
                  .document(user_id)
                  .collection('favorites')
                  .document(favorite_user_id))
            ref.set({
                'user_id': favorite_user_id,
                'created_at': datetime.now(UTC)
            })
            return True
        except Exception as e:
            logger.error("Error adding favorite for %s: %s", user_id, e)
            return False

    async def remove_favorite(self, user_id: str, favorite_user_id: str) -> bool:
        """Remove a user from favorites subcollection."""
        if not self.db:
            return False
        try:
            ref = (self._get_collection('users')
                  .document(user_id)
                  .collection('favorites')
                  .document(favorite_user_id))
            ref.delete()
            return True
        except Exception as e:
            logger.error("Error removing favorite %s for %s: %s", favorite_user_id, user_id, e)
            return False

    async def add_outgoing_service_requests(self, user_id: str, request_ids: list[str]) -> bool:
        """Add service request IDs to user's outgoing requests subcollection."""
        if not self.db:
            return False
        try:
            for request_id in request_ids:
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('outgoing_service_requests')
                      .document(request_id))
                ref.set({
                    'service_request_id': request_id,
                    'created_at': datetime.now(UTC)
                })
            return True
        except Exception as e:
            logger.error("Error adding outgoing requests for %s: %s", user_id, e)
            return False

    async def add_incoming_service_requests(self, user_id: str, request_ids: list[str]) -> bool:
        """Add service request IDs to user's incoming requests subcollection."""
        if not self.db:
            return False
        try:
            for request_id in request_ids:
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('incoming_service_requests')
                      .document(request_id))
                ref.set({
                    'service_request_id': request_id,
                    'created_at': datetime.now(UTC)
                })
            return True
        except Exception as e:
            logger.error("Error adding incoming requests for %s: %s", user_id, e)
            return False

    async def remove_outgoing_service_requests(self, user_id: str, request_ids: list[str]) -> bool:
        """Remove service request IDs from user's outgoing requests subcollection."""
        if not self.db:
            return False
        try:
            for request_id in request_ids:
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('outgoing_service_requests')
                      .document(request_id))
                ref.delete()
            return True
        except Exception as e:
            logger.error("Error removing outgoing requests for %s: %s", user_id, e)
            return False

    async def remove_incoming_service_requests(self, user_id: str, request_ids: list[str]) -> bool:
        """Remove service request IDs from user's incoming requests subcollection."""
        if not self.db:
            return False
        try:
            for request_id in request_ids:
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('incoming_service_requests')
                      .document(request_id))
                ref.delete()
            return True
        except Exception as e:
            logger.error("Error removing incoming requests for %s: %s", user_id, e)
            return False

    async def get_outgoing_service_requests(self, user_id: str) -> list[str]:
        """Get all outgoing service request IDs for a user.

        Returns:
            List of service request IDs
        """
        if not self.db:
            return []
        try:
            requests_ref = (self._get_collection('users')
                           .document(user_id)
                           .collection('outgoing_service_requests'))
            docs = requests_ref.stream()
            return [doc.id for doc in docs]
        except Exception as e:
            logger.error("Error getting outgoing requests for %s: %s", user_id, e)
            return []

    async def get_incoming_service_requests(self, user_id: str) -> list[str]:
        """Get all incoming service request IDs for a user.

        Returns:
            List of service request IDs
        """
        if not self.db:
            return []
        try:
            requests_ref = (self._get_collection('users')
                           .document(user_id)
                           .collection('incoming_service_requests'))
            docs = requests_ref.stream()
            return [doc.id for doc in docs]
        except Exception as e:
            logger.error("Error getting incoming requests for %s: %s", user_id, e)
            return []

    # --- User Operations ---

    async def get_competencies(self, user_id: str) -> list[str]:
        """Fetch user's competencies from subcollection."""
        if not self.db:
            return []
        try:
            competencies_ref = self.db.collection('users').document(user_id).collection('competencies')
            docs = competencies_ref.stream()
            competencies = []
            for doc in docs:
                comp_data = doc.to_dict()
                # Include the document ID
                comp_data['competence_id'] = doc.id
                competencies.append(comp_data)
            return competencies
        except Exception as e:
            logger.error("Error fetching competencies for %s: %s", user_id, e)
            return []

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get user with competencies from subcollection."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('users').document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                if data is None:
                    return None
                data['user_id'] = doc.id

                # Fetch competencies from subcollection
                competencies = await self.get_competencies(user_id)
                # Override the competencies field with subcollection data
                data['competencies'] = competencies

                return data
            return None
        except Exception as e:
            logger.error("Error getting user %s: %s", user_id, e)
            return None

    async def update_user(self, user_id: str, user_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update user.

        Args:
            user_id: The user's ID
            user_data: Data to update

        Returns:
            Full updated user object with competencies, or None if failed
        """
        if not self.db:
            return None
        try:
            # Check if user exists
            user_ref = self._get_collection('users').document(user_id)
            if not user_ref.get().exists:
                logger.warning("Cannot update user %s: user does not exist", user_id)
                return None

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(user_data, UserUpdateSchema, exclude_unset=True)

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Update the document (will fail if document doesn't exist)
            user_ref.update(validated_data)
            return await self.get_user(user_id)
        except Exception as e:
            logger.error("Error updating %s: %s", user_id, e)
            return None

    async def create_user(
        self,
        user_id: str | None = None,
        user_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create a new user.

        Args:
            user_id: The user's ID (typically Firebase UID). If None, auto-generates an ID.
            user_data: User data to create

        Returns:
            The created user object with user_id, or None if failed
        """
        if not self.db:
            return None
        try:
            if user_data is None:
                return None
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(user_data, UserSchema)

            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(UTC)
            validated_data['updated_at'] = datetime.now(UTC)

            # Create the user document
            if user_id:
                # Use provided ID
                self._get_collection('users').document(user_id).set(validated_data)
                final_user_id = user_id
            else:
                # Auto-generate ID using Firestore
                doc_ref = self._get_collection('users').document()
                doc_ref.set(validated_data)
                final_user_id = doc_ref.id

            # Return full object
            result = validated_data.copy()
            result['user_id'] = final_user_id
            return result
        except Exception as e:
            logger.error("Error creating user: %s", e)
            return None

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user and all their subcollections (competencies, favorites, service requests).

        Args:
            user_id: The user's ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            user_ref = self._get_collection('users').document(user_id)

            # Delete all competencies in subcollection
            competencies_ref = user_ref.collection('competencies')
            competencies = competencies_ref.stream()
            for comp in competencies:
                comp.reference.delete()

            # Delete all favorites in subcollection
            favorites_ref = user_ref.collection('favorites')
            favorites = favorites_ref.stream()
            for fav in favorites:
                fav.reference.delete()

            # Delete all outgoing service requests in subcollection
            outgoing_ref = user_ref.collection('outgoing_service_requests')
            outgoing = outgoing_ref.stream()
            for req in outgoing:
                req.reference.delete()

            # Delete all incoming service requests in subcollection
            incoming_ref = user_ref.collection('incoming_service_requests')
            incoming = incoming_ref.stream()
            for req in incoming:
                req.reference.delete()

            # Delete the user document
            user_ref.delete()
            return True
        except Exception as e:
            logger.error("Error deleting user %s: %s", user_id, e)
            return False

    async def create_competence(self, user_id: str, competence: dict) -> dict[str, Any] | None:
        """Create a competence for user's competencies subcollection.

        Args:
            user_id: The user's ID
            competence: Dictionary with 'title' (required) and any other
                CompetenceSchema fields.  The caller must strip non-schema keys
                such as 'competence_id' and 'availability_time' before calling
                (availability_time is written separately via create_availability_time).

        Returns:
            The created competence object with auto-generated competence_id, or None if failed
        """
        if not self.db:
            return None
        try:
            title = competence.get('title')
            if not title:
                logger.error("Competence missing title for user %s", user_id)
                return None

            # Generate prefixed competence ID
            competence_id = self._generate_prefixed_id('competence')

            # Build validated data from ALL known CompetenceSchema fields.
            # Strip IDs and subcollection-only keys that must not be stored on the
            # competence document itself.
            _STRIP_KEYS = {'competence_id', 'availability_time', 'created_at', 'updated_at'}
            competence_data = {k: v for k, v in competence.items() if k not in _STRIP_KEYS}

            # Validate data against schema (raises ValidationError on bad data)
            validated_data = self._validate_data(competence_data, CompetenceSchema)

            # Overwrite timestamps with authoritative server values
            validated_data['created_at'] = datetime.now()
            validated_data['updated_at'] = datetime.now()

            # Add document to competencies subcollection with prefixed ID
            competencies_ref = self._get_collection('users').document(user_id).collection('competencies')
            competencies_ref.document(competence_id).set(validated_data)

            result = validated_data.copy()
            result['competence_id'] = competence_id
            return result
        except Exception as e:
            logger.error("Error creating competence for %s: %s", user_id, e)
            return None

    async def remove_competence(self, user_id: str, competence_id: str) -> bool:
        """Remove a competence from user's competencies subcollection.

        Args:
            user_id: The user's ID
            competence_id: The competence document ID to delete
        """
        if not self.db:
            return False
        try:
            # Delete document from competencies subcollection using competence_id
            competencies_ref = self._get_collection('users').document(user_id).collection('competencies')
            competencies_ref.document(competence_id).delete()
            return True
        except Exception as e:
            logger.error("Error removing competence %s for %s: %s", competence_id, user_id, e)
            return False

    async def update_competence(self, user_id: str, competence_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a competence.

        Args:
            user_id: The user's ID
            competence_id: The competence document ID to update
            update_data: Data to update

        Returns:
            Full updated competence object, or None if failed
        """
        if not self.db:
            return None
        try:
            # Check if competence exists
            competence_ref = self._get_collection('users').document(user_id).collection('competencies').document(competence_id)
            if not competence_ref.get().exists:
                logger.warning("Cannot update competence %s for user %s: competence does not exist", competence_id, user_id)
                return None

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, CompetenceUpdateSchema, exclude_unset=True)

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Update document in competencies subcollection
            competence_ref.update(validated_data)
            return await self.get_competence(user_id, competence_id)
        except Exception as e:
            logger.error("Error updating competence %s for %s: %s", competence_id, user_id, e)
            return None

    async def get_competence(self, user_id: str, competence_id: str) -> dict[str, Any] | None:
        """Get a single competence by ID.

        Args:
            user_id: The user's ID
            competence_id: The competence document ID

        Returns:
            The competence data as a dictionary, or None if not found
        """
        if not self.db:
            return None
        try:
            competence_ref = self._get_collection('users').document(user_id).collection('competencies').document(competence_id)
            doc = competence_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error("Error getting competence %s for %s: %s", competence_id, user_id, e)
            return None

    # --- Availability Time Operations ---

    async def create_availability_time(
        self,
        user_id: str,
        availability_data: dict[str, Any],
        competence_id: str | None = None
    ) -> dict[str, Any] | None:
        """Create an availability time for a user or competence.

        Args:
            user_id: The user's ID
            availability_data: Availability time data
            competence_id: Optional competence ID if this is for a competence subcollection

        Returns:
            The created availability time object with availability_time_id, or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed availability time ID
            availability_time_id = self._generate_prefixed_id('availability_time')

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(availability_data, AvailabilityTimeSchema)

            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(UTC)
            validated_data['updated_at'] = datetime.now(UTC)

            # Determine the collection reference
            if competence_id:
                # Subcollection under competence
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('competencies')
                      .document(competence_id)
                      .collection('availability_time')
                      .document(availability_time_id))
            else:
                # Subcollection under user
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('availability_time')
                      .document(availability_time_id))

            ref.set(validated_data)

            # Return full object
            result = validated_data.copy()
            result['availability_time_id'] = availability_time_id
            return result
        except Exception as e:
            logger.error("Error creating availability time: %s", e)
            return None

    async def get_availability_times(
        self,
        user_id: str,
        competence_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all availability times for a user or competence.

        Args:
            user_id: The user's ID
            competence_id: Optional competence ID

        Returns:
            List of availability time dictionaries
        """
        if not self.db:
            return []
        try:
            # Determine the collection reference
            if competence_id:
                # Subcollection under competence
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('competencies')
                      .document(competence_id)
                      .collection('availability_time'))
            else:
                # Subcollection under user
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('availability_time'))

            docs = ref.stream()
            availability_times = []
            for doc in docs:
                data = doc.to_dict()
                data['availability_time_id'] = doc.id
                availability_times.append(data)
            return availability_times
        except Exception as e:
            logger.error("Error fetching availability times: %s", e)
            return []

    async def get_availability_time(
        self,
        user_id: str,
        availability_time_id: str,
        competence_id: str | None = None
    ) -> dict[str, Any] | None:
        """Fetch a single availability time.

        Args:
            user_id: The user's ID
            availability_time_id: The availability time ID
            competence_id: Optional competence ID

        Returns:
            Availability time dictionary or None if not found
        """
        if not self.db:
            return None
        try:
            # Determine the collection reference
            if competence_id:
                # Subcollection under competence
                doc = (self._get_collection('users')
                      .document(user_id)
                      .collection('competencies')
                      .document(competence_id)
                      .collection('availability_time')
                      .document(availability_time_id)
                      .get())
            else:
                # Subcollection under user
                doc = (self._get_collection('users')
                      .document(user_id)
                      .collection('availability_time')
                      .document(availability_time_id)
                      .get())

            if doc.exists:
                data = doc.to_dict()
                data['availability_time_id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error("Error fetching availability time %s: %s", availability_time_id, e)
            return None

    async def update_availability_time(
        self,
        user_id: str,
        availability_time_id: str,
        update_data: dict[str, Any],
        competence_id: str | None = None
    ) -> dict[str, Any] | None:
        """Update an availability time.

        Args:
            user_id: The user's ID
            availability_time_id: The availability time ID
            update_data: Data to update
            competence_id: Optional competence ID

        Returns:
            Full updated availability time object, or None if failed
        """
        if not self.db:
            return None
        try:
            # Determine the collection reference
            if competence_id:
                # Subcollection under competence
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('competencies')
                      .document(competence_id)
                      .collection('availability_time')
                      .document(availability_time_id))
            else:
                # Subcollection under user
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('availability_time')
                      .document(availability_time_id))

            if not ref.get().exists:
                logger.warning("Cannot update availability time %s: does not exist", availability_time_id)
                return None

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(
                update_data,
                AvailabilityTimeUpdateSchema,
                exclude_unset=True
            )

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Update document
            ref.update(validated_data)
            return await self.get_availability_time(user_id, availability_time_id, competence_id)
        except Exception as e:
            logger.error("Error updating availability time %s: %s", availability_time_id, e)
            return None

    async def delete_availability_time(
        self,
        user_id: str,
        availability_time_id: str,
        competence_id: str | None = None
    ) -> bool:
        """Delete an availability time.

        Args:
            user_id: The user's ID
            availability_time_id: The availability time ID
            competence_id: Optional competence ID

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            # Determine the collection reference
            if competence_id:
                # Subcollection under competence
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('competencies')
                      .document(competence_id)
                      .collection('availability_time')
                      .document(availability_time_id))
            else:
                # Subcollection under user
                ref = (self._get_collection('users')
                      .document(user_id)
                      .collection('availability_time')
                      .document(availability_time_id))

            ref.delete()
            return True
        except Exception as e:
            logger.error("Error deleting availability time %s: %s", availability_time_id, e)
            return False

    # --- Review Operations ---

    async def create_review(self, review_data: dict[str, Any]) -> dict[str, Any] | None:
        """Create a new review.

        Args:
            review_data: Review data (should include service_request_id, user_id, reviewer_user_id, rating, etc.)

        Returns:
            The created review object with review_id, or None if failed
        """
        if not self.db:
            return None
        try:
            # Validate that the service request exists and is completed
            service_request_id = review_data.get('service_request_id')
            if service_request_id:
                service_request = await self.get_service_request(service_request_id)
                if not service_request:
                    logger.error("Cannot create review: service request %s not found", service_request_id)
                    return None
                if service_request.get('status') != 'completed':
                    logger.error("Cannot create review: service request %s is not completed (status: %s)", service_request_id, service_request.get('status'))
                    return None

            # Generate prefixed review ID
            review_id = self._generate_prefixed_id('review')

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(review_data, ReviewSchema)

            # Add timestamps after validation
            validated_data['created_at'] = datetime.now()
            validated_data['updated_at'] = datetime.now()

            # Create document with the prefixed ID
            ref = self._get_collection('reviews').document(review_id)
            ref.set(validated_data)

            # Return full object
            result = validated_data.copy()
            result['review_id'] = review_id
            return result
        except Exception as e:
            logger.error("Error creating review: %s", e)
            return None

    async def get_review(self, review_id: str) -> dict[str, Any] | None:
        """Get a review by ID."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('reviews').document(review_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error("Error getting review %s: %s", review_id, e)
            return None

    async def get_reviews_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Get all reviews for a user (as reviewee)."""
        if not self.db:
            return []
        try:
            query = self._get_collection('reviews').where('user_id', '==', user_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error("Error getting reviews for user %s: %s", user_id, e)
            return []

    async def get_reviews_by_reviewer(self, reviewer_user_id: str) -> list[dict[str, Any]]:
        """Get all reviews written by a reviewer."""
        if not self.db:
            return []
        try:
            query = self._get_collection('reviews').where('reviewer_user_id', '==', reviewer_user_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error("Error getting reviews by reviewer %s: %s", reviewer_user_id, e)
            return []

    async def get_reviews_by_request(self, service_request_id: str) -> list[dict[str, Any]]:
        """Get all reviews for a service request."""
        if not self.db:
            return []
        try:
            query = self._get_collection('reviews').where('service_request_id', '==', service_request_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error("Error getting reviews for request %s: %s", service_request_id, e)
            return []

    async def update_review(self, review_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a review.

        Args:
            review_id: The review ID
            update_data: Data to update

        Returns:
            Full updated review object, or None if failed
        """
        if not self.db:
            return None
        try:
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ReviewUpdateSchema, exclude_unset=True)

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.utcnow()

            # Update the document
            ref = self._get_collection('reviews').document(review_id)
            ref.update(validated_data)
            return await self.get_review(review_id)
        except Exception as e:
            logger.error("Error updating review %s: %s", review_id, e)
            return None

    async def delete_review(self, review_id: str) -> bool:
        """Delete a review."""
        if not self.db:
            return False
        try:
            self._get_collection('reviews').document(review_id).delete()
            return True
        except Exception as e:
            logger.error("Error deleting review %s: %s", review_id, e)
            return False

    # --- Chat Operations ---

    async def create_chat(self, chat_data: dict[str, Any]) -> dict[str, Any] | None:
        """Create a new chat in root chats collection.

        Args:
            chat_data: Chat data (should include service_request_id, provider_candidate_id,
                      seeker_user_id, provider_user_id, and optional title)

        Returns:
            The created chat object with chat_id, or None if failed
        """
        if not self.db:
            return None
        try:
            # Validate required fields
            required_fields = ['service_request_id', 'provider_candidate_id', 'seeker_user_id', 'provider_user_id']
            for field in required_fields:
                if not chat_data.get(field):
                    logger.error("%s is required for chat creation", field)
                    return None

            # Generate prefixed chat ID
            chat_id = self._generate_prefixed_id('chat')

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(chat_data, ChatSchema)

            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(UTC)
            validated_data['updated_at'] = datetime.now(UTC)

            # Create document in root chats collection
            ref = self._get_collection('chats').document(chat_id)
            ref.set(validated_data)

            # Return full object
            result = validated_data.copy()
            result['chat_id'] = chat_id
            return result
        except Exception as e:
            logger.error("Error creating chat: %s", e)
            return None

    async def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        """Get a chat by ID from root chats collection.

        Args:
            chat_id: The chat ID

        Returns:
            Chat dictionary or None if not found
        """
        if not self.db:
            return None
        try:
            doc = self._get_collection('chats').document(chat_id).get()
            if doc.exists:
                data = doc.to_dict()
                if data is None:
                    return None
                data['chat_id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error("Error getting chat %s: %s", chat_id, e)
            return None

    async def get_chats_by_request(self, service_request_id: str) -> list[dict[str, Any]]:
        """Get all chats for a service request.

        Args:
            service_request_id: The service request ID

        Returns:
            List of chat dictionaries
        """
        if not self.db:
            return []
        try:
            query = self._get_collection('chats').where('service_request_id', '==', service_request_id)
            docs = query.stream()
            chats = []
            for doc in docs:
                data = doc.to_dict() or {}
                data['chat_id'] = doc.id
                chats.append(data)
            return chats
        except Exception as e:
            logger.error("Error getting chats for request %s: %s", service_request_id, e)
            return []

    async def get_chats_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Get all chats where user is either seeker or provider.

        Args:
            user_id: The user ID

        Returns:
            List of chat dictionaries
        """
        if not self.db:
            return []
        try:
            # Query for chats where user is seeker
            seeker_query = self._get_collection('chats').where('seeker_user_id', '==', user_id)
            seeker_docs = seeker_query.stream()

            # Query for chats where user is provider
            provider_query = self._get_collection('chats').where('provider_user_id', '==', user_id)
            provider_docs = provider_query.stream()

            # Combine results and deduplicate
            chats = {}
            for doc in seeker_docs:
                data = doc.to_dict() or {}
                data['chat_id'] = doc.id
                chats[doc.id] = data

            for doc in provider_docs:
                if doc.id not in chats:
                    data = doc.to_dict() or {}
                    data['chat_id'] = doc.id
                    chats[doc.id] = data

            return list(chats.values())
        except Exception as e:
            logger.error("Error getting chats for user %s: %s", user_id, e)
            return []

    async def update_chat(self, chat_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a chat in root chats collection.

        Args:
            chat_id: The chat ID
            update_data: Data to update

        Returns:
            Full updated chat object, or None if failed
        """
        if not self.db:
            return None
        try:
            ref = self._get_collection('chats').document(chat_id)

            if not ref.get().exists:
                logger.warning("Cannot update chat %s: does not exist", chat_id)
                return None

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ChatUpdateSchema, exclude_unset=True)

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Update the document
            ref.update(validated_data)
            return await self.get_chat(chat_id)
        except Exception as e:
            logger.error("Error updating chat %s: %s", chat_id, e)
            return None

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages from root chats collection.

        Args:
            chat_id: The chat ID

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            chat_ref = self._get_collection('chats').document(chat_id)

            # Delete all messages in the subcollection first
            messages_ref = chat_ref.collection('messages')
            messages = messages_ref.stream()
            for msg in messages:
                msg.reference.delete()

            # Delete the chat document
            chat_ref.delete()
            return True
        except Exception as e:
            logger.error("Error deleting chat %s: %s", chat_id, e)
            return False

    # --- Chat Message Operations ---

    async def create_chat_message(self, chat_id: str, message_data: dict[str, Any]) -> dict[str, Any] | None:
        """Create a new chat message in a chat's messages subcollection.

        Args:
            chat_id: The chat ID
            message_data: Message data (should include sender_user_id, receiver_user_id, message)

        Returns:
            The created message object with chat_message_id, or None if failed
        """
        if not self.db:
            return None
        try:
            # Fetch chat to validate participants
            chat = await self.get_chat(chat_id)
            if not chat:
                logger.error("Chat %s not found", chat_id)
                return None

            # Validate that sender and receiver are the chat participants
            seeker_id = chat.get('seeker_user_id')
            provider_id = chat.get('provider_user_id')
            sender_id = message_data.get('sender_user_id')
            receiver_id = message_data.get('receiver_user_id')

            valid_participants = {seeker_id, provider_id}
            if sender_id not in valid_participants or receiver_id not in valid_participants:
                logger.error("Invalid participants: sender=%s, receiver=%s. Must be one of %s", sender_id, receiver_id, valid_participants)
                return None

            if sender_id == receiver_id:
                logger.error("Sender and receiver cannot be the same: %s", sender_id)
                return None

            # Generate prefixed message ID
            message_id = self._generate_prefixed_id('chat_message')
            message_data['chat_id'] = chat_id

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(message_data, ChatMessageSchema)

            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(UTC)
            validated_data['updated_at'] = datetime.now(UTC)

            # Create document in messages subcollection under chat
            ref = (self._get_collection('chats')
                   .document(chat_id)
                   .collection('messages')
                   .document(message_id))
            ref.set(validated_data)

            # Return full object
            result = validated_data.copy()
            result['chat_message_id'] = message_id
            return result
        except Exception as e:
            logger.error("Error creating chat message in %s: %s", chat_id, e)
            return None

    async def get_chat_messages(self, chat_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all messages for a chat, ordered by time.

        Args:
            chat_id: The chat ID
            limit: Maximum number of messages to return

        Returns:
            List of message dictionaries
        """
        if not self.db:
            return []
        try:
            messages_ref = (self._get_collection('chats')
                           .document(chat_id)
                           .collection('messages'))
            query = messages_ref.order_by('created_at').limit(limit)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error("Error getting messages for chat %s: %s", chat_id, e)
            return []

    async def get_chat_message(self, chat_id: str, message_id: str) -> dict[str, Any] | None:
        """Get a specific chat message.

        Args:
            chat_id: The chat ID
            message_id: The message ID

        Returns:
            Message dictionary or None if not found
        """
        if not self.db:
            return None
        try:
            doc = (self._get_collection('chats')
                  .document(chat_id)
                  .collection('messages')
                  .document(message_id)
                  .get())
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error("Error getting message %s from chat %s: %s", message_id, chat_id, e)
            return None

    async def update_chat_message(self, chat_id: str, message_id: str, update_data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a chat message.

        Args:
            chat_id: The chat ID
            message_id: The message ID
            update_data: Data to update

        Returns:
            Full updated chat message object, or None if failed
        """
        if not self.db:
            return None
        try:
            # If updating sender or receiver, validate they are chat participants
            if 'sender_user_id' in update_data or 'receiver_user_id' in update_data:
                chat = await self.get_chat(chat_id)
                if not chat:
                    logger.error("Chat %s not found", chat_id)
                    return None

                # Get current message to merge with updates
                current_message = await self.get_chat_message(chat_id, message_id)
                if not current_message:
                    logger.error("Message %s not found in chat %s", message_id, chat_id)
                    return None

                # Determine final sender and receiver after update
                sender_id = update_data.get('sender_user_id', current_message.get('sender_user_id'))
                receiver_id = update_data.get('receiver_user_id', current_message.get('receiver_user_id'))

                # Validate participants
                seeker_id = chat.get('seeker_user_id')
                provider_id = chat.get('provider_user_id')
                valid_participants = {seeker_id, provider_id}

                if sender_id not in valid_participants or receiver_id not in valid_participants:
                    logger.error("Invalid participants: sender=%s, receiver=%s. Must be one of %s", sender_id, receiver_id, valid_participants)
                    return None

                if sender_id == receiver_id:
                    logger.error("Sender and receiver cannot be the same: %s", sender_id)
                    return None

            ref = (self._get_collection('chats')
                   .document(chat_id)
                   .collection('messages')
                   .document(message_id))

            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ChatMessageUpdateSchema, exclude_unset=True)

            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(UTC)

            # Update the document
            ref.update(validated_data)
            return await self.get_chat_message(chat_id, message_id)
        except Exception as e:
            logger.error("Error updating message %s in chat %s: %s", message_id, chat_id, e)
            return None

    async def delete_chat_message(self, chat_id: str, message_id: str) -> bool:
        """Delete a chat message.

        Args:
            chat_id: The chat ID
            message_id: The message ID

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            (self._get_collection('chats')
             .document(chat_id)
             .collection('messages')
             .document(message_id)
             .delete())
            return True
        except Exception as e:
            logger.error("Error deleting message %s from chat %s: %s", message_id, chat_id, e)
            return False

    # ── AI Conversations ─────────────────────────────────────────────────────

    async def create_ai_conversation(self, user_id: str, data: dict[str, Any]) -> str | None:
        """Create a new AI conversation document under users/{user_id}/ai_conversations.

        Args:
            user_id: The owner of this conversation.
            data:    Dict with optional topic_title, request_id, etc.

        Returns:
            The auto-generated conversation_id string, or None on failure.
        """
        if not self.db:
            return None
        try:
            validated = self._validate_data(data, AIConversationSchema)
            doc_ref = (
                self._get_collection('users')
                .document(user_id)
                .collection('ai_conversations')
                .document()
            )
            doc_ref.set(validated)
            return doc_ref.id
        except Exception as exc:
            logger.error("Error creating ai_conversation: %s", exc)
            return None

    async def create_ai_conversation_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        text: str,
        stage: ConversationStage | str,
        sequence: int,
    ) -> str | None:
        """Append a message to the ai_conversation's messages subcollection.

        Also updates first_message_at / last_message_at / message_count on the
        parent document (as a separate Firestore write — not in a transaction).

        Args:
            user_id:         The owner of the conversation.
            conversation_id: The parent ai_conversation document ID.
            role:            'user' or 'assistant'.
            text:            Plain text of the message.
            stage:           Current ConversationStage value.
            sequence:        0-based monotonically-increasing counter.

        Returns:
            The new message document ID, or None on failure.
        """
        if not self.db:
            return None
        try:
            stage_str = stage.value if isinstance(stage, ConversationStage) else str(stage)
            msg_data = {
                "conversation_id": conversation_id,
                "role": role,
                "text": text,
                "stage": stage_str,
                "sequence": sequence,
            }
            validated = self._validate_data(msg_data, AIConversationMessageSchema)
            now = datetime.now(UTC)
            conv_ref = (
                self._get_collection('users')
                .document(user_id)
                .collection('ai_conversations')
                .document(conversation_id)
            )
            msg_ref = conv_ref.collection('messages').document()
            msg_ref.set(validated)
            # Update parent doc counters
            parent_update: dict[str, Any] = {
                "last_message_at": now,
                "message_count": Increment(1),
                "updated_at": now,
            }
            if sequence == 0:
                parent_update["first_message_at"] = now
            conv_ref.update(parent_update)
            return msg_ref.id
        except Exception as exc:
            logger.error("Error saving ai_conversation message: %s", exc)
            return None

    async def update_ai_conversation(
        self, user_id: str, conversation_id: str, update_data: dict[str, Any]
    ) -> bool:
        """Partial-update an AI conversation document.

        Returns True on success, False otherwise.
        """
        if not self.db:
            return False
        try:
            validated = self._validate_data(update_data, AIConversationUpdateSchema, exclude_unset=True)
            validated["updated_at"] = datetime.now(UTC)
            (
                self._get_collection('users')
                .document(user_id)
                .collection('ai_conversations')
                .document(conversation_id)
                .update(validated)
            )
            return True
        except Exception as exc:
            logger.error("Error updating ai_conversation %s: %s", conversation_id, exc)
            return False

    async def get_ai_conversations(
        self,
        user_id: str,
        limit: int = 20,
        start_after_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List AI conversations for a user, ordered by last_message_at DESC.

        Args:
            user_id:        The user whose conversations to list.
            limit:          Maximum number of results to return.
            start_after_id: Document ID to start after for cursor-based pagination.

        Returns:
            List of conversation dicts (each includes 'conversation_id').
        """
        if not self.db:
            return []
        try:
            user_conv_ref = (
                self._get_collection('users')
                .document(user_id)
                .collection('ai_conversations')
            )
            query = (
                user_conv_ref
                .order_by('last_message_at', direction='DESCENDING')
                .limit(limit)
            )
            if start_after_id:
                cursor_doc = user_conv_ref.document(start_after_id).get()
                if cursor_doc.exists:
                    query = query.start_after(cursor_doc)
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data['conversation_id'] = doc.id
                results.append(data)
            return results
        except Exception as exc:
            logger.error("Error listing ai_conversations for user %s: %s", user_id, exc)
            return []

    async def get_ai_conversation_messages(
        self, user_id: str, conversation_id: str
    ) -> list[dict[str, Any]]:
        """Return all messages for an AI conversation, ordered by sequence ASC.

        Args:
            user_id:         The owner of the conversation.
            conversation_id: The parent ai_conversation document ID.

        Returns:
            List of message dicts (each includes 'message_id').
        """
        if not self.db:
            return []
        try:
            query = (
                self._get_collection('users')
                .document(user_id)
                .collection('ai_conversations')
                .document(conversation_id)
                .collection('messages')
                .order_by('sequence')
            )
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data['message_id'] = doc.id
                results.append(data)
            return results
        except Exception as exc:
            logger.error(
                "Error listing messages for ai_conversation %s: %s",
                conversation_id, exc,
            )
            return []

    async def get_ai_conversation(
        self, user_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        """Fetch a single AI conversation document by owner + ID (O(1) lookup).

        Returns the conversation dict (including 'conversation_id') or None if
        the document does not exist.
        """
        if not self.db:
            return None
        try:
            doc = (
                self._get_collection('users')
                .document(user_id)
                .collection('ai_conversations')
                .document(conversation_id)
                .get()
            )
            if not doc.exists:
                return None
            data = doc.to_dict()
            data['conversation_id'] = doc.id
            return data
        except Exception as exc:
            logger.error(
                "Error fetching ai_conversation %s: %s", conversation_id, exc,
            )
            return None

    async def get_recent_ai_conversation(
        self, user_id: str, within_hours: int = 24
    ) -> dict[str, Any] | None:
        """Return the most recent AI conversation if it ended within *within_hours* hours.

        Fetches the single most recent conversation ordered by last_message_at DESC.
        Returns None if no conversation exists, if Firestore is unavailable, or if
        the most recent conversation's last_message_at is older than the cutoff.
        """
        conversations = await self.get_ai_conversations(user_id, limit=1)
        if not conversations:
            return None
        recent = conversations[0]
        last_message_at = recent.get("last_message_at")
        if last_message_at is None:
            return None
        cutoff = datetime.now(UTC) - timedelta(hours=within_hours)
        if hasattr(last_message_at, "tzinfo") and last_message_at.tzinfo is None:
            last_message_at = last_message_at.replace(tzinfo=UTC)
        if last_message_at < cutoff:
            return None
        return recent
