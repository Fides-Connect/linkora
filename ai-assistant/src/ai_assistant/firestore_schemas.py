"""Pydantic schemas for Firestore document validation.

All schemas use ConfigDict with extra='forbid' to reject unknown fields.
Timestamps (created_at, updated_at) are auto-injected and not part of validation.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class UserSchema(BaseModel):
    """Schema for User documents in Firestore.
    
    Note: User ID is used as the document ID (document name) and not stored in the document data.
    Competencies are stored in a subcollection, not as a field.
    """
    model_config = ConfigDict(extra='forbid')
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(), init=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(), init=False)
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=1, max_length=200)
    photo_url: str = Field(default="")
    location: str = Field(default="", max_length=200)
    self_introduction: str = Field(default="", max_length=1000)
    is_service_provider: bool = Field(default=False)
    fcm_token: str = Field(default="")
    has_open_request: bool = Field(default=False)
    last_sign_in: Optional[datetime] = None
    user_app_settings: dict = Field(default_factory=dict)
    feedback_positive: List[str] = Field(default_factory=list)
    feedback_negative: List[str] = Field(default_factory=list)
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    review_count: int = Field(default=0, ge=0)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v


class UserUpdateSchema(BaseModel):
    """Schema for updating User documents in Firestore.
    
    All fields are optional. ID fields are excluded (user_id is the document key).
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = Field(None, min_length=1, max_length=200)
    photo_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    self_introduction: Optional[str] = Field(None, max_length=1000)
    is_service_provider: Optional[bool] = None
    fcm_token: Optional[str] = None
    has_open_request: Optional[bool] = None
    last_sign_in: Optional[datetime] = None
    user_app_settings: Optional[dict] = None
    feedback_positive: Optional[List[str]] = None
    feedback_negative: Optional[List[str]] = None
    average_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    review_count: Optional[int] = Field(None, ge=0)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation."""
        if v is not None and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class CompetenceSchema(BaseModel):
    """Schema for Competence documents (subcollection under users).
    
    Note: Competence ID is auto-generated with prefix 'competence_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="", max_length=100)
    price_range: str = Field(default="", max_length=100)
    year_of_experience: int = Field(default=0, ge=0)
    feedback_positive: List[str] = Field(default_factory=list)
    feedback_negative: List[str] = Field(default_factory=list)
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, data):
        """Set default timestamps if not provided."""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get('created_at') is None:
                data['created_at'] = now
            if data.get('updated_at') is None:
                data['updated_at'] = now
        return data


class CompetenceUpdateSchema(BaseModel):
    """Schema for updating Competence documents.
    
    All fields are optional. ID field (competence_id) is excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    price_range: Optional[str] = Field(None, max_length=100)


class ServiceRequestSchema(BaseModel):
    """Schema for ServiceRequest documents in Firestore.
    
    Note: Service request ID is auto-generated with prefix 'service_request_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    seeker_user_id: str = Field(..., min_length=1)
    selected_provider_user_id: str = Field(default="")
    title: str = Field(..., min_length=1, max_length=200)
    amount_value: Optional[float] = Field(None, ge=0.0)
    currency: Optional[str] = Field(None, max_length=10)
    description: str = Field(default="", max_length=1000)
    requested_competencies: List[str] = Field(default_factory=list)
    status: str = Field(default="pending", max_length=50)
    start_date: Optional[datetime] = None  # Fixed typo from start_data
    end_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status values."""
        valid_statuses = ['pending', 'accepted', 'rejected', 'active', 'waitingForAnswer', 'completed', 'cancelled', 'expired', 'unknown']
        if v and v not in valid_statuses:
            raise ValueError(f'status must be one of {valid_statuses}')
        return v
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, data):
        """Set default timestamps if not provided."""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get('created_at') is None:
                data['created_at'] = now
            if data.get('updated_at') is None:
                data['updated_at'] = now
        return data


class ServiceRequestUpdateSchema(BaseModel):
    """Schema for updating ServiceRequest documents.
    
    All fields are optional. ID field (service_request_id) is excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    updated_at: Optional[datetime] = None
    selected_provider_user_id: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    amount_value: Optional[float] = Field(None, ge=0.0)
    currency: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=1000)
    requested_competencies: Optional[List[str]] = None
    status: Optional[str] = Field(None, max_length=50)
    start_data: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status values."""
        if v is not None:
            valid_statuses = ['pending', 'accepted', 'rejected', 'active', 'waitingForAnswer', 'completed', 'cancelled', 'expired', 'unknown']
            if v not in valid_statuses:
                raise ValueError(f'status must be one of {valid_statuses}')
        return v


class ReviewSchema(BaseModel):
    """Schema for Review documents in Firestore.
    
    Note: Review ID is auto-generated with prefix 'review_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    service_request_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)  # Reviewee (user being reviewed)
    reviewer_user_id: str = Field(..., min_length=1)  # Reviewer (user writing the review)
    feedback_raw: str = Field(default="", max_length=5000)
    feedback_positive: List[str] = Field(default_factory=list)
    feedback_negative: List[str] = Field(default_factory=list)
    rating_reliance: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_quality: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_competence: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_response_speed: Optional[float] = Field(None, ge=1.0, le=5.0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('user_id', 'reviewer_user_id')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure user IDs are not empty."""
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, data):
        """Set default timestamps if not provided."""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get('created_at') is None:
                data['created_at'] = now
            if data.get('updated_at') is None:
                data['updated_at'] = now
        return data


class ReviewUpdateSchema(BaseModel):
    """Schema for updating Review documents.
    
    All fields are optional. ID field (review_id) is excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    feedback_raw: Optional[str] = Field(None, max_length=5000)
    feedback_positive: Optional[List[str]] = None
    feedback_negative: Optional[List[str]] = None
    rating_reliance: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_quality: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_competence: Optional[float] = Field(None, ge=1.0, le=5.0)
    rating_response_speed: Optional[float] = Field(None, ge=1.0, le=5.0)

class ChatSchema(BaseModel):
    """Schema for Chat documents in root collection.
    
    Note: Chat ID is auto-generated with prefix 'chat_' and used as the document ID (document name).
    Chats are now a root collection for better scalability and query performance.
    """
    model_config = ConfigDict(extra='forbid')
    
    provider_candidate_id: str = Field(..., min_length=1)
    service_request_id: str = Field(..., min_length=1)
    seeker_user_id: str = Field(..., min_length=1)  # For direct user queries
    provider_user_id: str = Field(..., min_length=1)  # For direct user queries
    title: str = Field(default="", max_length=200)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, data):
        """Set default timestamps if not provided."""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get('created_at') is None:
                data['created_at'] = now
            if data.get('updated_at') is None:
                data['updated_at'] = now
        return data


