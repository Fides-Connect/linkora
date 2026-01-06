"""
Weaviate Vector Database Configuration
Handles connection and schema setup using Hub and Spoke architecture.
Supports both local (self-hosted) and cloud (Weaviate Cloud Services) deployments.
"""
import os
import logging
import weaviate
from weaviate.auth import AuthApiKey
from typing import Optional

# Handle both package and direct imports
try:
    from .hub_spoke_schema import (
        init_hub_spoke_schema,
        get_unified_profile_collection,
        get_competence_entry_collection,
        cleanup_hub_spoke_schema
    )
except ImportError:
    from hub_spoke_schema import (
        init_hub_spoke_schema,
        get_unified_profile_collection,
        get_competence_entry_collection,
        cleanup_hub_spoke_schema
    )

logger = logging.getLogger(__name__)


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
    """Initialize Weaviate schema with Hub and Spoke architecture."""
    try:
        # Initialize hub and spoke schema
        init_hub_spoke_schema()
        logger.info("Hub and Spoke schema initialization complete")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Hub and Spoke schema: {e}")
        raise


def get_users_collection():
    """Get unified profile collection (replaces old users collection)."""
    return get_unified_profile_collection()


def get_providers_collection():
    """Get competence entry collection (replaces old providers collection)."""
    return get_competence_entry_collection()
