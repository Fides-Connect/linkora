"""
Unit tests for Firestore schema validation using Pydantic.
"""
import pytest
from datetime import datetime, UTC
from pydantic import ValidationError

from ai_assistant.firestore_schemas import (
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
    ChatMessageUpdateSchema
)


class TestUserSchema:
    """Tests for UserSchema validation."""
    
    def test_valid_user(self):
        """Test valid user data passes validation."""
        user_data = {
            "user_id": "user_123",
            "name": "John Doe",
            "email": "john@example.com",
            "photo_url": "https://example.com/photo.jpg",
            "fcm_token": "fcm_token_123",
            "is_service_provider": True,
            "self_introduction": "Hello!",
            "favorites": ["user_123", "user_456"],
            "average_rating": 4.5,
            "review_count": 10,
            "feedback_positive": ["Punctual", "Professional"],
            "feedback_negative": ["Expensive"],
            "last_sign_in": datetime.now(UTC)
        }
        
        user = UserSchema(**user_data)
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
        assert user.average_rating == 4.5
    
    def test_minimal_user(self):
        """Test minimal valid user data."""
        user_data = {
            "user_id": "user_456",
            "name": "Jane Doe",
            "email": "jane@example.com"
        }
        
        user = UserSchema(**user_data)
        assert user.name == "Jane Doe"
        assert user.email == "jane@example.com"
        assert user.photo_url == ""
        assert user.is_service_provider is False
        assert user.average_rating == 0.0
        assert user.review_count == 0
        assert user.favorites == []
    
    def test_invalid_email(self):
        """Test that invalid email format fails validation."""
        user_data = {
            "name": "John Doe",
            "email": "invalid_email"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UserSchema(**user_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('email',) for error in errors)
    
    def test_missing_required_fields(self):
        """Test that missing required fields fail validation."""
        user_data = {"name": "John Doe"}
        
        with pytest.raises(ValidationError) as exc_info:
            UserSchema(**user_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('email',) for error in errors)
    
    def test_invalid_rating_range(self):
        """Test that rating outside 0-5 range fails validation."""
        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "average_rating": 6.0
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UserSchema(**user_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('average_rating',) for error in errors)
    
    def test_extra_fields_rejected(self):
        """Test that extra fields are rejected (strict mode)."""
        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "unknown_field": "should_fail"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            UserSchema(**user_data)
        
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)


