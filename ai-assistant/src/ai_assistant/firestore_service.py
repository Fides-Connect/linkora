import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import firebase_admin
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

    # --- Request Operations ---

    async def get_requests(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch incoming and outgoing service requests involving the user."""
        if not self.db:
            return []
        
        requests = []
        try:         
            requests_ref = self._get_collection('requests')
            
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

    async def create_request(self, request_data: Dict[str, Any]) -> str:
        """Create a new service request."""
        if not self.db:
            return ""
        try:
            # Ensure timestamps are set
            if 'createdAt' not in request_data:
                request_data['createdAt'] = datetime.utcnow()
            update_time, ref = self._get_collection('requests').add(request_data)
            return ref.id
        except Exception as e:
            logger.error(f"Error creating request: {e}")
            return ""

    async def update_request_status(self, request_id: str, status: str) -> bool:
        """Update request status."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('requests').document(request_id)
            ref.update({'status': status})
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
                            'introduction': user_data.get('introduction', ''),
                            'competencies': user_data.get('competencies', []),
                            'average_rating': user_data.get('average_rating', 0.0),
                            'review_count': user_data.get('review_count', 0),
                            'positive_feedback': user_data.get('positive_feedback', []),
                            'negative_feedback': user_data.get('negative_feedback', [])
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
                # Extract just the title for the User model
                if 'title' in comp_data:
                    competencies.append(comp_data['title'])
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
            # Use set with merge=True to create if not exists or update existing fields
            self._get_collection('users').document(user_id).set(user_data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Error updating {user_id}: {e}")
            return False

    async def add_competence(self, user_id: str, competence: dict) -> bool:
        """Add a competence to user's competencies subcollection.
        
        Args:
            user_id: The user's ID
            competence: Dictionary with 'title' (required), 'description', 'category', 'price_range' (optional)
        """
        if not self.db:
            return False
        try:
            title = competence.get('title')
            if not title:
                logger.error(f"Competence missing title for user {user_id}")
                return False
            
            # Add document to competencies subcollection
            competencies_ref = self._get_collection('users').document(user_id).collection('competencies')
            # Use the competence title as the document ID
            competence_data = {
                'title': title,
                'description': competence.get('description', ''),
                'category': competence.get('category', ''),
                'price_range': competence.get('price_range', ''),
            }
            competencies_ref.document(title).set(competence_data)
            return True
        except Exception as e:
            logger.error(f"Error adding competence for {user_id}: {e}")
            return False

    async def remove_competence(self, user_id: str, competence: str) -> bool:
        """Remove a competence from user's competencies subcollection."""
        if not self.db:
            return False
        try:
            # Delete document from competencies subcollection
            competencies_ref = self._get_collection('users').document(user_id).collection('competencies')
            competencies_ref.document(competence).delete()
            return True
        except Exception as e:
            logger.error(f"Error removing competence for {user_id}: {e}")
            return False
