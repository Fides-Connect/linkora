"""
Data templates and test datasets for the AI Assistant.
Contains User Templates for seeding and static Test Personas.
"""

# Data template for new users
from datetime import UTC
from typing import Any
USER_TEMPLATE = {
    # id matches firebase uid
    # name comes from auth provider
    # email comes from auth provider
    # photo_url comes from auth provider
    "location": "Berlin, Germany",
    "self_introduction": "Passionate developer and tech enthusiast. I love building things and helping others.",
    "is_service_provider": True,
    "fcm_token": "", # Will be set by client
    "has_open_request": True,
    "last_sign_in": 0,  # 0 days ago (will be overridden with actual datetime in seeding service)
    "user_app_settings": {},  # Map with key-value pairs for app settings
    "feedback_positive": ["Fast learner", "Great communicator"],
    "feedback_negative": [],
    "average_rating": 5.0,
    "review_count": 3,
    # Note: created_at and updated_at will be set dynamically when seeding
}

USER_TEMPLATE_SERVICE_REQUESTS = [
    # Request 1: New user is seeker, provider is User E (Eva Enthusiast)
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
    # Request 2: New user is seeker, provider is User D (David Generalist) - COMPLETED
    {
        "title": "General Electrical Work",
        "description": "Need help with wiring and installation for a new apartment.",
        "amount_value": 200.0,
        "currency": "EUR",
        "start_date": "2026-02-10T09:00:00.000000",
        "end_date": "2026-02-10T13:00:00.000000",
        "seeker_user_id": "{uid}",
        "selected_provider_user_id": "user_david_004",
        "category": "Electrical",
        "status": "completed",
        "location": "Frankfurt, Germany",
    },
    # Request 3: New user is provider for User A (Alice Professional) - INCOMING REQUEST
    {
        "title": "Home Network Setup",
        "description": "Need assistance setting up a home WiFi network with mesh system and security configuration.",
        "amount_value": 150.0,
        "currency": "EUR",
        "start_date": "2026-02-20T14:00:00.000000",
        "end_date": "2026-02-20T17:00:00.000000",
        "seeker_user_id": "user_alice_001",
        "selected_provider_user_id": "{uid}",
        "category": "Technology",
        "status": "waitingForAnswer",
        "location": "Berlin, Germany",
    }
]

USER_TEMPLATE_PROVIDER_CANDIDATES = [
    # Candidates for request_001 (Eva is selected provider, new user is seeker)
    [
        {
            "provider_candidate_user_id": "user_eva_005",
            "matching_score": 92.0,
            "matching_score_reasons": ["Expert in garden design", "High rating", "Creative designs", "Experienced"],
            "introduction": "Hi! I'd be delighted to help with your garden design. I have 6 years of experience and love creating beautiful outdoor spaces!",
            "status": "accepted"
        },
        {
            "provider_candidate_user_id": "user_david_004",
            "matching_score": 75.0,
            "matching_score_reasons": ["Versatile skillset", "Good availability", "Willing to try gardening"],
            "introduction": "Hi! While I'm more of a generalist, I'm happy to help with garden design.",
            "status": "pending"
        },
        {
            "provider_candidate_user_id": "user_alice_001",
            "matching_score": 65.5,
            "introduction": "Hello! I'm willing to learn garden design and would love to try.",
            "matching_score_reasons": ["Willing to try new tasks", "Good communicator"],
            "status": "declined"
        },
    ],
    # Candidates for request_002 (David is selected provider, new user is seeker)
    [
        {
            "provider_candidate_user_id": "user_david_004",
            "matching_score": 90.0,
            "matching_score_reasons": ["General electrical work expert", "7 years experience", "Reliable", "Good availability"],
            "introduction": "Hello! I can definitely help with electrical wiring. I have 7 years of experience in all types of electrical work.",
            "status": "accepted"
        },
        {
            "provider_candidate_user_id": "user_alice_001",
            "matching_score": 88.0,
            "matching_score_reasons": ["Expert in electrical work", "High rating", "Verified professional"],
            "introduction": "Hi! I'm a professional electrician with expertise in electrical work. I'd be happy to help.",
            "status": "pending"
        },
        {
            "provider_candidate_user_id": "user_eva_005",
            "matching_score": 45.0,
            "matching_score_reasons": ["Willing to learn", "Some basic electrical knowledge"],
            "introduction": "Hello! I have some basic electrical knowledge and I'm eager to help.",
            "status": "pending"
        },
    ],
    # Candidates for request_003 (New user is selected provider, Alice is seeker)
    [
        {
            "provider_candidate_user_id": "{uid}",
            "matching_score": 95.0,
            "matching_score_reasons": ["IT experience", "Network configuration expert", "High rating", "Available in timeframe"],
            "introduction": "Hello Alice! I'd be happy to help with your home network setup. I have experience with mesh systems and security configurations.",
            "status": "accepted"
        },
        {
            "provider_candidate_user_id": "user_david_004",
            "matching_score": 82.0,
            "matching_score_reasons": ["General tech skills", "Good availability", "Reliable"],
            "introduction": "Hi! I can help with your network setup. I have experience with home networks.",
            "status": "pending"
        },
        {
            "provider_candidate_user_id": "user_eva_005",
            "matching_score": 55.0,
            "matching_score_reasons": ["Basic technical knowledge", "Willing to help"],
            "introduction": "Hello! I have some basic network knowledge and would be happy to assist.",
            "status": "pending"
        },
    ],
]

