"""
Test data for AI Assistant
Contains sample user data and service providers for testing conversation flow.
"""

# Sample user data
USER_DATA = {
    "user_id": "user_123",
    "name": "Wolfgang",
    "email": "wolfgang@example.com",
    "address": "Hauptstraße 42, 10115 Berlin",
    "has_open_request": False,
}

# Sample service providers
SERVICE_PROVIDERS = [
    {
        "id": "provider_001",
        "name": "GreenThumb Gartenpflege",
        "category": "Gartenpflege",
        "skills": ["Rasenmähen", "Heckenschneiden", "Gartengestaltung"],
        "rating": 4.8,
        "experience_years": 5,
        "price_range": "€50-€60",
        "availability": "Mo-Sa",
        "description": "Professioneller Gartenpflegeservice mit langjähriger Erfahrung"
    },
    {
        "id": "provider_002",
        "name": "TechFix IT-Support",
        "category": "IT-Support",
        "skills": ["Drucker-Reparatur", "Netzwerk-Installation", "PC-Wartung"],
        "rating": 4.9,
        "experience_years": 8,
        "price_range": "€50-€60",
        "availability": "Mo-Fr",
        "description": "Zertifizierte IT-Spezialisten für alle technischen Probleme"
    },
    {
        "id": "provider_003",
        "name": "Schmidt Handwerk",
        "category": "Handwerk",
        "skills": ["Reparaturen", "Installation", "Renovierung"],
        "rating": 4.7,
        "experience_years": 12,
        "price_range": "€50-€60",
        "availability": "Mo-Sa",
        "description": "Zuverlässiger Handwerker für alle Reparaturen im Haushalt"
    },
    {
        "id": "provider_004",
        "name": "PrintMaster Solutions",
        "category": "IT-Support",
        "skills": ["Drucker-Reparatur", "Scanner-Service", "Kopierer-Wartung"],
        "rating": 4.6,
        "experience_years": 6,
        "price_range": "€50-€60",
        "availability": "Mo-Fr",
        "description": "Spezialisiert auf Drucker- und Kopierer-Service"
    },
    {
        "name": "Rasen-Profis Berlin",
        "category": "Gartenpflege",
        "skills": ["Rasenmähen", "Vertikutieren", "Rasenpflege"],
        "rating": 4.5,
        "experience_years": 3,
        "price_range": "€50-€60",
        "availability": "Mo-So",
        "description": "Günstige und schnelle Rasenpflege in Berlin"
    },
    {
        "id": "provider_005",
        "id": "provider_006",
        "name": "ElektroFix Express",
        "category": "Elektrik",
        "skills": ["Elektrische Reparaturen", "Installation", "Fehlersuche"],
        "rating": 4.8,
        "experience_years": 10,
        "price_range": "€50-€60",
        "availability": "Mo-Sa",
        "description": "Schneller Elektrik-Service mit Notdienst"
    },
    {
        "id": "provider_007",
        "name": "Klempner24",
        "category": "Sanitär",
        "skills": ["Rohrreinigung", "Sanitärinstallation", "Wasserschaden"],
        "rating": 4.7,
        "experience_years": 15,
        "price_range": "€50-€60",
        "availability": "24/7",
        "description": "Klempner-Notdienst rund um die Uhr verfügbar"
    },
    {
        "id": "provider_008",
        "name": "Garten & Mehr",
        "category": "Gartenpflege",
        "skills": ["Rasenmähen", "Baumpflege", "Gartenplanung"],
        "rating": 4.9,
        "experience_years": 7,
        "price_range": "€50-€60",
        "availability": "Mo-Sa",
        "description": "Premium Gartenpflege mit Beratungsservice"
    },
    {
        "id": "provider_009",
        "name": "PC-Doktor Berlin",
        "category": "IT-Support",
        "skills": ["PC-Reparatur", "Datenrettung", "Virus-Entfernung"],
        "rating": 4.6,
        "experience_years": 9,
        "price_range": "€50-€60",
        "availability": "Mo-Fr",
        "description": "Computer-Reparatur und IT-Beratung vor Ort"
    },
    {
        "id": "provider_010",
        "name": "MalerMeister Plus",
        "category": "Malerei",
        "skills": ["Innenmalerei", "Außenmalerei", "Tapezieren"],
        "rating": 4.8,
        "experience_years": 11,
        "price_range": "€50-€60",
        "availability": "Mo-Fr",
        "description": "Professionelle Malerarbeiten für Wohnung und Haus"
    }
]


def search_providers(query: str, category: str = None, limit: int = 3):
    """
    Simple search function to find matching service providers.
    
    Args:
        query: Search query (problem description)
        category: Optional category filter
        limit: Maximum number of results
        
    Returns:
        List of matching providers sorted by relevance
    """
    query_lower = query.lower()
    matches = []
    
    for provider in SERVICE_PROVIDERS:
        score = 0
        
        # Category match (highest priority)
        if category and provider["category"].lower() == category.lower():
            score += 50
        
        # Skills match
        for skill in provider["skills"]:
            if skill.lower() in query_lower:
                score += 20
        
        # Category in query
        if provider["category"].lower() in query_lower:
            score += 15
        
        # Rating bonus
        score += provider["rating"] * 2
        
        # Experience bonus
        score += min(provider["experience_years"], 10)
        
        if score > 0:
            matches.append((score, provider))
    
    # Sort by score (descending)
    matches.sort(key=lambda x: x[0], reverse=True)
    
    # Return top matches
    return [provider for score, provider in matches[:limit]]


# Keyword mappings for category detection
CATEGORY_KEYWORDS = {
    "Gartenpflege": ["rasen", "mähen", "garten", "hecke", "grün", "pflanzen", "baum"],
    "IT-Support": ["drucker", "computer", "pc", "laptop", "netzwerk", "wlan", "wifi", "internet", "software", "hardware"],
    "Handwerk": ["reparatur", "reparieren", "kaputt", "defekt", "installieren"],
    "Elektrik": ["elektrik", "strom", "lampe", "licht", "steckdose", "sicherung"],
    "Sanitär": ["wasser", "rohr", "waschbecken", "toilette", "bad", "dusche", "klempner"],
    "Malerei": ["malen", "streichen", "farbe", "wand", "tapete"],
}


def detect_category(text: str) -> str:
    """
    Detect the most likely category from user's text.
    
    Args:
        text: User's problem description
        
    Returns:
        Detected category name or None
    """
    text_lower = text.lower()
    category_scores = {}
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            category_scores[category] = score
    
    if category_scores:
        return max(category_scores, key=category_scores.get)
    
    return None
