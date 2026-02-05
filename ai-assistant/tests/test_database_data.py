"""
Data templates and test datasets for the AI Assistant.
Contains User Templates for seeding and static Test Personas.
"""

# Data template for new users
USER_TEMPLATE = {
    # user_id matches firebase uid
    # name comes from auth provider
    # email comes from auth provider
    "introduction": "Passionate developer and tech enthusiast. I love building things and helping others.",
    "type": "user",
    "is_service_provider": True,
    "fcm_token": "", # Will be set by client
    "has_open_request": True,
    "favorites": [], # Will be populated with default friend
    "last_active_date": 0, # Today
    "positive_feedback": ["Fast learner", "Great communicator"],
    "negative_feedback": [],
    "average_rating": 5.0,
    "review_count": 3,
    "requests": [
        {
            "id": "request_{uid}_001", # Template for ID
            "title": "Need help with Python project",
            "description": "I need an expert to help me structure my AI project properly.",
            "amount_value": 50.0,
            "currency": "EUR",
            "start_date": "2026-02-10T10:00:00.000000",
            "end_date": "2026-02-10T14:00:00.000000",
            "user_name": "{name}", # Template
            "user_initials": "{initials}", # Template
            "category": "technology",
            "type": "outgoing",
            "status": "accepted",
            "location": "Berlin, Germany",
        },
        {
            "id": "request_{uid}_002", # Template for ID
            "title": "Gardening Advice",
            "description": "My plants are dying, please help! Need diagnosis and tips.",
            "amount_value": 30.0,
            "currency": "EUR",
            "start_date": "2026-02-15T09:00:00.000000",
            "end_date": "2026-02-15T10:00:00.000000",
            "user_name": "{name}", # Template 
            "user_initials": "{initials}", # Template
            "category": "gardening",
            "type": "outgoing",
            "status": "pending",
            "location": "Munich, Germany",
        }
    ],
    "competencies": [
        "Software Development",
        "Project Management",
        "Flutter"
    ]
}

# --- Test Personas ---

# Test Persona: User A - The Pro
# Active user with specific electrical skill
USER_A = {
    "user_id": "user_alice_001",
    "name": "Alice Professional",
    "email": "alice@example.com",
    "introduction": "Experienced electrician specializing in residential lighting installations.",
    "type": "user",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_alice",
    "has_open_request": False,
    "favorites": [],
    "last_active_date": 1,  # Active 1 day ago
    "positive_feedback": ["Punctual", "Clean work", "Friendly", "Explains everything clearly"],
    "negative_feedback": ["Sometimes late on big jobs"],
    "average_rating": 4.8,
    "review_count": 25,
}

USER_A_COMPETENCES = [
    {
        "title": "Installing Pot Lights",
        "description": "Expert installation of recessed lighting and pot lights in residential and commercial spaces.",
        "category": "Electrical",
        "price_range": "$100-$200/hour",
    }
]


# Test Persona: User B - The Spammer
# Description stuffed with keywords to test spam filtering
USER_B = {
    "user_id": "user_bob_002",
    "name": "Bob Spammer",
    "email": "bob@example.com",
    "introduction": "I do everything! Plumbing, electrical, driving, teaching, you name it!",
    "type": "user",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_bob",
    "has_open_request": False,
    "favorites": [],
    "last_active_date": 5,  # Active 5 days ago
    "positive_feedback": ["Quick response"],
    "negative_feedback": ["Unfocused", "Quality varies", "Too many services listed"],
    "average_rating": 3.2,
    "review_count": 8,
}

USER_B_COMPETENCES = [
    {
        "title": "Everything Services",
        "description": "Plumber Electrician Driver Nurse Teacher Plumber Driver Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher",
        "category": "General",
        "price_range": "$50-$500/hour",
    }
]


