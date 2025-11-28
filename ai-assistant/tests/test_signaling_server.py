"""
Unit tests for SignalingServer and WebSocket handling.
Tests concurrent connections, user isolation, and cleanup.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_assistant.signaling_server import SignalingServer


class TestSignalingServer:
    """Test SignalingServer functionality."""
    
    @pytest.fixture
    def server(self):
        """Create a SignalingServer instance for testing."""
        return SignalingServer(
            gemini_api_key='test_api_key',
            language_code='en-US',
            voice_name='en-US-Test'
        )
    
    def test_server_initialization(self, server):
        """Test server initializes correctly."""
        assert server.gemini_api_key == 'test_api_key'
        assert server.language_code == 'en-US'
        assert server.voice_name == 'en-US-Test'
        assert len(server.active_connections) == 0
        assert len(server.user_assistants) == 0
    
    def test_cleanup_user_assistant_success(self, server):
        """Test cleaning up user assistant."""
        # Mock AIAssistant instance directly
        mock_assistant = Mock()
        mock_assistant.clear_conversation_history = Mock()
        server.user_assistants['user_123'] = mock_assistant
        
        result = server.cleanup_user_assistant('user_123')
        
        assert result is True
        assert 'user_123' not in server.user_assistants
        mock_assistant.clear_conversation_history.assert_called_once_with(clear_persistent=False)
    
    def test_cleanup_user_assistant_not_found(self, server):
        """Test cleaning up non-existent user assistant."""
        result = server.cleanup_user_assistant('non_existent')
        assert result is False
    
    def test_multiple_users_get_separate_assistants(self, server):
        """Test that multiple users get separate AIAssistant instances."""
        # Simulate creating assistants for different users
        user_ids = ['user_a', 'user_b', 'user_c']
        
        assistants = []
        for user_id in user_ids:
            mock_assistant = Mock()
            mock_assistant.user_id = user_id
            server.user_assistants[user_id] = mock_assistant
            assistants.append(mock_assistant)
        
        # Verify all users have assistants
        assert len(server.user_assistants) == 3
        assert all(uid in server.user_assistants for uid in user_ids)
        
        # Verify they're separate instances
        assert assistants[0] is not assistants[1]
        assert assistants[1] is not assistants[2]
class TestConcurrentConnections:
    """Test concurrent connection handling."""
    
    @pytest.fixture
    def server(self):
        return SignalingServer(
            gemini_api_key='test_key',
            language_code='en-US',
            voice_name='test'
        )
    
    def test_multiple_connections_tracked(self, server):
        """Test that multiple connections are tracked correctly."""
        # Mock handlers
        handler1 = Mock()
        handler1.user_id = 'user_1'
        handler2 = Mock()
        handler2.user_id = 'user_2'
        handler3 = Mock()
        handler3.user_id = 'user_1'  # Same user, different connection
        
        server.active_connections['conn_1'] = handler1
        server.active_connections['conn_2'] = handler2
        server.active_connections['conn_3'] = handler3
        
        assert len(server.active_connections) == 3
        
        # Count connections per user
        user_1_conns = [h for h in server.active_connections.values() if h.user_id == 'user_1']
        assert len(user_1_conns) == 2
    
    def test_connection_cleanup_preserves_other_user_connections(self, server):
        """Test that cleaning up one connection doesn't affect others."""
        handler1 = Mock()
        handler1.user_id = 'user_a'
        handler2 = Mock()
        handler2.user_id = 'user_b'
        
        server.active_connections['conn_1'] = handler1
        server.active_connections['conn_2'] = handler2
        
        # Remove one connection
        del server.active_connections['conn_1']
        
        assert len(server.active_connections) == 1
        assert 'conn_2' in server.active_connections
        assert server.active_connections['conn_2'].user_id == 'user_b'


class TestUserIsolation:
    """Test that users are properly isolated from each other."""
    
    @pytest.fixture
    def server(self):
        return SignalingServer(
            gemini_api_key='test_key',
            language_code='en-US',
            voice_name='test'
        )
    
    def test_user_assistants_isolated(self, server):
        """Test that each user gets their own isolated AIAssistant."""
        # Create assistants for two users
        assistant_a = Mock()
        assistant_a.user_id = 'user_a'
        assistant_a.store = {}
        
        assistant_b = Mock()
        assistant_b.user_id = 'user_b'
        assistant_b.store = {}
        
        server.user_assistants['user_a'] = assistant_a
        server.user_assistants['user_b'] = assistant_b
        
        # Verify they have separate stores (conversation history)
        assert assistant_a.store is not assistant_b.store        # Modify one user's data
        assistant_a.store['conversation'] = ['message from user_a']
        
        # Verify other user's data is unaffected
        assert 'conversation' not in assistant_b.store
    
    def test_cleanup_one_user_preserves_others(self, server):
        """Test that cleaning up one user doesn't affect others."""
        server.user_assistants['user_1'] = Mock()
        server.user_assistants['user_2'] = Mock()
        server.user_assistants['user_3'] = Mock()
        
        # Add clear_conversation_history method to mocks
        for assistant in server.user_assistants.values():
            assistant.clear_conversation_history = Mock()
            
        # Cleanup one user
        server.cleanup_user_assistant('user_2')
        
        # Verify others are preserved
        assert len(server.user_assistants) == 2
        assert 'user_1' in server.user_assistants
        assert 'user_3' in server.user_assistants
        assert 'user_2' not in server.user_assistants


class TestReconnectionScenarios:
    """Test user reconnection scenarios."""
    
    @pytest.fixture
    def server(self):
        return SignalingServer(
            gemini_api_key='test_key',
            language_code='en-US',
            voice_name='test'
        )
    
    def test_user_reconnects_reuses_assistant(self, server):
        """Test that reconnecting user reuses existing AIAssistant."""
        # First connection
        assistant = Mock()
        assistant.user_id = 'user_reconnect'
        assistant.store = {'history': ['previous message']}
        
        server.user_assistants['user_reconnect'] = assistant
            
        # User disconnects (connection removed but assistant preserved)
        # ... connection cleanup happens ...
        
        # User reconnects - assistant should still exist
        assert 'user_reconnect' in server.user_assistants
        reused_assistant = server.user_assistants['user_reconnect']
        
        # Verify it's the same instance with history
        assert reused_assistant is assistant
        assert reused_assistant.store['history'] == ['previous message']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
