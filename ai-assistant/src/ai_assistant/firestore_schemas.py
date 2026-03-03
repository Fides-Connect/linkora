"""Pydantic schemas for Firestore document validation.

All schemas use ConfigDict with extra='forbid' to reject unknown fields.
Timestamps (created_at, updated_at) are auto-injected and not part of validation.
"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# Sentinel value for permanent opt-out of the provider pitch flow.
# Stored as a far-future datetime so the field stays a single Optional[datetime]
# type without needing a Union. Any value equal to this constant means the user
# has permanently opted out and must never be pitched again.
PROVIDER_PITCH_OPT_OUT_SENTINEL: datetime = datetime(9999, 1, 1, tzinfo=timezone.utc)


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
    self_introduction: str = Field(default="", max_length=1000)
    is_service_provider: bool = Field(default=False)
    fcm_token: str = Field(default="")
    last_sign_in: Optional[datetime] = None
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    review_count: int = Field(default=0, ge=0)
    has_open_request: Optional[bool] = None
    feedback_positive: List[str] = Field(default_factory=list)
    feedback_negative: List[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=200)
    user_app_settings: dict = Field(default_factory=dict)
    # Provider pitch eligibility — None means never been set (new schema field);
    # PROVIDER_PITCH_OPT_OUT_SENTINEL means permanent opt-out.
    last_time_asked_being_provider: Optional[datetime] = None
    
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
    
    updated_at: Optional[datetime] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = Field(None, min_length=1, max_length=200)
    photo_url: Optional[str] = Field(None, max_length=500)
    self_introduction: Optional[str] = Field(None, max_length=1000)
    is_service_provider: Optional[bool] = None
    fcm_token: Optional[str] = None
    last_sign_in: Optional[datetime] = None
    average_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    review_count: Optional[int] = Field(None, ge=0)
    has_open_request: Optional[bool] = None
    feedback_positive: Optional[List[str]] = None
    feedback_negative: Optional[List[str]] = None
    location: Optional[str] = Field(None, max_length=200)
    user_app_settings: Optional[dict] = None
    last_time_asked_being_provider: Optional[datetime] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation."""
        if v is not None and '@' not in v:
            raise ValueError('Invalid email format')
        return v


class CompetenceSchema(BaseModel):
    """Schema for Competence documents (subcollection under users).

    Note: Competence ID is auto-generated with prefix 'competence_' and used as the document ID
    (document name).  Availability is stored in the 'availability_time' subcollection
    (AvailabilityTimeSchema) — not as flat fields on this document.

    Enriched fields (skills_list, search_optimized_summary, price_per_hour) are populated
    asynchronously by CompetenceEnricher after the initial save and written back to Firestore.
    They are also synced to Weaviate as filterable/rankable properties.
    Availability tags for Weaviate are derived at sync-time from the availability_time subcollection
    via derive_availability_tags().
    The raw fields (description, price_range) stay in Firestore for display only.
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

    # ── Enriched fields — LLM-extracted, populated by CompetenceEnricher ───
    # Stored in Firestore as source-of-truth; also synced to Weaviate for
    # filtering and vector search.
    skills_list: List[str] = Field(default_factory=list)
    """Explicit + implicit skills extracted by LLM, e.g. ['residential wiring', 'lighting installation']."""
    search_optimized_summary: str = Field(default="", max_length=1500)
    """LLM-rewritten profile optimised for semantic vector search. Primary vector source in Weaviate."""
    price_per_hour: Optional[float] = Field(default=None, ge=0)
    """Numeric hourly rate extracted by LLM from price_range string. Used for range filtering in Weaviate."""

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
    Extra fields (including 'id', 'availability_time') are ignored automatically — availability
    is managed via the separate 'availability_time' subcollection.
    Validation rules still apply when fields are provided.
    """
    model_config = ConfigDict(extra='ignore')

    updated_at: Optional[datetime] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    price_range: Optional[str] = Field(None, max_length=100)
    year_of_experience: Optional[int] = Field(None, ge=0)
    feedback_positive: Optional[List[str]] = None
    feedback_negative: Optional[List[str]] = None
    # ── Enriched fields ─────────────────────────────────────────────────────
    skills_list: Optional[List[str]] = None
    search_optimized_summary: Optional[str] = Field(None, max_length=1500)
    price_per_hour: Optional[float] = Field(None, ge=0)


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
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status values."""
        valid_statuses = ['pending', 'accepted', 'rejected', 'active', 'waitingForAnswer', 'completed', 'cancelled', 'expired', 'unknown', 'serviceProvided']
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
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status values."""
        if v is not None:
            valid_statuses = ['pending', 'accepted', 'rejected', 'active', 'waitingForAnswer', 'completed', 'cancelled', 'expired', 'unknown', 'serviceProvided']
            if v not in valid_statuses:
                raise ValueError(f'status must be one of {valid_statuses}')
        return v


