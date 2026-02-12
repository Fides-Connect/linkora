"""Unit tests for user management endpoints."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from aiohttp.web import Request, Response
from datetime import datetime

from ai_assistant.api.v1.endpoints.auth import user_sync, user_logout


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
        
        # Mock dependencies in ai_assistant.api.v1.endpoints.auth
        with patch('ai_assistant.api.v1.endpoints.auth.firestore_service') as mock_firestore, \
             patch('ai_assistant.api.v1.endpoints.auth.UserModelWeaviate') as mock_weaviate, \
             patch('ai_assistant.api.v1.endpoints.auth.seeding_service') as mock_seeding:
            
            # Setup behavior
            mock_firestore.get_user = AsyncMock(return_value=None)  # User does not exist in Firestore
            mock_firestore.update_user = AsyncMock(return_value=True)
            mock_seeding.seed_new_user = AsyncMock(return_value=True)
            mock_weaviate.create_user.return_value = "new_uuid"
            
            # Act
            response = await user_sync(request)
            
            # Assert
            assert response.status == 200
            mock_firestore.get_user.assert_called_once_with("test_user_123")
            mock_seeding.seed_new_user.assert_called_once()
            mock_firestore.update_user.assert_called_once()
            mock_weaviate.create_user.assert_called_once()
    
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
        
        # Mock dependencies
        with patch('ai_assistant.api.v1.endpoints.auth.firestore_service') as mock_firestore, \
             patch('ai_assistant.api.v1.endpoints.auth.UserModelWeaviate') as mock_weaviate:
            
            # Setup behavior
            # User exists in Firestore
            mock_firestore.get_user = AsyncMock(return_value={'user_id': 'test_user_123'})
            mock_firestore.update_user = AsyncMock(return_value=True)
            
            # User exists in Weaviate
            mock_weaviate.get_user_by_id.return_value = {
                "user_id": "test_user_123",
                "name": "Old User",
                "email": "old@example.com"
            }
            mock_weaviate.update_user.return_value = True
            
            # Act
            response = await user_sync(request)
            
            # Assert
            assert response.status == 200
            mock_firestore.get_user.assert_called_once_with("test_user_123")
            mock_firestore.update_user.assert_called_once()
            mock_weaviate.get_user_by_id.assert_called_once_with("test_user_123")
            mock_weaviate.update_user.assert_called_once()
    
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
        with patch('ai_assistant.api.v1.endpoints.auth._sessions') as mock_sessions:
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
