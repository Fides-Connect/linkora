"""
Data templates and test datasets for the AI Assistant.
Contains User Templates for seeding and static Test Personas.
"""

# Data template for new users
USER_TEMPLATE = {
    # user_id matches firebase uid
    # name comes from auth provider
    # email comes from auth provider
    # photo_url comes from auth provider
    "location": "Berlin, Germany",
    "self_introduction": "Passionate developer and tech enthusiast. I love building things and helping others.",
    "is_service_provider": True,
    "fcm_token": "", # Will be set by client
    "has_open_request": True,
    "favorites": [], # Will be populated with default friend
    "last_sign_in": 0,  # 0 days ago (will be overridden with actual datetime in seeding service)
    "user_app_settings": {},  # Map with key-value pairs for app settings
    "open_incoming_service_requests": [],  # Array of incoming service request IDs
    "open_outgoing_service_requests": [],  # Array of outgoing service request IDs
    "feedback_positive": ["Fast learner", "Great communicator"],
    "feedback_negative": [],
    "average_rating": 5.0,
    "review_count": 3,
    # Note: created_at and updated_at will be set dynamically when seeding
}

USER_TEMPLATE_SERVICE_REQUESTS = [
    # Request 1: New user is provider for User A (Alice Professional)
    {
        "title": "Printer Setup and Troubleshooting",
        "description": "Need help setting up a new printer and fixing connectivity issues. Prefer someone with IT experience.",
        "amount_value": 80.0,
        "currency": "EUR",
        "start_date": "2026-02-15T09:00:00.000000",
        "end_date": "2026-02-15T11:00:00.000000",
        "seeker_user_id": "user_eva_005",
        "selected_provider_user_id": "{uid}",
        "category": "Technology",
        "status": "pending",
        "location": "Berlin, Germany",
    },
    # Request 2: New user is seeker, provider is User E (Eva Enthusiast)
    {
        "title": "Garden Design",
        "description": "Looking for creative garden design and landscaping planning services.",
        "amount_value": 120.0,
        "currency": "EUR",
        "start_date": "2026-03-01T10:00:00.000000",
        "end_date": "2026-03-01T12:00:00.000000",
        "seeker_user_id": "{uid}",
        "selected_provider_user_id": "user_eva_005",
        "category": "Gardening",
        "status": "accepted",
        "location": "Munich, Germany",
    },
    # Request 3: New user is seeker, provider is User D (David Generalist)
    {
        "title": "General Electrical Work",
        "description": "Need help with wiring and installation for a new apartment.",
        "amount_value": 200.0,
        "currency": "EUR",
        "start_date": "2026-03-10T09:00:00.000000",
        "end_date": "2026-03-10T13:00:00.000000",
        "seeker_user_id": "{uid}",
        "selected_provider_user_id": "user_david_004",
        "category": "Electrical",
        "status": "pending",
        "location": "Frankfurt, Germany",
    }
]

USER_TEMPLATE_PROVIDER_CANDIDATES = [
    # Candidates for request_001 (New user is selected provider)
    [
        {
            "provider_candidate_user_id": "user_alice_001",
            "matching_score": 85.5,
            "matching_score_reasons": ["Has relevant IT experience", "High rating", "Available in requested timeframe"],
            "introduction": "Hi! I can help with your printer setup. I have IT experience and good reviews.",
            "status": "contacted"
        },
        {
            "provider_candidate_user_id": "user_david_004",
            "matching_score": 78.2,
            "matching_score_reasons": ["General technical skills", "Good availability", "Positive reviews"],
            "introduction": "Hello! I have general technical skills and can assist with your printer setup.",
            "status": "pending"
        },
    ],
    # Candidates for request_002 (Eva is selected provider, new user is seeker)
    [
        {
            "provider_candidate_user_id": "user_david_004",
            "matching_score": 75.0,
            "matching_score_reasons": ["Versatile skillset", "Good availability", "Willing to try gardening"],
            "introduction": "Hi! While I'm more of a generalist, I'm happy to help with garden design.",
            "status": "pending"
        },
        {
            "provider_candidate_id": "candidate_{uid}_002_2",
            "service_request_id": "request_{uid}_002",
            "provider_candidate_user_id": "user_alice_001",
            "matching_score": 65.5,
            "introduction": "Hello! I'm willing to learn garden design and would love to try.",
            "matching_score_reasons": ["Willing to try new tasks", "Good communicator"],
            "status": "declined"
        },
    ],
    # Candidates for request_003 (David is selected provider, new user is seeker)
    [
        {
            "provider_candidate_user_id": "user_alice_001",
            "matching_score": 88.0,
            "matching_score_reasons": ["Expert in electrical work", "High rating", "Verified professional"],
            "introduction": "Hi! I'm a professional electrician with expertise in electrical work. I'd be happy to help.",
            "status": "accepted"
        },
        {
            "provider_candidate_user_id": "user_eva_005",
            "matching_score": 45.0,
            "matching_score_reasons": ["Willing to learn", "Some basic electrical knowledge"],
            "introduction": "Hello! I have some basic electrical knowledge and I'm eager to help.",
            "status": "pending"
        },
    ],
]