# Test Persona: User C - The Ghost
# Perfect match but inactive for 365 days
USER_C = {
    "user_id": "user_charlie_003",
    "name": "Charlie Ghost",
    "email": "charlie@example.com",
    "introduction": "Master electrician with 20 years experience. Specialist in residential wiring and lighting installation.",
    "type": "user",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_charlie",
    "has_open_request": False,
    "favorites": [],
    "last_active_date": 365,  # Inactive for 365 days
    "positive_feedback": ["Expert knowledge", "Great results"],
    "negative_feedback": ["Rarely available", "Slow to respond"],
    "average_rating": 4.5,
    "review_count": 12,
}

USER_C_COMPETENCES = [
    {
        "title": "Expert Electrician",
        "description": "Master electrician with 20 years experience. Specialist in residential wiring and lighting installation.",
        "category": "Electrical",
        "price_range": "$150-$300/hour",
    }
]


# Test Persona: User D - The Generalist
# Broad electrical work
USER_D = {
    "user_id": "user_david_004",
    "name": "David Generalist",
    "email": "david@example.com",
    "introduction": "Experienced in all types of electrical work including wiring, installations, and repairs.",
    "type": "user",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_david",
    "has_open_request": False,
    "favorites": [],
    "last_active_date": 10,  # Active 10 days ago
    "positive_feedback": ["Versatile", "Helpful", "Good communicator"],
    "negative_feedback": ["Sometimes overbooked"],
    "average_rating": 4.2,
    "review_count": 15,
}

USER_D_COMPETENCES = [
    {
        "title": "General Electrical Work",
        "description": "Experienced in all types of electrical work including wiring, installations, and repairs.",
        "category": "Electrical",
        "price_range": "$80-$150/hour",
    }
]


# Test Persona: User E - The Enthusiast
# Multiple gardening skills to test result grouping
USER_E = {
    "user_id": "user_eva_005",
    "name": "Eva Enthusiast",
    "email": "eva@example.com",
    "introduction": "Gardening enthusiast offering a variety of services for beautiful and healthy gardens.",
    "type": "user",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_eva",
    "has_open_request": False,
    "favorites": [],
    "last_active_date": 3,  # Active 3 days ago
    "positive_feedback": ["Creative designs", "Very friendly", "Great with plants"],
    "negative_feedback": ["Sometimes hard to book in spring"],
    "average_rating": 4.7,
    "review_count": 18,
}

USER_E_COMPETENCES = [
    {
        "title": "Lawn Mowing",
        "description": "Professional lawn mowing and edging services for residential properties.",
        "category": "Gardening",
        "price_range": "$40-$60/hour",
    },
    {
        "title": "Garden Design",
        "description": "Creative garden design and landscaping planning services.",
        "category": "Gardening",
        "price_range": "$80-$120/hour",
    },
    {
        "title": "Tree Pruning",
        "description": "Expert tree pruning and maintenance for healthy gardens.",
        "category": "Gardening",
        "price_range": "$60-$100/hour",
    },
    {
        "title": "Flower Planting",
        "description": "Seasonal flower planting and garden bed preparation.",
        "category": "Gardening",
        "price_range": "$50-$80/hour",
    },
    {
        "title": "Vegetable Garden Setup",
        "description": "Complete vegetable garden setup and maintenance for home growers.",
        "category": "Gardening",
        "price_range": "$70-$100/hour",
    },
]


# All test personas for easy iteration
TEST_PERSONAS = [
    {"user": USER_A, "competences": USER_A_COMPETENCES, "name": "User A (The Pro)"},
    {"user": USER_B, "competences": USER_B_COMPETENCES, "name": "User B (The Spammer)"},
    {"user": USER_C, "competences": USER_C_COMPETENCES, "name": "User C (The Ghost)"},
    {"user": USER_D, "competences": USER_D_COMPETENCES, "name": "User D (The Generalist)"},
    {"user": USER_E, "competences": USER_E_COMPETENCES, "name": "User E (The Enthusiast)"},
]

