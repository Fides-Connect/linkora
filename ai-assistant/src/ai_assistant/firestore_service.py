import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

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

    # --- Request Operations ---

    async def get_requests(self, user_id: str) -> List[Dict[str, Any]]:
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
            for req in requests:
                # Add seeker user info
                if 'seeker_user_id' in req:
                    seeker = await self.get_user(req['seeker_user_id'])
                    if seeker and 'name' in seeker:
                        req['seeker_user_name'] = seeker['name']
                        req['seeker_user_initials'] = "".join([n[0] for n in seeker['name'].split() if n]).upper()[:2]
                    else:
                        req['seeker_user_name'] = ''
                        req['seeker_user_initials'] = ''
                
                # Add provider user info
                if 'selected_provider_user_id' in req:
                    provider = await self.get_user(req['selected_provider_user_id'])
                    if provider and 'name' in provider:
                        req['selected_provider_user_name'] = provider['name']
                        req['selected_provider_user_initials'] = "".join([n[0] for n in provider['name'].split() if n]).upper()[:2]
                    else:
                        req['selected_provider_user_name'] = ''
                        req['selected_provider_user_initials'] = ''
            return requests

        except Exception as e:
            logger.error(f"Error fetching requests for user {user_id}: {e}")
            return []

    async def add_service_request(self, request_data: Dict[str, Any]) -> str:
        """Create a new service request."""
        if not self.db:
            return ""
        try:
            # Generate prefixed service request ID
            service_request_id = self._generate_prefixed_id('service_request')
            request_data['service_request_id'] = service_request_id
            
            # Ensure timestamps are set
            if 'createdAt' not in request_data:
                request_data['createdAt'] = datetime.now(timezone.utc)
            if 'created_at' not in request_data:
                request_data['created_at'] = datetime.now(timezone.utc)
            request_data['updated_at'] = datetime.now(timezone.utc)
            
            # Populate provider fields if provider is selected
            if 'selected_provider_user_id' in request_data and request_data['selected_provider_user_id']:
                provider = await self.get_user(request_data['selected_provider_user_id'])
                if provider and 'name' in provider:
                    request_data['selected_provider_user_name'] = provider['name']
                    request_data['selected_provider_user_initials'] = "".join([n[0] for n in provider['name'].split() if n]).upper()[:2]
                else:
                    request_data['selected_provider_user_name'] = ''
                    request_data['selected_provider_user_initials'] = ''
            else:
                # No provider selected, set empty strings
                request_data['selected_provider_user_id'] = ''
                request_data['selected_provider_user_name'] = ''
                request_data['selected_provider_user_initials'] = ''
            
            # Populate seeker fields
            if 'seeker_user_id' in request_data and request_data['seeker_user_id']:
                seeker = await self.get_user(request_data['seeker_user_id'])
                if seeker and 'name' in seeker:
                    request_data['seeker_user_name'] = seeker['name']
                    request_data['seeker_user_initials'] = "".join([n[0] for n in seeker['name'].split() if n]).upper()[:2]
                else:
                    request_data['seeker_user_name'] = ''
                    request_data['seeker_user_initials'] = ''
            
            # Create document with the prefixed ID
            ref = self._get_collection('service_requests').document(service_request_id)
            ref.set(request_data)
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
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching request {request_id}: {e}")
            return None

    async def update_request_status(self, request_id: str, status: str) -> bool:
        """Update request status."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('service_requests').document(request_id)
            ref.update({
                'status': status,
                'updated_at': datetime.now(timezone.utc)
            })
            return True
        except Exception as e:
            logger.error(f"Error updating request status {request_id}: {e}")
            return False

    # --- Favorites Operations ---

    async def get_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch user's favorite users with full user data."""
        if not self.db:
            return []
        try:
            doc = self._get_collection('users').document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                favorite_ids = data.get('favorites', [])
                
                # Fetch full user data for each favorite user ID
                favorite_users = []
                for favorite_id in favorite_ids:
                    user_data = await self.get_user(favorite_id)
                    if user_data:
                        # Transform to match the User model expected by Flutter
                        favorite_users.append({
                            'user_id': user_data.get('user_id', favorite_id),
                            'name': user_data.get('name', ''),
                            'self_introduction': user_data.get('self_introduction', ''),
                            'competencies': user_data.get('competencies', []),
                            'average_rating': user_data.get('average_rating', 0.0),
                            'review_count': user_data.get('review_count', 0),
                            'feedback_positive': user_data.get('feedback_positive', []),
                            'feedback_negative': user_data.get('feedback_negative', [])
                        })
                return favorite_users
            return []
        except Exception as e:
            logger.error(f"Error fetching favorites for {user_id}: {e}")
            return []

    async def add_favorite(self, user_id: str, favorite_user_id: str) -> bool:
        """Add a user to favorites."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('users').document(user_id)
            ref.update({'favorites': firestore.ArrayUnion([favorite_user_id])})
            return True
        except Exception as e:
            logger.error(f"Error adding favorite for {user_id}: {e}")
            return False

    async def remove_favorite(self, user_id: str, favorite_user_id: str) -> bool:
        """Remove a user from favorites."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('users').document(user_id)
            ref.update({'favorites': firestore.ArrayRemove([favorite_user_id])})
            return True
        except Exception as e:
            logger.error(f"Error removing favorite {favorite_user_id} for {user_id}: {e}")
            return False

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
                # Include the document ID as competence_id
                comp_data['competence_id'] = doc.id
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
            # Add updated_at timestamp
            user_data['updated_at'] = datetime.now(timezone.utc)
            # Use set with merge=True to create if not exists or update existing fields
            self._get_collection('users').document(user_id).set(user_data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Error updating {user_id}: {e}")
            return False

    async def add_competence(self, user_id: str, competence: dict) -> Optional[Dict[str, Any]]:
        """Add a competence to user's competencies subcollection.
        
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
                'competence_id': competence_id,
                'title': title,
                'description': competence.get('description', ''),
                'category': competence.get('category', ''),
                'price_range': competence.get('price_range', ''),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            }
            # Use the generated competence_id as the document ID
            competencies_ref.document(competence_id).set(competence_data)
            
            return competence_data
        except Exception as e:
            logger.error(f"Error adding competence for {user_id}: {e}")
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
            review_data['review_id'] = review_id
            
            # Ensure timestamps are set
            if 'created_at' not in review_data:
                review_data['created_at'] = datetime.utcnow()
            review_data['updated_at'] = datetime.utcnow()
            
            # Create document with the prefixed ID
            ref = self._get_collection('reviews').document(review_id)
            ref.set(review_data)
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
            ref = self._get_collection('reviews').document(review_id)
            update_data['updated_at'] = datetime.utcnow()
            ref.update(update_data)
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

    async def create_chat(self, provider_candidate_id: str, chat_data: Dict[str, Any]) -> Optional[str]:
        """Create a new chat as subcollection under provider_candidate.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_data: Chat data (should include title, service_request_id, etc.)
            
        Returns:
            The generated chat_id or None if failed
        """
        if not self.db:
            return None
        try:
            # Validate required fields
            service_request_id = chat_data.get('service_request_id')
            if not service_request_id:
                logger.error("service_request_id is required for chat creation")
                return None
            
            # Generate prefixed chat ID
            chat_id = self._generate_prefixed_id('chat')
            chat_data['chat_id'] = chat_id
            chat_data['provider_candidate_id'] = provider_candidate_id
            
            # Ensure timestamps are set
            if 'created_at' not in chat_data:
                chat_data['created_at'] = datetime.now(timezone.utc)
            chat_data['updated_at'] = datetime.now(timezone.utc)
            
            # Create document in chats subcollection under provider_candidate
            ref = (self._get_collection('requests')
                   .document(service_request_id)
                   .collection('provider_candidates')
                   .document(provider_candidate_id)
                   .collection('chats')
                   .document(chat_id))
            ref.set(chat_data)
            return chat_id
        except Exception as e:
            logger.error(f"Error creating chat: {e}")
            return None

    async def get_chat(self, provider_candidate_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get a chat by ID from provider_candidate subcollection.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
        """
        if not self.db:
            return None
        try:
            # First get the provider_candidate to know the request_id
            candidate_docs = self._get_collection('requests').stream()
            for req_doc in candidate_docs:
                candidate_ref = req_doc.reference.collection('provider_candidates').document(provider_candidate_id)
                candidate_doc = candidate_ref.get()
                if candidate_doc.exists:
                    # Found the provider_candidate, now get the chat
                    chat_ref = candidate_ref.collection('chats').document(chat_id)
                    chat_doc = chat_ref.get()
                    if chat_doc.exists:
                        return chat_doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting chat {chat_id}: {e}")
            return None

    async def get_chats_by_request(self, service_request_id: str) -> List[Dict[str, Any]]:
        """Get all chats for a service request by scanning all provider_candidates."""
        if not self.db:
            return []
        try:
            chats = []
            # Get all provider_candidates for this request
            candidates_ref = (self._get_collection('requests')
                            .document(service_request_id)
                            .collection('provider_candidates'))
            candidates = candidates_ref.stream()
            
            # For each provider_candidate, get all their chats
            for candidate_doc in candidates:
                chats_ref = candidate_doc.reference.collection('chats')
                chat_docs = chats_ref.stream()
                for chat_doc in chat_docs:
                    chats.append(chat_doc.to_dict())
            
            return chats
        except Exception as e:
            logger.error(f"Error getting chats for request {service_request_id}: {e}")
            return []

    async def update_chat(self, provider_candidate_id: str, chat_id: str, service_request_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a chat in provider_candidate subcollection.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
            update_data: Data to update
        """
        if not self.db:
            return False
        try:
            ref = (self._get_collection('service_requests')
                   .document(service_request_id)
                   .collection('provider_candidates')
                   .document(provider_candidate_id)
                   .collection('chats')
                   .document(chat_id))
            update_data['updated_at'] = datetime.now(timezone.utc)
            ref.update(update_data)
            return True
        except Exception as e:
            logger.error(f"Error updating chat {chat_id}: {e}")
            return False

    async def delete_chat(self, provider_candidate_id: str, chat_id: str, service_request_id: str) -> bool:
        """Delete a chat and all its messages from provider_candidate subcollection.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
        """
        if not self.db:
            return False
        try:
            chat_ref = (self._get_collection('service_requests')
                       .document(service_request_id)
                       .collection('provider_candidates')
                       .document(provider_candidate_id)
                       .collection('chats')
                       .document(chat_id))
            
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

    async def create_chat_message(self, provider_candidate_id: str, chat_id: str, service_request_id: str, message_data: Dict[str, Any]) -> Optional[str]:
        """Create a new chat message in a chat's messages subcollection.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
            message_data: Message data (should include sender_user_id, receiver_user_id, message, etc.)
            
        Returns:
            The generated chat_message_id or None if failed
        """
        if not self.db:
            return None
        try:
            # Generate prefixed message ID
            message_id = self._generate_prefixed_id('chat_message')
            message_data['chat_message_id'] = message_id
            message_data['chat_id'] = chat_id
            
            # Ensure timestamps are set
            if 'created_at' not in message_data:
                message_data['created_at'] = datetime.now(timezone.utc)
            message_data['updated_at'] = datetime.now(timezone.utc)
            
            # Create document in messages subcollection
            ref = (self._get_collection('service_requests')
                   .document(service_request_id)
                   .collection('provider_candidates')
                   .document(provider_candidate_id)
                   .collection('chats')
                   .document(chat_id)
                   .collection('messages')
                   .document(message_id))
            ref.set(message_data)
            return message_id
        except Exception as e:
            logger.error(f"Error creating chat message in {chat_id}: {e}")
            return None

    async def get_chat_messages(self, provider_candidate_id: str, chat_id: str, service_request_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all messages for a chat, ordered by time.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
            limit: Maximum number of messages to return
        """
        if not self.db:
            return []
        try:
            messages_ref = (self._get_collection('service_requests')
                           .document(service_request_id)
                           .collection('provider_candidates')
                           .document(provider_candidate_id)
                           .collection('chats')
                           .document(chat_id)
                           .collection('messages'))
            query = messages_ref.limit(limit)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Error getting messages for chat {chat_id}: {e}")
            return []

    async def get_chat_message(self, provider_candidate_id: str, chat_id: str, service_request_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific chat message.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
            message_id: The message ID
        """
        if not self.db:
            return None
        try:
            doc = (self._get_collection('service_requests')
                  .document(service_request_id)
                  .collection('provider_candidates')
                  .document(provider_candidate_id)
                  .collection('chats')
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

    async def update_chat_message(self, provider_candidate_id: str, chat_id: str, service_request_id: str, message_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a chat message.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
            message_id: The message ID
            update_data: Data to update
        """
        if not self.db:
            return False
        try:
            ref = (self._get_collection('service_requests')
                   .document(service_request_id)
                   .collection('provider_candidates')
                   .document(provider_candidate_id)
                   .collection('chats')
                   .document(chat_id)
                   .collection('messages')
                   .document(message_id))
            update_data['updated_at'] = datetime.now(timezone.utc)
            ref.update(update_data)
            return True
        except Exception as e:
            logger.error(f"Error updating message {message_id} in chat {chat_id}: {e}")
            return False

    async def delete_chat_message(self, provider_candidate_id: str, chat_id: str, service_request_id: str, message_id: str) -> bool:
        """Delete a chat message.
        
        Args:
            provider_candidate_id: The provider candidate ID
            chat_id: The chat ID
            service_request_id: The service request ID
            message_id: The message ID
        """
        if not self.db:
            return False
        try:
            (self._get_collection('service_requests')
             .document(service_request_id)
             .collection('provider_candidates')
             .document(provider_candidate_id)
             .collection('chats')
             .document(chat_id)
             .collection('messages')
             .document(message_id)
             .delete())
            return True
        except Exception as e:
            logger.error(f"Error deleting message {message_id} from chat {chat_id}: {e}")
            return False