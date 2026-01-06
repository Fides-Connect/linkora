"""
Hub and Spoke Architecture: Test Dataset
=========================================

Test Personas:
1. User A (The Pro): Active electrician with specific skill
2. User B (The Spammer): Keyword-stuffed description
3. User C (The Ghost): Great match but inactive 365 days
4. User D (The Generalist): Broad electrical skill
5. User E (The Enthusiast): Multiple gardening skills (tests grouping)
"""
from datetime import datetime, UTC, timedelta


# Test Persona: User A - The Pro
# Active user with specific electrical skill
USER_A_PROFILE = {
    "name": "Alice Professional",
    "email": "alice@example.com",
    "type": "user",
    "fcm_token": "token_alice",
    "has_open_request": False,
    "last_active_date": 1,  # Active 1 day ago
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
USER_B_PROFILE = {
    "name": "Bob Spammer",
    "email": "bob@example.com",
    "type": "user",
    "fcm_token": "token_bob",
    "has_open_request": False,
    "last_active_date": 5,  # Active 5 days ago
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
USER_C_PROFILE = {
    "name": "Charlie Ghost",
    "email": "charlie@example.com",
    "type": "user",
    "fcm_token": "token_charlie",
    "has_open_request": False,
    "last_active_date": 365,  # Inactive for 365 days
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
USER_D_PROFILE = {
    "name": "David Generalist",
    "email": "david@example.com",
    "type": "user",
    "fcm_token": "token_david",
    "has_open_request": False,
    "last_active_date": 10,  # Active 10 days ago
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
USER_E_PROFILE = {
    "name": "Eva Enthusiast",
    "email": "eva@example.com",
    "type": "user",
    "fcm_token": "token_eva",
    "has_open_request": False,
    "last_active_date": 3,  # Active 3 days ago
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
    {"profile": USER_A_PROFILE, "competences": USER_A_COMPETENCES, "name": "User A (The Pro)"},
    {"profile": USER_B_PROFILE, "competences": USER_B_COMPETENCES, "name": "User B (The Spammer)"},
    {"profile": USER_C_PROFILE, "competences": USER_C_COMPETENCES, "name": "User C (The Ghost)"},
    {"profile": USER_D_PROFILE, "competences": USER_D_COMPETENCES, "name": "User D (The Generalist)"},
    {"profile": USER_E_PROFILE, "competences": USER_E_COMPETENCES, "name": "User E (The Enthusiast)"},
]