USER_TEMPLATE_COMPETENCIES = [
    {
        "title": "Software Development",
        "description": "Professional software development services including architecture, design, and implementation.",
        "category": "Technology",
        "price_range": "$80-$150/hour",
        "year_of_experience": 5,
        "feedback_positive": ["Excellent code quality", "Great architecture"],
        "feedback_negative": [],
    },
    {
        "title": "Project Management",
        "description": "Expert project management for software and tech projects.",
        "category": "Technology",
        "price_range": "$100-$200/hour",
        "year_of_experience": 8,
        "feedback_positive": ["Well organized", "Delivers on time"],
        "feedback_negative": [],
    },
    {
        "title": "Flutter",
        "description": "Mobile app development using Flutter framework.",
        "category": "Technology",
        "price_range": "$90-$180/hour",
        "year_of_experience": 3,
        "feedback_positive": ["Beautiful UIs", "Fast development"],
        "feedback_negative": [],
    }
]

USER_TEMPLATE_AVAILABILITY_TIMES = [
    {
        "availability_time_id": "availability_time_template_001",
        "user_id": "{uid}",
        "monday_time_ranges": [
            {"start_time": "08:00", "end_time": "12:00"},
            {"start_time": "13:30", "end_time": "17:30"}
        ],
        "tuesday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}],
        "wednesday_time_ranges": [{"start_time": "10:00", "end_time": "15:00"}],
        "thursday_time_ranges": [
            {"start_time": "09:00", "end_time": "11:30"},
            {"start_time": "14:00", "end_time": "18:00"}
        ],
        "friday_time_ranges": [{"start_time": "09:00", "end_time": "16:00"}],
        "saturday_time_ranges": [],
        "sunday_time_ranges": [],
        "absence_days": ["2026-03-15", "2026-03-16", "2026-12-24", "2026-12-25", "2026-12-26"],
    }
]

# --- Test Personas ---

# Test Persona: User A - The Pro
# Active user with specific electrical skill
USER_A = {
    "user_id": "user_alice_001",
    "name": "Alice Professional",
    "email": "alice@example.com",
    "photo_url": "https://example.com/photos/alice.jpg",
    "location": "Berlin, Germany",
    "self_introduction": "Experienced electrician specializing in residential lighting installations.",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_alice",
    "has_open_request": False,
    "favorites": [],
    "last_sign_in": 1,  # 1 day ago (will be converted to datetime in init script)
    "user_app_settings": {},
    "open_incoming_service_requests": [],
    "open_outgoing_service_requests": [],
    "feedback_positive": ["Punctual", "Clean work", "Friendly", "Explains everything clearly"],
    "feedback_negative": ["Sometimes late on big jobs"],
    "average_rating": 4.8,
    "review_count": 25,
    # Note: created_at and updated_at will be set dynamically in init script
}

USER_A_COMPETENCIES = [
    {
        "title": "Installing Pot Lights",
        "description": "Expert installation of recessed lighting and pot lights in residential and commercial spaces.",
        "category": "Electrical",
        "price_range": "$100-$200/hour",
        "year_of_experience": 10,
        "feedback_positive": ["Expert installer", "Clean wiring", "Professional"],
        "feedback_negative": [],
    }
]

