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
        service.create_availability_time = AsyncMock(return_value={"availability_time_id": "avail_123"})
        service.create_competence = AsyncMock(return_value={"competence_id": "comp_123"})
        service.create_service_request = AsyncMock(return_value={"service_request_id": "req_123"})
        service.create_provider_candidate = AsyncMock(return_value={"candidate_id": "cand_123"})
        service.add_outgoing_service_requests = AsyncMock()
        service.add_incoming_service_requests = AsyncMock()
        service.create_chat = AsyncMock(return_value={"chat_id": "chat_123"})
        service.create_chat_message = AsyncMock(return_value={"chat_message_id": "msg_123"})
        service.create_review = AsyncMock(return_value={"review_id": "review_123"})
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
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_CHATS', [{"request_index": 0, "seeker_user_id": "{uid}", "provider_user_id": "p1", "title": "Test Chat"}]), \
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_CHAT_MESSAGES', [[{"sender_user_id": "{uid}", "receiver_user_id": "p1", "message": "Hello"}]]), \
              patch('ai_assistant.services.user_seeding_service.USER_TEMPLATE_REVIEWS', [{"request_index": 0, "user_id": "{uid}", "reviewer_user_id": "user_eva_005", "feedback_raw": "Great!", "feedback_positive": ["Fast"], "feedback_negative": [], "rating_reliance": 5.0, "rating_quality": 5.0, "rating_competence": 5.0, "rating_response_speed": 5.0}]), \
              patch('ai_assistant.services.user_seeding_service.USER_A', {"id": "user_alice_001", "name": "Alice"}):
             yield

    @pytest.mark.asyncio
    async def test_seed_new_user_structure(self, seeding_service, mock_firestore, mock_user_template):
        """Test the full seeding flow."""
        # Arrange
        user_id = "new_user"
        name = "New Name"
        email = "new@example.com"
        
        # Mock HubSpokeIngestion to avoid actual Weaviate calls
        with patch('ai_assistant.services.user_seeding_service.HubSpokeIngestion.create_user_with_competencies') as mock_hub_spoke:
            mock_hub_spoke.return_value = {
                "user_uuid": "test_uuid",
                "competence_uuids": ["comp_uuid_1"]
            }
            
            # Act
            await seeding_service.seed_new_user(user_id, name, email)
            
            # Assert 1: Main user update
            mock_firestore.create_user.assert_any_call(user_id, ANY)
            call_args = mock_firestore.create_user.call_args_list[0][0]
            assert call_args[1]['intro'] == "Hello"
            
            # Assert 2: Competencies created via service layer
            mock_firestore.create_competence.assert_called()
            
            # Assert 3: HubSpokeIngestion called for Weaviate sync
            mock_hub_spoke.assert_called_once()
            
            # Assert 4: Service Requests created via service layer
            mock_firestore.create_service_request.assert_called()
            
            # Assert 5: Provider candidates created via service layer
            mock_firestore.create_provider_candidate.assert_called()
            
            # Assert 6: Chats created via service layer
            mock_firestore.create_chat.assert_called()
            
            # Assert 7: Chat messages created via service layer
            mock_firestore.create_chat_message.assert_called()
            
            # Assert 8: Default friend added
            mock_firestore.update_user.assert_any_call("user_alice_001", ANY)
            mock_firestore.add_favorite.assert_called_with(user_id, "user_alice_001")

    @pytest.mark.asyncio
    async def test_seed_new_user_with_enricher(self, seeding_service, mock_firestore, mock_user_template):
        """Enricher path: enrich() is called per competency, summary persisted to Firestore."""
        user_id = "new_user"
        mock_enricher = AsyncMock()
        mock_enricher.enrich = AsyncMock(return_value={
            "title": "Flutter",
            "description": "Mobile app development using Flutter.",
            "category": "IT",
            "price_range": "$90-$180/hour",
            "year_of_experience": 3,
            "feedback_positive": [],
            "feedback_negative": [],
            "search_optimized_summary": "Expert Flutter developer for cross-platform mobile apps.",
            "skills_list": ["flutter", "dart", "mobile development"],
            "price_per_hour": 135.0,
        })
        mock_firestore.update_competence = AsyncMock(return_value={"competence_id": "comp_123"})

        with patch('ai_assistant.services.user_seeding_service.HubSpokeIngestion.create_user_with_competencies') as mock_hub_spoke:
            mock_hub_spoke.return_value = {"user_uuid": "test_uuid", "competence_uuids": ["comp_uuid_1"]}

            await seeding_service.seed_new_user(user_id, "New", "n@e.com", enricher=mock_enricher)

            # Enricher called once per template competency
            mock_enricher.enrich.assert_called_once()

            # Enriched fields persisted back to Firestore
            mock_firestore.update_competence.assert_called_once_with(
                user_id,
                "comp_123",
                ANY,  # dict with search_optimized_summary / skills_list / price_per_hour
            )
            update_kwargs = mock_firestore.update_competence.call_args[0][2]
            assert update_kwargs.get("search_optimized_summary") == "Expert Flutter developer for cross-platform mobile apps."
            assert "flutter" in update_kwargs.get("skills_list", [])

            # Weaviate payload contains enriched summary
            hub_call_competencies = mock_hub_spoke.call_args[1]["competencies_data"]
            assert hub_call_competencies[0]["search_optimized_summary"] == \
                "Expert Flutter developer for cross-platform mobile apps."
