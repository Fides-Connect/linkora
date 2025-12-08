"""
Unit tests for Data Provider functionality.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from ai_assistant.data_provider import (
    DataProvider,
    WeaviateDataProvider,
    LocalDataProvider,
    get_data_provider
)


class TestLocalDataProvider:
    """Test LocalDataProvider functionality."""
    
    @pytest.fixture
    def local_provider(self):
        """Create LocalDataProvider instance."""
        with patch('ai_assistant.test_data.USER_DATA', {
            'user_id': 'user123',
            'name': 'Test User',
            'has_open_request': False
        }), patch('ai_assistant.test_data.SERVICE_PROVIDERS', [
            {'id': 'p1', 'name': 'Provider 1', 'category': 'plumbing'},
            {'id': 'p2', 'name': 'Provider 2', 'category': 'electrical'}
        ]), patch('ai_assistant.test_data.search_providers') as mock_search:
            
            # Mock search function
            mock_search.return_value = [
                {'id': 'p1', 'name': 'Provider 1', 'category': 'plumbing'}
            ]
            
            provider = LocalDataProvider()
            return provider
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, local_provider):
        """Test getting user by ID when user exists."""
        user = await local_provider.get_user_by_id('user123')
        assert user is not None
        assert user['user_id'] == 'user123'
        assert user['name'] == 'Test User'
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, local_provider):
        """Test getting user by ID when user doesn't exist."""
        user = await local_provider.get_user_by_id('nonexistent')
        assert user is None
    
    @pytest.mark.asyncio
    async def test_search_providers(self, local_provider):
        """Test searching providers."""
        providers = await local_provider.search_providers('plumber', 'plumbing', 3)
        assert len(providers) > 0
        # Check that id is normalized to provider_id
        assert 'provider_id' in providers[0]
    
    @pytest.mark.asyncio
    async def test_get_provider_by_id(self, local_provider):
        """Test getting provider by ID."""
        provider = await local_provider.get_provider_by_id('p1')
        assert provider is not None
        assert provider['provider_id'] == 'p1'


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
    
    def test_get_data_provider_local_default(self):
        """Test that local provider is returned by default."""
        with patch.dict('os.environ', {}, clear=True):
            provider = get_data_provider()
            assert isinstance(provider, LocalDataProvider)
    
    def test_get_data_provider_weaviate_when_enabled(self):
        """Test that Weaviate provider is returned when enabled."""
        with patch.dict('os.environ', {'USE_WEAVIATE': 'true', 'WEAVIATE_URL': 'http://localhost:8080'}):
            with patch('ai_assistant.data_provider.WeaviateDataProvider') as mock_weaviate:
                mock_instance = Mock()
                mock_weaviate.return_value = mock_instance
                provider = get_data_provider()
                assert isinstance(provider, type(mock_instance))
    
    def test_get_data_provider_local_fallback_on_weaviate_error(self):
        """Test fallback to local when Weaviate initialization fails."""
        with patch.dict('os.environ', {'USE_WEAVIATE': 'true', 'WEAVIATE_URL': 'http://localhost:8080'}):
            with patch('ai_assistant.data_provider.WeaviateDataProvider', side_effect=Exception('Connection failed')):
                provider = get_data_provider()
                assert isinstance(provider, LocalDataProvider)
    
    def test_get_data_provider_local_when_weaviate_url_missing(self):
        """Test that local provider is used when Weaviate URL is missing."""
        with patch.dict('os.environ', {'USE_WEAVIATE': 'true'}, clear=True):
            provider = get_data_provider()
            assert isinstance(provider, LocalDataProvider)
