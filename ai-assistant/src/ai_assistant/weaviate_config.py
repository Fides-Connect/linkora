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
        get_user_collection,
        get_competence_collection,
        WeaviateCollection,
        cleanup_hub_spoke_schema  # noqa: F401
    )
except ImportError:
    from hub_spoke_schema import (  # pyright: ignore[reportMissingImports]
        init_hub_spoke_schema,
        get_user_collection,
        get_competence_collection,
        WeaviateCollection,
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
                    logger.info("Connecting to Weaviate Cloud Services at %s", cluster_url)
                    cls._client = weaviate.connect_to_wcs(
                        cluster_url=cluster_url,
                        auth_credentials=AuthApiKey(api_key),
                    )
                    logger.info("Successfully connected to Weaviate Cloud Services")

                else:
                    # Local/self-hosted deployment
                    weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8090')
                    logger.info("Connecting to local Weaviate at %s", weaviate_url)

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
                    logger.info("Successfully connected to local Weaviate at %s", weaviate_url)

                # Test connection
                if not cls._client.is_ready():
                    raise ConnectionError("Weaviate is not ready")

            except Exception as e:
                logger.error("Failed to connect to Weaviate: %s", e)
                raise

        return cls._client

    @classmethod
    def close(cls) -> None:
        """Close Weaviate connection."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            logger.info("Weaviate connection closed")


def init_weaviate_schema() -> Optional[bool]:
    """Initialize Weaviate schema with Hub and Spoke architecture."""
    try:
        # Initialize hub and spoke schema
        init_hub_spoke_schema()
        logger.info("Hub and Spoke schema initialization complete")
        return True

    except Exception as e:
        logger.error("Error initializing Hub and Spoke schema: %s", e)
        raise


def get_users_collection() -> WeaviateCollection:
    """Get user collection."""
    return get_user_collection()


def get_providers_collection() -> WeaviateCollection:
    """Get competence entry collection."""
    return get_competence_collection()