USER_TEMPLATE_CHATS = [
    # Chat for Request 1: New User (seeker) to Eva (selected provider) about garden design
    {
        "request_index": 0,  # Links to USER_TEMPLATE_SERVICE_REQUESTS[0]
        "provider_candidate_index": None,  # Will use actual created provider_candidate_id
        "seeker_user_id": "{uid}",
        "provider_user_id": "user_eva_005",
        "title": "Garden Design Consultation",
    },
    # Chat for Request 2: New User (seeker) to David (selected provider) about electrical work
    {
        "request_index": 1,  # Links to USER_TEMPLATE_SERVICE_REQUESTS[1]
        "provider_candidate_index": None,  # Will use actual created provider_candidate_id
        "seeker_user_id": "{uid}",
        "provider_user_id": "user_david_004",
        "title": "Electrical Work Details",
    },
    # Chat for Request 3: Alice (seeker) to New User (selected provider) about network setup
    {
        "request_index": 2,  # Links to USER_TEMPLATE_SERVICE_REQUESTS[2]
        "provider_candidate_index": None,  # Will use actual created provider_candidate_id
        "seeker_user_id": "user_alice_001",
        "provider_user_id": "{uid}",
        "title": "Home Network Setup",
    },
]

USER_TEMPLATE_CHAT_MESSAGES = [
    # Messages for Chat 0 (Garden Design - New User to Eva) - 1 day ago
    [
        {
            "sender_user_id": "{uid}",
            "receiver_user_id": "user_eva_005",
            "message": "Hello Eva! I'd love to work with you on my garden design project. When would be a good time to discuss the details?",
            "timestamp": "2026-02-12T09:35:00.000000",
        },
        {
            "sender_user_id": "user_eva_005",
            "receiver_user_id": "{uid}",
            "message": "Hi! I'd be delighted to help with your garden design. I'm available next week. Let's schedule a consultation!",
            "timestamp": "2026-02-12T14:20:00.000000",
        },
        {
            "sender_user_id": "{uid}",
            "receiver_user_id": "user_eva_005",
            "message": "Perfect! I'm thinking of creating a mix of flowers and vegetables. The backyard is about 200 square meters with partial shade. Would you be able to visit the site first?",
            "timestamp": "2026-02-12T16:10:00.000000",
        },
    ],
    # Messages for Chat 1 (Electrical Work - New User to David) - Today
    [
        {
            "sender_user_id": "{uid}",
            "receiver_user_id": "user_david_004",
            "message": "Hi David! I need help with electrical wiring in my new apartment. Can you help with this project?",
            "timestamp": "2026-02-13T08:05:00.000000",
        },
        {
            "sender_user_id": "user_david_004",
            "receiver_user_id": "{uid}",
            "message": "Hello! Yes, I can definitely help with electrical wiring. What specific work needs to be done?",
            "timestamp": "2026-02-13T09:15:00.000000",
        },
    ],
    # Messages for Chat 2 (Home Network Setup - Alice to New User) - Recent
    [
        {
            "sender_user_id": "user_alice_001",
            "receiver_user_id": "{uid}",
            "message": "Hi! I saw your profile and I need help setting up a mesh WiFi network in my home. Are you available this month?",
            "timestamp": "2026-02-12T15:30:00.000000",
        },
        {
            "sender_user_id": "{uid}",
            "receiver_user_id": "user_alice_001",
            "message": "Hello Alice! I'd be happy to help with your home network setup. I have experience with mesh systems and security configurations. When would work best for you?",
            "timestamp": "2026-02-12T17:45:00.000000",
        },
        {
            "sender_user_id": "user_alice_001",
            "receiver_user_id": "{uid}",
            "message": "Great! I'm thinking Thursday the 20th in the afternoon. I need to set up 3 mesh nodes and configure guest network and parental controls. Does that work?",
            "timestamp": "2026-02-13T10:20:00.000000",
        },
    ],
]

