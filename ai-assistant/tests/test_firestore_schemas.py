"""
Unit tests for Firestore schema validation using Pydantic.
"""
import pytest
from datetime import datetime, timedelta, UTC
from pydantic import ValidationError

from ai_assistant.firestore_schemas import (
    UserSchema,
    UserUpdateSchema,
    CompetenceSchema,
    CompetenceUpdateSchema,
    AvailabilityTimeSchema,
    AvailabilityTimeUpdateSchema,
    TimeRangeSchema,
    derive_availability_tags,
    ServiceRequestSchema,
    ServiceRequestUpdateSchema,
    ReviewSchema,
    ReviewUpdateSchema,
    ChatSchema,
    ChatUpdateSchema,
    ChatMessageSchema,
    ChatMessageUpdateSchema,
    PROVIDER_PITCH_OPT_OUT_SENTINEL,
)


class TestUserSchema:
    """Tests for UserSchema validation."""
    
    def test_valid_user(self):
        """Test valid user data passes validation."""
        user_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "photo_url": "https://example.com/photo.jpg",
            "fcm_token": "fcm_token_123",
            "is_service_provider": True,
            "self_introduction": "Hello!",
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


# ─────────────────────────────────────────────────────────────────────────────
# Provider pitch timestamp field
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderPitchTimestamp:
    """Tests for last_time_asked_being_provider field and opt-out sentinel."""

    def test_sentinel_constant_is_far_future(self):
        assert PROVIDER_PITCH_OPT_OUT_SENTINEL == datetime(9999, 1, 1, tzinfo=UTC)

    def test_user_schema_defaults_to_none(self):
        user = UserSchema(name="A", email="a@b.com")
        assert user.last_time_asked_being_provider is None

    def test_user_schema_accepts_datetime(self):
        ts = datetime(2026, 1, 1, 12, 0, 0)
        user = UserSchema(name="A", email="a@b.com", last_time_asked_being_provider=ts)
        assert user.last_time_asked_being_provider == ts

    def test_user_schema_accepts_opt_out_sentinel(self):
        user = UserSchema(
            name="A", email="a@b.com",
            last_time_asked_being_provider=PROVIDER_PITCH_OPT_OUT_SENTINEL,
        )
        assert user.last_time_asked_being_provider == datetime(9999, 1, 1, tzinfo=UTC)

    def test_user_update_schema_defaults_to_none(self):
        update = UserUpdateSchema()
        assert update.last_time_asked_being_provider is None

    def test_user_update_schema_accepts_datetime(self):
        ts = datetime(2025, 6, 15)
        update = UserUpdateSchema(last_time_asked_being_provider=ts)
        assert update.last_time_asked_being_provider == ts

    def test_user_update_schema_accepts_sentinel(self):
        update = UserUpdateSchema(
            last_time_asked_being_provider=PROVIDER_PITCH_OPT_OUT_SENTINEL
        )
        assert update.last_time_asked_being_provider == datetime(9999, 1, 1, tzinfo=UTC)

    def test_user_schema_dumps_timestamp_field(self):
        ts = datetime(2026, 2, 22, 10, 0, 0)
        user = UserSchema(name="A", email="a@b.com", last_time_asked_being_provider=ts)
        d = user.model_dump()
        assert d["last_time_asked_being_provider"] == ts


class TestCompetenceSchema:
    """Tests for CompetenceSchema validation."""
    
    def test_valid_competence(self):
        """Test valid competence data passes validation."""
        competence_data = {
            "title": "Python Programming",
            "description": "Expert in Python",
            "category": "Programming",
            "price_range": "$50-$100/hr"
        }
        
        competence = CompetenceSchema(**competence_data)
        assert competence.title == "Python Programming"
    
    def test_minimal_competence(self):
        """Test minimal valid competence data."""
        competence_data = {
            "title": "Web Design"
        }
        
        competence = CompetenceSchema(**competence_data)
        assert competence.title == "Web Design"
        assert competence.description == ""
        assert competence.category == ""
    
    def test_missing_title(self):
        """Test that missing title fails validation."""
        competence_data = {}
        
        with pytest.raises(ValidationError) as exc_info:
            CompetenceSchema(**competence_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('title',) for error in errors)

    def test_rejects_availability_text_flat_field(self):
        """availability_text is no longer part of the schema; it must be rejected."""
        with pytest.raises(ValidationError):
            CompetenceSchema(title="X", availability_text="weekends")

    def test_rejects_availability_tags_flat_field(self):
        """availability_tags is no longer part of the schema; it must be rejected."""
        with pytest.raises(ValidationError):
            CompetenceSchema(title="X", availability_tags=["weekend"])