USER_A_AVAILABILITY_TIMES = [
    {
        "availability_time_id": "availability_time_alice_001",
        "user_id": "user_alice_001",
        "monday_time_ranges": [{"start_time": "08:00", "end_time": "17:00"}],
        "tuesday_time_ranges": [
            {"start_time": "08:00", "end_time": "12:30"},
            {"start_time": "14:00", "end_time": "17:00"}
        ],
        "wednesday_time_ranges": [{"start_time": "08:00", "end_time": "17:00"}],
        "thursday_time_ranges": [{"start_time": "08:00", "end_time": "17:00"}],
        "friday_time_ranges": [
            {"start_time": "08:00", "end_time": "11:00"},
            {"start_time": "13:00", "end_time": "16:00"}
        ],
        "saturday_time_ranges": [],
        "sunday_time_ranges": [],
        "absence_days": ["2026-08-01", "2026-08-02", "2026-08-03"],
    }
]


# Test Persona: User B - The Spammer
# Description stuffed with keywords to test spam filtering
USER_B = {
    "user_id": "user_bob_002",
    "name": "Bob Spammer",
    "email": "bob@example.com",
    "photo_url": "https://example.com/photos/bob.jpg",
    "location": "Jakarta, Indonesia",
    "self_introduction": "I do everything! Plumbing, electrical, driving, teaching, you name it!",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_bob",
    "has_open_request": False,
    "favorites": [],
    "last_sign_in": 5,  # 5 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
    "open_incoming_service_requests": [],
    "open_outgoing_service_requests": [],
    "feedback_positive": ["Quick response"],
    "feedback_negative": ["Unfocused", "Quality varies", "Too many services listed"],
    "average_rating": 3.2,
    "review_count": 8,
    # Note: created_at and updated_at will be set dynamically in init script
}

USER_B_COMPETENCIES = [
    {
        "title": "Everything Services",
        "description": "Plumber Electrician Driver Nurse Teacher Plumber Driver Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher Electrician Plumber Driver Nurse Teacher",
        "category": "General",
        "price_range": "$50-$500/hour",
        "year_of_experience": 2,
        "feedback_positive": ["Available"],
        "feedback_negative": ["Lacks focus", "Quality inconsistent"],
    }
]

USER_B_AVAILABILITY_TIMES = [
    {
        "availability_time_id": "availability_time_bob_001",
        "user_id": "user_bob_002",
        "monday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "tuesday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "wednesday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "thursday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "friday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "saturday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "sunday_time_ranges": [{"start_time": "00:00", "end_time": "23:59"}],
        "absence_days": [],
    }
]


# Test Persona: User C - The Ghost
# Perfect match but inactive for 365 days
USER_C = {
    "user_id": "user_charlie_003",
    "name": "Charlie Ghost",
    "email": "charlie@example.com",
    "photo_url": "https://example.com/photos/charlie.jpg",
    "location": "London, UK",
    "self_introduction": "Master electrician with 20 years experience. Specialist in residential wiring and lighting installation.",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_charlie",
    "has_open_request": False,
    "favorites": [],
    "last_sign_in": 365,  # 365 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
    "open_incoming_service_requests": [],
    "open_outgoing_service_requests": [],
    "feedback_positive": ["Expert knowledge", "Great results"],
    "feedback_negative": ["Rarely available", "Slow to respond"],
    "average_rating": 4.5,
    "review_count": 12,
    # Note: created_at and updated_at will be set dynamically in init script
}

USER_C_COMPETENCIES = [
    {
        "title": "Expert Electrician",
        "description": "Master electrician with 20 years experience. Specialist in residential wiring and lighting installation.",
        "category": "Electrical",
        "price_range": "$150-$300/hour",
        "year_of_experience": 20,
        "feedback_positive": ["Master level skills", "Highly experienced"],
        "feedback_negative": ["Hard to reach"],
    }
]