class ChatUpdateSchema(BaseModel):
    """Schema for updating Chat documents.
    
    All fields are optional. ID fields (chat_id, provider_candidate_id, service_request_id, user_ids) are excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    title: Optional[str] = Field(None, max_length=200)


class ChatMessageSchema(BaseModel):
    """Schema for ChatMessage documents (subcollection under chats).
    
    Note: Chat message ID is auto-generated with prefix 'chat_message_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    chat_id: str = Field(..., min_length=1)
    sender_user_id: str = Field(..., min_length=1)
    receiver_user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=5000)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('sender_user_id', 'receiver_user_id')
    @classmethod
    def validate_user_ids(cls, v: str) -> str:
        """Ensure user IDs are not empty."""
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, data):
        """Set default timestamps if not provided."""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get('created_at') is None:
                data['created_at'] = now
            if data.get('updated_at') is None:
                data['updated_at'] = now
        return data


class ChatMessageUpdateSchema(BaseModel):
    """Schema for updating ChatMessage documents.
    
    All fields are optional. ID fields (chat_message_id, chat_id) are excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    sender_user_id: Optional[str] = Field(None, min_length=1)
    receiver_user_id: Optional[str] = Field(None, min_length=1)
    message: Optional[str] = Field(None, min_length=1, max_length=5000)
    
    @field_validator('sender_user_id', 'receiver_user_id')
    @classmethod
    def validate_user_ids(cls, v: Optional[str]) -> Optional[str]:
        """Ensure user IDs are not empty."""
        if v is not None and (not v or not v.strip()):
            raise ValueError('User ID cannot be empty')
        return v


class ProviderCandidateSchema(BaseModel):
    """Schema for ProviderCandidate documents (subcollection under service_requests).
    
    Note: Provider candidate ID is auto-generated with prefix 'provider_candidate_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    service_request_id: str = Field(..., min_length=1)
    provider_candidate_user_id: str = Field(..., min_length=1)
    matching_score: float = Field(..., ge=0.0, le=100.0)
    matching_score_reasons: List[str] = Field(default_factory=list)
    introduction: str = Field(default="", max_length=2000)
    status: str = Field(default="pending", max_length=50)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status values."""
        valid_statuses = ['pending', 'contacted', 'accepted', 'declined', 'rejected']
        if v and v not in valid_statuses:
            raise ValueError(f'status must be one of {valid_statuses}')
        return v
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, data):
        """Set default timestamps if not provided."""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get('created_at') is None:
                data['created_at'] = now
            if data.get('updated_at') is None:
                data['updated_at'] = now
        return data


class ProviderCandidateUpdateSchema(BaseModel):
    """Schema for updating ProviderCandidate documents.
    
    All fields are optional. ID fields are excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    provider_candidate_user_id: Optional[str] = Field(None, min_length=1)
    matching_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    matching_score_reasons: Optional[List[str]] = None
    introduction: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, max_length=50)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status values."""
        if v is not None:
            valid_statuses = ['pending', 'contacted', 'accepted', 'declined', 'rejected']
            if v not in valid_statuses:
                raise ValueError(f'status must be one of {valid_statuses}')
        return v


class TimeRangeSchema(BaseModel):
    """Schema for time ranges within availability times."""
    model_config = ConfigDict(extra='forbid')
    
    start_time: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')


class AvailabilityTimeSchema(BaseModel):
    """Schema for AvailabilityTime documents (subcollection under users or competencies).
    
    Note: Availability time ID is auto-generated with prefix 'availability_time_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    monday_time_ranges: List[dict] = Field(default_factory=list)
    tuesday_time_ranges: List[dict] = Field(default_factory=list)
    wednesday_time_ranges: List[dict] = Field(default_factory=list)
    thursday_time_ranges: List[dict] = Field(default_factory=list)
    friday_time_ranges: List[dict] = Field(default_factory=list)
    saturday_time_ranges: List[dict] = Field(default_factory=list)
    sunday_time_ranges: List[dict] = Field(default_factory=list)
    absence_days: List[str] = Field(default_factory=list)


class AvailabilityTimeUpdateSchema(BaseModel):
    """Schema for updating AvailabilityTime documents.
    
    All fields are optional. ID field is excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')
    
    monday_time_ranges: Optional[List[dict]] = None
    tuesday_time_ranges: Optional[List[dict]] = None
    wednesday_time_ranges: Optional[List[dict]] = None
    thursday_time_ranges: Optional[List[dict]] = None
    friday_time_ranges: Optional[List[dict]] = None
    saturday_time_ranges: Optional[List[dict]] = None
    sunday_time_ranges: Optional[List[dict]] = None
    absence_days: Optional[List[str]] = None
