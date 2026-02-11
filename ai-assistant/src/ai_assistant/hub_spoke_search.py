"""
Hub and Spoke Search: Hybrid Search with Grouping and Filtering
================================================================

Handles:
1. Ghost User Filtering (last_sign_in)
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
    get_user_collection,
    get_competence_collection
)

logger = logging.getLogger(__name__)


class HubSpokeSearch:
    """
    Search manager for Hub and Spoke architecture.
    
    Implements:
    1. Hybrid search on Competence (vector + keyword)
    2. Ghost user filtering (excludes inactive users)
    3. Result grouping (one result per user)
    """
    
    @staticmethod
    def search_competencies(
        query: str,
        limit: int = 10,
        max_inactive_days: int = 180,
        group_by_user: bool = True,
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search for competencies with ghost filtering and grouping.
        
        Search Strategy:
        1. Perform hybrid search on Competence.description
        2. Filter by owned_by.last_sign_in (ghost filtering)
        3. Group by owned_by to prevent duplicate users
        
        Args:
            query: Search query text
            limit: Maximum results
            max_inactive_days: Maximum days since last_sign_in
            group_by_user: Whether to group results by user
            alpha: Hybrid search weight (0=pure vector, 1=pure keyword, 0.5=balanced)
            
        Returns:
            List of competence results with user info
        """
        try:
            competence_collection = get_competence_collection()
            
            # Calculate cutoff date for ghost filtering
            cutoff_date = datetime.now(UTC) - timedelta(days=max_inactive_days)
            
            # Build query with ghost filtering and provider filtering
            # Filter: owned_by.last_sign_in >= cutoff_date AND owned_by.is_service_provider == True
            filter_clause = Filter.by_ref("owned_by").by_property("last_sign_in").greater_or_equal(cutoff_date) & \
                           Filter.by_ref("owned_by").by_property("is_service_provider").equal(True)
            
            if group_by_user:
                # Note: Weaviate's GroupBy doesn't work with reference properties,
                # so we'll fetch more results and do client-side grouping
                response = competence_collection.query.hybrid(
                    query=query,
                    limit=limit * 10,  # Fetch more results to ensure we get enough unique users
                    filters=filter_clause,
                    alpha=alpha,
                    return_metadata=MetadataQuery(score=True),
                    return_references=QueryReference(
                        link_on="owned_by",
                        return_properties=["name", "email", "is_service_provider", "last_sign_in"]
                    )
                )
                
                # Client-side grouping: Keep only the best competence per user
                seen_users = {}
                for obj in response.objects:
                    competence = obj.properties.copy()
                    competence['uuid'] = str(obj.uuid)
                    competence['score'] = obj.metadata.score if obj.metadata else 0
                    
                    # Extract user info from references
                    user_uuid = None
                    if obj.references and 'owned_by' in obj.references:
                        owned_by_refs = obj.references['owned_by'].objects
                        if owned_by_refs:
                            user = owned_by_refs[0].properties
                            user_uuid = str(owned_by_refs[0].uuid)
                            competence['user'] = {
                                'uuid': user_uuid,
                                'name': user.get('name'),
                                'email': user.get('email'),
                                'is_service_provider': user.get('is_service_provider', False),
                                'last_sign_in': user.get('last_sign_in'),
                            }
                    
                    # Keep only the best-scoring competence per user
                    if user_uuid:
                        if user_uuid not in seen_users or competence['score'] > seen_users[user_uuid]['score']:
                            seen_users[user_uuid] = competence
                
                results = list(seen_users.values())[:limit]  # Limit to requested number
                
                logger.info(f"Grouped search found {len(results)} unique users for: '{query[:50]}...'")
                return results
                
            else:
                # Hybrid search WITHOUT grouping (may return multiple competencies per user)
                response = competence_collection.query.hybrid(
                    query=query,
                    limit=limit,
                    filters=filter_clause,
                    alpha=alpha,
                    return_metadata=MetadataQuery(score=True),
                    return_references=QueryReference(
                        link_on="owned_by",
                        return_properties=["name", "email", "is_service_provider", "last_sign_in"]
                    )
                )
                
                results = []
                for obj in response.objects:
                    competence = obj.properties.copy()
                    competence['uuid'] = str(obj.uuid)
                    competence['score'] = obj.metadata.score if obj.metadata else 0
                    
                    # Extract user info
                    if obj.references and 'owned_by' in obj.references:
                        owned_by_refs = obj.references['owned_by'].objects
                        if owned_by_refs:
                            user = owned_by_refs[0].properties
                            competence['user'] = {
                                'uuid': str(owned_by_refs[0].uuid),
                                'name': user.get('name'),
                                'email': user.get('email'),
                                'last_sign_in': user.get('last_sign_in'),
                            }
                    
                    results.append(competence)
                
                logger.info(f"Ungrouped search found {len(results)} competencies for: '{query[:50]}...'")
                return results
            
        except Exception as e:
            logger.error(f"Error searching competencies: {e}")
            return []
    
    @staticmethod
    def get_user_competencies(user_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all competencies for a specific user.
        
        Args:
            user_uuid: UUID of the user
            
        Returns:
            List of competence dictionaries
        """
        try:
            user_collection = get_user_collection()
            
            # Fetch user with competence references
            response = user_collection.query.fetch_object_by_id(
                uuid=user_uuid,
                return_references=QueryReference(
                    link_on="has_competencies",
                    return_properties=["title", "description", "category", "price_range"]
                )
            )
            
            if not response:
                return []
            
            # Extract competencies from references
            competencies = []
            if response.references and 'has_competencies' in response.references:
                for comp_obj in response.references['has_competencies'].objects:
                    comp = comp_obj.properties.copy()
                    comp['uuid'] = str(comp_obj.uuid)
                    competencies.append(comp)
            
            logger.info(f"Retrieved {len(competencies)} competencies for user {user_uuid}")
            return competencies
            
        except Exception as e:
            logger.error(f"Error getting user competencies: {e}")
            return []
    
    @staticmethod
    def _build_filters_and_query(
        search_request: Dict[str, Any],
        max_inactive_days: int
    ) -> tuple[Filter, str, str]:
        """
        Build search filters and query text from search request.
        
        Returns:
            Tuple of (filter_clause, query_text, available_time)
        """
        # Build base filter: ghost filtering + provider filtering
        cutoff_date = datetime.now(UTC) - timedelta(days=max_inactive_days)
        filter_clause = (
            Filter.by_ref("owned_by").by_property("last_sign_in").greater_or_equal(cutoff_date) &
            Filter.by_ref("owned_by").by_property("is_service_provider").equal(True)
        )
        
        # Extract and normalize availability
        available_time = search_request.get("available_time") or ""
        if isinstance(available_time, str):
            available_time = available_time.strip()
        else:
            available_time = ""
        
        # Add availability filter if specified and not flexible
        if available_time and available_time.lower() not in ["flexibel", "flexible", "any", ""]:
            filter_clause = filter_clause & Filter.by_property("availability").contains_any([available_time])
            logger.info(f"Added availability filter: {available_time}")
        
        # Build query text from category and criterions
        # STRATEGY: Combine category and criteria into a natural language sentence
        # to avoid semantic dilution in vector space while retaining keywords.
        category = search_request.get("category") or ""
        if isinstance(category, str):
            category = category.strip()
        else:
            category = ""
        
        criterions = search_request.get("criterions") or []
        # specific clean up for criterions
        clean_criterions = []
        for crit in criterions:
            if crit and isinstance(crit, str) and crit.strip():
                clean_criterions.append(crit.strip())

        # Construct query: "Category. Features: criterion, criterion."
        if category and clean_criterions:
            query_text = f"{category}. Features: {', '.join(clean_criterions)}"
        elif category:
            query_text = category
        elif clean_criterions:
            query_text = ", ".join(clean_criterions)
        else:
            query_text = "service provider"
        
        return filter_clause, query_text, available_time
    
    @staticmethod
    def _process_search_results(response, limit: int) -> List[Dict[str, Any]]:
        """
        Process search results: extract data, group by user, sort by score.
        
        Args:
            response: Weaviate query response
            limit: Maximum number of results to return
            
        Returns:
            List of provider results sorted by relevance
        """
        seen_users = {}
        
        for obj in response.objects:
            competence = obj.properties.copy()
            competence['uuid'] = str(obj.uuid)
            competence['score'] = obj.metadata.score if obj.metadata else 0
            
            # Extract user info from references
            user_uuid = None
            if obj.references and 'owned_by' in obj.references:
                owned_by_refs = obj.references['owned_by'].objects
                if owned_by_refs:
                    user = owned_by_refs[0].properties
                    user_uuid = str(owned_by_refs[0].uuid)
                    competence['user'] = {
                        'uuid': user_uuid,
                        'name': user.get('name'),
                        'email': user.get('email'),
                        'is_service_provider': user.get('is_service_provider', False),
                        'last_sign_in': user.get('last_sign_in'),
                    }
            
            # Keep only the best-scoring competence per user
            if user_uuid:
                if user_uuid not in seen_users or competence['score'] > seen_users[user_uuid]['score']:
                    seen_users[user_uuid] = competence
        
        # Sort by score and limit
        return sorted(seen_users.values(), key=lambda x: x.get('score', 0), reverse=True)[:limit]
    
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
            max_inactive_days: Maximum days since last_sign_in
            alpha: Hybrid search weight (0=pure vector, 1=pure keyword, 0.5=balanced)
            
        Returns:
            List of provider results sorted by relevance
        """
        try:
            competence_collection = get_competence_collection()
            
            # Build filters and query text
            filter_clause, query_text, available_time = HubSpokeSearch._build_filters_and_query(
                search_request, max_inactive_days
            )
            
            logger.info(f"Hybrid search query: '{query_text[:100]}...'")
            logger.info(f"Active filters: availability={available_time or 'none'}")
            
            # Execute hybrid search
            # STRATEGY: Use query_properties to boost title and category matches.
            # This ensures that even with long criteria lists, the core "what" (category/title) remains dominant.
            # We include price_range and availability in search scope to catch keywords like "cheap" or "weekend".
            response = competence_collection.query.hybrid(
                query=query_text,
                limit=limit * 10,  # Fetch more for client-side grouping
                filters=filter_clause,
                alpha=alpha,
                # Boost title and category to prioritize exact service matches over peripheral criteria
                query_properties=["title^2", "category^2", "description", "price_range", "availability"],
                return_metadata=MetadataQuery(score=True),
                return_references=QueryReference(
                    link_on="owned_by",
                    return_properties=["name", "email", "is_service_provider", "last_sign_in"]
                )
            )
            
            # Process results: group by user and sort
            results = HubSpokeSearch._process_search_results(response, limit)
            
            logger.info(f"Hybrid search found {len(results)} unique providers")
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid_search_providers: {e}", exc_info=True)
            return []
