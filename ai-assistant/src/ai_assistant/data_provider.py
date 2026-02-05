"""
Data Provider Interface
Provides a clean abstraction for switching between Weaviate vector database and local test data.
"""
import json
import logging
import os
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """Abstract base class for data providers."""
    
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        pass
    
    @abstractmethod
    async def search_providers(self, query_text: str, category: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        """Search for service providers."""
        pass
    
    @abstractmethod
    async def get_provider_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider by ID."""
        pass


class WeaviateDataProvider(DataProvider):
    """Weaviate-based data provider using vector search."""
    
    def __init__(self):
        from .weaviate_models import UserModelWeaviate, ProviderModelWeaviate
        self.user_model = UserModelWeaviate
        self.provider_model = ProviderModelWeaviate
        logger.info("Initialized Weaviate data provider")
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from Weaviate."""
        return self.user_model.get_user_by_id(user_id)
    
    async def search_providers(self, query_text: str, category: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search providers using Weaviate hybrid search.
        Supports both simple text queries and structured JSON queries.
        
        Args:
            query_text: Search query - can be plain text or JSON string with structure:
                {
                    "available_time": "when service is needed",
                    "category": "service category",
                    "location": "where service is needed",
                    "criterions": ["criterion 1", "criterion 2", ...]
                }
            category: Optional category filter (legacy, overridden by JSON structure)
            limit: Maximum number of results
        """
        logger.info(f"Searching providers with query: '{query_text[:100]}...'")
        
        # Try to parse query_text as JSON for structured search
        try:
            search_request = json.loads(query_text)
            if isinstance(search_request, dict): #and any(k in search_request for k in ['category', 'location', 'available_time', 'criterions'])
                # Use structured hybrid search
                logger.info(f"Using structured hybrid search with request: {search_request}")
                from .hub_spoke_search import HubSpokeSearch
                providers = HubSpokeSearch.hybrid_search_providers(
                    search_request=search_request,
                    limit=limit
                )
                
                # Map to provider format for backward compatibility
                mapped_providers = []
                for result in providers:
                    user = result.get('user', {})
                    provider = {
                        'user_id': user.get('uuid'),
                        'name': user.get('name'),
                        'category': result.get('category'),
                        'description': result.get('description'),
                        'availability': result.get('availability'),
                        'skills': result.get('keywords', []),
                        'score': result.get('score', 0),
                    }
                    mapped_providers.append(provider)
                
                logger.info(f"Returning {len(mapped_providers)} providers from structured search")
                return mapped_providers
        except (json.JSONDecodeError, ValueError):
            # Not JSON, use simple text search
            logger.info("Query is not JSON, using simple vector search")
        
        # Fallback to simple vector search
        providers = self.provider_model.vector_search_providers(query_text, limit)
        
        logger.info(f"Returning {len(providers)} providers from search")
        return providers
    
    async def get_provider_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider from Weaviate."""
        return self.provider_model.get_provider_by_id(provider_id)


def get_data_provider() -> DataProvider:
    """
    Factory function to get the Weaviate data provider.
    
    Now exclusively uses Weaviate with Hub and Spoke schema.
    Set WEAVIATE_URL to configure connection (defaults to http://localhost:8090).
    
    Returns:
        WeaviateDataProvider instance
    """
    weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8090')
    logger.info(f"Using Weaviate data provider at {weaviate_url}")
    return WeaviateDataProvider()
