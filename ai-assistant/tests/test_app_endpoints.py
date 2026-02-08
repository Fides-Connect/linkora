"""
Unit tests for application endpoints.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from aiohttp import web
from datetime import datetime

from ai_assistant import app_endpoints

class TestAppEndpoints:
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock aiohttp request."""
        request = Mock(spec=web.Request)
        request.headers = {}
        request.match_info = {}
        request.json = AsyncMock(return_value={})
        return request

    @pytest.fixture
    def mock_auth(self):
        """Mock firebase auth verification."""
        with patch('ai_assistant.app_endpoints.auth.verify_id_token') as mock_verify:
            mock_verify.return_value = {'uid': 'test_user_id'}
            yield mock_verify

    @pytest.fixture
    def mock_firestore(self):
        """Mock the global firestore_service in app_endpoints."""
        with patch('ai_assistant.app_endpoints.firestore_service') as mock_service:
            yield mock_service

    @pytest.mark.asyncio
    async def test_get_current_user_id_success(self, mock_request, mock_auth):
        """Test successful user ID extraction."""
        mock_request.headers = {'Authorization': 'Bearer valid_token'}
        user_id = await app_endpoints.get_current_user_id(mock_request)
        assert user_id == 'test_user_id'
        mock_auth.assert_called_with('valid_token')

    @pytest.mark.asyncio
    async def test_get_current_user_id_missing_header(self, mock_request):
        """Test missing authorization header."""
        mock_request.headers = {}
        with pytest.raises(web.HTTPUnauthorized):
            await app_endpoints.get_current_user_id(mock_request)

    @pytest.mark.asyncio
    async def test_get_current_user_id_invalid_token(self, mock_request):
        """Test invalid token raises unauthorized."""
        mock_request.headers = {'Authorization': 'Bearer invalid_token'}
        with patch('ai_assistant.app_endpoints.auth.verify_id_token', side_effect=Exception("Invalid")):
            with pytest.raises(web.HTTPUnauthorized):
                await app_endpoints.get_current_user_id(mock_request)

    @pytest.mark.asyncio
    async def test_create_service_request(self, mock_request, mock_auth, mock_firestore):
        """Test create_service_request endpoint."""
        # Arrange
        mock_request.headers = {'Authorization': 'Bearer token'}
        mock_request.json = AsyncMock(return_value={
            "title": "Need help",
            "category": "plumbing"
        })
        
        mock_firestore.add_service_request = AsyncMock(return_value="req_123")

        # Act
        response = await app_endpoints.add_service_request(mock_request)

        # Assert
        assert response.status == 201
        # response is web.Response, body is bytes
        import json
        body = json.loads(response.body.decode())
        assert body['service_request_id'] == 'req_123'
        assert body['status'] == 'created'
        
        # Verify call arguments
        mock_firestore.add_service_request.assert_called_once()
        ca = mock_firestore.add_service_request.call_args[0][0]
        assert ca['seeker_user_id'] == 'test_user_id'
        assert ca['title'] == 'Need help'

    @pytest.mark.asyncio
    async def test_get_favorites(self, mock_request, mock_auth, mock_firestore):
        """Test get_favorites endpoint with datetime serialization."""
        # Arrange
        mock_request.headers = {'Authorization': 'Bearer token'}
        
        favorites_data = [{
            "user_id": "fav1",
            "created_at": datetime(2023, 1, 1, 12, 0, 0)
        }]
        mock_firestore.get_favorites = AsyncMock(return_value=favorites_data)

        # Act
        response = await app_endpoints.get_favorites(mock_request)

        # Assert
        assert response.status == 200
        import json
        body = json.loads(response.body.decode())
        assert len(body) == 1
        assert body[0]['user_id'] == 'fav1'
        # Verify datetime was serialized to string
        assert body[0]['created_at'] == '2023-01-01T12:00:00'

    @pytest.mark.asyncio
    async def test_update_service_request_status(self, mock_request, mock_auth, mock_firestore):
        """Test update_service_request_status endpoint."""
        # Arrange
        mock_request.headers = {'Authorization': 'Bearer token'}
        mock_request.match_info = {'service_request_id': 'req_123'}
        mock_request.json = AsyncMock(return_value={'status': 'completed'})
        
        mock_firestore.update_request_status = AsyncMock(return_value=True)

        # Act
        response = await app_endpoints.update_service_request_status(mock_request)

        # Assert
        assert response.status == 200
        mock_firestore.update_request_status.assert_called_with('req_123', 'completed')

    @pytest.mark.asyncio
    async def test_add_favorite_success(self, mock_request, mock_auth, mock_firestore):
        """Test add_favorite success."""
        mock_request.headers = {'Authorization': 'Bearer token'}
        mock_request.match_info = {'user_id': 'fav_user'}
        
        mock_firestore.get_user = AsyncMock(return_value={'name': 'Fav User'})
        mock_firestore.add_favorite = AsyncMock(return_value=True)

        response = await app_endpoints.add_favorite(mock_request)
        assert response.status == 200
        mock_firestore.add_favorite.assert_called_with('test_user_id', 'fav_user')

    @pytest.mark.asyncio
    async def test_add_favorite_not_found(self, mock_request, mock_auth, mock_firestore):
        """Test add_favorite when user does not exist."""
        mock_request.headers = {'Authorization': 'Bearer token'}
        mock_request.match_info = {'user_id': 'unknown_user'}
        
        mock_firestore.get_user = AsyncMock(return_value=None)

        response = await app_endpoints.add_favorite(mock_request)
        assert response.status == 404
