"""
Unit tests for Data Provider functionality.
Tests the Weaviate data provider with Hub and Spoke schema.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from ai_assistant.data_provider import (
    DataProvider,
    NullDataProvider,
    WeaviateDataProvider,
    get_data_provider
)


class TestWeaviateDataProvider:
    """Test WeaviateDataProvider functionality."""
    
    @pytest.fixture
    def mock_weaviate_models(self):
        """Mock Weaviate models."""
        with patch('ai_assistant.weaviate_models.UserModelWeaviate') as mock_user, \
             patch('ai_assistant.weaviate_models.ProviderModelWeaviate') as mock_provider:
            
            # Mock user model methods
            mock_user.get_user_by_id = Mock(return_value={
                'user_id': 'user123',
                'name': 'Test User'
            })
            
            # Mock provider model methods
            mock_provider.vector_search_providers = Mock(return_value=[
                {'provider_id': 'p1', 'name': 'Provider 1'}
            ])
            mock_provider.get_provider_by_id = Mock(return_value={
                'provider_id': 'p1',
                'name': 'Provider 1'
            })
            
            yield {
                'user': mock_user,
                'provider': mock_provider
            }
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mock_weaviate_models):
        """Test getting user from Weaviate."""
        provider = WeaviateDataProvider()
        user = await provider.get_user_by_id('user123')
        
        assert user is not None
        assert user['user_id'] == 'user123'
        mock_weaviate_models['user'].get_user_by_id.assert_called_once_with('user123')
    
    @pytest.mark.asyncio
    async def test_search_providers(self, mock_weaviate_models):
        """Test searching providers in Weaviate."""
        provider = WeaviateDataProvider()
        providers = await provider.search_providers('electrician', limit=5)
        
        assert len(providers) > 0
        mock_weaviate_models['provider'].vector_search_providers.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_provider_by_id(self, mock_weaviate_models):
        """Test getting provider by ID from Weaviate."""
        provider = WeaviateDataProvider()
        result = await provider.get_provider_by_id('p1')
        
        assert result is not None
        assert result['provider_id'] == 'p1'
        mock_weaviate_models['provider'].get_provider_by_id.assert_called_once_with('p1')


class TestDataProviderFactory:
    """Test data provider factory function."""
    
    def test_get_data_provider_returns_weaviate_in_full_mode(self):
        """Test that WeaviateDataProvider is returned in full mode."""
        with patch.dict('os.environ', {'AGENT_MODE': 'full', 'WEAVIATE_URL': 'http://localhost:8090'}):
            with patch('ai_assistant.data_provider.WeaviateDataProvider') as mock_weaviate:
                mock_instance = Mock()
                mock_weaviate.return_value = mock_instance
                provider = get_data_provider()
                assert isinstance(provider, type(mock_instance))

    def test_get_data_provider_returns_null_in_lite_mode(self):
        """Test that NullDataProvider is returned in lite mode (no Weaviate connection)."""
        with patch.dict('os.environ', {'AGENT_MODE': 'lite'}):
            provider = get_data_provider()
            assert isinstance(provider, NullDataProvider)

    def test_get_data_provider_uses_default_url(self):
        """Test that default URL is used when not specified."""
        with patch.dict('os.environ', {'AGENT_MODE': 'full'}, clear=False):
            with patch('ai_assistant.data_provider.WeaviateDataProvider') as mock_weaviate:
                mock_instance = Mock()
                mock_weaviate.return_value = mock_instance
                provider = get_data_provider()
                # Should use default http://localhost:8090
                assert isinstance(provider, type(mock_instance))


class TestNullDataProvider:
    """Test NullDataProvider — lite mode no-op provider."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_returns_none(self):
        provider = NullDataProvider()
        assert await provider.get_user_by_id("any_id") is None

    @pytest.mark.asyncio
    async def test_search_providers_returns_empty(self):
        provider = NullDataProvider()
        assert await provider.search_providers("plumber") == []

    @pytest.mark.asyncio
    async def test_get_provider_by_id_returns_none(self):
        provider = NullDataProvider()
        assert await provider.get_provider_by_id("any_id") is None
