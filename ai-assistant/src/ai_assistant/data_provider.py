"""
Data Provider Interface
Provides a clean abstraction for switching between Weaviate vector database and local test data.
"""
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
        Search providers using Weaviate vector search.
        Weaviate automatically generates embeddings for the query.
        """
        logger.info(f"Searching providers with query: '{query_text[:50]}...'")
        
        # Use Weaviate's hybrid search (combines vector and keyword search)
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
