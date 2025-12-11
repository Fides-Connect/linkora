"""Unit tests for user management endpoints."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from aiohttp.web import Request, Response
from datetime import datetime

from ai_assistant.user_endpoints import user_sync, user_logout


class TestUserSyncEndpoint:
    """Tests for user_sync endpoint."""
    
    @pytest.mark.asyncio
    async def test_user_sync_creates_new_user(self):
        """Test creating a new user via sync endpoint."""
        # Arrange
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "user_id": "test_user_123",
            "name": "Test User",
            "email": "test@example.com",
            "photo_url": "https://example.com/photo.jpg",
            "fcm_token": "test_fcm_token"
        })
        
        # Mock UserModelWeaviate
        with patch('ai_assistant.user_endpoints.UserModelWeaviate') as mock_model:
            mock_model.get_user_by_id.return_value = None  # User doesn't exist
            mock_model.create_user.return_value = "uuid_123"  # Successfully created
            
            # Act
            response = await user_sync(request)
            
            # Assert
            assert response.status == 200
            assert mock_model.get_user_by_id.called
            assert mock_model.create_user.called
    
    @pytest.mark.asyncio
    async def test_user_sync_updates_existing_user(self):
        """Test updating an existing user via sync endpoint."""
        # Arrange
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "user_id": "test_user_123",
            "name": "Updated User",
            "email": "updated@example.com",
            "photo_url": "https://example.com/new_photo.jpg",
            "fcm_token": "updated_fcm_token"
        })
        
        # Mock UserModelWeaviate
        with patch('ai_assistant.user_endpoints.UserModelWeaviate') as mock_model:
            mock_model.get_user_by_id.return_value = {
                "user_id": "test_user_123",
                "name": "Old User",
                "email": "old@example.com"
            }
            mock_model.update_user.return_value = True  # Successfully updated
            
            # Act
            response = await user_sync(request)
            
            # Assert
            assert response.status == 200
            assert mock_model.get_user_by_id.called
            assert mock_model.update_user.called
    
    @pytest.mark.asyncio
    async def test_user_sync_missing_user_id(self):
        """Test user_sync with missing user_id."""
        # Arrange
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "name": "Test User",
            "email": "test@example.com"
        })
        
        # Act
        response = await user_sync(request)
        
        # Assert
        assert response.status == 400


class TestUserLogoutEndpoint:
    """Tests for user_logout endpoint."""
    
    @pytest.mark.asyncio
    async def test_user_logout_success(self):
        """Test successful user logout."""
        # Arrange
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={
            "user_id": "test_user_123"
        })
        
        # Mock sessions
        with patch('ai_assistant.user_endpoints._sessions') as mock_sessions:
            mock_sessions.items.return_value = [
                ("session_1", {"user_id": "test_user_123"}),
                ("session_2", {"user_id": "other_user"})
            ]
            
            # Act
            response = await user_logout(request)
            
            # Assert
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_user_logout_missing_user_id(self):
        """Test user_logout with missing user_id."""
        # Arrange
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={})
        
        # Act
        response = await user_logout(request)
        
        # Assert
        assert response.status == 400
