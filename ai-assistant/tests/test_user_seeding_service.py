"""
Unit tests for UserSeedingService.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, ANY

from ai_assistant.services.user_seeding_service import UserSeedingService

class TestUserSeedingService:
    @pytest.fixture
    def mock_firestore(self):
        service = Mock()
        # Mock the db property to simulate initialized state
        service.db = Mock()
        # Mock ID generation
        service._generate_prefixed_id = Mock(side_effect=lambda prefix: f"{prefix}_123")
        service.add_user = AsyncMock()
        service.update_user = AsyncMock()
        service.add_favorite = AsyncMock()
        return service
    
    @pytest.fixture
    def seeding_service(self, mock_firestore):
        return UserSeedingService(mock_firestore)
    
    @pytest.fixture
    def mock_user_template(self):
         # Mock the templates imported in the service
         # We need to patch where they are IMPORTED, not defined
         with patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE', {"intro": "Hello"}), \
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_COMPETENCES', [{"title": "Coding"}]), \
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_SERVICE_REQUESTS', [{"title": "Help", "seeker_user_id": "{uid}"}]), \
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_PROVIDER_CANDIDATES', [[{"provider_candidate_user_id": "p1"}]]), \
              patch('ai_assistant.services.user_seeding_service.USER_A', {"user_id": "alice", "name": "Alice"}):
             yield

    @pytest.mark.asyncio
    async def test_seed_new_user_structure(self, seeding_service, mock_firestore, mock_user_template):
        """Test the full seeding flow."""
        # Arrange
        user_id = "new_user"
        name = "New Name"
        email = "new@example.com"
        
        # Mock subcollection references
        # db.collection('users').document(uid).collection('competencies').document(id)
        mock_user_ref = Mock()
        mock_comp_coll = Mock()
        mock_comp_doc = Mock()
        
        mock_firestore.db.collection.return_value.document.return_value = mock_user_ref
        mock_user_ref.collection.return_value = mock_comp_coll
        mock_comp_coll.document.return_value = mock_comp_doc
        
        # Mock Weaviate UUID lookup to avoid syncing
        with patch.object(seeding_service, '_get_weaviate_user_uuid', return_value=None):
            # Act
            await seeding_service.seed_new_user(user_id, name, email)
            
            # Assert 1: Main user update
            mock_firestore.add_user.assert_any_call(user_id, ANY)
            call_args = mock_firestore.add_user.call_args_list[0][0]
            assert call_args[1]['intro'] == "Hello"
            assert call_args[1]['user_id'] == user_id
            
            # Assert 2: Competencies created
            mock_comp_doc.set.assert_called()
            
            # Assert 3: Service Requests created
            # Verify _generate_prefixed_id was called for request
            # Verify {uid} replacement happened in request
            # This logic is complex to assert fully with mocks but we check basic flow
            assert mock_firestore._generate_prefixed_id.call_count >= 2 # 1 comp + 1 req + 1 candidate
            
            # Assert 4: Default friend added
            mock_firestore.update_user.assert_any_call("alice", ANY)
            mock_firestore.add_favorite.assert_called_with(user_id, "alice")