USER_TEMPLATE_REVIEWS = [
    # Review from David for the new user (electrical work service)
    {
        "request_index": 1,  # Links to USER_TEMPLATE_SERVICE_REQUESTS[1] - General Electrical Work
        "user_id": "user_david_004",  # Reviewee - David who provided the service
        "reviewer_user_id": "{uid}",  # Reviewer - new user who requested the service
        "feedback_raw": "David did an outstanding job with the electrical wiring in my new apartment. Very professional, thorough, and safety-conscious. The installation was done perfectly and he explained everything clearly. Highly recommend for any electrical work!",
        "feedback_positive": ["Professional", "Thorough", "Safety-conscious", "Clear communication"],
        "feedback_negative": [],
        "rating_reliance": 5.0,
        "rating_quality": 5.0,
        "rating_competence": 5.0,
        "rating_response_speed": 4.5,
    },
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
    "last_sign_in": 1,  # 1 day ago (will be converted to datetime in init script)
    "user_app_settings": {},
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
    "last_sign_in": 5,  # 5 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
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
    "last_sign_in": 365,  # 365 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
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

USER_C_AVAILABILITY_TIMES: list[dict[str, Any]] = [
    {
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
    "last_sign_in": 10,  # 10 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
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
    "last_sign_in": 3,  # 3 days ago (will be converted to datetime in init script)
    "user_app_settings": {},
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


# --- Standalone Service Request Templates ---

# Template data for a lawn mowing service request.
# Use get_lawn_mowing_service_request() to obtain a fully-populated dict.
_LAWN_MOWING_SERVICE_REQUEST_TEMPLATE = {
    "title": "Lawn Mowing",
    "description": (
        "One time lawn mowing service for a mid-sized suburban garden (~150 m²). "
        "Includes edge trimming, grass collection, and disposal of clippings."
    ),
    "category": "Gardening",
    "amount_value": 45.0,
    "currency": "EUR",
    "requested_competencies": ["Lawn Mowing", "Garden Maintenance"],
    "location": "Berlin, Germany",
    "status": "waitingForAnswer",
}


def get_lawn_mowing_service_request(
    seeker_user_id: str,
    selected_provider_user_id: str,
) -> dict:
    """Return a lawn mowing service request dict ready for Firestore.

    Start date is set to approximately two weeks from *now*; end date is
    three hours after the start.

    Args:
        seeker_user_id: Firestore user ID of the service seeker.
        selected_provider_user_id: Firestore user ID of the selected provider.

    Returns:
        A dict compatible with ``ServiceRequestSchema`` (excluding timestamps,
        which are injected by ``FirestoreService.create_service_request``).
    """
    from datetime import datetime, timedelta

    start = datetime.now(UTC).replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(weeks=2)
    end = start + timedelta(hours=3)

    return {
        **_LAWN_MOWING_SERVICE_REQUEST_TEMPLATE,
        "seeker_user_id": seeker_user_id,
        "selected_provider_user_id": selected_provider_user_id,
        "start_date": start,
        "end_date": end,
    }