class ReviewSchema(BaseModel):
    """Schema for Review documents in Firestore.
    
    Note: Review ID is auto-generated with prefix 'review_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
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
    
    updated_at: Optional[datetime] = None
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
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    provider_candidate_id: str = Field(..., min_length=1)
    title: str = Field(default="", max_length=200)
    service_request_id: str = Field(..., min_length=1)
    seeker_user_id: str = Field(..., min_length=1)  # For direct user queries
    provider_user_id: str = Field(..., min_length=1)  # For direct user queries
    
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
    
    updated_at: Optional[datetime] = None
    title: Optional[str] = Field(None, max_length=200)


class ChatMessageSchema(BaseModel):
    """Schema for ChatMessage documents (subcollection under chats).
    
    Note: Chat message ID is auto-generated with prefix 'chat_message_' and used as the document ID (document name).
    """
    model_config = ConfigDict(extra='forbid')
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    chat_id: str = Field(..., min_length=1)
    sender_user_id: str = Field(..., min_length=1)
    receiver_user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=5000)
    timestamp: Optional[datetime] = Field(None)
    
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
    
    updated_at: Optional[datetime] = None
    sender_user_id: Optional[str] = Field(None, min_length=1)
    receiver_user_id: Optional[str] = Field(None, min_length=1)
    message: Optional[str] = Field(None, min_length=1, max_length=5000)
    timestamp: Optional[datetime] = Field(None)
    
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
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    introduction: str = Field(default="", max_length=2000)
    service_request_id: str = Field(..., min_length=1)
    provider_candidate_user_id: str = Field(..., min_length=1)
    matching_score: float = Field(..., ge=0.0, le=100.0)
    matching_score_reasons: List[str] = Field(default_factory=list)
    status: str = Field(default="pending", max_length=50)
    
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
    
    updated_at: Optional[datetime] = None
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

    Note: Availability time ID is auto-generated with prefix 'availability_time_' and used as the
    document ID (document name).  Each day's list is validated by TimeRangeSchema so every
    start_time / end_time must conform to the HH:MM pattern.  absence_days are ISO-8601 date
    strings (YYYY-MM-DD).
    """
    model_config = ConfigDict(extra='forbid')

    monday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    tuesday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    wednesday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    thursday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    friday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    saturday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    sunday_time_ranges: List[TimeRangeSchema] = Field(default_factory=list)
    absence_days: List[str] = Field(
        default_factory=list,
        description="ISO-8601 date strings (YYYY-MM-DD) for days the provider is unavailable.",
    )

    @field_validator('absence_days', mode='before')
    @classmethod
    def validate_absence_days(cls, v: list) -> list:
        """Ensure absence days follow YYYY-MM-DD format."""
        import re
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for day in v:
            if not pattern.match(str(day)):
                raise ValueError(
                    f"absence_days entries must be ISO-8601 date strings (YYYY-MM-DD), got: {day!r}"
                )
        return v


class AvailabilityTimeUpdateSchema(BaseModel):
    """Schema for updating AvailabilityTime documents.

    All fields are optional. ID field is excluded.
    Extra fields (including 'id') are ignored automatically.
    Validation rules still apply when fields are provided — each time range is validated by
    TimeRangeSchema.  absence_days must be ISO-8601 date strings (YYYY-MM-DD).
    """
    model_config = ConfigDict(extra='ignore')

    monday_time_ranges: Optional[List[TimeRangeSchema]] = None
    tuesday_time_ranges: Optional[List[TimeRangeSchema]] = None
    wednesday_time_ranges: Optional[List[TimeRangeSchema]] = None
    thursday_time_ranges: Optional[List[TimeRangeSchema]] = None
    friday_time_ranges: Optional[List[TimeRangeSchema]] = None
    saturday_time_ranges: Optional[List[TimeRangeSchema]] = None
    sunday_time_ranges: Optional[List[TimeRangeSchema]] = None
    absence_days: Optional[List[str]] = None

    @field_validator('absence_days', mode='before')
    @classmethod
    def validate_absence_days(cls, v: Optional[list]) -> Optional[list]:
        """Ensure absence days follow YYYY-MM-DD format."""
        if v is None:
            return v
        import re
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for day in v:
            if not pattern.match(str(day)):
                raise ValueError(
                    f"absence_days entries must be ISO-8601 date strings (YYYY-MM-DD), got: {day!r}"
                )
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Availability helpers
# ─────────────────────────────────────────────────────────────────────────────

_DAYS_AND_FIELDS = [
    ("monday",    "monday_time_ranges"),
    ("tuesday",   "tuesday_time_ranges"),
    ("wednesday", "wednesday_time_ranges"),
    ("thursday",  "thursday_time_ranges"),
    ("friday",    "friday_time_ranges"),
    ("saturday",  "saturday_time_ranges"),
    ("sunday",    "sunday_time_ranges"),
]
_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday"}
_WEEKEND = {"saturday", "sunday"}


