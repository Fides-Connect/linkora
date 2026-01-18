"""
Hub and Spoke Ingestion: Data Sanitization and Enrichment
==========================================================

Handles:
1. SEO Spam Defense (sanitize_input)
2. Granularity Enrichment (enrich_text)
3. Bidirectional Linking (Profile ↔ Competence)
"""
import re
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

from ai_assistant.hub_spoke_schema import (
    get_unified_profile_collection,
    get_competence_entry_collection
)

logger = logging.getLogger(__name__)


def sanitize_input(text: str, max_unique_words: int = 20) -> str:
    """
    SEO Spam Defense: Strip keyword stuffing from input text.
    
    Strategy:
    1. Extract unique words (case-insensitive)
    2. If unique word count > threshold, it's likely spam
    3. Truncate or reject the text
    
    Example:
        Input: "Plumber Electrician Driver Nurse Teacher Plumber Driver"
        Output: Returns only first 20 unique words
        
    Args:
        text: Input text to sanitize
        max_unique_words: Maximum unique words allowed before truncation
        
    Returns:
        Sanitized text
    """
    if not text or not text.strip():
        return ""
    
    # Split into words and normalize
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Get unique words while preserving order
    seen = set()
    unique_words = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)
    
    # If too many unique words, it's likely spam - truncate
    if len(unique_words) > max_unique_words:
        logger.warning(f"Keyword stuffing detected: {len(unique_words)} unique words. Truncating.")
        # Reconstruct from original text to maintain case and punctuation
        truncated = ' '.join(unique_words[:max_unique_words])
        return truncated
    
    return text


def enrich_text(text: str, category: str) -> str:
    """
    Granularity Enrichment: Expand specific skill text with parent categories.
    
    Strategy:
    1. Map categories to parent terms
    2. Append parent terms to original text
    3. Improves recall for broad searches
    
    Example:
        Input: text="Installing Pot Lights", category="Electrical"
        Output: "Installing Pot Lights Electrician Electrical Lighting Wiring"
        
    This ensures a search for "Electrician" matches specific skills like "Pot Lights"
    
    Args:
        text: Original skill description
        category: Skill category
        
    Returns:
        Enriched text with parent category terms
    """
    # Category enrichment map: category -> parent terms
    enrichment_map = {
        "Electrical": ["Electrician", "Electrical", "Lighting", "Wiring", "Power"],
        "Plumbing": ["Plumber", "Plumbing", "Pipes", "Water", "Drain"],
        "Gardening": ["Gardener", "Gardening", "Landscaping", "Plants", "Outdoor"],
        "Carpentry": ["Carpenter", "Carpentry", "Woodwork", "Construction"],
        "Cleaning": ["Cleaner", "Cleaning", "Housekeeping", "Janitorial"],
        "IT": ["Technician", "Technology", "Computer", "Software", "Hardware"],
    }
    
    # Get parent terms for category
    parent_terms = enrichment_map.get(category, [category])
    
    # Append parent terms to original text
    enriched = f"{text} {' '.join(parent_terms)}"
    
    logger.debug(f"Enriched '{text}' → '{enriched}'")
    return enriched