USER_C_AVAILABILITY_TIMES = [
    {
        "availability_time_id": "availability_time_charlie_001",
        "user_id": "user_charlie_003",
        "monday_time_ranges": [],
        "tuesday_time_ranges": [],
        "wednesday_time_ranges": [],
        "thursday_time_ranges": [],
        "friday_time_ranges": [],
        "saturday_time_ranges": [],
        "sunday_time_ranges": [],
        "absence_days": [],
    }
]


# Test Persona: User D - The Generalist
# Broad electrical work
USER_D = {
    "user_id": "user_david_004",
    "name": "David Generalist",
    "email": "david@example.com",
    "photo_url": "https://example.com/photos/david.jpg",
    "location": "New York, USA",
    "self_introduction": "Experienced in all types of electrical work including wiring, installations, and repairs.",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_david",
    "has_open_request": False,
    "favorites": [],
    "last_sign_in": 10,  # 10 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
    "open_incoming_service_requests": [],
    "open_outgoing_service_requests": [],
    "feedback_positive": ["Versatile", "Helpful", "Good communicator"],
    "feedback_negative": ["Sometimes overbooked"],
    "average_rating": 4.2,
    "review_count": 15,
    # Note: created_at and updated_at will be set dynamically in init script
}

USER_D_COMPETENCIES = [
    {
        "title": "General Electrical Work",
        "description": "Experienced in all types of electrical work including wiring, installations, and repairs.",
        "category": "Electrical",
        "price_range": "$80-$150/hour",
        "year_of_experience": 7,
        "feedback_positive": ["Reliable", "Good at many things"],
        "feedback_negative": ["Sometimes rushed"],
    }
]

USER_D_AVAILABILITY_TIMES = [
    {
        "availability_time_id": "availability_time_david_001",
        "user_id": "user_david_004",
        "monday_time_ranges": [
            {"start_time": "09:00", "end_time": "12:00"},
            {"start_time": "14:00", "end_time": "18:00"}
        ],
        "tuesday_time_ranges": [
            {"start_time": "09:00", "end_time": "13:00"},
            {"start_time": "15:00", "end_time": "18:00"}
        ],
        "wednesday_time_ranges": [],
        "thursday_time_ranges": [
            {"start_time": "08:00", "end_time": "12:00"},
            {"start_time": "13:00", "end_time": "17:00"}
        ],
        "friday_time_ranges": [{"start_time": "09:00", "end_time": "18:00"}],
        "saturday_time_ranges": [{"start_time": "10:00", "end_time": "14:00"}],
        "sunday_time_ranges": [],
        "absence_days": ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"],
    }
]


# Test Persona: User E - The Enthusiast
# Multiple gardening skills to test result grouping
USER_E = {
    "user_id": "user_eva_005",
    "name": "Eva Enthusiast",
    "email": "eva@example.com",
    "photo_url": "https://example.com/photos/eva.jpg",
    "location": "Paris, France",
    "self_introduction": "Gardening enthusiast offering a variety of services for beautiful and healthy gardens.",
    "is_service_provider": True,  # Service provider
    "fcm_token": "token_eva",
    "has_open_request": False,
    "favorites": [],
    "last_sign_in": 3,  # 3 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
    "open_incoming_service_requests": [],
    "open_outgoing_service_requests": [],
    "feedback_positive": ["Creative designs", "Very friendly", "Great with plants"],
    "feedback_negative": ["Sometimes hard to book in spring"],
    "average_rating": 4.7,
    "review_count": 18,
    # Note: created_at and updated_at will be set dynamically in init script
}