# ─────────────────────────────────────────────────────────────────────────────
# AvailabilityTimeSchema / TimeRangeSchema
# ─────────────────────────────────────────────────────────────────────────────

class TestAvailabilityTimeSchema:
    """Tests for AvailabilityTimeSchema and TimeRangeSchema validation."""

    def test_valid_single_day(self):
        data = {"monday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}]}
        schema = AvailabilityTimeSchema(**data)
        assert len(schema.monday_time_ranges) == 1
        assert schema.monday_time_ranges[0].start_time == "09:00"

    def test_valid_absence_days(self):
        data = {"absence_days": ["2026-03-15", "2026-12-25"]}
        schema = AvailabilityTimeSchema(**data)
        assert "2026-03-15" in schema.absence_days

    def test_invalid_absence_day_format_rejected(self):
        """absence_days must be YYYY-MM-DD; other formats raise ValidationError."""
        with pytest.raises(ValidationError):
            AvailabilityTimeSchema(absence_days=["15/03/2026"])

    def test_invalid_time_format_rejected(self):
        """TimeRangeSchema requires HH:MM pattern; free-form strings must fail."""
        with pytest.raises(ValidationError):
            AvailabilityTimeSchema(
                monday_time_ranges=[{"start_time": "not-a-time", "end_time": "17:00"}]
            )

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            AvailabilityTimeSchema(unknown_day_ranges=[{"start_time": "09:00", "end_time": "12:00"}])

    def test_empty_schema_valid(self):
        """All fields are optional; an empty dict must pass."""
        schema = AvailabilityTimeSchema()
        assert schema.monday_time_ranges == []
        assert schema.absence_days == []

    def test_multiple_ranges_per_day(self):
        data = {
            "tuesday_time_ranges": [
                {"start_time": "08:00", "end_time": "12:00"},
                {"start_time": "14:00", "end_time": "18:00"},
            ]
        }
        schema = AvailabilityTimeSchema(**data)
        assert len(schema.tuesday_time_ranges) == 2


# ─────────────────────────────────────────────────────────────────────────────
# derive_availability_tags
# ─────────────────────────────────────────────────────────────────────────────

class TestDeriveAvailabilityTags:
    """Tests for the pure derive_availability_tags() helper."""

    def test_empty_dict_returns_empty_list(self):
        assert derive_availability_tags({}) == []

    def test_monday_morning_produces_correct_tags(self):
        data = {"monday_time_ranges": [{"start_time": "09:00", "end_time": "12:00"}]}
        tags = derive_availability_tags(data)
        assert "monday" in tags
        assert "weekday" in tags
        assert "morning" in tags
        assert "weekend" not in tags

    def test_saturday_afternoon_produces_correct_tags(self):
        data = {"saturday_time_ranges": [{"start_time": "14:00", "end_time": "17:00"}]}
        tags = derive_availability_tags(data)
        assert "saturday" in tags
        assert "weekend" in tags
        assert "afternoon" in tags
        assert "weekday" not in tags

    def test_evening_tag_for_late_start(self):
        data = {"thursday_time_ranges": [{"start_time": "18:00", "end_time": "20:00"}]}
        tags = derive_availability_tags(data)
        assert "evening" in tags
        assert "thursday" in tags
        assert "weekday" in tags

    def test_multiple_days_produces_weekday_and_weekend(self):
        data = {
            "monday_time_ranges": [{"start_time": "09:00", "end_time": "12:00"}],
            "saturday_time_ranges": [{"start_time": "10:00", "end_time": "14:00"}],
        }
        tags = derive_availability_tags(data)
        assert "weekday" in tags
        assert "weekend" in tags
        assert "monday" in tags
        assert "saturday" in tags

    def test_absence_days_produce_absence_tags(self):
        data = {"absence_days": ["2026-03-15", "2026-12-25"]}
        tags = derive_availability_tags(data)
        assert "absence:2026-03-15" in tags
        assert "absence:2026-12-25" in tags

    def test_all_tags_are_lowercase(self):
        data = {"wednesday_time_ranges": [{"start_time": "14:00", "end_time": "16:00"}]}
        tags = derive_availability_tags(data)
        for tag in tags:
            assert tag == tag.lower(), f"Tag not lowercase: {tag!r}"

    def test_tags_are_deduplicated(self):
        """Two morning slots on the same day should not produce duplicate tags."""
        data = {
            "friday_time_ranges": [
                {"start_time": "08:00", "end_time": "10:00"},
                {"start_time": "10:00", "end_time": "12:00"},
            ]
        }
        tags = derive_availability_tags(data)
        assert tags.count("morning") == 1
        assert tags.count("friday") == 1


    """Tests for ServiceRequestSchema validation."""
    
    def test_valid_service_request(self):
        """Test valid service request data passes validation."""
        request_data = {
            "title": "Need help with plumbing",
            "seeker_user_id": "user_123",
            "selected_provider_user_id": "user_456",
            "status": "pending",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        request = ServiceRequestSchema(**request_data)
        assert request.seeker_user_id == "user_123"
        assert request.selected_provider_user_id == "user_456"
        assert request.status == "pending"
    
    def test_minimal_service_request(self):
        """Test minimal valid service request data."""
        request_data = {
            "title": "Need help with plumbing",
            "seeker_user_id": "user_123",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        request = ServiceRequestSchema(**request_data)
        assert request.seeker_user_id == "user_123"
        assert request.selected_provider_user_id == ""
        assert request.status == "pending"
    
    def test_invalid_status(self):
        """Test that invalid status value fails validation."""
        request_data = {
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
            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "feedback_positive": ["Punctual", "Professional"],
            "feedback_negative": [],
            "rating_quality": 4.5
        }
        
        review = ReviewSchema(**review_data)
        assert review.rating_quality == 4.5
        assert len(review.feedback_positive) == 2
    
    def test_minimal_review(self):
        """Test minimal valid review data."""
        review_data = {
            "service_request_id": "service_request_abc",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating_reliance": 3.0
        }
        
        review = ReviewSchema(**review_data)
        assert review.rating_reliance == 3.0
        assert review.feedback_positive == []
        assert review.feedback_negative == []
    
    def test_invalid_rating_too_low(self):
        """Test that rating below 1 fails validation."""
        review_data = {
            "review_id": "review_abc123",
            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating_reliance": 0.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReviewSchema(**review_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rating_reliance',) for error in errors)
    
    def test_invalid_rating_too_high(self):
        """Test that rating above 5 fails validation."""
        review_data = {

            "service_request_id": "service_request_xyz",
            "user_id": "user_123",
            "reviewer_user_id": "user_456",
            "rating_response_speed": 5.5
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReviewSchema(**review_data)
        
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rating_response_speed',) for error in errors)
    
    def test_empty_user_id(self):
        """Test that empty user_id fails validation."""
        review_data = {
            "service_request_id": "service_request_xyz",
            "user_id": "",
            "reviewer_user_id": "user_456",
            "rating_competence": 4.0
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
            "provider_candidate_id": "provider_456",
            "service_request_id": "service_request_xyz",
            "seeker_user_id": "user_seeker_123",
            "provider_user_id": "user_provider_456",
            "title": "Project Discussion"
        }
        
        chat = ChatSchema(**chat_data)
        assert chat.title == "Project Discussion"
        assert chat.seeker_user_id == "user_seeker_123"
        assert chat.provider_user_id == "user_provider_456"
    
    def test_minimal_chat(self):
        """Test minimal valid chat data."""
        chat_data = {
            "provider_candidate_id": "provider_456",
            "service_request_id": "service_request_abc",
            "seeker_user_id": "user_seeker_123",
            "provider_user_id": "user_provider_456"
        }
        
        chat = ChatSchema(**chat_data)
        assert chat.title == ""


class TestChatMessageSchema:
    """Tests for ChatMessageSchema validation."""
    
    def test_valid_chat_message(self):
        """Test valid chat message data passes validation."""
        message_data = {
            "chat_id": "chat_xyz",
            "sender_user_id": "user_123",
            "receiver_user_id": "user_456",
            "message": "Hello, how are you?"
        }
        
        message = ChatMessageSchema(**message_data)
        assert message.message == "Hello, how are you?"
        assert message.sender_user_id == "user_123"
    
    def test_empty_message(self):
        """Test that empty message fails validation."""
        message_data = {
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
    
    def test_id_and_extra_fields_ignored(self):
        """Test that id and extra fields are silently ignored."""
        update_data = {
            "id": "user_123",  # Should be ignored
            "user_id": "user_456",  # Should be ignored
            "name": "John",
            "email": "john@example.com",
            "unknown_field": "ignored"  # Should be ignored
        }
        user_update = UserUpdateSchema(**update_data)
        result = user_update.model_dump(exclude_unset=True)
        # Only name and email should be in the result
        assert result == {"name": "John", "email": "john@example.com"}
        assert "id" not in result
        assert "user_id" not in result
        assert "unknown_field" not in result


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
    
    def test_id_and_extra_fields_ignored(self):
        """Test that id and extra fields are silently ignored."""
        update_data = {
            "id": "competence_123",  # Should be ignored
            "competence_id": "competence_456",  # Should be ignored
            "title": "Test",
            "unknown_field": "ignored"  # Should be ignored
        }
        competence_update = CompetenceUpdateSchema(**update_data)
        result = competence_update.model_dump(exclude_unset=True)
        # Only title should be in the result
        assert result == {"title": "Test"}
        assert "id" not in result
        assert "competence_id" not in result
        assert "unknown_field" not in result


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
    
    def test_id_and_extra_fields_ignored(self):
        """Test that id and extra fields are silently ignored."""
        update_data = {
            "id": "service_request_123",  # Should be ignored
            "service_request_id": "service_request_456",  # Should be ignored
            "status": "pending",
            "unknown_field": "ignored"  # Should be ignored
        }
        request_update = ServiceRequestUpdateSchema(**update_data)
        result = request_update.model_dump(exclude_unset=True)
        # Only status should be in the result
        assert result == {"status": "pending"}
        assert "id" not in result
        assert "service_request_id" not in result
        assert "unknown_field" not in result


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
            "rating_competence": 4.5
        }
        review_update = ReviewUpdateSchema(**update_data)
        assert review_update.rating_competence == 4.5
    
    def test_invalid_rating(self):
        """Test that rating outside range fails."""
        update_data = {
            "rating_quality": 6.0
        }
        with pytest.raises(ValidationError) as exc_info:
            ReviewUpdateSchema(**update_data)
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('rating_quality',) for error in errors)
    
    def test_feedback_raw_update(self):
        """Test feedback_raw update."""
        update_data = {
            "feedback_raw": "Updated review feedback"
        }
        review_update = ReviewUpdateSchema(**update_data)
        assert review_update.feedback_raw == "Updated review feedback"
    
    def test_id_and_extra_fields_ignored(self):
        """Test that id and extra fields are silently ignored."""
        update_data = {
            "id": "review_123",  # Should be ignored
            "review_id": "review_456",  # Should be ignored
            "rating_competence": 4.0,
            "unknown_field": "ignored"  # Should be ignored
        }
        review_update = ReviewUpdateSchema(**update_data)
        result = review_update.model_dump(exclude_unset=True)
        # Only rating_competence should be in the result
        assert result == {"rating_competence": 4.0}
        assert "id" not in result
        assert "review_id" not in result
        assert "unknown_field" not in result


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
    
    def test_id_and_extra_fields_ignored(self):
        """Test that id and extra fields are silently ignored."""
        update_data = {
            "id": "chat_123",  # Should be ignored
            "chat_id": "chat_456",  # Should be ignored
            "title": "Test",
            "unknown_field": "ignored"  # Should be ignored
        }
        chat_update = ChatUpdateSchema(**update_data)
        result = chat_update.model_dump(exclude_unset=True)
        # Only title should be in the result
        assert result == {"title": "Test"}
        assert "id" not in result
        assert "chat_id" not in result
        assert "unknown_field" not in result


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
    
    def test_id_and_extra_fields_ignored(self):
        """Test that id and extra fields are silently ignored."""
        update_data = {
            "id": "chat_message_123",  # Should be ignored
            "chat_message_id": "chat_message_456",  # Should be ignored
            "message": "Test",
            "unknown_field": "ignored"  # Should be ignored
        }
        message_update = ChatMessageUpdateSchema(**update_data)
        result = message_update.model_dump(exclude_unset=True)
        # Only message should be in the result
        assert result == {"message": "Test"}
        assert "id" not in result
        assert "chat_message_id" not in result
        assert "unknown_field" not in result


# ─────────────────────────────────────────────────────────────────────────────
# AIConversationSchema / AIConversationUpdateSchema
# ─────────────────────────────────────────────────────────────────────────────

class TestAIConversationSchema:
    """Tests for the AI conversation persistence schemas."""

    def test_valid_minimal(self):
        from ai_assistant.firestore_schemas import AIConversationSchema
        schema = AIConversationSchema(user_id="u1")
        assert schema.user_id == "u1"
        assert schema.topic_title == ""
        assert schema.request_id is None
        assert schema.final_stage is None
        assert schema.message_count == 0
        assert schema.expires_at > schema.created_at

    def test_no_session_id_field(self):
        """session_id was removed — extra='ignore' swallows it silently."""
        from ai_assistant.firestore_schemas import AIConversationSchema
        schema = AIConversationSchema(user_id="u1", session_id="old_val")
        assert not hasattr(schema, "session_id")

    def test_request_id_stored(self):
        from ai_assistant.firestore_schemas import AIConversationSchema
        schema = AIConversationSchema(user_id="u1", request_id="req_xyz")
        assert schema.request_id == "req_xyz"

    def test_missing_user_id_raises(self):
        from ai_assistant.firestore_schemas import AIConversationSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AIConversationSchema()

    def test_topic_title_max_length(self):
        from ai_assistant.firestore_schemas import AIConversationSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AIConversationSchema(user_id="u1", topic_title="x" * 301)


class TestAIConversationUpdateSchema:

    def test_request_id_updatable(self):
        from ai_assistant.firestore_schemas import AIConversationUpdateSchema
        schema = AIConversationUpdateSchema(request_id="req_abc")
        result = schema.model_dump(exclude_unset=True)
        assert result == {"request_id": "req_abc"}

    def test_final_stage_updatable(self):
        from ai_assistant.firestore_schemas import AIConversationUpdateSchema
        schema = AIConversationUpdateSchema(final_stage="completed")
        result = schema.model_dump(exclude_unset=True)
        assert result == {"final_stage": "completed"}

    def test_empty_update_excludes_all(self):
        from ai_assistant.firestore_schemas import AIConversationUpdateSchema
        schema = AIConversationUpdateSchema()
        result = schema.model_dump(exclude_unset=True)
        assert result == {}


class TestAIConversationMessageSchema:
    """AIConversationMessage must carry its own TTL so orphaned messages expire."""

    def test_valid_message_has_expires_at(self):
        from ai_assistant.firestore_schemas import AIConversationMessageSchema
        msg = AIConversationMessageSchema(
            conversation_id="c1", role="user", text="hello", sequence=0
        )
        assert msg.expires_at > msg.created_at

    def test_expires_at_is_30_days_after_created_at(self):
        from ai_assistant.firestore_schemas import AIConversationMessageSchema
        from datetime import timedelta
        msg = AIConversationMessageSchema(
            conversation_id="c1", role="assistant", text="Hi!", sequence=1
        )
        delta = msg.expires_at - msg.created_at
        # Allow ±1 second tolerance
        assert abs(delta.total_seconds() - 30 * 86400) < 1

    def test_role_validation_rejects_invalid(self):
        from ai_assistant.firestore_schemas import AIConversationMessageSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AIConversationMessageSchema(
                conversation_id="c1", role="system", text="bad", sequence=0
            )

    def test_sequence_cannot_be_negative(self):
        from ai_assistant.firestore_schemas import AIConversationMessageSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AIConversationMessageSchema(
                conversation_id="c1", role="user", text="hi", sequence=-1
            )
