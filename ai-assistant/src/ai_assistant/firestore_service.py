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
            # Query where user is the creator (outgoing)
            # Assuming 'creator_id' or similar field. 
            # In the Dart model there is 'userName' which seems to be the creator's name.
            # We need to standardize on user IDs. 
            # For now I will assume requests have 'userId' (creator) and 'providerId' (optional).
            # The prompt implies querying requests relevant to the user.
            
            # Since the Dart code previously used mock data, we define the schema now.
            # Let's assume requests collection is 'requests'.
            
            requests_ref = self._get_collection('requests')
            
            # Requests created by user
            query1 = requests_ref.where(filter=FieldFilter("userId", "==", user_id)).stream()
            for doc in query1:
                data = doc.to_dict()
                data['id'] = doc.id
                requests.append(data)
                
            # Requests where user is the provider/supporter (optional, if we support that flow)
            # query2 = requests_ref.where(filter=FieldFilter("providerId", "==", user_id)).stream()
            # for doc in query2:
            #    data = doc.to_dict()
            #    data['id'] = doc.id
            #    requests.append(data)

            # Deduplicate if necessary (though separate queries shouldn't overlap if roles are distinct)
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
            
            # The Dart client sends fields matching ServiceRequest.toJson()
            # We can save it as is or map it. Saving as is is safer for now.
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
        """Fetch user's favorite supporters."""
        if not self.db:
            return []
        try:
            # Storing favorites in a subcollection 'favorites' under the user document
            # seems appropriate.
            favorites_ref = self._get_collection('users').document(user_id).collection('favorites')
            favorites = []
            for doc in favorites_ref.stream():
                data = doc.to_dict()
                # The doc id should probably be the fav supporter's ID, 
                # or we store the ID in the data.
                if 'id' not in data:
                    data['id'] = doc.id
                favorites.append(data)
            return favorites
        except Exception as e:
            logger.error(f"Error fetching favorites for {user_id}: {e}")
            return []

    async def add_favorite(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Add a supporter to favorites."""
        if not self.db:
            return False
        try:
            supporter_id = profile_data.get('id')
            if not supporter_id:
                return False
            
            ref = self._get_collection('users').document(user_id).collection('favorites').document(supporter_id)
            ref.set(profile_data)
            return True
        except Exception as e:
            logger.error(f"Error adding favorite for {user_id}: {e}")
            return False

    async def remove_favorite(self, user_id: str, favorite_id: str) -> bool:
        """Remove a supporter from favorites."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('users').document(user_id).collection('favorites').document(favorite_id)
            ref.delete()
            return True
        except Exception as e:
            logger.error(f"Error removing favorite {favorite_id} for {user_id}: {e}")
            return False

    # --- Profile Operations ---

    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile."""
        if not self.db:
            return None
        try:
            doc = self._get_collection('users').document(user_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Error getting profile {user_id}: {e}")
            return None

    async def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Update user profile."""
        if not self.db:
            return False
        try:
            # Use set with merge=True to create if not exists or update existing fields
            self._get_collection('users').document(user_id).set(profile_data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Error updating profile {user_id}: {e}")
            return False

    async def add_competence(self, user_id: str, competence: str) -> bool:
        """Add a competence to user profile."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('users').document(user_id)
            # Atomically add to array
            ref.update({'competencies': firestore.ArrayUnion([competence])})
            return True
        except Exception as e:
            logger.error(f"Error adding competence for {user_id}: {e}")
            return False

    async def remove_competence(self, user_id: str, competence: str) -> bool:
        """Remove a competence from user profile."""
        if not self.db:
            return False
        try:
            ref = self._get_collection('users').document(user_id)
            # Atomically remove from array
            ref.update({'competencies': firestore.ArrayRemove([competence])})
            return True
        except Exception as e:
            logger.error(f"Error removing competence for {user_id}: {e}")
            return False