USER_E_COMPETENCIES = [
    {
        "title": "Lawn Mowing",
        "description": "Professional lawn mowing and edging services for residential properties.",
        "category": "Gardening",
        "price_range": "$40-$60/hour",
        "year_of_experience": 4,
        "feedback_positive": ["Neat work", "Consistent"],
        "feedback_negative": [],
        # Note: created_at and updated_at will be set dynamically in init script
    },
    {
        "title": "Garden Design",
        "description": "Creative garden design and landscaping planning services.",
        "category": "Gardening",
        "price_range": "$80-$120/hour",
        "year_of_experience": 6,
        "feedback_positive": ["Beautiful designs", "Creative"],
        "feedback_negative": [],
        # Note: created_at and updated_at will be set dynamically in init script
    },
    {
        "title": "Tree Pruning",
        "description": "Expert tree pruning and maintenance for healthy gardens.",
        "category": "Gardening",
        "price_range": "$60-$100/hour",
        "year_of_experience": 5,
        "feedback_positive": ["Careful with trees", "Expert pruning"],
        "feedback_negative": [],
        # Note: created_at and updated_at will be set dynamically in init script
    },
    {
        "title": "Flower Planting",
        "description": "Seasonal flower planting and garden bed preparation.",
        "category": "Gardening",
        "price_range": "$50-$80/hour",
        "year_of_experience": 4,
        "feedback_positive": ["Great color choices", "Knows seasons"],
        "feedback_negative": [],
        # Note: created_at and updated_at will be set dynamically in init script
    },
    {
        "title": "Vegetable Garden Setup",
        "description": "Complete vegetable garden setup and maintenance for home growers.",
        "category": "Gardening",
        "price_range": "$70-$100/hour",
        "year_of_experience": 5,
        "feedback_positive": ["Great harvests", "Knowledgeable"],
        "feedback_negative": [],
        # Note: created_at and updated_at will be set dynamically in init script
    },
]

USER_E_AVAILABILITY_TIMES = [
    {
        "availability_time_id": "availability_time_eva_001",
        "user_id": "user_eva_005",
        "monday_time_ranges": [{"start_time": "07:00", "end_time": "19:00"}],
        "tuesday_time_ranges": [{"start_time": "07:00", "end_time": "19:00"}],
        "wednesday_time_ranges": [
            {"start_time": "08:00", "end_time": "12:00"},
            {"start_time": "15:00", "end_time": "18:00"}
        ],
        "thursday_time_ranges": [
            {"start_time": "07:00", "end_time": "11:00"},
            {"start_time": "13:00", "end_time": "16:00"},
            {"start_time": "17:00", "end_time": "19:00"}
        ],
        "friday_time_ranges": [{"start_time": "07:00", "end_time": "19:00"}],
        "saturday_time_ranges": [
            {"start_time": "08:00", "end_time": "12:00"},
            {"start_time": "14:00", "end_time": "16:00"}
        ],
        "sunday_time_ranges": [],
        "absence_days": ["2026-04-10", "2026-04-11", "2026-04-12", "2026-04-13"],
    }
]

# Competence-specific availability times (includes template for new users and test personas)
COMPETENCE_AVAILABILITY_TIMES = {
    "competence_{uid}_1": [  # Software Development (Template competence - only for new seed users)
        {
            "availability_time_id": "availability_time_comp_template_001",
            "monday_time_ranges": [
                {"start_time": "10:00", "end_time": "12:00"},
                {"start_time": "14:00", "end_time": "18:00"}
            ],
            "tuesday_time_ranges": [{"start_time": "09:00", "end_time": "18:00"}],
            "wednesday_time_ranges": [{"start_time": "09:00", "end_time": "18:00"}],
            "thursday_time_ranges": [{"start_time": "09:00", "end_time": "18:00"}],
            "friday_time_ranges": [{"start_time": "09:00", "end_time": "15:00"}],
            "saturday_time_ranges": [],
            "sunday_time_ranges": [],
            "absence_days": ["2026-03-15", "2026-03-16"],
        }
    ],
    "competence_user_eva_005_2": [  # Garden Design
        {
            "availability_time_id": "availability_time_comp_garden_design_001",
            "monday_time_ranges": [{"start_time": "08:00", "end_time": "16:00"}],
            "tuesday_time_ranges": [
                {"start_time": "08:00", "end_time": "12:00"},
                {"start_time": "13:30", "end_time": "16:00"}
            ],
            "wednesday_time_ranges": [],
            "thursday_time_ranges": [{"start_time": "08:00", "end_time": "16:00"}],
            "friday_time_ranges": [
                {"start_time": "08:00", "end_time": "11:00"},
                {"start_time": "14:00", "end_time": "16:00"}
            ],
            "saturday_time_ranges": [{"start_time": "09:00", "end_time": "13:00"}],
            "sunday_time_ranges": [],
            "absence_days": ["2026-05-20", "2026-05-21"],
        }
    ],
    "competence_user_alice_001_1": [  # Installing Pot Lights
        {
            "availability_time_id": "availability_time_comp_pot_lights_001",
            "monday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}],
            "tuesday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}],
            "wednesday_time_ranges": [
                {"start_time": "09:00", "end_time": "12:00"},
                {"start_time": "14:00", "end_time": "17:00"}
            ],
            "thursday_time_ranges": [{"start_time": "09:00", "end_time": "17:00"}],
            "friday_time_ranges": [{"start_time": "09:00", "end_time": "15:00"}],
            "saturday_time_ranges": [],
            "sunday_time_ranges": [],
            "absence_days": [],
        }
    ],
}


