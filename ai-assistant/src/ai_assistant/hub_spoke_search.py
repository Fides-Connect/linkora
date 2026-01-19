"""
Hub and Spoke Search: Hybrid Search with Grouping and Filtering
================================================================

Handles:
1. Ghost User Filtering (last_active_date)
2. Hybrid Search (vector + keyword, alpha=0.5)
3. Result Grouping (client-side by owned_by)
"""
import json
import logging
from datetime import datetime, UTC, timedelta
from typing import List, Dict, Any
from weaviate.classes.query import Filter, QueryReference, MetadataQuery

# Handle both package and direct imports
from ai_assistant.hub_spoke_schema import (
    get_unified_profile_collection,
    get_competence_entry_collection
)

logger = logging.getLogger(__name__)


class HubSpokeSearch:
    """
    Search manager for Hub and Spoke architecture.
    
    Implements:
    1. Hybrid search on CompetenceEntry (vector + keyword)
    2. Ghost user filtering (excludes inactive profiles)
    3. Result grouping (one result per profile)
    """
    
    @staticmethod
    def search_competences(
        query: str,
        limit: int = 10,
        max_inactive_days: int = 180,
        group_by_profile: bool = True,
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search for competences with ghost filtering and grouping.
        
        Search Strategy:
        1. Perform hybrid search on CompetenceEntry.description
        2. Filter by owned_by.last_active_date (ghost filtering)
        3. Group by owned_by to prevent duplicate profiles
        
        Args:
            query: Search query text
            limit: Maximum results
            max_inactive_days: Maximum days since last_active_date
            group_by_profile: Whether to group results by profile
            alpha: Hybrid search weight (0=pure vector, 1=pure keyword, 0.5=balanced)
            
        Returns:
            List of competence results with profile info
        """
        try:
            competence_collection = get_competence_entry_collection()
            
            # Calculate cutoff date for ghost filtering
            cutoff_date = datetime.now(UTC) - timedelta(days=max_inactive_days)
            
            # Build query with ghost filtering and provider filtering
            # Filter: owned_by.last_active_date >= cutoff_date AND owned_by.is_provider == True
            filter_clause = Filter.by_ref("owned_by").by_property("last_active_date").greater_or_equal(cutoff_date) & \
                           Filter.by_ref("owned_by").by_property("is_provider").equal(True)
            
            if group_by_profile:
                # Note: Weaviate's GroupBy doesn't work with reference properties,
                # so we'll fetch more results and do client-side grouping
                response = competence_collection.query.hybrid(
                    query=query,
                    limit=limit * 10,  # Fetch more results to ensure we get enough unique profiles
                    filters=filter_clause,
                    alpha=alpha,
                    return_metadata=MetadataQuery(score=True),
                    return_references=QueryReference(
                        link_on="owned_by",
                        return_properties=["name", "email", "type", "is_provider", "last_active_date"]
                    )
                )
                
                # Client-side grouping: Keep only the best competence per profile
                seen_profiles = {}
                for obj in response.objects:
                    competence = obj.properties.copy()
                    competence['uuid'] = str(obj.uuid)
                    competence['score'] = obj.metadata.score if obj.metadata else 0
                    
                    # Extract profile info from references
                    profile_uuid = None
                    if obj.references and 'owned_by' in obj.references:
                        owned_by_refs = obj.references['owned_by'].objects
                        if owned_by_refs:
                            profile = owned_by_refs[0].properties
                            profile_uuid = str(owned_by_refs[0].uuid)
                            competence['profile'] = {
                                'uuid': profile_uuid,
                                'name': profile.get('name'),
                                'email': profile.get('email'),
                                'type': profile.get('type'),
                                'is_provider': profile.get('is_provider', False),
                                'last_active_date': profile.get('last_active_date'),
                            }
                    
                    # Keep only the best-scoring competence per profile
                    if profile_uuid:
                        if profile_uuid not in seen_profiles or competence['score'] > seen_profiles[profile_uuid]['score']:
                            seen_profiles[profile_uuid] = competence
                
                results = list(seen_profiles.values())[:limit]  # Limit to requested number
                
                logger.info(f"Grouped search found {len(results)} unique profiles for: '{query[:50]}...'")
                return results
                
            else:
                # Hybrid search WITHOUT grouping (may return multiple competences per profile)
                response = competence_collection.query.hybrid(
                    query=query,
                    limit=limit,
                    filters=filter_clause,
                    alpha=alpha,
                    return_metadata=MetadataQuery(score=True),
                    return_references=QueryReference(
                        link_on="owned_by",
                        return_properties=["name", "email", "type", "is_provider", "last_active_date"]
                    )
                )
                
                results = []
                for obj in response.objects:
                    competence = obj.properties.copy()
                    competence['uuid'] = str(obj.uuid)
                    competence['score'] = obj.metadata.score if obj.metadata else 0
                    
                    # Extract profile info
                    if obj.references and 'owned_by' in obj.references:
                        owned_by_refs = obj.references['owned_by'].objects
                        if owned_by_refs:
                            profile = owned_by_refs[0].properties
                            competence['profile'] = {
                                'uuid': str(owned_by_refs[0].uuid),
                                'name': profile.get('name'),
                                'email': profile.get('email'),
                                'type': profile.get('type'),
                                'last_active_date': profile.get('last_active_date'),
                            }
                    
                    results.append(competence)
                
                logger.info(f"Ungrouped search found {len(results)} competences for: '{query[:50]}...'")
                return results
            
        except Exception as e:
            logger.error(f"Error searching competences: {e}")
            return []
    
    @staticmethod
    def get_profile_competences(profile_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all competences for a specific profile.
        
        Args:
            profile_uuid: UUID of the profile
            
        Returns:
            List of competence dictionaries
        """
        try:
            profile_collection = get_unified_profile_collection()
            
            # Fetch profile with competence references
            response = profile_collection.query.fetch_object_by_id(
                uuid=profile_uuid,
                return_references=QueryReference(
                    link_on="has_competences",
                    return_properties=["title", "description", "category", "price_range"]
                )
            )
            
            if not response:
                return []
            
            # Extract competences from references
            competences = []
            if response.references and 'has_competences' in response.references:
                for comp_obj in response.references['has_competences'].objects:
                    comp = comp_obj.properties.copy()
                    comp['uuid'] = str(comp_obj.uuid)
                    competences.append(comp)
            
            logger.info(f"Retrieved {len(competences)} competences for profile {profile_uuid}")
            return competences
            
        except Exception as e:
            logger.error(f"Error getting profile competences: {e}")
            return []
    
    @staticmethod
    def hybrid_search_providers(
        search_request: Dict[str, Any],
        limit: int = 10,
        max_inactive_days: int = 180,
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search for providers with structured filtering.
        
        Search Strategy:
        1. Filter by metadata: available_time
        2. Combine vector search for category + criterions
        3. Sort by relevance (score)
        
        Args:
            search_request: Structured search query with keys:
                - available_time: when service is needed
                - category: service category
                - criterions: list of additional requirements
            limit: Maximum results
            max_inactive_days: Maximum days since last_active_date
            alpha: Hybrid search weight (0=pure vector, 1=pure keyword, 0.5=balanced)
            
        Returns:
            List of provider results sorted by relevance
        """
        try:
            competence_collection = get_competence_entry_collection()
            
            # Calculate cutoff date for ghost filtering
            cutoff_date = datetime.now(UTC) - timedelta(days=max_inactive_days)
            
            # Build base filter: ghost filtering + provider filtering
            filter_clause = (
                Filter.by_ref("owned_by").by_property("last_active_date").greater_or_equal(cutoff_date) &
                Filter.by_ref("owned_by").by_property("is_provider").equal(True)
            )
            
            # Add availability filter if specified
            available_time = search_request.get("available_time") or ""
            if isinstance(available_time, str):
                available_time = available_time.strip()
            else:
                available_time = ""
            
            if available_time and available_time.lower() not in ["flexibel", "flexible", "any", ""]:
                # For availability, we can use contains to check if the time matches
                # This is a simple implementation - could be enhanced with date parsing
                filter_clause = filter_clause & Filter.by_property("availability").contains_any([available_time])
                logger.info(f"Added availability filter: {available_time}")
            
            # Build combined query text for vector search
            category = search_request.get("category") or ""
            if isinstance(category, str):
                category = category.strip()
            else:
                category = ""
            
            criterions = search_request.get("criterions") or []
            # Ensure criterions is a list
            if not isinstance(criterions, list):
                criterions = []
            
            # Combine category and criterions into a single query
            query_parts = []
            if category:
                query_parts.append(category)
            if criterions:
                # Join all criterions, handling None values
                for criterion in criterions:
                    if criterion and isinstance(criterion, str):
                        criterion_stripped = criterion.strip()
                        if criterion_stripped:
                            query_parts.append(criterion_stripped)
            
            query_text = " ".join(query_parts)
            
            if not query_text:
                query_text = "service provider"  # Fallback if no query text
            
            logger.info(f"Hybrid search query: '{query_text[:100]}...'")
            logger.info(f"Active filters: availability={available_time or 'none'}")
            
            # Perform hybrid search with filters
            response = competence_collection.query.hybrid(
                query=query_text,
                limit=limit * 10,  # Fetch more for client-side grouping
                filters=filter_clause,
                alpha=alpha,
                return_metadata=MetadataQuery(score=True),
                return_references=QueryReference(
                    link_on="owned_by",
                    return_properties=["name", "email", "type", "is_provider", "last_active_date"]
                )
            )
            
            # Client-side grouping: Keep only the best competence per profile
            seen_profiles = {}
            for obj in response.objects:
                competence = obj.properties.copy()
                competence['uuid'] = str(obj.uuid)
                competence['score'] = obj.metadata.score if obj.metadata else 0
                
                # Extract profile info from references
                profile_uuid = None
                if obj.references and 'owned_by' in obj.references:
                    owned_by_refs = obj.references['owned_by'].objects
                    if owned_by_refs:
                        profile = owned_by_refs[0].properties
                        profile_uuid = str(owned_by_refs[0].uuid)
                        competence['profile'] = {
                            'uuid': profile_uuid,
                            'name': profile.get('name'),
                            'email': profile.get('email'),
                            'type': profile.get('type'),
                            'is_provider': profile.get('is_provider', False),
                            'last_active_date': profile.get('last_active_date'),
                        }
                
                # Keep only the best-scoring competence per profile
                if profile_uuid:
                    if profile_uuid not in seen_profiles or competence['score'] > seen_profiles[profile_uuid]['score']:
                        seen_profiles[profile_uuid] = competence
            
            # Sort by score (descending) and limit results
            results = sorted(seen_profiles.values(), key=lambda x: x.get('score', 0), reverse=True)[:limit]
            
            logger.info(f"Hybrid search found {len(results)} unique providers")
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid_search_providers: {e}", exc_info=True)
            return []
