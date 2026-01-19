"""
Hub and Spoke Search Architecture for Service Marketplace
==========================================================

Architecture:
- Hub (UnifiedProfile): Unified identity model for users/companies
- Spoke (CompetenceEntry): Specific skills/services with descriptions
- Bidirectional Cross-References: Profile ↔ Competence

This replaces the old separate user/provider collections with a more
granular, searchable, and abuse-resistant model.
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
UNIFIED_PROFILE_COLLECTION = "UnifiedProfile"
COMPETENCE_ENTRY_COLLECTION = "CompetenceEntry"


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
    1. CompetenceEntry (Spoke) - Created FIRST
    2. UnifiedProfile (Hub) - Created SECOND with reference to CompetenceEntry
    3. Add owned_by reference to CompetenceEntry after UnifiedProfile exists
    
    Note: Weaviate v4 Python client handles cross-references at data insertion time,
    but we define the schema properties for explicit structure.
    """
    try:
        client = HubSpokeConnection.get_client()
        
        # Step 1: Create CompetenceEntry FIRST (without owned_by reference initially)
        if not client.collections.exists(COMPETENCE_ENTRY_COLLECTION):
            client.collections.create(
                name=COMPETENCE_ENTRY_COLLECTION,
                vectorizer_config=Configure.Vectorizer.text2vec_model2vec(),
                properties=[
                    Property(name="title", data_type=DataType.TEXT),
                    Property(
                        name="description", 
                        data_type=DataType.TEXT,
                        vectorize_property_name=True,  # Vectorize for semantic search
                        skip_vectorization=False
                    ),
                    Property(name="category", data_type=DataType.TEXT),
                    Property(name="price_range", data_type=DataType.TEXT),
                    Property(name="availability", data_type=DataType.TEXT),  # When service is available
                ],
            )
            logger.info(f"Created collection with vectorization: {COMPETENCE_ENTRY_COLLECTION}")
        else:
            logger.info(f"Collection already exists: {COMPETENCE_ENTRY_COLLECTION}")
        
        # Step 2: Create UnifiedProfile SECOND (now it can reference existing CompetenceEntry)
        if not client.collections.exists(UNIFIED_PROFILE_COLLECTION):
            client.collections.create(
                name=UNIFIED_PROFILE_COLLECTION,
                properties=[
                    Property(name="user_id", data_type=DataType.TEXT),  # External ID (e.g. Firebase UID)
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="email", data_type=DataType.TEXT),
                    Property(name="type", data_type=DataType.TEXT),  # "client" or "provider"
                    Property(name="is_provider", data_type=DataType.BOOL),  # True if user offers services
                    Property(name="photo_url", data_type=DataType.TEXT),
                    Property(name="fcm_token", data_type=DataType.TEXT),
                    Property(name="created_at", data_type=DataType.DATE),
                    Property(name="last_sign_in", data_type=DataType.DATE),
                    Property(name="has_open_request", data_type=DataType.BOOL),
                    Property(name="last_active_date", data_type=DataType.DATE),
                ],
                references=[
                    ReferenceProperty(
                        name="has_competences",
                        target_collection=COMPETENCE_ENTRY_COLLECTION
                    )
                ]
            )
            logger.info(f"Created collection: {UNIFIED_PROFILE_COLLECTION}")
        else:
            logger.info(f"Collection already exists: {UNIFIED_PROFILE_COLLECTION}")
        
        # Step 3: Add owned_by reference to CompetenceEntry (now that UnifiedProfile exists)
        # Update the collection to add the cross-reference
        competence_collection = client.collections.get(COMPETENCE_ENTRY_COLLECTION)
        config = competence_collection.config.get()
        
        # Check if owned_by reference already exists
        has_owned_by = any(ref.name == "owned_by" for ref in (config.references or []))
        
        if not has_owned_by:
            # Add the owned_by reference property
            competence_collection.config.add_reference(
                ref=ReferenceProperty(
                    name="owned_by",
                    target_collection=UNIFIED_PROFILE_COLLECTION
                )
            )
            logger.info(f"Added 'owned_by' reference to {COMPETENCE_ENTRY_COLLECTION}")
        else:
            logger.info(f"'owned_by' reference already exists in {COMPETENCE_ENTRY_COLLECTION}")
        
        logger.info("Hub and Spoke schema initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Hub and Spoke schema: {e}")
        raise


def get_unified_profile_collection():
    """Get UnifiedProfile collection."""
    client = HubSpokeConnection.get_client()
    return client.collections.get(UNIFIED_PROFILE_COLLECTION)


def get_competence_entry_collection():
    """Get CompetenceEntry collection."""
    client = HubSpokeConnection.get_client()
    return client.collections.get(COMPETENCE_ENTRY_COLLECTION)


def cleanup_hub_spoke_schema():
    """Delete collections (for testing purposes)."""
    try:
        client = HubSpokeConnection.get_client()
        
        if client.collections.exists(COMPETENCE_ENTRY_COLLECTION):
            client.collections.delete(COMPETENCE_ENTRY_COLLECTION)
            logger.info(f"Deleted collection: {COMPETENCE_ENTRY_COLLECTION}")
        
        if client.collections.exists(UNIFIED_PROFILE_COLLECTION):
            client.collections.delete(UNIFIED_PROFILE_COLLECTION)
            logger.info(f"Deleted collection: {UNIFIED_PROFILE_COLLECTION}")
        
        logger.info("Hub and Spoke schema cleanup complete")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up Hub and Spoke schema: {e}")
        raise
