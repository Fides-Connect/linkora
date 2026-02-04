"""
Hub and Spoke Architecture: Test Dataset
=========================================

Test Personas:
1. Profile A (The Pro): Active electrician with specific skill
2. Profile B (The Spammer): Keyword-stuffed description
3. Profile C (The Ghost): Great match but inactive 365 days
4. Profile D (The Generalist): Broad electrical skill
5. Profile E (The Enthusiast): Multiple gardening skills (tests grouping)
"""

# Test Persona: Profile A - The Pro
# Active profile with specific electrical skill
PROFILE_A = {
    "profile_id": "profile_alice_001",
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

PROFILE_A_COMPETENCES = [
    {
        "title": "Installing Pot Lights",
        "description": "Expert installation of recessed lighting and pot lights in residential and commercial spaces.",
        "category": "Electrical",
        "price_range": "$100-$200/hour",
    }
]


# Test Persona: Profile B - The Spammer
# Description stuffed with keywords to test spam filtering
PROFILE_B = {
    "profile_id": "profile_bob_002",
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

PROFILE_B_COMPETENCES = [
    {
        "title": "Everything Services",
        "description": "Plumber Electrician Driver Nurse Teacher Plumber Driver Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher",
        "category": "General",
        "price_range": "$50-$500/hour",
    }
]


# Test Persona: Profile C - The Ghost
# Perfect match but inactive for 365 days
PROFILE_C = {
    "profile_id": "profile_charlie_003",
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

PROFILE_C_COMPETENCES = [
    {
        "title": "Expert Electrician",
        "description": "Master electrician with 20 years experience. Specialist in residential wiring and lighting installation.",
        "category": "Electrical",
        "price_range": "$150-$300/hour",
    }
]


# Test Persona: Profile D - The Generalist
# Broad electrical work
PROFILE_D = {
    "profile_id": "profile_david_004",
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

PROFILE_D_COMPETENCES = [
    {
        "title": "General Electrical Work",
        "description": "Experienced in all types of electrical work including wiring, installations, and repairs.",
        "category": "Electrical",
        "price_range": "$80-$150/hour",
    }
]


# Test Persona: Profile E - The Enthusiast
# Multiple gardening skills to test result grouping
PROFILE_E = {
    "profile_id": "profile_eva_005",
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

PROFILE_E_COMPETENCES = [
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
    {"profile": PROFILE_A, "competences": PROFILE_A_COMPETENCES, "name": "Profile A (The Pro)"},
    {"profile": PROFILE_B, "competences": PROFILE_B_COMPETENCES, "name": "Profile B (The Spammer)"},
    {"profile": PROFILE_C, "competences": PROFILE_C_COMPETENCES, "name": "Profile C (The Ghost)"},
    {"profile": PROFILE_D, "competences": PROFILE_D_COMPETENCES, "name": "Profile D (The Generalist)"},
    {"profile": PROFILE_E, "competences": PROFILE_E_COMPETENCES, "name": "Profile E (The Enthusiast)"},
]

# --- Database Test Data (Requests, Chat, Reviews) ---

# Scenario 1: Profile E (Enthusiast/Seeker) asks Profile A (Pro) for Pot Lights
REQ_TEST_001 = {
    'id': "req_test_001",
    'seeker_profile_id': "profile_eva_005",
    'provider_profile_id': "profile_alice_001",
    'title': "Pot Light Installation",
    'price': 150.0,
    'description': "I need 5 pot lights installed in my living room. High ceilings.",
    'requested_competencies': ["Installing Pot Lights"],
    'status': 'pending',
    # Note: 'created_at' will be generated dynamically in the init script
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
    'sender_profile_id': "profile_eva_005",
    'receiver_profile_id': "AI_ASSISTANT",
    'message': "Can you find someone to help with pot lights?",
    # Note: 'time' will be generated dynamically
}

CHAT_MSG_TEST_001_2 = {
    'chat_message_id': "msg_test_001_2",
    'chat_id': "chat_test_001",
    'sender_profile_id': "AI_ASSISTANT",
    'receiver_profile_id': "profile_eva_005",
    'message': "I found Alice Professional who fits your request.",
    # Note: 'time' will be generated dynamically
}

REV_TEST_001 = {
    'review_id': "rev_test_001",
    'request_id': "req_past_000",
    'profile_id': "profile_alice_001",
    'reviewer_profile_id': "profile_eva_005",
    'rating': 5,
    'positive_feedback': ["Punctual", "Professional"],
    'negative_feedback': []
}


# --- Additional Test Scenarios ---

# Scenario 2: Profile C (Ghost) has an old inactive request
REQ_TEST_002_GHOST = {
    'id': "req_test_002",
    'seeker_profile_id': "profile_bob_002",
    'provider_profile_id': "profile_charlie_003",
    'title': "Panel Upgrade",
    'price': 1200.0,
    'description': "Safety upgrade for the old fuse box.",
    'competencies': ["Expert Electrician"],
    'status': 'expired', # Custom status for test
}

# Scenario 3: Ongoing chat between Profile A and AI
CHAT_TEST_002_PRO = {
    'chat_id': "chat_test_002",
    'service_request_id': None, # General inquiry
    'title': "Availability Update",
}

CHAT_MSG_TEST_002_1 = {
    'chat_message_id': "msg_test_002_1",
    'chat_id': "chat_test_002",
    'sender_profile_id': "profile_alice_001",
    'receiver_profile_id': "AI_ASSISTANT",
    'message': "I will be on vacation next week, please pause requests.",
}


# Collections for easy iteration in init script
TEST_SERVICE_REQUESTS = [REQ_TEST_001, REQ_TEST_002_GHOST]
TEST_CHATS = [CHAT_TEST_001, CHAT_TEST_002_PRO]
TEST_CHAT_MESSAGES = [CHAT_MSG_TEST_001_1, CHAT_MSG_TEST_001_2, CHAT_MSG_TEST_002_1]
TEST_REVIEWS = [REV_TEST_001]