class HubSpokeIngestion:
    """
    Ingestion manager for Hub and Spoke architecture.
    
    Handles:
    1. Creating UnifiedProfile (Hub)
    2. Creating CompetenceEntry (Spoke)
    3. Establishing bidirectional links
    """
    
    @staticmethod
    def create_profile(profile_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a UnifiedProfile (Hub).
        
        Args:
            profile_data: Dict with keys: name, email, type, fcm_token, 
                         has_open_request, last_active_date
                         
        Returns:
            UUID of created profile
        """
        try:
            collection = get_unified_profile_collection()
            
            # Handle last_active_date: can be datetime or days offset
            last_active = profile_data.get("last_active_date")
            if isinstance(last_active, int):
                # Treat as days ago
                from datetime import timedelta
                last_active = datetime.now(UTC) - timedelta(days=last_active)
            elif not isinstance(last_active, datetime):
                last_active = datetime.now(UTC)
            
            uuid = collection.data.insert(
                properties={
                    "name": profile_data.get("name"),
                    "email": profile_data.get("email"),
                    "type": profile_data.get("type", "user"),
                    "is_provider": profile_data.get("is_provider", False),
                    "fcm_token": profile_data.get("fcm_token", ""),
                    "created_at": profile_data.get("created_at", datetime.now(UTC)),
                    "has_open_request": profile_data.get("has_open_request", False),
                    "last_active_date": last_active,
                }
            )
            
            logger.info(f"Created UnifiedProfile: {profile_data.get('name')} (UUID: {uuid})")
            return str(uuid)
            
        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            return None
    
    @staticmethod
    def create_competence(
        competence_data: Dict[str, Any],
        profile_uuid: str,
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> Optional[str]:
        """
        Create a CompetenceEntry (Spoke) with bidirectional link to Profile.
        
        Critical Logic:
        1. Sanitize description to prevent keyword stuffing
        2. Enrich description with parent category terms
        3. Create competence with owned_by reference to Profile
        4. Add competence reference to Profile's has_competences
        
        Args:
            competence_data: Dict with keys: title, description, category, price_range
            profile_uuid: UUID of the owning UnifiedProfile
            apply_sanitization: Whether to sanitize description
            apply_enrichment: Whether to enrich description
            
        Returns:
            UUID of created competence
        """
        try:
            profile_collection = get_unified_profile_collection()
            competence_collection = get_competence_entry_collection()
            
            # Process description
            description = competence_data.get("description", "")
            category = competence_data.get("category", "")
            
            # Step 1: Sanitize (SEO spam defense)
            if apply_sanitization:
                description = sanitize_input(description)
            
            # Step 2: Enrich (granularity enhancement)
            if apply_enrichment and category:
                description = enrich_text(description, category)
            
            # Step 3: Create CompetenceEntry with owned_by reference
            competence_uuid = competence_collection.data.insert(
                properties={
                    "title": competence_data.get("title"),
                    "description": description,
                    "category": category,
                    "price_range": competence_data.get("price_range", ""),
                },
                references={
                    "owned_by": profile_uuid  # Link to Profile (Spoke → Hub)
                }
            )
            
            logger.info(f"Created CompetenceEntry: {competence_data.get('title')} (UUID: {competence_uuid})")
            
            # Step 4: Add reverse reference (Hub → Spoke)
            # Add competence to Profile's has_competences list
            profile_collection.data.reference_add(
                from_uuid=profile_uuid,
                from_property="has_competences",
                to=competence_uuid
            )
            
            logger.info(f"Linked Profile {profile_uuid} ↔ Competence {competence_uuid}")
            return str(competence_uuid)
            
        except Exception as e:
            logger.error(f"Error creating competence: {e}")
            return None
    
    @staticmethod
    def create_profile_with_competences(
        profile_data: Dict[str, Any],
        competences_data: List[Dict[str, Any]],
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Create a complete Profile with multiple Competences.
        
        Convenience method for bulk ingestion.
        
        Args:
            profile_data: Profile properties
            competences_data: List of competence properties
            apply_sanitization: Whether to sanitize descriptions
            apply_enrichment: Whether to enrich descriptions
            
        Returns:
            Dict with profile_uuid and list of competence_uuids
        """
        try:
            # Create profile
            profile_uuid = HubSpokeIngestion.create_profile(profile_data)
            if not profile_uuid:
                return None
            
            # Create competences
            competence_uuids = []
            for comp_data in competences_data:
                comp_uuid = HubSpokeIngestion.create_competence(
                    comp_data,
                    profile_uuid,
                    apply_sanitization=apply_sanitization,
                    apply_enrichment=apply_enrichment
                )
                if comp_uuid:
                    competence_uuids.append(comp_uuid)
            
            result = {
                "profile_uuid": profile_uuid,
                "competence_uuids": competence_uuids
            }
            
            logger.info(f"Created profile with {len(competence_uuids)} competences")
            return result
            
        except Exception as e:
            logger.error(f"Error creating profile with competences: {e}")
            return None
