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


class LocalDataProvider(DataProvider):
    """Local test data provider using in-memory data."""
    
    def __init__(self):
        from .test_data import USER_DATA, SERVICE_PROVIDERS, search_providers
        self.user_data = USER_DATA
        self.service_providers = SERVICE_PROVIDERS
        self.search_function = search_providers
        logger.info("Initialized local test data provider")
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from local test data."""
        if self.user_data.get('user_id') == user_id:
            return self.user_data
        return None
    
    async def search_providers(self, query_text: str, category: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        """Search providers using local test data."""
        # Use the test_data search function
        providers = self.search_function(query_text, category, limit)
        
        # Normalize field names (id -> provider_id)
        normalized_providers = []
        for p in providers:
            normalized = p.copy()
            if 'id' in normalized and 'provider_id' not in normalized:
                normalized['provider_id'] = normalized.pop('id')
            normalized_providers.append(normalized)
        
        return normalized_providers
    
    async def get_provider_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider from local test data."""
        for provider in self.service_providers:
            if provider.get('id') == provider_id or provider.get('provider_id') == provider_id:
                normalized = provider.copy()
                if 'id' in normalized and 'provider_id' not in normalized:
                    normalized['provider_id'] = normalized.pop('id')
                return normalized
        return None


def get_data_provider() -> DataProvider:
    """
    Factory function to get the appropriate data provider based on configuration.
    
    Returns:
        DataProvider instance (Weaviate or Local)
    """
    use_weaviate = os.getenv('USE_WEAVIATE', 'false').lower() in ('true', '1', 'yes')
    
    if use_weaviate:
        try:
            # Test Weaviate connection
            weaviate_url = os.getenv('WEAVIATE_URL')
            if not weaviate_url:
                logger.warning("USE_WEAVIATE=true but WEAVIATE_URL not set, falling back to local data")
                return LocalDataProvider()
            
            logger.info("Using Weaviate data provider")
            return WeaviateDataProvider()
        except Exception as e:
            logger.error(f"Failed to initialize Weaviate provider: {e}, falling back to local data")
            return LocalDataProvider()
    else:
        logger.info("Using local test data provider")
        return LocalDataProvider()