class TestCompetenceSchema:
    """Tests for CompetenceSchema validation."""
    
    def test_valid_competence(self):
        """Test valid competence data passes validation."""
        competence_data = {
            "competence_id": "competence_abc123",
            "title": "Python Programming",
            "description": "Expert in Python",
            "category": "Programming",
            "price_range": "$50-$100/hr"
        }
        
        competence = CompetenceSchema(**competence_data)
        assert competence.title == "Python Programming"
        assert competence.competence_id == "competence_abc123"
    
    def test_minimal_competence(self):
        """Test minimal valid competence data."""
        competence_data = {
            "competence_id": "competence_xyz789",
            "title": "Web Design"
        }
        
        competence = CompetenceSchema(**competence_data)
        assert competence.title == "Web Design"
        assert competence.description == ""
        assert competence.category == ""
    
    def test_invalid_competence_id_prefix(self):
        """Test that competence_id without correct prefix fails."""
        competence_data = {
            "competence_id": "wrong_prefix_abc123",
            "title": "Python Programming"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CompetenceSchema(**competence_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('competence_id',) for error in errors)
    
    def test_missing_title(self):
        """Test that missing title fails validation."""
        competence_data = {
            "competence_id": "competence_abc123"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            CompetenceSchema(**competence_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('title',) for error in errors)


class TestServiceRequestSchema:
    """Tests for ServiceRequestSchema validation."""
    
    def test_valid_service_request(self):
        """Test valid service request data passes validation."""
        request_data = {
            "service_request_id": "service_request_abc123",
            "title": "Need help with plumbing",
            "seeker_user_id": "user_123",
            "selected_provider_user_id": "user_456",
            "status": "pending",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        request = ServiceRequestSchema(**request_data)
        assert request.service_request_id == "service_request_abc123"
        assert request.status == "pending"
    
    def test_minimal_service_request(self):
        """Test minimal valid service request data."""
        request_data = {
            "service_request_id": "service_request_xyz789",
            "title": "Need help with plumbing",
            "seeker_user_id": "user_123",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        request = ServiceRequestSchema(**request_data)
        assert request.seeker_user_id == "user_123"
        assert request.selected_provider_user_id == ""
        assert request.status == "pending"
    
    def test_invalid_service_request_id_prefix(self):
        """Test that service_request_id without correct prefix fails."""
        request_data = {
            "service_request_id": "wrong_abc123",
            "seeker_user_id": "user_123",
            "created_at": datetime.now(UTC)
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceRequestSchema(**request_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('service_request_id',) for error in errors)
    
    def test_invalid_status(self):
        """Test that invalid status value fails validation."""
        request_data = {
            "service_request_id": "service_request_abc123",
            "seeker_user_id": "user_123",
            "status": "invalid_status",
            "created_at": datetime.now(UTC)
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceRequestSchema(**request_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('status',) for error in errors)


class TestReviewSchema:
    """Tests for ReviewSchema validation."""
    
    def test_valid_review(self):
        """Test valid review data passes validation."""
        review_data = {
            "review_id": "review_abc123",
            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating": 4.5,
            "positive_feedback": ["Punctual", "Professional"],
            "negative_feedback": [],
            "comment": "Great service!"
        }
        
        review = ReviewSchema(**review_data)
        assert review.rating == 4.5
        assert len(review.positive_feedback) == 2
    
    def test_minimal_review(self):
        """Test minimal valid review data."""
        review_data = {
            "review_id": "review_xyz789",
            "service_request_id": "service_request_abc",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating": 3.0
        }
        
        review = ReviewSchema(**review_data)
        assert review.rating == 3.0
        assert review.positive_feedback == []
        assert review.comment == ""
    
    def test_invalid_rating_too_low(self):
        """Test that rating below 1 fails validation."""
        review_data = {
            "review_id": "review_abc123",
            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating": 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReviewSchema(**review_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rating',) for error in errors)
    
    def test_invalid_rating_too_high(self):
        """Test that rating above 5 fails validation."""
        review_data = {
            "review_id": "review_abc123",
            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating": 5.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReviewSchema(**review_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rating',) for error in errors)
    
    def test_invalid_review_id_prefix(self):
        """Test that review_id without correct prefix fails."""
        review_data = {
            "review_id": "wrong_abc123",
            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating": 4.0
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReviewSchema(**review_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('review_id',) for error in errors)
    
    def test_empty_user_id(self):
        """Test that empty user_id fails validation."""
        review_data = {
            "review_id": "review_abc123",
            "service_request_id": "service_request_xyz",
            "user_id": "",
            "reviewer_user_id": "user_456",
            "rating": 4.0
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReviewSchema(**review_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('user_id',) for error in errors)


class TestChatSchema:
    """Tests for ChatSchema validation."""
    
    def test_valid_chat(self):
        """Test valid chat data passes validation."""
        chat_data = {
            "chat_id": "chat_abc123",
            "provider_candidate_id": "provider_456",
            "service_request_id": "service_request_xyz",
            "title": "Project Discussion"
        }
        
        chat = ChatSchema(**chat_data)
        assert chat.chat_id == "chat_abc123"
        assert chat.title == "Project Discussion"
    
    def test_minimal_chat(self):
        """Test minimal valid chat data."""
        chat_data = {
            "chat_id": "chat_xyz789",
            "provider_candidate_id": "provider_456",
            "service_request_id": "service_request_abc"
        }
        
        chat = ChatSchema(**chat_data)
        assert chat.title == ""
    
    def test_invalid_chat_id_prefix(self):
        """Test that chat_id without correct prefix fails."""
        chat_data = {
            "chat_id": "wrong_abc123",
            "provider_candidate_id": "provider_456",
            "service_request_id": "service_request_xyz"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ChatSchema(**chat_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('chat_id',) for error in errors)


class TestChatMessageSchema:
    """Tests for ChatMessageSchema validation."""
    
    def test_valid_chat_message(self):
        """Test valid chat message data passes validation."""
        message_data = {
            "chat_message_id": "chat_message_abc123",
            "chat_id": "chat_xyz",
            "sender_user_id": "user_123",
            "receiver_user_id": "user_456",
            "message": "Hello, how are you?"
        }
        
        message = ChatMessageSchema(**message_data)
        assert message.message == "Hello, how are you?"
        assert message.sender_user_id == "user_123"
    
    def test_invalid_chat_message_id_prefix(self):
        """Test that chat_message_id without correct prefix fails."""
        message_data = {
            "chat_message_id": "wrong_abc123",
            "chat_id": "chat_xyz",
            "sender_user_id": "user_123",
            "receiver_user_id": "user_456",
            "message": "Hello!"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageSchema(**message_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('chat_message_id',) for error in errors)
    
    def test_empty_message(self):
        """Test that empty message fails validation."""
        message_data = {
            "chat_message_id": "chat_message_abc123",
            "chat_id": "chat_xyz",
            "sender_user_id": "user_123",
            "receiver_user_id": "user_456",
            "message": ""
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageSchema(**message_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('message',) for error in errors)
    
    def test_empty_user_ids(self):
        """Test that empty user IDs fail validation."""
        message_data = {
            "chat_message_id": "chat_message_abc123",
            "chat_id": "chat_xyz",
            "sender_user_id": "",
            "receiver_user_id": "user_456",
            "message": "Hello!"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageSchema(**message_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('sender_user_id',) for error in errors)


# ===== Update Schema Tests =====

class TestUserUpdateSchema:
    """Tests for UserUpdateSchema validation."""
    
    def test_empty_update(self):
        """Test that empty update data is valid (all fields optional)."""
        update_data = {}
        user_update = UserUpdateSchema(**update_data)
        assert user_update.model_dump(exclude_none=True) == {}
    
    def test_partial_update(self):
        """Test that partial update with some fields is valid."""
        update_data = {
            "name": "Updated Name",
            "email": "updated@example.com"
        }
        user_update = UserUpdateSchema(**update_data)
        assert user_update.name == "Updated Name"
        assert user_update.email == "updated@example.com"
    
    def test_validation_rules_apply(self):
        """Test that validation rules still apply when fields are provided."""
        update_data = {
            "email": "invalid_email"
        }
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('email',) for error in errors)
    
    def test_rating_range_validation(self):
        """Test that rating range validation applies."""
        update_data = {
            "average_rating": 6.0
        }
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('average_rating',) for error in errors)
    
    def test_no_user_id_field(self):
        """Test that user_id is not in update schema."""
        update_data = {
            "user_id": "user_123",  # This should be rejected
            "name": "John"
        }
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)


class TestCompetenceUpdateSchema:
    """Tests for CompetenceUpdateSchema validation."""
    
    def test_empty_update(self):
        """Test that empty update is valid."""
        update_data = {}
        competence_update = CompetenceUpdateSchema(**update_data)
        assert competence_update.model_dump(exclude_none=True) == {}
    
    def test_partial_update(self):
        """Test partial update."""
        update_data = {
            "title": "Updated Title"
        }
        competence_update = CompetenceUpdateSchema(**update_data)
        assert competence_update.title == "Updated Title"
    
    def test_validation_rules_apply(self):
        """Test that min_length validation applies."""
        update_data = {
            "title": ""  # Empty string should fail min_length=1
        }
        with pytest.raises(ValidationError) as exc_info:
            CompetenceUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('title',) for error in errors)
    
    def test_no_id_field(self):
        """Test that competence_id is not in update schema."""
        update_data = {
            "competence_id": "competence_123",
            "title": "Test"
        }
        with pytest.raises(ValidationError) as exc_info:
            CompetenceUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)


class TestServiceRequestUpdateSchema:
    """Tests for ServiceRequestUpdateSchema validation."""
    
    def test_empty_update(self):
        """Test that empty update is valid."""
        update_data = {}
        request_update = ServiceRequestUpdateSchema(**update_data)
        assert request_update.model_dump(exclude_none=True) == {}
    
    def test_status_update(self):
        """Test status update with validation."""
        update_data = {
            "status": "completed"
        }
        request_update = ServiceRequestUpdateSchema(**update_data)
        assert request_update.status == "completed"
    
    def test_invalid_status(self):
        """Test that invalid status fails validation."""
        update_data = {
            "status": "invalid_status"
        }
        with pytest.raises(ValidationError) as exc_info:
            ServiceRequestUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('status',) for error in errors)
    
    def test_no_id_field(self):
        """Test that service_request_id is not in update schema."""
        update_data = {
            "service_request_id": "service_request_123",
            "status": "pending"
        }
        with pytest.raises(ValidationError) as exc_info:
            ServiceRequestUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)


class TestReviewUpdateSchema:
    """Tests for ReviewUpdateSchema validation."""
    
    def test_empty_update(self):
        """Test that empty update is valid."""
        update_data = {}
        review_update = ReviewUpdateSchema(**update_data)
        assert review_update.model_dump(exclude_none=True) == {}
    
    def test_rating_update(self):
        """Test rating update with validation."""
        update_data = {
            "rating": 4.5
        }
        review_update = ReviewUpdateSchema(**update_data)
        assert review_update.rating == 4.5
    
    def test_invalid_rating(self):
        """Test that rating outside range fails."""
        update_data = {
            "rating": 6.0
        }
        with pytest.raises(ValidationError) as exc_info:
            ReviewUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rating',) for error in errors)
    
    def test_comment_update(self):
        """Test comment update."""
        update_data = {
            "comment": "Updated review comment"
        }
        review_update = ReviewUpdateSchema(**update_data)
        assert review_update.comment == "Updated review comment"
    
    def test_no_id_field(self):
        """Test that review_id is not in update schema."""
        update_data = {
            "review_id": "review_123",
            "rating": 4.0
        }
        with pytest.raises(ValidationError) as exc_info:
            ReviewUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)


class TestChatUpdateSchema:
    """Tests for ChatUpdateSchema validation."""
    
    def test_empty_update(self):
        """Test that empty update is valid."""
        update_data = {}
        chat_update = ChatUpdateSchema(**update_data)
        assert chat_update.model_dump(exclude_none=True) == {}
    
    def test_title_update(self):
        """Test title update."""
        update_data = {
            "title": "Updated Chat Title"
        }
        chat_update = ChatUpdateSchema(**update_data)
        assert chat_update.title == "Updated Chat Title"
    
    def test_no_id_fields(self):
        """Test that ID fields are not in update schema."""
        update_data = {
            "chat_id": "chat_123",
            "title": "Test"
        }
        with pytest.raises(ValidationError) as exc_info:
            ChatUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)


class TestChatMessageUpdateSchema:
    """Tests for ChatMessageUpdateSchema validation."""
    
    def test_empty_update(self):
        """Test that empty update is valid."""
        update_data = {}
        message_update = ChatMessageUpdateSchema(**update_data)
        assert message_update.model_dump(exclude_none=True) == {}
    
    def test_message_update(self):
        """Test message content update."""
        update_data = {
            "message": "Updated message content"
        }
        message_update = ChatMessageUpdateSchema(**update_data)
        assert message_update.message == "Updated message content"
    
    def test_empty_message_fails(self):
        """Test that empty message fails validation."""
        update_data = {
            "message": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('message',) for error in errors)
    
    def test_no_id_fields(self):
        """Test that ID fields are not in update schema."""
        update_data = {
            "chat_message_id": "chat_message_123",
            "message": "Test"
        }
        with pytest.raises(ValidationError) as exc_info:
            ChatMessageUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['type'] == 'extra_forbidden' for error in errors)