# --- Database Test Data (Requests, Chat, Reviews) ---

# Scenario 1: User E (Enthusiast/Seeker) asks User A (Pro) for Pot Lights
REQ_TEST_001 = {
    'id': "req_test_001",
    'seeker_user_id': "user_eva_005",
    'provider_user_id': "user_alice_001",
    'title': "Pot Light Installation",
    'amount_value': 150.0,
    'currency': "EUR",
    'description': "I need 5 pot lights installed in my living room. High ceilings.",
    'requested_competencies': ["Installing Pot Lights"],
    'status': 'pending',
    # Note: 'created_at' will be generated dynamically in the init script
    'start_date': "2026-02-15T09:00:00Z",
    'end_date': "2026-02-15T14:00:00Z",
    'category': "Electrical",
    'location': {
        'address': "123 Main St, Anytown",
        'latitude': 40.7128,
        'longitude': -74.0060,
    },
}

CHAT_TEST_001 = {
    'chat_id': "chat_test_001",
    'service_request_id': "req_test_001",
    'title': "Pot Light Inquiry",
    # Chat Messages will be stored in subcollection
}

CHAT_MSG_TEST_001_1 = {
    'chat_message_id': "msg_test_001_1",
    'chat_id': "chat_test_001",
    'sender_user_id': "user_eva_005",
    'receiver_user_id': "AI_ASSISTANT",
    'message': "Can you find someone to help with pot lights?",
    # Note: 'time' will be generated dynamically
}

CHAT_MSG_TEST_001_2 = {
    'chat_message_id': "msg_test_001_2",
    'chat_id': "chat_test_001",
    'sender_user_id': "AI_ASSISTANT",
    'receiver_user_id': "user_eva_005",
    'message': "I found Alice Professional who fits your request.",
    # Note: 'time' will be generated dynamically
}

REV_TEST_001 = {
    'review_id': "rev_test_001",
    'request_id': "req_past_000",
    'user_id': "user_alice_001",
    'reviewer_user_id': "user_eva_005",
    'rating': 5,
    'positive_feedback': ["Punctual", "Professional"],
    'negative_feedback': []
}


# --- Additional Test Scenarios ---

# Scenario 2: User C (Ghost) has an old inactive request
REQ_TEST_002_GHOST = {
    'id': "req_test_002",
    'seeker_user_id': "user_bob_002",
    'provider_user_id': "user_charlie_003",
    'title': "Panel Upgrade",
    'amount_value': 1200.0,
    'currency': "EUR",
    'description': "Safety upgrade for the old fuse box.",
    'competencies': ["Expert Electrician"],
    'status': 'expired', # Custom status for test
    'start_date': "2025-01-10T08:00:00Z",
    'end_date': "2025-01-12T17:00:00Z",
    'category': "Electrical",
    'location': {
        'address': "456 Old Rd, Ghosttown",
        'latitude': 40.7200,
        'longitude': -74.0100,
    },
}

# Scenario 3: Ongoing chat between User A and AI
CHAT_TEST_002_PRO = {
    'chat_id': "chat_test_002",
    'service_request_id': None, # General inquiry
    'title': "Availability Update",
}

CHAT_MSG_TEST_002_1 = {
    'chat_message_id': "msg_test_002_1",
    'chat_id': "chat_test_002",
    'sender_user_id': "user_alice_001",
    'receiver_user_id': "AI_ASSISTANT",
    'message': "I will be on vacation next week, please pause requests.",
}


# Collections for easy iteration in init script
TEST_SERVICE_REQUESTS = [REQ_TEST_001, REQ_TEST_002_GHOST]
TEST_CHATS = [CHAT_TEST_001, CHAT_TEST_002_PRO]
TEST_CHAT_MESSAGES = [CHAT_MSG_TEST_001_1, CHAT_MSG_TEST_001_2, CHAT_MSG_TEST_002_1]
TEST_REVIEWS = [REV_TEST_001]
