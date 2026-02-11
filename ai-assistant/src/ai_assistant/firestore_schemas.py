"""Pydantic schemas for Firestore document validation.

All schemas use ConfigDict with extra='forbid' to reject unknown fields.
Timestamps (created_at, updated_at) are auto-injected and not part of validation.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserSchema(BaseModel):
    """Schema for User documents in Firestore.
    
    Note: user_id is the document ID and not included in the document data.
    Competencies are stored in a subcollection, not as a field.
    """
    model_config = ConfigDict(extra='forbid')
    
    user_id: str = Field(..., min_length=1)
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
    favorites: List[str] = Field(default_factory=list)
    last_sign_in: Optional[datetime] = None
    user_app_settings: dict = Field(default_factory=dict)
    open_incoming_service_requests: List[str] = Field(default_factory=list)
    open_outgoing_service_requests: List[str] = Field(default_factory=list)
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
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='forbid')
    
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = Field(None, min_length=1, max_length=200)
    photo_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    self_introduction: Optional[str] = Field(None, max_length=1000)
    is_service_provider: Optional[bool] = None
    fcm_token: Optional[str] = None
    has_open_request: Optional[bool] = None
    favorites: Optional[List[str]] = None
    last_sign_in: Optional[datetime] = None
    user_app_settings: Optional[dict] = None
    open_incoming_service_requests: Optional[List[str]] = None
    open_outgoing_service_requests: Optional[List[str]] = None
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
    
    Note: competence_id is auto-generated with prefix 'competence_'
    """
    model_config = ConfigDict(extra='forbid')
    
    competence_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="", max_length=100)
    price_range: str = Field(default="", max_length=100)
    
    @field_validator('competence_id')
    @classmethod
    def validate_competence_id(cls, v: str) -> str:
        """Ensure competence_id has the correct prefix."""
        if not v.startswith('competence_'):
            raise ValueError('competence_id must start with "competence_"')
        return v


class CompetenceUpdateSchema(BaseModel):
    """Schema for updating Competence documents.
    
    All fields are optional. ID field (competence_id) is excluded.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='forbid')
    
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    price_range: Optional[str] = Field(None, max_length=100)


class ServiceRequestSchema(BaseModel):
    """Schema for ServiceRequest documents in Firestore.
    
    Note: service_request_id is auto-generated with prefix 'service_request_'
    """
    model_config = ConfigDict(extra='forbid')
    
    service_request_id: str = Field(..., min_length=1)
    created_at: datetime
    updated_at: datetime
    seeker_user_id: str = Field(..., min_length=1)
    selected_provider_user_id: str = Field(default="")
    title: str = Field(..., min_length=1, max_length=200)
    amount_value: Optional[float] = Field(None, ge=0.0)
    currency: Optional[str] = Field(None, max_length=10)
    description: str = Field(default="", max_length=1000)
    requested_competencies: List[str] = Field(default_factory=list)
    status: str = Field(default="pending", max_length=50)
    start_data: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    
    @field_validator('service_request_id')
    @classmethod
    def validate_service_request_id(cls, v: str) -> str:
        """Ensure service_request_id has the correct prefix."""
        if not v.startswith('service_request_'):
            raise ValueError('service_request_id must start with "service_request_"')
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status values."""
        valid_statuses = ['pending', 'active', 'completed', 'cancelled']
        if v and v not in valid_statuses:
            raise ValueError(f'status must be one of {valid_statuses}')
        return v


class ServiceRequestUpdateSchema(BaseModel):
    """Schema for updating ServiceRequest documents.
    
    All fields are optional. ID field (service_request_id) is excluded.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='forbid')
    
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
            valid_statuses = [
                'pending',
                'waitingForAnswer',
                'accepted',
                'rejected',
                'active',
                'completed',
                'cancelled']
            if v not in valid_statuses:
                raise ValueError(f'status must be one of {valid_statuses}')
        return v


class ReviewSchema(BaseModel):
    """Schema for Review documents in Firestore.
    
    Note: review_id is auto-generated with prefix 'review_'
    """
    model_config = ConfigDict(extra='forbid')
    
    review_id: str = Field(..., min_length=1)
    service_request_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)  # Reviewee (user being reviewed)
    reviewer_user_id: str = Field(..., min_length=1)  # Reviewer (user writing the review)
    rating: float = Field(..., ge=1.0, le=5.0)
    positive_feedback: List[str] = Field(default_factory=list)
    negative_feedback: List[str] = Field(default_factory=list)
    comment: str = Field(default="", max_length=2000)
    
    @field_validator('review_id')
    @classmethod
    def validate_review_id(cls, v: str) -> str:
        """Ensure review_id has the correct prefix."""
        if not v.startswith('review_'):
            raise ValueError('review_id must start with "review_"')
        return v
    
    @field_validator('user_id', 'reviewer_user_id')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure user IDs are not empty."""
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v


class ReviewUpdateSchema(BaseModel):
    """Schema for updating Review documents.
    
    All fields are optional. ID field (review_id) is excluded.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='forbid')
    
    service_request_id: Optional[str] = Field(None, min_length=1)
    user_id: Optional[str] = Field(None, min_length=1)
    reviewer_user_id: Optional[str] = Field(None, min_length=1)
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    positive_feedback: Optional[List[str]] = None
    negative_feedback: Optional[List[str]] = None
    comment: Optional[str] = Field(None, max_length=2000)
    
    @field_validator('user_id', 'reviewer_user_id')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure user IDs are not empty."""
        if v is not None and (not v or not v.strip()):
            raise ValueError('User ID cannot be empty')
        return v


class ChatSchema(BaseModel):
    """Schema for Chat documents (subcollection under service_requests/provider_candidates).
    
    Note: chat_id is auto-generated with prefix 'chat_'
    """
    model_config = ConfigDict(extra='forbid')
    
    chat_id: str = Field(..., min_length=1)
    provider_candidate_id: str = Field(..., min_length=1)
    service_request_id: str = Field(..., min_length=1)
    title: str = Field(default="", max_length=200)
    
    @field_validator('chat_id')
    @classmethod
    def validate_chat_id(cls, v: str) -> str:
        """Ensure chat_id has the correct prefix."""
        if not v.startswith('chat_'):
            raise ValueError('chat_id must start with "chat_"')
        return v


class ChatUpdateSchema(BaseModel):
    """Schema for updating Chat documents.
    
    All fields are optional. ID fields (chat_id, provider_candidate_id, service_request_id) are excluded.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='forbid')
    
    title: Optional[str] = Field(None, max_length=200)


class ChatMessageSchema(BaseModel):
    """Schema for ChatMessage documents (subcollection under chats).
    
    Note: chat_message_id is auto-generated with prefix 'chat_message_'
    """
    model_config = ConfigDict(extra='forbid')
    
    chat_message_id: str = Field(..., min_length=1)
    chat_id: str = Field(..., min_length=1)
    sender_user_id: str = Field(..., min_length=1)
    receiver_user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=5000)
    
    @field_validator('chat_message_id')
    @classmethod
    def validate_chat_message_id(cls, v: str) -> str:
        """Ensure chat_message_id has the correct prefix."""
        if not v.startswith('chat_message_'):
            raise ValueError('chat_message_id must start with "chat_message_"')
        return v
    
    @field_validator('sender_user_id', 'receiver_user_id')
    @classmethod
    def validate_user_ids(cls, v: str) -> str:
        """Ensure user IDs are not empty."""
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v


class ChatMessageUpdateSchema(BaseModel):
    """Schema for updating ChatMessage documents.
    
    All fields are optional. ID fields (chat_message_id, chat_id) are excluded.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='forbid')
    
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
