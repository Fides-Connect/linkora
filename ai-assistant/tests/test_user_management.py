"""
Unit tests for user management functionality.
Tests user sync, logout, and session management.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_assistant.common_endpoints import (
    user_sync, 
    user_logout, 
    get_active_user,
    get_all_active_users,
    remove_active_user,
    _active_users,
    set_signaling_server
)


class TestUserManagement(AioHTTPTestCase):
    """Test user management endpoints and functions."""
    
    async def get_application(self):
        """Create test application."""
        app = web.Application()
        app.router.add_post('/user/sync', user_sync)
        app.router.add_post('/user/logout', user_logout)
        return app
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Clear active users before each test
        _active_users.clear()
        
        # Mock Firebase auth
        self.firebase_patcher = patch('ai_assistant.common_endpoints.firebase_auth')
        self.mock_firebase = self.firebase_patcher.start()
        
        # Mock Weaviate operations
        self.weaviate_patcher = patch('ai_assistant.common_endpoints.UserModelWeaviate')
        # Mock chat history persistence
        self.chat_history_patcher = patch('ai_assistant.common_endpoints.ChatMessageModelWeaviate')
        self.mock_chat_history = self.chat_history_patcher.start()
        self.mock_weaviate = self.weaviate_patcher.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.firebase_patcher.stop()
        self.weaviate_patcher.stop()
        self.chat_history_patcher.stop()
        set_signaling_server(None)
        _active_users.clear()
        super().tearDown()
    
    async def test_user_sync_new_user(self):
        """Test syncing a new user creates database entry."""
        # Mock Firebase token verification
        self.mock_firebase.verify_id_token.return_value = {
            'uid': 'test_user_123',
            'email': 'test@example.com',
            'name': 'Test User'
        }
        
        # Mock Weaviate - user doesn't exist initially, then exists after creation
        self.mock_weaviate.get_user_by_id.side_effect = [
            None,  # First call - user doesn't exist
            {      # Second call - user exists after creation
                'user_id': 'test_user_123',
                'email': 'test@example.com',
                'name': 'Test User'
            }
        ]
        self.mock_weaviate.create_user.return_value = 'uuid_123'
        
        # Make request
        resp = await self.client.post('/user/sync', json={
            'id_token': 'valid_token',
            'user_id': 'test_user_123',
            'email': 'test@example.com',
            'name': 'Test User',
            'fcm_token': 'fcm_token_123'
        })
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data['success'] is True
        assert data['is_new_user'] is True
        assert data['user_id'] == 'test_user_123'
        assert 'user_profile' in data
        
        # Verify user added to active users
        assert 'test_user_123' in _active_users
        assert _active_users['test_user_123']['fcm_token'] == 'fcm_token_123'
    
    async def test_user_sync_existing_user(self):
        """Test syncing an existing user updates their info."""
        # Mock Firebase token verification
        self.mock_firebase.verify_id_token.return_value = {
            'uid': 'existing_user_456',
            'email': 'existing@example.com'
        }
        
        # Mock Weaviate - user exists
        self.mock_weaviate.get_user_by_id.return_value = {
            'user_id': 'existing_user_456',
            'email': 'existing@example.com',
            'fcm_token': 'old_token'
        }
        self.mock_weaviate.update_user.return_value = True
        
        # Make request
        resp = await self.client.post('/user/sync', json={
            'id_token': 'valid_token',
            'user_id': 'existing_user_456',
            'email': 'existing@example.com',
            'fcm_token': 'new_fcm_token_456'
        })
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data['success'] is True
        assert data['is_new_user'] is False
        assert data['user_id'] == 'existing_user_456'
        
        # Verify FCM token updated
        assert _active_users['existing_user_456']['fcm_token'] == 'new_fcm_token_456'
        
        # Verify Weaviate update called
        self.mock_weaviate.update_user.assert_called_once()
    
    async def test_user_sync_invalid_token(self):
        """Test user sync with invalid Firebase token."""
        # Mock Firebase token verification failure
        self.mock_firebase.verify_id_token.side_effect = Exception('Invalid token')
        
        resp = await self.client.post('/user/sync', json={
            'id_token': 'invalid_token',
            'user_id': 'test_user'
        })
        
        assert resp.status == 401
        data = await resp.json()
        assert 'error' in data
    
    async def test_user_sync_missing_token(self):
        """Test user sync without ID token."""
        resp = await self.client.post('/user/sync', json={
            'user_id': 'test_user'
        })
        
        assert resp.status == 400
        data = await resp.json()
        assert data['error'] == 'Missing id_token'
    
    async def test_user_logout_success(self):
        """Test successful user logout."""
        # Setup: Add user to active users
        _active_users['logout_user_789'] = {
            'user_id': 'logout_user_789',
            'email': 'logout@example.com',
            'fcm_token': 'fcm_789'
        }
        
        # Mock Firebase token verification
        self.mock_firebase.verify_id_token.return_value = {
            'uid': 'logout_user_789'
        }
        
        resp = await self.client.post('/user/logout', json={
            'id_token': 'valid_token',
            'user_id': 'logout_user_789'
        })
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data['success'] is True
        assert data['message'] == 'Logged out successfully'
        
        # Verify user removed from active users
        assert 'logout_user_789' not in _active_users
    
    async def test_user_logout_with_history_clear(self):
        """Test user logout with conversation history clearing."""
        # Setup
        _active_users['history_user_101'] = {
            'user_id': 'history_user_101',
            'email': 'history@example.com'
        }
        
        # Mock signaling server
        mock_server = Mock()
        mock_server.cleanup_user_assistant.return_value = True
        set_signaling_server(mock_server)
        
        # Mock Firebase
        self.mock_firebase.verify_id_token.return_value = {
            'uid': 'history_user_101'
        }
        
        resp = await self.client.post('/user/logout', json={
            'id_token': 'valid_token',
            'user_id': 'history_user_101',
            'clear_history': True
        })
        
        assert resp.status == 200
        data = await resp.json()
        
        assert data['success'] is True
        assert data['history_cleared'] is True
        
        # Verify cleanup was called
        mock_server.cleanup_user_assistant.assert_called_once_with('history_user_101', clear_persistent=True)
        self.mock_chat_history.delete_messages.assert_not_called()

    async def test_user_logout_with_history_clear_no_assistant(self):
        """Ensure persisted history is cleared even without active assistant."""
        _active_users['history_user_202'] = {
            'user_id': 'history_user_202',
            'email': 'history202@example.com'
        }

        # No signaling server configured
        set_signaling_server(None)

        self.mock_firebase.verify_id_token.return_value = {
            'uid': 'history_user_202'
        }
        self.mock_chat_history.delete_messages.return_value = True

        resp = await self.client.post('/user/logout', json={
            'id_token': 'valid_token',
            'user_id': 'history_user_202',
            'clear_history': True
        })

        assert resp.status == 200
        data = await resp.json()
        assert data['history_cleared'] is True
        self.mock_chat_history.delete_messages.assert_called_once_with('history_user_202')
    
    async def test_user_logout_not_in_active_users(self):
        """Test logout for user not in active sessions."""
        self.mock_firebase.verify_id_token.return_value = {
            'uid': 'unknown_user'
        }
        
        resp = await self.client.post('/user/logout', json={
            'id_token': 'valid_token',
            'user_id': 'unknown_user'
        })
        
        assert resp.status == 200
        data = await resp.json()
        assert data['success'] is True
    
    def test_get_active_user(self):
        """Test getting active user data."""
        # Setup
        _active_users['user_abc'] = {
            'user_id': 'user_abc',
            'fcm_token': 'fcm_abc'
        }
        
        result = get_active_user('user_abc')
        assert result is not None
        assert result['fcm_token'] == 'fcm_abc'
        
        # Test non-existent user
        result = get_active_user('non_existent')
        assert result is None
    
    def test_get_all_active_users(self):
        """Test getting all active users."""
        _active_users['user1'] = {'user_id': 'user1'}
        _active_users['user2'] = {'user_id': 'user2'}
        
        result = get_all_active_users()
        assert len(result) == 2
        assert 'user1' in result
        assert 'user2' in result
    
    def test_remove_active_user(self):
        """Test removing active user."""
        _active_users['user_xyz'] = {'user_id': 'user_xyz'}
        
        # Remove existing user
        result = remove_active_user('user_xyz')
        assert result is True
        assert 'user_xyz' not in _active_users
        
        # Try to remove non-existent user
        result = remove_active_user('user_xyz')
        assert result is False


class TestConcurrentUsers(AioHTTPTestCase):
    """Test concurrent user scenarios."""
    
    async def get_application(self):
        app = web.Application()
        app.router.add_post('/user/sync', user_sync)
        return app
    
    def setUp(self):
        super().setUp()
        _active_users.clear()
        self.firebase_patcher = patch('ai_assistant.common_endpoints.firebase_auth')
        self.mock_firebase = self.firebase_patcher.start()
        self.weaviate_patcher = patch('ai_assistant.common_endpoints.UserModelWeaviate')
        self.mock_weaviate = self.weaviate_patcher.start()
    
    def tearDown(self):
        self.firebase_patcher.stop()
        self.weaviate_patcher.stop()
        _active_users.clear()
        super().tearDown()
    
    async def test_multiple_users_sync_concurrently(self):
        """Test multiple users can sync simultaneously."""
        # Setup mocks
        def verify_token(token):
            return {'uid': token, 'email': f'{token}@test.com'}
        
        self.mock_firebase.verify_id_token.side_effect = verify_token
        self.mock_weaviate.get_user_by_id.return_value = None
        self.mock_weaviate.create_user.return_value = 'uuid'
        
        def get_user(user_id):
            return {'user_id': user_id, 'email': f'{user_id}@test.com'}
        
        self.mock_weaviate.get_user_by_id.side_effect = get_user
        
        # Sync multiple users
        users = ['user_a', 'user_b', 'user_c']
        
        for user_id in users:
            resp = await self.client.post('/user/sync', json={
                'id_token': user_id,
                'user_id': user_id,
                'email': f'{user_id}@test.com',
                'fcm_token': f'fcm_{user_id}'
            })
            assert resp.status == 200
        
        # Verify all users in active_users
        assert len(_active_users) == 3
        for user_id in users:
            assert user_id in _active_users
            assert _active_users[user_id]['fcm_token'] == f'fcm_{user_id}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
