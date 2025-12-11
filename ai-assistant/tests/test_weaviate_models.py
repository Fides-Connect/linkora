"""Unit tests for Weaviate Models."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

from ai_assistant.weaviate_models import UserModelWeaviate, ProviderModelWeaviate


class TestUserModelWeaviate:
    """Tests for UserModelWeaviate."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Setup mocks for the tests."""
        self.mock_collection = MagicMock()
        mock_get_users_collection = Mock(return_value=self.mock_collection)
        monkeypatch.setattr(
            'ai_assistant.weaviate_models.get_users_collection',
            mock_get_users_collection
        )

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data."""
        return {
            "user_id": "user_123",
            "name": "Test User",
            "email": "test@example.com",
            "photo_url": "https://example.com/photo.jpg",
            "fcm_token": "fcm_token_abc",
            "has_open_request": False,
            "created_at": datetime.now(UTC),
            "last_sign_in": datetime.now(UTC)
        }

    def test_create_user_success(self, sample_user_data):
        """Test creating a new user successfully."""
        self.mock_collection.data.insert.return_value = "uuid_123"

        result = UserModelWeaviate.create_user(sample_user_data)

        assert result == "uuid_123"
        self.mock_collection.data.insert.assert_called_once()
        call_args = self.mock_collection.data.insert.call_args[1]['properties']
        assert call_args['user_id'] == "user_123"
        assert call_args['name'] == "Test User"
        assert call_args['email'] == "test@example.com"

    def test_create_user_failure(self, sample_user_data):
        """Test creating user with exception."""
        self.mock_collection.data.insert.side_effect = Exception("Database error")

        result = UserModelWeaviate.create_user(sample_user_data)

        assert result is None

    def test_get_user_by_id_success(self):
        """Test getting user by ID successfully."""
        mock_obj = MagicMock()
        mock_obj.properties = {
            "user_id": "user_123",
            "name": "Test User",
            "email": "test@example.com",
            "fcm_token": "fcm_token_abc"
        }
        self.mock_collection.query.fetch_objects.return_value.objects = [mock_obj]

        result = UserModelWeaviate.get_user_by_id("user_123")

        assert result is not None
        assert result["user_id"] == "user_123"
        assert result["name"] == "Test User"
        assert result["fcm_token"] == "fcm_token_abc"

    def test_get_user_by_id_not_found(self):
        """Test getting user by ID when user doesn't exist."""
        self.mock_collection.query.fetch_objects.return_value.objects = []

        result = UserModelWeaviate.get_user_by_id("nonexistent_user")

        assert result is None

    def test_get_user_by_id_exception(self):
        """Test getting user by ID with exception."""
        self.mock_collection.query.fetch_objects.side_effect = Exception("Database error")

        result = UserModelWeaviate.get_user_by_id("user_123")

        assert result is None

    def test_update_user_success(self):
        """Test updating user successfully."""
        mock_obj = MagicMock()
        mock_obj.uuid = "uuid_123"
        mock_obj.properties = {
            "user_id": "user_123",
            "name": "Old Name",
            "email": "old@example.com",
            "photo_url": "https://example.com/photo.jpg",
            "fcm_token": "old_token",
            "has_open_request": False,
            "last_sign_in": datetime.now(UTC)
        }
        self.mock_collection.query.fetch_objects.return_value.objects = [mock_obj]

        update_data = {
            "name": "New Name",
            "email": "new@example.com",
            "fcm_token": "new_token"
        }

        result = UserModelWeaviate.update_user("user_123", update_data)

        assert result is True
        self.mock_collection.data.update.assert_called_once()
        
        call_args = self.mock_collection.data.update.call_args[1]
        assert call_args['uuid'] == "uuid_123"
        
        updated_properties = call_args['properties']
        assert updated_properties['name'] == "New Name"
        assert updated_properties['email'] == "new@example.com"
        assert updated_properties['fcm_token'] == "new_token"
        
        # Ensure other properties are not lost
        assert 'photo_url' in updated_properties
        assert 'has_open_request' in updated_properties
        assert 'last_sign_in' in updated_properties

    def test_update_user_not_found(self):
        """Test updating user that doesn't exist."""
        self.mock_collection.query.fetch_objects.return_value.objects = []

        result = UserModelWeaviate.update_user("nonexistent_user", {"name": "New Name"})

        assert result is False
        self.mock_collection.data.update.assert_not_called()

    def test_update_user_exception_on_fetch(self):
        """Test updating user with exception on fetch."""
        self.mock_collection.query.fetch_objects.side_effect = Exception("Database error")

        result = UserModelWeaviate.update_user("user_123", {"name": "New Name"})

        assert result is False
        self.mock_collection.data.update.assert_not_called()
    
    def test_update_user_exception_on_update(self):
        """Test updating user with exception on update."""
        mock_obj = MagicMock()
        mock_obj.uuid = "uuid_123"
        self.mock_collection.query.fetch_objects.return_value.objects = [mock_obj]
        self.mock_collection.data.update.side_effect = Exception("Database error")

        result = UserModelWeaviate.update_user("user_123", {"name": "New Name"})

        assert result is False

    def test_get_attributes_by_filter_success(self):
        """Test getting attributes by filter successfully."""
        mock_obj1 = MagicMock()
        mock_obj1.properties = {"user_id": "user_1", "fcm_token": "token_1"}
        mock_obj2 = MagicMock()
        mock_obj2.properties = {"user_id": "user_2", "fcm_token": "token_2"}
        self.mock_collection.query.fetch_objects.return_value.objects = [mock_obj1, mock_obj2]

        result = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=["user_1", "user_2", "user_3"],
            return_attr="fcm_token"
        )

        assert result == {
            "user_1": "token_1",
            "user_2": "token_2",
            "user_3": None
        }

    def test_get_attributes_by_filter_single_value(self):
        """Test getting attributes with single filter value."""
        mock_obj = MagicMock()
        mock_obj.properties = {"user_id": "user_1", "fcm_token": "token_1"}
        self.mock_collection.query.fetch_objects.return_value.objects = [mock_obj]

        result = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=["user_1"],
            return_attr="fcm_token"
        )

        assert result == {"user_1": "token_1"}

    def test_get_attributes_by_filter_empty_input(self):
        """Test getting attributes with empty filter values."""
        result = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=[],
            return_attr="fcm_token"
        )

        assert result == {}
        self.mock_collection.query.fetch_objects.assert_not_called()

    def test_get_attributes_by_filter_no_matches(self):
        """Test getting attributes when no users match."""
        self.mock_collection.query.fetch_objects.return_value.objects = []

        result = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=["user_1", "user_2"],
            return_attr="fcm_token"
        )

        assert result == {
            "user_1": None,
            "user_2": None
        }

    def test_get_attributes_by_filter_exception(self):
        """Test getting attributes with exception."""
        self.mock_collection.query.fetch_objects.side_effect = Exception("Database error")

        result = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=["user_1", "user_2"],
            return_attr="fcm_token"
        )

        assert result == {
            "user_1": None,
            "user_2": None
        }

    def test_get_attributes_by_filter_missing_return_attr(self):
        """Test getting attributes when return attribute doesn't exist."""
        mock_obj = MagicMock()
        mock_obj.properties = {"user_id": "user_1", "name": "Test User"}
        self.mock_collection.query.fetch_objects.return_value.objects = [mock_obj]

        result = UserModelWeaviate.get_attributes_by_filter(
            filter_attr="user_id",
            filter_values=["user_1"],
            return_attr="fcm_token"
        )

        assert result == {"user_1": None}