# All test personas for easy iteration
TEST_PERSONAS = [
    {"user": USER_A, "competencies": USER_A_COMPETENCIES, "availability_times": USER_A_AVAILABILITY_TIMES, "name": "User A (The Pro)"},
    {"user": USER_B, "competencies": USER_B_COMPETENCIES, "availability_times": USER_B_AVAILABILITY_TIMES, "name": "User B (The Spammer)"},
    {"user": USER_C, "competencies": USER_C_COMPETENCIES, "availability_times": USER_C_AVAILABILITY_TIMES, "name": "User C (The Ghost)"},
    {"user": USER_D, "competencies": USER_D_COMPETENCIES, "availability_times": USER_D_AVAILABILITY_TIMES, "name": "User D (The Generalist)"},
    {"user": USER_E, "competencies": USER_E_COMPETENCIES, "availability_times": USER_E_AVAILABILITY_TIMES, "name": "User E (The Enthusiast)"},
]

# --- Database Test Data (Requests, Chat, Reviews) ---

# Scenario 1: User E (Enthusiast/Seeker) asks User A (Pro) for Pot Lights
REQ_TEST_001 = {
    'service_request_id': "service_request_test_001",
    'seeker_user_id': "user_eva_005",
    'selected_provider_user_id': "user_alice_001",
    'title': "Pot Light Installation",
    'amount_value': 150.0,
    'currency': "EUR",
    'description': "I need 5 pot lights installed in my living room. High ceilings.",
    'requested_competencies': ["Installing Pot Lights"],
    'status': 'pending',
    'start_date': "2026-02-15T09:00:00Z",
    'end_date': "2026-02-15T14:00:00Z",
    'category': "Electrical",
    'location': "Paris, France",
    # Note: created_at and updated_at will be set dynamically in init script
}

# --- Test Provider Candidates ---

PROV_CAND_TEST_001_ALICE = {
    'provider_candidate_id': "provider_candidate_test_001_alice",
    'service_request_id': "service_request_test_001",
    'provider_candidate_user_id': "user_alice_001",
    'matching_score': 95.0,
    'matching_score_reasons': ["Expert in electrical work", "High rating", "Available in timeframe"],
    'introduction': "Hi! I'm Alice, a professional electrician with 10 years of experience. I'd love to help with your pot light installation.",
    'status': 'contacted',
    # Note: created_at and updated_at will be set dynamically in init script
}

PROV_CAND_TEST_001_DAVID = {
    'provider_candidate_id': "provider_candidate_test_001_david",
    'service_request_id': "service_request_test_001",
    'provider_candidate_user_id': "user_david_004",
    'matching_score': 78.0,
    'matching_score_reasons': ["General technical skills", "Good availability"],
    'introduction': "Hello! I'm David and I handle various electrical tasks. I can help with your pot lights.",
    'status': 'pending',
    # Note: created_at and updated_at will be set dynamically in init script
}

PROV_CAND_TEST_002_CHARLIE = {
    'provider_candidate_id': "provider_candidate_test_002_charlie",
    'service_request_id': "service_request_test_002",
    'provider_candidate_user_id': "user_charlie_003",
    'matching_score': 88.0,
    'matching_score_reasons': ["Expert electrician", "Has done panel upgrades before"],
    'introduction': "Greetings! I'm Charlie, a master electrician with 20 years of experience in panel upgrades.",
    'status': 'accepted',
    # Note: created_at and updated_at will be set dynamically in init script
}

