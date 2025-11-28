"""
Weaviate Vector Database Configuration
Handles connection and schema setup for storing users and service providers.
Supports both local (self-hosted) and cloud (Weaviate Cloud Services) deployments.
"""
import os
import logging
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.auth import AuthApiKey
from typing import Optional

logger = logging.getLogger(__name__)

# Collection names
USERS_COLLECTION = "User"
PROVIDERS_COLLECTION = "ServiceProvider"
CHAT_MESSAGES_COLLECTION = "ChatMessage"


class WeaviateConnection:
    """Singleton Weaviate connection manager.
    
    Supports two deployment modes:
    1. Local/Self-hosted: Uses WEAVIATE_URL (e.g., http://localhost:8090)
    2. Cloud (WCS): Uses WEAVIATE_CLUSTER_URL + WEAVIATE_API_KEY
    """
    
    _client: Optional[weaviate.WeaviateClient] = None
    
    @classmethod
    def get_client(cls) -> weaviate.WeaviateClient:
        """Get or create Weaviate client.
        
        Configuration options:
        - Local: Set WEAVIATE_URL (e.g., http://localhost:8090)
        - Cloud: Set WEAVIATE_CLUSTER_URL and WEAVIATE_API_KEY
        """
        if cls._client is None:
            # Check for cloud deployment first
            cluster_url = os.getenv('WEAVIATE_CLUSTER_URL')
            api_key = os.getenv('WEAVIATE_API_KEY')
            
            try:
                if cluster_url and api_key:
                    # Cloud deployment (Weaviate Cloud Services)
                    logger.info(f"Connecting to Weaviate Cloud Services at {cluster_url}")
                    cls._client = weaviate.connect_to_wcs(
                        cluster_url=cluster_url,
                        auth_credentials=AuthApiKey(api_key),
                    )
                    logger.info("Successfully connected to Weaviate Cloud Services")
                    
                else:
                    # Local/self-hosted deployment
                    weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8090')
                    logger.info(f"Connecting to local Weaviate at {weaviate_url}")
                    
                    # Parse URL components
                    url_parts = weaviate_url.replace('http://', '').replace('https://', '')
                    host = url_parts.split(':')[0]
                    
                    # Extract port if specified, default to 8080
                    if ':' in url_parts:
                        port = int(url_parts.split(':')[-1].split('/')[0])
                    else:
                        port = 8080
                    
                    is_https = weaviate_url.startswith('https')
                    
                    cls._client = weaviate.connect_to_custom(
                        http_host=host,
                        http_port=port,
                        http_secure=is_https,
                        grpc_host=host,
                        grpc_port=50051,
                        grpc_secure=is_https
                    )
                    logger.info(f"Successfully connected to local Weaviate at {weaviate_url}")
                
                # Test connection
                if not cls._client.is_ready():
                    raise ConnectionError("Weaviate is not ready")
                    
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


def init_weaviate_schema():
    """Initialize Weaviate schema with collections for users, providers, and chat history."""
    try:
        client = WeaviateConnection.get_client()
        
        # Create Users collection
        if not client.collections.exists(USERS_COLLECTION):
            client.collections.create(
                name=USERS_COLLECTION,
                properties=[
                    Property(name="user_id", data_type=DataType.TEXT),
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="email", data_type=DataType.TEXT),
                    Property(name="photo_url", data_type=DataType.TEXT),
                    Property(name="fcm_token", data_type=DataType.TEXT),
                    Property(name="has_open_request", data_type=DataType.BOOL),
                    Property(name="created_at", data_type=DataType.TEXT),
                    Property(name="last_sign_in", data_type=DataType.TEXT),
                ],
            )
            logger.info(f"Created collection: {USERS_COLLECTION}")
        else:
            logger.info(f"Collection already exists: {USERS_COLLECTION}")
        
        # Create ServiceProvider collection with vectorization
        if not client.collections.exists(PROVIDERS_COLLECTION):
            client.collections.create(
                name=PROVIDERS_COLLECTION,
                vectorizer_config=Configure.Vectorizer.text2vec_model2vec(),
                properties=[
                    Property(name="provider_id", data_type=DataType.TEXT),
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="category", data_type=DataType.TEXT),
                    Property(name="skills", data_type=DataType.TEXT_ARRAY),
                    Property(name="rating", data_type=DataType.NUMBER),
                    Property(name="experience_years", data_type=DataType.INT),
                    Property(name="price_range", data_type=DataType.TEXT),
                    Property(name="availability", data_type=DataType.TEXT),
                    Property(name="description", data_type=DataType.TEXT, 
                             vectorize_property_name=True,  # Vectorize description
                             skip_vectorization=False),
                ],
            )
            logger.info(f"Created collection with vectorization: {PROVIDERS_COLLECTION}")
        else:
            logger.info(f"Collection already exists: {PROVIDERS_COLLECTION}")
        
        # Create ChatMessage collection for conversation history persistence
        if not client.collections.exists(CHAT_MESSAGES_COLLECTION):
            client.collections.create(
                name=CHAT_MESSAGES_COLLECTION,
                properties=[
                    Property(name="user_id", data_type=DataType.TEXT),
                    Property(name="session_id", data_type=DataType.TEXT),
                    Property(name="role", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="timestamp", data_type=DataType.TEXT),
                    Property(name="stage", data_type=DataType.TEXT),
                ],
            )
            logger.info(f"Created collection: {CHAT_MESSAGES_COLLECTION}")
        else:
            logger.info(f"Collection already exists: {CHAT_MESSAGES_COLLECTION}")
        
        logger.info("Weaviate schema initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Weaviate schema: {e}")
        raise


def get_users_collection():
    """Get users collection."""
    client = WeaviateConnection.get_client()
    return client.collections.get(USERS_COLLECTION)


def get_providers_collection():
    """Get providers collection."""
    client = WeaviateConnection.get_client()
    return client.collections.get(PROVIDERS_COLLECTION)


def get_chat_messages_collection():
    """Get chat messages collection."""
    client = WeaviateConnection.get_client()
    return client.collections.get(CHAT_MESSAGES_COLLECTION)
