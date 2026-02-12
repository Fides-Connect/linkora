import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError
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
    AvailabilityTimeUpdateSchema
)

logger = logging.getLogger(__name__)

class FirestoreService:
    """Service to interact with Firestore database."""
    
    def __init__(self):
        """Initialize Firestore client lazily."""
        self._db = None

    @property
    def db(self):
        if self._db is None:
            try:
                # Initialization should have happened in main.py
                # This call will work if the default app is initialized.
                self._db = firestore.client()
            except Exception as e:
                # If app is not initialized yet (e.g. during imports), log it but don't crash
                # It will retry on next access
                logger.debug(f"Firestore client not initialized (yet): {e}")
                return None
        return self._db

    def _get_collection(self, collection_name: str):
        if not self.db:
            return None
        return self.db.collection(collection_name)
    
    def _generate_prefixed_id(self, prefix: str) -> str:
        """Generate a Firestore auto-ID with a prefix.
        
        Args:
            prefix: The prefix to add (e.g., 'user', 'competence', 'service_request')
            
        Returns:
            A prefixed ID like 'user_abc123def456'
        """
        # Generate a Firestore-style auto ID
        doc_ref = self.db.collection('_temp').document()
        auto_id = doc_ref.id
        return f"{prefix}_{auto_id}"
    
    def _validate_data(self, data: Dict[str, Any], schema_class, exclude_unset: bool = False) -> Dict[str, Any]:
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
            logger.error(f"Validation error for {schema_class.__name__}: {e}")
            raise

    # --- Service Request Operations ---

    async def _enrich_service_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
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
        if 'selected_provider_user_id' in request:
            provider = await self.get_user(request['selected_provider_user_id'])
            if provider and 'name' in provider:
                request['selected_provider_user_name'] = provider['name']
                request['selected_provider_user_initials'] = "".join([n[0] for n in provider['name'].split() if n]).upper()[:2]
            else:
                request['selected_provider_user_name'] = ''
                request['selected_provider_user_initials'] = ''
        
        return request

    async def get_service_requests(self, user_id: str) -> List[Dict[str, Any]]:
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
                data['id'] = doc.id
                requests.append(data)
            
            query2 = requests_ref.where(filter=FieldFilter("selected_provider_user_id", "==", user_id)).stream()
            for doc in query2:
                data = doc.to_dict()
                data['id'] = doc.id
                # Avoid duplicates
                if not any(r['id'] == data['id'] for r in requests):
                    requests.append(data)
            
            # Enrich requests with user names and initials
            for i, req in enumerate(requests):
                requests[i] = await self._enrich_service_request(req)
            return requests

        except Exception as e:
            logger.error(f"Error fetching requests for user {user_id}: {e}")
            return []

    async def create_service_request(self, request_data: Dict[str, Any]) -> str:
        """Create a new service request."""
        if not self.db:
            return ""
        try:
            # Generate prefixed service request ID
            service_request_id = self._generate_prefixed_id('service_request')
            
            # Add timestamps before validation (they will be validated as well)
            request_data['created_at'] = datetime.now(timezone.utc)
            request_data['updated_at'] = datetime.now(timezone.utc)

            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(request_data, ServiceRequestSchema)
            
            # Create document with the prefixed ID
            ref = self._get_collection('service_requests').document(service_request_id)
            ref.set(validated_data)
            return service_request_id
        except Exception as e:
            logger.error(f"Error creating request: {e}")
            return ""

    async def get_service_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single service request by ID."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('service_requests').document(request_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return await self._enrich_service_request(data)
            return None
        except Exception as e:
            logger.error(f"Error fetching request {request_id}: {e}")
            return None

    async def update_service_request_status(self, request_id: str, status: str) -> bool:
        """Update service request status."""
        if not self.db:
            return False
        try:
            # Validate status value using the update schema
            update_data = {'status': status}
            validated_data = self._validate_data(update_data, ServiceRequestUpdateSchema, exclude_unset=True)
            
            ref = self._get_collection('service_requests').document(request_id)
            ref.update({
                'status': validated_data['status'],
                'updated_at': datetime.now(timezone.utc)
            })
            return True
        except Exception as e:
            logger.error(f"Error updating request status {request_id}: {e}")
            return False

    async def update_service_request(self, request_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a service request with full data.
        
        Args:
            request_id: The service request ID to update
            update_data: Data to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            # Check if service request exists
            ref = self._get_collection('service_requests').document(request_id)
            if not ref.get().exists:
                logger.warning(f"Cannot update service request {request_id}: service request does not exist")
                return False
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ServiceRequestUpdateSchema, exclude_unset=True)
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update the document
            ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating service request {request_id}: {e}")
            return False

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
            logger.error(f"Error deleting service request {request_id}: {e}")
            return False

    # --- Provider Candidate Operations ---

    async def create_provider_candidate(
        self,
        service_request_id: str,
        candidate_data: Dict[str, Any]
    ) -> Optional[str]:
        """Create a new provider candidate for a service request.
        
        Args:
            service_request_id: The service request ID
            candidate_data: Provider candidate data
            
        Returns:
            The generated provider_candidate_id or None if failed
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
            validated_data['created_at'] = datetime.now(timezone.utc)
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Create document as subcollection under service_request
            ref = (self._get_collection('service_requests')
                  .document(service_request_id)
                  .collection('provider_candidates')
                  .document(provider_candidate_id))
            ref.set(validated_data)
            return provider_candidate_id
        except Exception as e:
            logger.error(f"Error creating provider candidate for request {service_request_id}: {e}")
            return None

    async def get_provider_candidates(
        self,
        service_request_id: str
    ) -> List[Dict[str, Any]]:
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
                data['id'] = doc.id
                candidates.append(data)
            return candidates
        except Exception as e:
            logger.error(f"Error fetching provider candidates for request {service_request_id}: {e}")
            return []

    async def get_provider_candidate(
        self,
        service_request_id: str,
        provider_candidate_id: str
    ) -> Optional[Dict[str, Any]]:
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
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching provider candidate {provider_candidate_id}: {e}")
            return None

    async def update_provider_candidate(
        self,
        service_request_id: str,
        provider_candidate_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """Update a provider candidate.
        
        Args:
            service_request_id: The service request ID
            provider_candidate_id: The provider candidate ID
            update_data: Data to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            # Check if provider candidate exists
            ref = (self._get_collection('service_requests')
                  .document(service_request_id)
                  .collection('provider_candidates')
                  .document(provider_candidate_id))
            
            if not ref.get().exists:
                logger.warning(
                    f"Cannot update provider candidate {provider_candidate_id}: does not exist"
                )
                return False
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(
                update_data,
                ProviderCandidateUpdateSchema,
                exclude_unset=True
            )
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update document
            ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating provider candidate {provider_candidate_id}: {e}")
            return False

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
            logger.error(f"Error deleting provider candidate {provider_candidate_id}: {e}")
            return False

    # --- Favorites Operations ---

    async def get_favorites(self, user_id: str) -> List[Dict[str, Any]]:
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
                        'id': favorite_user_id,
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
            logger.error(f"Error fetching favorites for {user_id}: {e}")
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
                'created_at': datetime.now(timezone.utc)
            })
            return True
        except Exception as e:
            logger.error(f"Error adding favorite for {user_id}: {e}")
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
            logger.error(f"Error removing favorite {favorite_user_id} for {user_id}: {e}")
            return False

    async def add_outgoing_service_requests(self, user_id: str, request_ids: List[str]) -> bool:
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
                    'created_at': datetime.now(timezone.utc)
                })
            return True
        except Exception as e:
            logger.error(f"Error adding outgoing requests for {user_id}: {e}")
            return False

    async def add_incoming_service_requests(self, user_id: str, request_ids: List[str]) -> bool:
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
                    'created_at': datetime.now(timezone.utc)
                })
            return True
        except Exception as e:
            logger.error(f"Error adding incoming requests for {user_id}: {e}")
            return False

    async def remove_outgoing_service_requests(self, user_id: str, request_ids: List[str]) -> bool:
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
            logger.error(f"Error removing outgoing requests for {user_id}: {e}")
            return False

    async def remove_incoming_service_requests(self, user_id: str, request_ids: List[str]) -> bool:
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
            logger.error(f"Error removing incoming requests for {user_id}: {e}")
            return False

    async def get_outgoing_service_requests(self, user_id: str) -> List[str]:
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
            logger.error(f"Error getting outgoing requests for {user_id}: {e}")
            return []
    
    async def get_incoming_service_requests(self, user_id: str) -> List[str]:
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
            logger.error(f"Error getting incoming requests for {user_id}: {e}")
            return []

    # --- User Operations ---

    async def get_competencies(self, user_id: str) -> List[str]:
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
                comp_data['id'] = doc.id
                competencies.append(comp_data)
            return competencies
        except Exception as e:
            logger.error(f"Error fetching competencies for {user_id}: {e}")
            return []

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user with competencies from subcollection."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('users').document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                
                # Fetch competencies from subcollection
                competencies = await self.get_competencies(user_id)
                # Override the competencies field with subcollection data
                data['competencies'] = competencies
                
                return data
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    async def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Update user."""
        if not self.db:
            return False
        try:
            # Check if user exists
            user_ref = self._get_collection('users').document(user_id)
            if not user_ref.get().exists:
                logger.warning(f"Cannot update user {user_id}: user does not exist")
                return False
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(user_data, UserUpdateSchema, exclude_unset=True)
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update the document (will fail if document doesn't exist)
            user_ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating {user_id}: {e}")
            return False

    async def create_user(self, user_id: Optional[str] = None, user_data: Dict[str, Any] = None) -> Optional[str]:
        """Create a new user.
        
        Args:
            user_id: The user's ID (typically Firebase UID). If None, auto-generates an ID.
            user_data: User data to create
            
        Returns:
            The user_id if created successfully, None otherwise
        """
        if not self.db:
            return None
        try:
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(user_data, UserSchema)
            
            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(timezone.utc)
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Create the user document
            if user_id:
                # Use provided ID
                self._get_collection('users').document(user_id).set(validated_data)
                return user_id
            else:
                # Auto-generate ID using Firestore
                doc_ref = self._get_collection('users').document()
                doc_ref.set(validated_data)
                return doc_ref.id
        except Exception as e:
            logger.error(f"Error creating user: {e}")
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
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    async def create_competence(self, user_id: str, competence: dict) -> Optional[Dict[str, Any]]:
        """Create a competence for user's competencies subcollection.
        
        Args:
            user_id: The user's ID
            competence: Dictionary with 'title' (required), 'description', 'category', 'price_range' (optional)
            
        Returns:
            The created competence object with auto-generated competence_id, or None if failed
        """
        if not self.db:
            return None
        try:
            title = competence.get('title')
            if not title:
                logger.error(f"Competence missing title for user {user_id}")
                return None
            
            # Generate prefixed competence ID
            competence_id = self._generate_prefixed_id('competence')
            
            # Add document to competencies subcollection with prefixed ID
            competencies_ref = self._get_collection('users').document(user_id).collection('competencies')
            competence_data = {
                'title': title,
                'description': competence.get('description', ''),
                'category': competence.get('category', ''),
                'price_range': competence.get('price_range', ''),
            }
            
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(competence_data, CompetenceSchema)
            
            # Add timestamps after validation
            validated_data['created_at'] = datetime.now()
            validated_data['updated_at'] = datetime.now()
            
            # Use the generated competence_id as the document ID
            competencies_ref.document(competence_id).set(validated_data)
            
            result = validated_data.copy()
            result['competence_id'] = competence_id
            return result
        except Exception as e:
            logger.error(f"Error creating competence for {user_id}: {e}")
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
            logger.error(f"Error removing competence {competence_id} for {user_id}: {e}")
            return False

    async def update_competence(self, user_id: str, competence_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a competence.
        
        Args:
            user_id: The user's ID
            competence_id: The competence document ID to update
            update_data: Data to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            # Check if competence exists
            competence_ref = self._get_collection('users').document(user_id).collection('competencies').document(competence_id)
            if not competence_ref.get().exists:
                logger.warning(f"Cannot update competence {competence_id} for user {user_id}: competence does not exist")
                return False
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, CompetenceUpdateSchema, exclude_unset=True)
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update document in competencies subcollection
            competence_ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating competence {competence_id} for {user_id}: {e}")
            return False

    async def get_competence(self, user_id: str, competence_id: str) -> Optional[Dict[str, Any]]:
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
            logger.error(f"Error getting competence {competence_id} for {user_id}: {e}")
            return None

    # --- Availability Time Operations ---

    async def create_availability_time(
        self,
        user_id: str,
        availability_data: Dict[str, Any],
        competence_id: Optional[str] = None
    ) -> Optional[str]:
        """Create an availability time for a user or competence.
        
        Args:
            user_id: The user's ID
            availability_data: Availability time data
            competence_id: Optional competence ID if this is for a competence subcollection
            
        Returns:
            The generated availability_time_id or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed availability time ID
            availability_time_id = self._generate_prefixed_id('availability_time')
            
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(availability_data, AvailabilityTimeSchema)
            
            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(timezone.utc)
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
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
            return availability_time_id
        except Exception as e:
            logger.error(f"Error creating availability time: {e}")
            return None

    async def get_availability_times(
        self,
        user_id: str,
        competence_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
                data['id'] = doc.id
                availability_times.append(data)
            return availability_times
        except Exception as e:
            logger.error(f"Error fetching availability times: {e}")
            return []

    async def get_availability_time(
        self,
        user_id: str,
        availability_time_id: str,
        competence_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
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
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching availability time {availability_time_id}: {e}")
            return None

    async def update_availability_time(
        self,
        user_id: str,
        availability_time_id: str,
        update_data: Dict[str, Any],
        competence_id: Optional[str] = None
    ) -> bool:
        """Update an availability time.
        
        Args:
            user_id: The user's ID
            availability_time_id: The availability time ID
            update_data: Data to update
            competence_id: Optional competence ID
            
        Returns:
            True if updated successfully, False otherwise
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
            
            if not ref.get().exists:
                logger.warning(
                    f"Cannot update availability time {availability_time_id}: does not exist"
                )
                return False
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(
                update_data,
                AvailabilityTimeUpdateSchema,
                exclude_unset=True
            )
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update document
            ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating availability time {availability_time_id}: {e}")
            return False

    async def delete_availability_time(
        self,
        user_id: str,
        availability_time_id: str,
        competence_id: Optional[str] = None
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
            logger.error(f"Error deleting availability time {availability_time_id}: {e}")
            return False

    # --- Review Operations ---

    async def create_review(self, review_data: Dict[str, Any]) -> Optional[str]:
        """Create a new review.
        
        Args:
            review_data: Review data (should include service_request_id, user_id, reviewer_user_id, rating, etc.)
            
        Returns:
            The generated review_id or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed review ID
            review_id = self._generate_prefixed_id('review')
            
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(review_data, ReviewSchema)
            
            # Add timestamps after validation
            validated_data['created_at'] = datetime.utcnow()
            validated_data['updated_at'] = datetime.utcnow()
            
            # Create document with the prefixed ID
            ref = self._get_collection('reviews').document(review_id)
            ref.set(validated_data)
            return review_id
        except Exception as e:
            logger.error(f"Error creating review: {e}")
            return None

    async def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Get a review by ID."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('reviews').document(review_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting review {review_id}: {e}")
            return None

    async def get_reviews_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all reviews for a user (as reviewee)."""
        if not self.db:
            return []
        try:
            query = self._get_collection('reviews').where('user_id', '==', user_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting reviews for user {user_id}: {e}")
            return []

    async def get_reviews_by_reviewer(self, reviewer_user_id: str) -> List[Dict[str, Any]]:
        """Get all reviews written by a reviewer."""
        if not self.db:
            return []
        try:
            query = self._get_collection('reviews').where('reviewer_user_id', '==', reviewer_user_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting reviews by reviewer {reviewer_user_id}: {e}")
            return []

    async def get_reviews_by_request(self, service_request_id: str) -> List[Dict[str, Any]]:
        """Get all reviews for a service request."""
        if not self.db:
            return []
        try:
            query = self._get_collection('reviews').where('service_request_id', '==', service_request_id)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting reviews for request {service_request_id}: {e}")
            return []

    async def update_review(self, review_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a review."""
        if not self.db:
            return False
        try:
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ReviewUpdateSchema, exclude_unset=True)
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.utcnow()
            
            # Update the document
            ref = self._get_collection('reviews').document(review_id)
            ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating review {review_id}: {e}")
            return False

    async def delete_review(self, review_id: str) -> bool:
        """Delete a review."""
        if not self.db:
            return False
        try:
            self._get_collection('reviews').document(review_id).delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting review {review_id}: {e}")
            return False

    # --- Chat Operations ---

    async def create_chat(self, chat_data: Dict[str, Any]) -> Optional[str]:
        """Create a new chat in root chats collection.
        
        Args:
            chat_data: Chat data (should include service_request_id, provider_candidate_id,
                      seeker_user_id, provider_user_id, and optional title)
            
        Returns:
            The generated chat_id or None if failed
        """
        if not self.db:
            return None
        try:
            # Validate required fields
            required_fields = ['service_request_id', 'provider_candidate_id', 'seeker_user_id', 'provider_user_id']
            for field in required_fields:
                if not chat_data.get(field):
                    logger.error(f"{field} is required for chat creation")
                    return None
            
            # Generate prefixed chat ID
            chat_id = self._generate_prefixed_id('chat')
            
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(chat_data, ChatSchema)
            
            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(timezone.utc)
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Create document in root chats collection
            ref = self._get_collection('chats').document(chat_id)
            ref.set(validated_data)
            return chat_id
        except Exception as e:
            logger.error(f"Error creating chat: {e}")
            return None

    async def get_chat(self, chat_id: str) -> Optional[Dict[str, Any]]:
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
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Error getting chat {chat_id}: {e}")
            return None

    async def get_chats_by_request(self, service_request_id: str) -> List[Dict[str, Any]]:
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
                data = doc.to_dict()
                data['id'] = doc.id
                chats.append(data)
            return chats
        except Exception as e:
            logger.error(f"Error getting chats for request {service_request_id}: {e}")
            return []
    
    async def get_chats_by_user(self, user_id: str) -> List[Dict[str, Any]]:
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
                data = doc.to_dict()
                data['id'] = doc.id
                chats[doc.id] = data
            
            for doc in provider_docs:
                if doc.id not in chats:
                    data = doc.to_dict()
                    data['id'] = doc.id
                    chats[doc.id] = data
            
            return list(chats.values())
        except Exception as e:
            logger.error(f"Error getting chats for user {user_id}: {e}")
            return []

    async def update_chat(self, chat_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a chat in root chats collection.
        
        Args:
            chat_id: The chat ID
            update_data: Data to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            ref = self._get_collection('chats').document(chat_id)
            
            if not ref.get().exists:
                logger.warning(f"Cannot update chat {chat_id}: does not exist")
                return False
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ChatUpdateSchema, exclude_unset=True)
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update the document
            ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating chat {chat_id}: {e}")
            return False

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
            logger.error(f"Error deleting chat {chat_id}: {e}")
            return False

    # --- Chat Message Operations ---

    async def create_chat_message(self, chat_id: str, message_data: Dict[str, Any]) -> Optional[str]:
        """Create a new chat message in a chat's messages subcollection.
        
        Args:
            chat_id: The chat ID
            message_data: Message data (should include sender_user_id, receiver_user_id, message)
            
        Returns:
            The generated chat_message_id or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed message ID
            message_id = self._generate_prefixed_id('chat_message')
            message_data['chat_id'] = chat_id
            
            # Validate data against schema (timestamps excluded)
            validated_data = self._validate_data(message_data, ChatMessageSchema)
            
            # Add timestamps after validation
            validated_data['created_at'] = datetime.now(timezone.utc)
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Create document in messages subcollection under chat
            ref = (self._get_collection('chats')
                   .document(chat_id)
                   .collection('messages')
                   .document(message_id))
            ref.set(validated_data)
            return message_id
        except Exception as e:
            logger.error(f"Error creating chat message in {chat_id}: {e}")
            return None

    async def get_chat_messages(self, chat_id: str, limit: int = 100) -> List[Dict[str, Any]]:
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
            logger.error(f"Error getting messages for chat {chat_id}: {e}")
            return []

    async def get_chat_message(self, chat_id: str, message_id: str) -> Optional[Dict[str, Any]]:
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
            logger.error(f"Error getting message {message_id} from chat {chat_id}: {e}")
            return None

    async def update_chat_message(self, chat_id: str, message_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a chat message.
        
        Args:
            chat_id: The chat ID
            message_id: The message ID
            update_data: Data to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        if not self.db:
            return False
        try:
            ref = (self._get_collection('chats')
                   .document(chat_id)
                   .collection('messages')
                   .document(message_id))
            
            # Validate update data against UpdateSchema (Pydantic filters out 'id' and other non-updatable fields)
            validated_data = self._validate_data(update_data, ChatMessageUpdateSchema, exclude_unset=True)
            
            # Add updated_at timestamp after validation
            validated_data['updated_at'] = datetime.now(timezone.utc)
            
            # Update the document
            ref.update(validated_data)
            return True
        except Exception as e:
            logger.error(f"Error updating message {message_id} in chat {chat_id}: {e}")
            return False

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
            logger.error(f"Error deleting message {message_id} from chat {chat_id}: {e}")
            return False