def derive_availability_tags(availability_time: dict) -> List[str]:
    """Derive Weaviate filter tokens from an AvailabilityTimeSchema-shaped dict.

    Tokens produced:
    - Day names in English: "monday" … "sunday"
    - "weekday" if any Mon–Fri day has time ranges
    - "weekend" if Saturday or Sunday has time ranges
    - "morning"   for any range with a start_time before 12:00
    - "afternoon" for any range overlapping 12:00–17:00
    - "evening"   for any range with an end_time after 17:00
    - "absence:YYYY-MM-DD" for each absence day

    Args:
        availability_time: Dict shaped like AvailabilityTimeSchema (may be empty or None).

    Returns:
        Sorted list of lowercase string tokens.
    """
    if not availability_time:
        return []

    tags: set = set()
    has_weekday = False
    has_weekend = False
    has_morning = False
    has_afternoon = False
    has_evening = False

    for day_name, field in _DAYS_AND_FIELDS:
        ranges = availability_time.get(field, []) or []
        if not ranges:
            continue

        tags.add(day_name)
        if day_name in _WEEKDAYS:
            has_weekday = True
        else:
            has_weekend = True

        for r in ranges:
            # Accept both dict and TimeRangeSchema instances
            if hasattr(r, "start_time"):
                start_str, end_str = r.start_time, r.end_time
            else:
                start_str = r.get("start_time", "")
                end_str = r.get("end_time", "")

            try:
                if start_str:
                    sh = int(str(start_str).split(":")[0])
                    if sh < 12:
                        has_morning = True
                    elif sh < 17:
                        has_afternoon = True
                    else:
                        has_evening = True
                if end_str:
                    eh = int(str(end_str).split(":")[0])
                    # end hour touches afternoon / evening bucket
                    if eh <= 12:
                        pass  # start already classified the morning slot
                    elif eh <= 17:
                        has_afternoon = True
                    else:
                        has_evening = True
            except (ValueError, IndexError):
                pass  # skip malformed time strings

    if has_weekday:
        tags.add("weekday")
    if has_weekend:
        tags.add("weekend")
    if has_morning:
        tags.add("morning")
    if has_afternoon:
        tags.add("afternoon")
    if has_evening:
        tags.add("evening")

    for absent in availability_time.get("absence_days", []) or []:
        tags.add(f"absence:{absent}")

    return sorted(tags)


# ─────────────────────────────────────────────────────────────────────────────
# AI Conversation schemas
# ─────────────────────────────────────────────────────────────────────────────

_AI_CONV_TTL_DAYS = 30


class AIConversationSchema(BaseModel):
    """Schema for AIConversation documents stored as a subcollection under users.

    Path: users/{user_id}/ai_conversations/{conversation_id}
    TTL is enforced via the ``expires_at`` field (Firestore TTL policy targeting
    the 'ai_conversations' collection group — covers both root and subcollection
    paths because Firestore TTL policies match by collection group name).
    """
    model_config = ConfigDict(extra='ignore')

    user_id: str = Field(..., min_length=1)
    topic_title: str = Field(default="", max_length=300)
    request_id: Optional[str] = Field(default=None)
    final_stage: Optional[str] = Field(default=None)
    first_message_at: Optional[datetime] = Field(default=None)
    last_message_at: Optional[datetime] = Field(default=None)
    message_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=_AI_CONV_TTL_DAYS)
    )


class AIConversationUpdateSchema(BaseModel):
    """Partial-update schema for AIConversation documents."""
    model_config = ConfigDict(extra='ignore')

    topic_title: Optional[str] = Field(default=None, max_length=300)
    request_id: Optional[str] = Field(default=None)
    final_stage: Optional[str] = Field(default=None)
    first_message_at: Optional[datetime] = Field(default=None)
    last_message_at: Optional[datetime] = Field(default=None)
    message_count: Optional[int] = Field(default=None, ge=0)
    updated_at: Optional[datetime] = Field(default=None)


class AIConversationMessageSchema(BaseModel):
    """Schema for messages in the 'messages' subcollection of an AIConversation.

    ``expires_at`` mirrors the parent AIConversation TTL so that Firestore's TTL
    policy can clean up orphaned message documents even if the parent document
    was deleted by a separate process (e.g. a Cloud Function).
    """
    model_config = ConfigDict(extra='ignore')

    conversation_id: str = Field(..., min_length=1)
    role: str = Field(..., pattern=r'^(user|assistant)$')
    text: str = Field(..., min_length=1)
    stage: str = Field(default="")
    sequence: int = Field(..., ge=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=_AI_CONV_TTL_DAYS)
    )
