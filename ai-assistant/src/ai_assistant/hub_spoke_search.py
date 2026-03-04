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
import re
from datetime import datetime, UTC, timedelta
from typing import List, Dict, Any
from weaviate.classes.query import Filter, QueryReference, MetadataQuery

# Handle both package and direct imports
from ai_assistant.hub_spoke_schema import (
    get_user_collection,
    get_competence_collection
)

logger = logging.getLogger(__name__)

# Normalised availability tokens stored in Competence.availability_tags.
# Must stay in sync with derive_availability_tags() in firestore_schemas.py.
_AVAILABILITY_TOKENS: frozenset = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "weekday", "weekend",
    "morning", "afternoon", "evening",
})


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
            
            # Build query with ghost filtering and provider filtering.
            # Null last_sign_in is treated as active (providers who signed in before
            # the field was tracked are included rather than silently excluded).
            # Filter: (owned_by.last_sign_in is_none OR >= cutoff) AND is_service_provider == True
            filter_clause = (
                (
                    Filter.by_ref("owned_by").by_property("last_sign_in").is_none(True)
                    | Filter.by_ref("owned_by").by_property("last_sign_in").greater_or_equal(cutoff_date)
                )
                & Filter.by_ref("owned_by").by_property("is_service_provider").equal(True)
            )
            
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
        # Build base filter: ghost filtering + provider filtering.
        # Null last_sign_in is treated as active (providers who signed in before
        # the field was tracked are included rather than silently excluded).
        # The User collection has indexNullState:true (hub_spoke_schema.py), which
        # is required for is_none() to work correctly on this property.
        cutoff_date = datetime.now(UTC) - timedelta(days=max_inactive_days)
        filter_clause = (
            (
                Filter.by_ref("owned_by").by_property("last_sign_in").is_none(True)
                | Filter.by_ref("owned_by").by_property("last_sign_in").greater_or_equal(cutoff_date)
            )
            & Filter.by_ref("owned_by").by_property("is_service_provider").equal(True)
        )
        
        # Extract and normalize availability
        available_time = search_request.get("available_time") or ""
        if isinstance(available_time, str):
            available_time = available_time.strip()
        else:
            available_time = ""
        
        # Add availability filter if specified and not flexible.
        # The Weaviate schema stores normalised tokens in `availability_tags` (TEXT_ARRAY).
        # The LLM may produce a free-form string (e.g. "nächste Woche", "Monday morning"),
        # so we intersect with the known token vocabulary before filtering. This prevents
        # the raw string from never matching stored tags and silently returning zero results.
        if available_time and available_time.lower() not in ("flexibel", "flexible", "any", "anytime", ""):
            raw_words = set(re.findall(r'[a-z]+', available_time.lower()))
            matched_tokens = sorted(raw_words & _AVAILABILITY_TOKENS)
            if matched_tokens:
                filter_clause = filter_clause & Filter.by_property("availability_tags").contains_any(matched_tokens)
                logger.info("Added availability filter: %r → tokens: %s", available_time, matched_tokens)
            else:
                logger.info("Availability filter skipped — no known tokens in %r", available_time)
        
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
        alpha: float = 0.5,
        hyde_text: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search for providers with structured filtering.

        Search Strategy:
        1. Filter by metadata: available_time, is_service_provider, last_sign_in
        2. If ``hyde_text`` is provided, use it as the Weaviate query text so
           that the vector component searches for semantically similar profiles
           (HyDE — Hypothetical Document Embeddings).  The BM25 component still
           benefits from the richer vocabulary in the hypothetical profile.
           Otherwise fall back to the category + criterions structured string.
        3. Fetch ``limit * 5`` (capped at 30) candidates for downstream reranking.
        4. Group by user and sort by Weaviate hybrid score.

        Args:
            search_request: Structured search query with keys:
                - available_time: when service is needed
                - category: service category
                - criterions: list of additional requirements
            limit: Final maximum results returned (after grouping).
            max_inactive_days: Maximum days since last_sign_in.
            alpha: Hybrid search weight (0=pure vector, 1=pure keyword, 0.5=balanced).
            hyde_text: Optional hypothetical provider profile generated by LLM.
                       When supplied it is used as the Weaviate query string,
                       bridging the vocabulary gap between user needs and stored
                       competency descriptions.

        Returns:
            List of provider results sorted by relevance
        """
        try:
            competence_collection = get_competence_collection()

            # ── DEBUG Step 0: total collection size ──────────────────────────
            if logger.isEnabledFor(logging.DEBUG):
                total = competence_collection.aggregate.over_all(total_count=True).total_count
                logger.debug("[HyDE Step 0] Total competencies in Weaviate collection: %d", total or 0)

            # Build filters and query text
            filter_clause, structured_query_text, available_time = HubSpokeSearch._build_filters_and_query(
                search_request, max_inactive_days
            )

            # ── DEBUG Step 1: unfiltered fetch (raw collection state) ────────
            if logger.isEnabledFor(logging.DEBUG):
                unfiltered = competence_collection.query.fetch_objects(limit=5)
                logger.debug(
                    "[HyDE Step 1] Unfiltered sample (%d objects): %s",
                    len(unfiltered.objects),
                    [o.properties.get("title") for o in unfiltered.objects],
                )

            # ── DEBUG Step 2: filter-only fetch (is_service_provider guard) ──
            if logger.isEnabledFor(logging.DEBUG):
                sp_filter = Filter.by_ref("owned_by").by_property("is_service_provider").equal(True)
                sp_results = competence_collection.query.fetch_objects(filters=sp_filter, limit=20)
                logger.debug(
                    "[HyDE Step 2] is_service_provider=True fetch: %d objects → %s",
                    len(sp_results.objects),
                    [o.properties.get("title") for o in sp_results.objects],
                )

            # HyDE: prefer the hypothetical profile text as the Weaviate query when
            # available — it produces a richer vector representation that bridges the
            # vocabulary gap between the user's problem and stored provider bios.
            query_text = hyde_text.strip() if hyde_text and hyde_text.strip() else structured_query_text

            # ── DEBUG Step 3: query selection ────────────────────────────────
            logger.debug(
                "[HyDE Step 3] Query mode: %s | query text (first 200 chars): %s",
                "HyDE" if (hyde_text and hyde_text.strip()) else "structured",
                query_text[:200],
            )

            logger.info(f"Hybrid search query ({'HyDE' if hyde_text else 'structured'}): '{query_text[:120]}...'")
            logger.info(f"Active filters: availability={available_time or 'none'}")

            # Wide-net fetch: retrieve enough candidates to feed the cross-encoder
            # reranker (Stage 2).  5x limit, capped at 30.
            fetch_limit = min(limit * 5, 30)

            # ── DEBUG Step 4: hybrid search WITHOUT full filter ───────────────
            if logger.isEnabledFor(logging.DEBUG):
                no_filter_response = competence_collection.query.hybrid(
                    query=query_text,
                    limit=5,
                    alpha=alpha,
                    query_properties=["title^2", "category^2", "description", "search_optimized_summary", "availability_text"],
                    return_metadata=MetadataQuery(score=True),
                )
                logger.debug(
                    "[HyDE Step 4] Hybrid search NO-FILTER top-5: %s",
                    [(o.properties.get("title"), round(o.metadata.score or 0, 4)) for o in no_filter_response.objects],
                )

            # Execute hybrid search
            # STRATEGY: Use query_properties to boost title and category matches.
            # This ensures that even with long criteria lists, the core "what" (category/title) remains dominant.
            # We include availability_text in search scope to catch temporal keywords like "weekend".
            # Note: price_range is NOT included — the ingestion pipeline stores numeric price_per_hour;
            #       any legacy price_range TEXT property may lack indexSearchable and would crash.
            response = competence_collection.query.hybrid(
                query=query_text,
                limit=fetch_limit * 10,  # Fetch more for client-side grouping
                filters=filter_clause,
                alpha=alpha,
                # Boost title and category to prioritize exact service matches over peripheral criteria.
                # search_optimized_summary is the primary vector source and also benefits BM25 recall
                # for niche skills well-described in the summary but not literally in the title.
                query_properties=["title^2", "category^2", "description", "search_optimized_summary", "availability_text"],
                return_metadata=MetadataQuery(score=True),
                return_references=QueryReference(
                    link_on="owned_by",
                    return_properties=["name", "email", "is_service_provider", "last_sign_in"]
                )
            )

            # ── DEBUG Step 5: raw results from full hybrid+filter search ─────
            logger.debug(
                "[HyDE Step 5] Hybrid+filter raw results: %d objects → top scores: %s",
                len(response.objects),
                [(o.properties.get("title"), round(o.metadata.score or 0, 4)) for o in response.objects[:5]],
            )
            
            # Process results: group by user and sort; use fetch_limit so we
            # pass enough candidates to the cross-encoder reranker upstream.
            results = HubSpokeSearch._process_search_results(response, fetch_limit)
            
            # ── DEBUG Step 6: final grouped results ──────────────────────────
            logger.debug(
                "[HyDE Step 6] Final grouped providers (%d): %s",
                len(results),
                [r.get("name") for r in results],
            )

            if results:
                logger.info("Hybrid search found %d unique providers", len(results))
            else:
                # Zero results — emit a diagnostic so the cause (no matching
                # competencies vs. missing/wrong is_service_provider flag) is
                # immediately visible at INFO level in production logs.
                try:
                    sp_filter = Filter.by_ref("owned_by").by_property("is_service_provider").equal(True)
                    sp_count = (
                        competence_collection.aggregate.over_all(
                            filters=sp_filter, total_count=True
                        ).total_count
                        or 0
                    )
                    logger.info(
                        "Hybrid search found 0 providers — "
                        "competencies with is_service_provider=True in Weaviate: %d — "
                        "query=%r availability=%r",
                        sp_count,
                        query_text[:80],
                        available_time or "none",
                    )
                except Exception:
                    logger.info(
                        "Hybrid search found 0 providers — query=%r availability=%r",
                        query_text[:80],
                        available_time or "none",
                    )
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid_search_providers: {e}", exc_info=True)
            return []
