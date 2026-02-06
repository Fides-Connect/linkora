import logging
import copy
import sys
import os

# Ensure tests can be imported by adding project root to sys.path
# This is required because test_database_data is in the tests folder
# which is not a standard package.

# Assuming we are in src/ai_assistant/services/
# We want to add /app/ (root) to path to be able to import tests.*
# In typical detailed structure: /app/src/ai_assistant/services
current_dir = os.path.dirname(os.path.abspath(__file__))
# up to ai_assistant, up to src, up to root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ..firestore_service import FirestoreService

try:
    from tests.test_database_data import USER_TEMPLATE, USER_TEMPLATE_SERVICE_REQUESTS, USER_TEMPLATE_COMPETENCES, USER_A
except ImportError:
    # Fallback or error if tests are not present (e.g. lean docker build)
    # Ideally tests/test_database_data.py should be moved to src/ if it's needed here.
    logging.getLogger(__name__).error("Could not import USER_TEMPLATE from tests.test_database_data")
    USER_TEMPLATE = {}
    USER_TEMPLATE_SERVICE_REQUESTS = []
    USER_TEMPLATE_COMPETENCES = []
    USER_A = {}

logger = logging.getLogger(__name__)

class UserSeedingService:
    """Service to auto-seed data for new users."""

    def __init__(self, firestore_service: FirestoreService):
        self.firestore_service = firestore_service

    async def seed_new_user(self, user_id: str, name: str, email: str):
        """Seed initial data for a new user if not already present."""
        if not self.firestore_service.db:
            logger.warning("Firestore not initialized, skipping seeding.")
            return

        logger.info(f"Seeding data for new user: {user_id} ({name})")
        
        # Prepare data from template
        initials = "".join([n[0] for n in name.split() if n]).upper()[:2]
        
        # 1. Update User with Template Defaults (intro, competencies, feedback)
        user_update = {k: v for k, v in USER_TEMPLATE.items()}
        user_update['competencies'] = USER_TEMPLATE_COMPETENCES
        
        # We use the existing update_user_user method which does a set with merge=True
        await self.firestore_service.update_user(user_id, user_update)
        
        # 2. Create Sample Requests
        requests = USER_TEMPLATE_SERVICE_REQUESTS
        for req in requests:
            # Create a deep copy to modify
            req_data = copy.deepcopy(req)
            
            # Format dynamic values
            req_id = req_data["service_request_id"].format(uid=user_id)
            req_data["service_request_id"] = req_id
            req_data["userId"] = user_id
            req_data["user_name"] = req_data["user_name"].format(name=name)
            req_data["user_initials"] = req_data["user_initials"].format(initials=initials)
            
            try:
                requests_ref = self.firestore_service.db.collection('requests') # access public prop
                requests_ref.document(req_id).set(req_data, merge=True)
                logger.info(f"Created seed request: {req_id}")
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
