"""
Hub and Spoke Ingestion: Data Sanitization and Enrichment
==========================================================

Handles:
1. SEO Spam Defense (sanitize_input)
2. Granularity Enrichment (enrich_text)
3. Bidirectional Linking (User ↔ Competence)
"""
import re
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional

from ai_assistant.hub_spoke_schema import (
    get_user_collection,
    get_competence_collection
)
from weaviate.classes.query import Filter

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
    1. Creating User (Hub)
    2. Creating Competence (Spoke)
    3. Establishing bidirectional links
    """
    
    @staticmethod
    def add_user(user_data: Dict[str, Any]) -> Optional[str]:
        """
        Adds a User (Hub).
        
        Args:
            user_data: Dict with keys: name, email, fcm_token, 
                         has_open_request, last_sign_in
                         
        Returns:
            UUID of added user
        """
        try:
            collection = get_user_collection()
            
            # Handle last_sign_in: can be datetime or days offset
            last_active = user_data.get("last_sign_in")
            if isinstance(last_active, int):
                # Treat as days ago
                from datetime import timedelta
                last_active = datetime.now(UTC) - timedelta(days=last_active)
            elif not isinstance(last_active, datetime):
                last_active = datetime.now(UTC)
            
            uuid = collection.data.insert(
                properties={
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "location": user_data.get("location", ""),
                    "user_id": user_data.get("user_id"),
                    "self_introduction": user_data.get("self_introduction", ""),
                    "is_service_provider": user_data.get("is_service_provider", False),
                    "fcm_token": user_data.get("fcm_token", ""),
                    "feedback_positive": user_data.get("feedback_positive", []),
                    "feedback_negative": user_data.get("feedback_negative", []),
                    "average_rating": user_data.get("average_rating", 0.0),
                    "review_count": user_data.get("review_count", 0),
                    "created_at": user_data.get("created_at", datetime.now(UTC)),
                    "has_open_request": user_data.get("has_open_request", False),
                    "last_sign_in": last_active,
                }
            )
            
            logger.info(f"Created User: {user_data.get('name')} (UUID: {uuid})")
            return str(uuid)
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    @staticmethod
    def create_competence(
        competence_data: Dict[str, Any],
        user_uuid: str,
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> Optional[str]:
        """
        Create a Competence (Spoke) with bidirectional link to User.
        
        Critical Logic:
        1. Sanitize description to prevent keyword stuffing
        2. Enrich description with parent category terms
        3. Create competence with owned_by reference to User
        4. Add competence reference to User's has_competences
        
        Args:
            competence_data: Dict with keys: title, description, category, price_range
            user_uuid: UUID of the owning User
            apply_sanitization: Whether to sanitize description
            apply_enrichment: Whether to enrich description
            
        Returns:
            UUID of created competence
        """
        try:
            user_collection = get_user_collection()
            competence_collection = get_competence_collection()
            
            # Process description
            description = competence_data.get("description", "")
            category = competence_data.get("category", "")
            
            # Step 1: Sanitize (SEO spam defense)
            if apply_sanitization:
                description = sanitize_input(description)
            
            # Step 2: Enrich (granularity enhancement)
            if apply_enrichment and category:
                description = enrich_text(description, category)
            
            # Step 3: Create Competence with owned_by reference
            competence_uuid = competence_collection.data.insert(
                properties={
                    "competence_id": competence_data.get("competence_id", ""),
                    "title": competence_data.get("title"),
                    "description": description,
                    "category": category,
                    "price_range": competence_data.get("price_range", ""),
                },
                references={
                    "owned_by": user_uuid  # Link to User (Spoke → Hub)
                }
            )
            
            logger.info(f"Created Competence: {competence_data.get('title')} (UUID: {competence_uuid})")
            
            # Step 4: Add reverse reference (Hub → Spoke)
            # Add competence to User's has_competences list
            user_collection.data.reference_add(
                from_uuid=user_uuid,
                from_property="has_competences",
                to=competence_uuid
            )
            
            logger.info(f"Linked User {user_uuid} ↔ Competence {competence_uuid}")
            return str(competence_uuid)
            
        except Exception as e:
            logger.error(f"Error creating competence: {e}")
            return None
    
    @staticmethod
    def add_user_with_competences(
        user_data: Dict[str, Any],
        competences_data: List[Dict[str, Any]],
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Create a complete User with multiple Competences.
        
        Convenience method for bulk ingestion.
        
        Args:
            user_data: User properties
            competences_data: List of competence properties
            apply_sanitization: Whether to sanitize descriptions
            apply_enrichment: Whether to enrich descriptions
            
        Returns:
            Dict with user_uuid and list of competence_uuids
        """
        try:
            # Create user
            user_uuid = HubSpokeIngestion.add_user(user_data)
            if not user_uuid:
                return None
            
            # Create competences
            competence_uuids = []
            for comp_data in competences_data:
                comp_uuid = HubSpokeIngestion.create_competence(
                    comp_data,
                    user_uuid,
                    apply_sanitization=apply_sanitization,
                    apply_enrichment=apply_enrichment
                )
                if comp_uuid:
                    competence_uuids.append(comp_uuid)
            
            result = {
                "user_uuid": user_uuid,
                "competence_uuids": competence_uuids
            }
            
            logger.info(f"Created user with {len(competence_uuids)} competences")
            return result
            
        except Exception as e:
            logger.error(f"Error creating user with competences: {e}")
            return None
    
    @staticmethod
    def add_competences_by_user_id(
        user_id: str,
        competences: str | List[str],
        category: str = "",
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> Dict[str, Any]:
        """
        Add new competences to an existing user by user_id.
        
        Args:
            user_id: The user_id to add competences to
            competences: Single string or list of strings describing competences
            category: Category for the competences (optional)
            apply_sanitization: Whether to sanitize descriptions
            apply_enrichment: Whether to enrich descriptions
            
        Returns:
            Dict with success status and list of added competence UUIDs
        """
        try:
            user_collection = get_user_collection()
            
            # Find user by user_id
            from weaviate.classes.query import Filter
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )
            
            if not result.objects:
                logger.error(f"No user found with user_id: {user_id}")
                return {"success": False, "error": "User not found", "added_uuids": []}
            
            user_uuid = str(result.objects[0].uuid)
            logger.info(f"Found user {user_uuid} for user_id {user_id}")
            
            # Normalize input to list
            if isinstance(competences, str):
                competences_list = [competences]
            else:
                competences_list = competences
            
            # Add each competence
            added_uuids = []
            for comp_text in competences_list:
                comp_data = {
                    "title": comp_text[:50] if len(comp_text) > 50 else comp_text,
                    "description": comp_text,
                    "category": category,
                    "price_range": ""
                }
                
                comp_uuid = HubSpokeIngestion.create_competence(
                    competence_data=comp_data,
                    user_uuid=user_uuid,
                    apply_sanitization=apply_sanitization,
                    apply_enrichment=apply_enrichment
                )
                
                if comp_uuid:
                    added_uuids.append(comp_uuid)
                    logger.info(f"Added competence: {comp_uuid}")
            
            logger.info(f"Added {len(added_uuids)} competences to user {user_id}")
            return {
                "success": True,
                "added_uuids": added_uuids,
                "count": len(added_uuids)
            }
            
        except Exception as e:
            logger.error(f"Error adding competences: {e}")
            return {"success": False, "error": str(e), "added_uuids": []}
    
    @staticmethod
    def update_competences_by_user_id(
        user_id: str,
        competences: str | List[str],
        category: str = "",
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> Dict[str, Any]:
        """
        Update (replace) competences for a user by user_id.
        Deletes existing competences and creates new ones.
        
        Args:
            user_id: The user_id to update competences for
            competences: Single string or list of strings describing new competences
            category: Category for the competences (optional)
            apply_sanitization: Whether to sanitize descriptions
            apply_enrichment: Whether to enrich descriptions
            
        Returns:
            Dict with success status and list of updated competence UUIDs
        """
        try:
            user_collection = get_user_collection()
            competence_collection = get_competence_collection()
            
            # Find user by user_id
            from weaviate.classes.query import Filter
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )
            
            if not result.objects:
                logger.error(f"No user found with user_id: {user_id}")
                return {"success": False, "error": "User not found", "updated_uuids": []}
            
            user_uuid = str(result.objects[0].uuid)
            logger.info(f"Found user {user_uuid} for user_id {user_id}")
            
            # Delete all existing competences
            from weaviate.classes.query import QueryReference
            user_with_refs = user_collection.query.fetch_object_by_id(
                uuid=user_uuid,
                return_references=QueryReference(link_on="has_competences")
            )
            
            if user_with_refs.references and 'has_competences' in user_with_refs.references:
                for comp_obj in user_with_refs.references['has_competences'].objects:
                    comp_uuid = str(comp_obj.uuid)
                    # Delete the competence
                    competence_collection.data.delete_by_id(comp_uuid)
                    # Remove reference from user
                    user_collection.data.reference_delete(
                        from_uuid=user_uuid,
                        from_property="has_competences",
                        to=comp_uuid
                    )
                    logger.info(f"Deleted old competence: {comp_uuid}")
            
            # Normalize input to list
            if isinstance(competences, str):
                competences_list = [competences]
            else:
                competences_list = competences
            
            # Add new competences
            updated_uuids = []
            for comp_text in competences_list:
                comp_data = {
                    "title": comp_text[:50] if len(comp_text) > 50 else comp_text,
                    "description": comp_text,
                    "category": category,
                    "price_range": ""
                }
                
                comp_uuid = HubSpokeIngestion.create_competence(
                    competence_data=comp_data,
                    user_uuid=user_uuid,
                    apply_sanitization=apply_sanitization,
                    apply_enrichment=apply_enrichment
                )
                
                if comp_uuid:
                    updated_uuids.append(comp_uuid)
                    logger.info(f"Created new competence: {comp_uuid}")
            
            logger.info(f"Updated competences for user {user_id}: {len(updated_uuids)} new competences")
            return {
                "success": True,
                "updated_uuids": updated_uuids,
                "count": len(updated_uuids)
            }
            
        except Exception as e:
            logger.error(f"Error updating competences: {e}")
            return {"success": False, "error": str(e), "updated_uuids": []}
    
    @staticmethod
    def delete_competences_by_user_id(
        user_id: str,
        competences: str | List[str]
    ) -> Dict[str, Any]:
        """
        Delete specific competences for a user by user_id.
        Matches competences by title or description pattern.
        
        Args:
            user_id: The user_id to delete competences from
            competences: Single string or list of strings to match against competence titles/descriptions
            
        Returns:
            Dict with success status and list of deleted competence UUIDs
        """
        try:
            user_collection = get_user_collection()
            competence_collection = get_competence_collection()
            
            # Find user by user_id
            from weaviate.classes.query import Filter, QueryReference
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )
            
            if not result.objects:
                logger.error(f"No user found with user_id: {user_id}")
                return {"success": False, "error": "User not found", "deleted_uuids": []}
            
            user_uuid = str(result.objects[0].uuid)
            logger.info(f"Found user {user_uuid} for user_id {user_id}")
            
            # Get all competences for this user
            user_with_refs = user_collection.query.fetch_object_by_id(
                uuid=user_uuid,
                return_references=QueryReference(
                    link_on="has_competences",
                    return_properties=["title", "description", "category"]
                )
            )
            
            if not user_with_refs.references or 'has_competences' not in user_with_refs.references:
                logger.info(f"No competences found for user {user_id}")
                return {"success": True, "deleted_uuids": [], "count": 0}
            
            # Normalize input to list
            if isinstance(competences, str):
                patterns = [competences.lower()]
            else:
                patterns = [c.lower() for c in competences]
            
            # Find and delete matching competences
            deleted_uuids = []
            for comp_obj in user_with_refs.references['has_competences'].objects:
                comp_uuid = str(comp_obj.uuid)
                comp_props = comp_obj.properties
                comp_title = (comp_props.get('title') or '').lower()
                comp_desc = (comp_props.get('description') or '').lower()
                comp_category = (comp_props.get('category') or '').lower()
                
                # Check if any pattern matches
                for pattern in patterns:
                    if pattern in comp_title or pattern in comp_desc or pattern in comp_category:
                        # Delete the competence
                        competence_collection.data.delete_by_id(comp_uuid)
                        # Remove reference from user
                        user_collection.data.reference_delete(
                            from_uuid=user_uuid,
                            from_property="has_competences",
                            to=comp_uuid
                        )
                        deleted_uuids.append(comp_uuid)
                        logger.info(f"Deleted competence: {comp_uuid} (matched pattern: '{pattern}')")
                        break  # Only delete once per competence
            
            logger.info(f"Deleted {len(deleted_uuids)} competences for user {user_id}")
            return {
                "success": True,
                "deleted_uuids": deleted_uuids,
                "count": len(deleted_uuids)
            }
            
        except Exception as e:
            logger.error(f"Error deleting competences: {e}")
            return {"success": False, "error": str(e), "deleted_uuids": []}

    @staticmethod
    def remove_competence_by_firestore_id(firestore_id: str) -> bool:
        """
        Remove a competence by its Firestore ID.
        
        Args:
            firestore_id: The Firestore competence_id (e.g., 'competence_12345')
            
        Returns:
            bool: True if deletion was successful (or if not found, as it's idempotent-ish)
        """
        try:
            collection = get_competence_collection()
            # Find by competence_id
            response = collection.query.fetch_objects(
                filters=Filter.by_property("competence_id").equal(firestore_id),
                limit=1
            )
            
            if not response.objects:
                logger.info(f"Competence not found for deletion (already deleted?): {firestore_id}")
                return True
                
            uuid = response.objects[0].uuid
            collection.data.delete_by_id(uuid)
            logger.info(f"Deleted competence {firestore_id} (UUID: {uuid})")
            return True
        except Exception as e:
            logger.error(f"Error removing competence {firestore_id}: {e}")
            # Log error but don't crash main loop if used in bulk
            return False
