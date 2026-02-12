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
        service.create_user = AsyncMock()
        service.update_user = AsyncMock()
        service.add_favorite = AsyncMock()
        service.create_availability_time = AsyncMock(return_value="avail_123")
        service.create_competence = AsyncMock(return_value={"competence_id": "comp_123"})
        service.create_service_request = AsyncMock(return_value="req_123")
        service.create_provider_candidate = AsyncMock(return_value="cand_123")
        service.add_outgoing_service_requests = AsyncMock()
        service.add_incoming_service_requests = AsyncMock()
        return service
    
    @pytest.fixture
    def seeding_service(self, mock_firestore):
        return UserSeedingService(mock_firestore)
    
    @pytest.fixture
    def mock_user_template(self):
         # Mock the templates imported in the service
         # We need to patch where they are IMPORTED, not defined
         with patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE', {"intro": "Hello"}), \
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_COMPETENCIES', [{"title": "Coding"}]), \
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
        
        # Mock Weaviate UUID lookup to avoid syncing
        with patch.object(seeding_service, '_get_weaviate_user_uuid', return_value=None):
            # Act
            await seeding_service.seed_new_user(user_id, name, email)
            
            # Assert 1: Main user update
            mock_firestore.create_user.assert_any_call(user_id, ANY)
            call_args = mock_firestore.create_user.call_args_list[0][0]
            assert call_args[1]['intro'] == "Hello"
            assert call_args[1]['user_id'] == user_id
            
            # Assert 2: Competencies created via service layer
            mock_firestore.create_competence.assert_called()
            
            # Assert 3: Service Requests created via service layer
            mock_firestore.create_service_request.assert_called()
            
            # Assert 4: Provider candidates created via service layer
            mock_firestore.create_provider_candidate.assert_called()
            
            # Assert 5: Default friend added
            mock_firestore.update_user.assert_any_call("alice", ANY)
            mock_firestore.add_favorite.assert_called_with(user_id, "alice")
