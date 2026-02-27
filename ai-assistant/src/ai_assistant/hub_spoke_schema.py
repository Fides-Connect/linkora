"""
Hub and Spoke Search Architecture for Service Marketplace
==========================================================

Architecture:
- Hub (User): Identity model for users/companies
- Spoke (Competence): Specific skills/services with descriptions
- Bidirectional Cross-References: User ↔ Competence

"""
import os
import logging
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional
import weaviate
from weaviate.classes.config import Configure, Property, DataType, ReferenceProperty
from weaviate.classes.query import Filter, QueryReference
from weaviate.auth import AuthApiKey

logger = logging.getLogger(__name__)

# Collection names
USER_COLLECTION = "User"
COMPETENCE_COLLECTION = "Competence"

class HubSpokeConnection:
    """Singleton connection manager for Hub and Spoke architecture."""
    
    _client: Optional[weaviate.WeaviateClient] = None
    
    @classmethod
    def get_client(cls) -> weaviate.WeaviateClient:
        """Get or create Weaviate client."""
        if cls._client is None:
            cluster_url = os.getenv('WEAVIATE_CLUSTER_URL')
            api_key = os.getenv('WEAVIATE_API_KEY')
            
            try:
                if cluster_url and api_key:
                    logger.info(f"Connecting to Weaviate Cloud Services at {cluster_url}")
                    cls._client = weaviate.connect_to_wcs(
                        cluster_url=cluster_url,
                        auth_credentials=AuthApiKey(api_key),
                    )
                else:
                    weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8090')
                    logger.info(f"Connecting to local Weaviate at {weaviate_url}")
                    
                    url_parts = weaviate_url.replace('http://', '').replace('https://', '')
                    host = url_parts.split(':')[0]
                    port = int(url_parts.split(':')[-1].split('/')[0]) if ':' in url_parts else 8080
                    is_https = weaviate_url.startswith('https')
                    
                    cls._client = weaviate.connect_to_custom(
                        http_host=host,
                        http_port=port,
                        http_secure=is_https,
                        grpc_host=host,
                        grpc_port=50051,
                        grpc_secure=is_https
                    )
                
                if not cls._client.is_ready():
                    raise ConnectionError("Weaviate is not ready")
                    
                logger.info("Successfully connected to Weaviate")
                
            except Exception as e:
                logger.error(f"Failed to connect to Weaviate: {e}")
                raise
        
        return cls._client
    
    @classmethod
    def close(cls):
        """Close Weaviate connection."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            logger.info("Weaviate connection closed")


def init_hub_spoke_schema():
    """
    Initialize Hub and Spoke schema with bidirectional cross-references.
    
    Collections:
    1. Competence (Spoke) - Created FIRST
    2. User (Hub) - Created SECOND with reference to Competence
    3. Add owned_by reference to Competence after User exists
    
    Note: Weaviate v4 Python client handles cross-references at data insertion time,
    but we define the schema properties for explicit structure.
    """
    try:
        client = HubSpokeConnection.get_client()
        
        # Step 1: Create Competence FIRST (without owned_by reference initially)
        if not client.collections.exists(COMPETENCE_COLLECTION):
            try:
                client.collections.create(
                    name=COMPETENCE_COLLECTION,
                    vector_config=Configure.Vectors.text2vec_model2vec(),
                    properties=[
                        Property(name="competence_id", data_type=DataType.TEXT,
                                 skip_vectorization=True),  # Link to Firestore ID
                        Property(name="title", data_type=DataType.TEXT,
                                 skip_vectorization=True),
                        # Raw description — stored for display only, NOT vectorized.
                        # Vector search is driven by search_optimized_summary instead.
                        Property(
                            name="description",
                            data_type=DataType.TEXT,
                            skip_vectorization=True,
                        ),
                        # ── Filter / rank properties ─────────────────────────────────
                        Property(name="category", data_type=DataType.TEXT,
                                 skip_vectorization=True),
                        Property(name="year_of_experience", data_type=DataType.INT,
                                 skip_vectorization=True),
                        Property(name="price_per_hour", data_type=DataType.NUMBER,
                                 skip_vectorization=True),
                        # availability_tags: normalised tokens, e.g. ["weekend","monday","morning"]
                        # Used for ContainsAny where-filters in search_providers.
                        Property(name="availability_tags", data_type=DataType.TEXT_ARRAY,
                                 skip_vectorization=True),
                        # availability_text: human-readable string stored for display (Firestore
                        # is authoritative, but kept here so result objects are self-contained).
                        Property(name="availability_text", data_type=DataType.TEXT,
                                 skip_vectorization=True),
                        # ── Primary vector source ────────────────────────────────────
                        # LLM-rewritten summary, optimised for semantic search.
                        # This is the ONLY vectorized field — all nearText queries target it.
                        Property(
                            name="search_optimized_summary",
                            data_type=DataType.TEXT,
                            vectorize_property_name=True,
                            skip_vectorization=False,
                        ),
                        # skills_list: explicit + implicit skills, stored for retrieval.
                        # NOT vectorized individually — the summary already captures them.
                        Property(name="skills_list", data_type=DataType.TEXT_ARRAY,
                                 skip_vectorization=True),
                    ],
                )
                logger.info(f"Created collection with vectorization: {COMPETENCE_COLLECTION}")
            except weaviate.exceptions.ObjectAlreadyExistsError:
                logger.warning(f"Collection {COMPETENCE_COLLECTION} already exists — skipping creation")
        else:
            logger.info(f"Collection already exists: {COMPETENCE_COLLECTION}")
        
        # Step 2: Create User SECOND (now it can reference existing Competence)
        if not client.collections.exists(USER_COLLECTION):
            try:
                client.collections.create(
                    name=USER_COLLECTION,
                    properties=[
                        Property(name="user_id", data_type=DataType.TEXT),  # External ID (e.g. Firebase UID)
                        Property(name="name", data_type=DataType.TEXT),
                        Property(name="email", data_type=DataType.TEXT),
                        Property(name="location", data_type=DataType.TEXT),
                        Property(name="self_introduction", data_type=DataType.TEXT),
                        Property(name="is_service_provider", data_type=DataType.BOOL),  # True if user offers services
                        Property(name="photo_url", data_type=DataType.TEXT),
                        Property(name="fcm_token", data_type=DataType.TEXT),
                        Property(name="created_at", data_type=DataType.DATE),
                        Property(name="last_sign_in", data_type=DataType.DATE),
                        Property(name="has_open_request", data_type=DataType.BOOL),
                        Property(name="feedback_positive", data_type=DataType.TEXT_ARRAY),
                        Property(name="feedback_negative", data_type=DataType.TEXT_ARRAY),
                        Property(name="average_rating", data_type=DataType.NUMBER),
                        Property(name="review_count", data_type=DataType.INT),
                    ],
                    references=[
                        ReferenceProperty(
                            name="has_competencies",
                            target_collection=COMPETENCE_COLLECTION
                        )
                    ]
                )
                logger.info(f"Created collection: {USER_COLLECTION}")
            except weaviate.exceptions.ObjectAlreadyExistsError:
                logger.warning(f"Collection {USER_COLLECTION} already exists — skipping creation")
        else:
            logger.info(f"Collection already exists: {USER_COLLECTION}")
        
        # Step 3: Add owned_by reference to Competence (now that User exists)
        # Update the collection to add the cross-reference
        competence_collection = client.collections.get(COMPETENCE_COLLECTION)
        config = competence_collection.config.get()
        
        # Check if owned_by reference already exists
        has_owned_by = any(ref.name == "owned_by" for ref in (config.references or []))
        
        if not has_owned_by:
            try:
                competence_collection.config.add_reference(
                    ref=ReferenceProperty(
                        name="owned_by",
                        target_collection=USER_COLLECTION
                    )
                )
                logger.info(f"Added 'owned_by' reference to {COMPETENCE_COLLECTION}")
            except weaviate.exceptions.ObjectAlreadyExistsError:
                logger.warning(f"'owned_by' reference in {COMPETENCE_COLLECTION} already exists — skipping")
        else:
            logger.info(f"'owned_by' reference already exists in {COMPETENCE_COLLECTION}")
        
        logger.info("Hub and Spoke schema initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Hub and Spoke schema: {e}")
        raise


def get_user_collection():
    """Get User collection, auto-initialising schema if needed."""
    client = HubSpokeConnection.get_client()
    if not client.collections.exists(USER_COLLECTION):
        logger.warning("User collection missing — auto-initialising Hub and Spoke schema")
        init_hub_spoke_schema()
    return client.collections.get(USER_COLLECTION)


def get_competence_collection():
    """Get Competence collection, auto-initialising schema if needed."""
    client = HubSpokeConnection.get_client()
    if not client.collections.exists(COMPETENCE_COLLECTION):
        logger.warning("Competence collection missing — auto-initialising Hub and Spoke schema")
        init_hub_spoke_schema()
    return client.collections.get(COMPETENCE_COLLECTION)


def cleanup_hub_spoke_schema():
    """Delete collections (for testing purposes)."""
    try:
        client = HubSpokeConnection.get_client()
        
        if client.collections.exists(COMPETENCE_COLLECTION):
            client.collections.delete(COMPETENCE_COLLECTION)
            logger.info(f"Deleted collection: {COMPETENCE_COLLECTION}")
        
        if client.collections.exists(USER_COLLECTION):
            client.collections.delete(USER_COLLECTION)
            logger.info(f"Deleted collection: {USER_COLLECTION}")
        
        logger.info("Hub and Spoke schema cleanup complete")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up Hub and Spoke schema: {e}")
        raise