class TestProviderModelWeaviate:
    """Tests for ProviderModelWeaviate."""
    
    @pytest.fixture
    def mock_collection(self):
        """Mock Weaviate collection."""
        collection = Mock()
        collection.data = Mock()
        collection.query = Mock()
        return collection
    
    @pytest.fixture
    def sample_provider_data(self):
        """Sample provider data."""
        return {
            "provider_id": "provider_123",
            "name": "John's Plumbing",
            "category": "plumbing",
            "skills": ["residential", "commercial"],
            "rating": 4.5,
            "experience_years": 10,
            "price_range": "$$",
            "availability": "weekdays",
            "description": "Professional plumbing services"
        }
    
    def test_create_provider_success(self, mock_collection, sample_provider_data):
        """Test creating a new provider successfully."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_collection.data.insert.return_value = "uuid_456"
            
            result = ProviderModelWeaviate.create_provider(sample_provider_data)
            
            assert result == "uuid_456"
            assert mock_collection.data.insert.called
            call_args = mock_collection.data.insert.call_args[1]['properties']
            assert call_args['provider_id'] == "provider_123"
            assert call_args['name'] == "John's Plumbing"
            assert call_args['category'] == "plumbing"
    
    def test_create_provider_failure(self, mock_collection, sample_provider_data):
        """Test creating provider with exception."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_collection.data.insert.side_effect = Exception("Database error")
            
            result = ProviderModelWeaviate.create_provider(sample_provider_data)
            
            assert result is None
    
    def test_get_provider_by_id_success(self, mock_collection):
        """Test getting provider by ID successfully."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_obj = Mock()
            mock_obj.properties = {
                "provider_id": "provider_123",
                "name": "John's Plumbing",
                "category": "plumbing"
            }
            mock_response = Mock()
            mock_response.objects = [mock_obj]
            mock_collection.query.fetch_objects.return_value = mock_response
            
            result = ProviderModelWeaviate.get_provider_by_id("provider_123")
            
            assert result is not None
            assert result["provider_id"] == "provider_123"
            assert result["name"] == "John's Plumbing"
    
    def test_get_provider_by_id_not_found(self, mock_collection):
        """Test getting provider when not found."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_response = Mock()
            mock_response.objects = []
            mock_collection.query.fetch_objects.return_value = mock_response
            
            result = ProviderModelWeaviate.get_provider_by_id("nonexistent")
            
            assert result is None
    
    def test_search_providers_by_category_success(self, mock_collection):
        """Test searching providers by category."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_obj1 = Mock()
            mock_obj1.properties = {"name": "Provider 1", "category": "plumbing"}
            mock_obj2 = Mock()
            mock_obj2.properties = {"name": "Provider 2", "category": "plumbing"}
            mock_response = Mock()
            mock_response.objects = [mock_obj1, mock_obj2]
            mock_collection.query.fetch_objects.return_value = mock_response
            
            result = ProviderModelWeaviate.search_providers_by_category("plumbing", limit=10)
            
            assert len(result) == 2
            assert result[0]["category"] == "plumbing"
            assert result[1]["category"] == "plumbing"
    
    def test_search_providers_by_category_empty(self, mock_collection):
        """Test searching providers with no results."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_response = Mock()
            mock_response.objects = []
            mock_collection.query.fetch_objects.return_value = mock_response
            
            result = ProviderModelWeaviate.search_providers_by_category("nonexistent")
            
            assert result == []
    
    def test_vector_search_providers_success(self, mock_collection):
        """Test vector search for providers."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_obj = Mock()
            mock_obj.properties = {"name": "Provider 1"}
            mock_obj.metadata = Mock()
            mock_obj.metadata.score = 0.95
            mock_response = Mock()
            mock_response.objects = [mock_obj]
            mock_collection.query.hybrid.return_value = mock_response
            
            result = ProviderModelWeaviate.vector_search_providers("need plumber", limit=3)
            
            assert len(result) == 1
            assert result[0]["name"] == "Provider 1"
            assert result[0]["score"] == 0.95
    
    def test_vector_search_providers_exception(self, mock_collection):
        """Test vector search with exception."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_collection.query.hybrid.side_effect = Exception("Search error")
            
            result = ProviderModelWeaviate.vector_search_providers("need plumber")
            
            assert result == []
    
    def test_get_all_providers_success(self, mock_collection):
        """Test getting all providers."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_obj1 = Mock()
            mock_obj1.properties = {"name": "Provider 1"}
            mock_obj2 = Mock()
            mock_obj2.properties = {"name": "Provider 2"}
            mock_response = Mock()
            mock_response.objects = [mock_obj1, mock_obj2]
            mock_collection.query.fetch_objects.return_value = mock_response
            
            result = ProviderModelWeaviate.get_all_providers(limit=100)
            
            assert len(result) == 2
            assert result[0]["name"] == "Provider 1"
            assert result[1]["name"] == "Provider 2"
    
    def test_get_all_providers_exception(self, mock_collection):
        """Test getting all providers with exception."""
        with patch('ai_assistant.weaviate_models.get_providers_collection', return_value=mock_collection):
            mock_collection.query.fetch_objects.side_effect = Exception("Database error")
            
            result = ProviderModelWeaviate.get_all_providers()
            
            assert result == []