# --- Test Chats ---

CHAT_TEST_001 = {
    'chat_id': "chat_test_001",
    'service_request_id': "service_request_test_001",
    'provider_candidate_id': "provider_candidate_test_001_alice",
    'title': "Pot Light Inquiry",
    # Chat Messages will be stored in subcollection
    # Note: created_at and updated_at will be set dynamically in init script
}

CHAT_MSG_TEST_001_1 = {
    'chat_message_id': "chat_message_test_001_1",
    'chat_id': "chat_test_001",
    'sender_user_id': "user_eva_005",
    'receiver_user_id': "AI_ASSISTANT",
    'message': "Can you find someone to help with pot lights?",
    # Note: created_at and updated_at will be set dynamically in init script
}

CHAT_MSG_TEST_001_2 = {
    'chat_message_id': "chat_message_test_001_2",
    'chat_id': "chat_test_001",
    'sender_user_id': "AI_ASSISTANT",
    'receiver_user_id': "user_eva_005",
    'message': "I found Alice Professional who fits your request.",
    # Note: created_at and updated_at will be set dynamically in init script
}

REV_TEST_001 = {
    'review_id': "review_test_001",
    'service_request_id': "service_request_past_000",
    'user_id': "user_alice_001",
    'reviewer_user_id': "user_eva_005",
    'feedback_raw': "Alice did an excellent job! Very professional and the pot lights look amazing. She was punctual and cleaned up after herself.",
    'rating_relevance': 5.0,
    'rating_quality': 5.0,
    'rating_competence': 5.0,
    'rating_response_speed': 4.5,
    'feedback_positive': ["Punctual", "Professional", "Clean work"],
    'feedback_negative': []
    # Note: created_at and updated_at will be set dynamically in init script
}


# --- Additional Test Scenarios ---

# Scenario 2: User C (Ghost) has an old inactive request
REQ_TEST_002_GHOST = {
    'service_request_id': "service_request_test_002",
    'seeker_user_id': "user_bob_002",
    'selected_provider_user_id': "user_charlie_003",
    'title': "Panel Upgrade",
    'amount_value': 1200.0,
    'currency': "EUR",
    'description': "Safety upgrade for the old fuse box.",
    'requested_competencies': ["Expert Electrician"],
    'status': 'expired', # Custom status for test
    'start_date': "2025-01-10T08:00:00Z",
    'end_date': "2025-01-12T17:00:00Z",
    'category': "Electrical",
    'location': "Jakarta, Indonesia",
    # Note: created_at and updated_at will be set dynamically in init script
}

# Scenario 3: Ongoing chat between User A and AI for service_request_test_001
CHAT_TEST_002_PRO = {
    'chat_id': "chat_test_002",
    'service_request_id': "service_request_test_001",
    'provider_candidate_id': "provider_candidate_test_001_alice",
    'title': "Availability Update",
    # Note: created_at and updated_at will be set dynamically in init script
}

CHAT_MSG_TEST_002_1 = {
    'chat_message_id': "chat_message_test_002_1",
    'chat_id': "chat_test_002",
    'sender_user_id': "user_alice_001",
    'receiver_user_id': "AI_ASSISTANT",
    'message': "I will be on vacation next week, please pause requests.",
    # Note: created_at and updated_at will be set dynamically in init script
}


# Collections for easy iteration in init script
TEST_PROVIDER_CANDIDATES = [PROV_CAND_TEST_001_ALICE, PROV_CAND_TEST_001_DAVID, PROV_CAND_TEST_002_CHARLIE]
TEST_SERVICE_REQUESTS = [REQ_TEST_001, REQ_TEST_002_GHOST]
TEST_CHATS = [CHAT_TEST_001, CHAT_TEST_002_PRO]
TEST_CHAT_MESSAGES = [CHAT_MSG_TEST_001_1, CHAT_MSG_TEST_001_2, CHAT_MSG_TEST_002_1]
TEST_REVIEWS = [REV_TEST_001]
