"""
Unit tests for Signaling Server functionality.
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aiohttp import web, WSMsgType
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from ai_assistant.signaling_server import SignalingServer


@pytest.fixture
def mock_ai_assistant():
    """Mock AI Assistant."""
    assistant = Mock()
    assistant.get_greeting_audio = AsyncMock(return_value=(
        "Hello!",
        async_audio_gen()
    ))
    return assistant


async def async_audio_gen():
    """Mock audio generator."""
    yield b'audio'


@pytest.fixture
def signaling_server():
    """Create SignalingServer instance."""
    return SignalingServer()


class TestSignalingServerInitialization:
    """Test SignalingServer initialization."""
    
    def test_initialization(self, signaling_server):
        """Test that SignalingServer initializes correctly."""
        assert isinstance(signaling_server.active_connections, dict)
        assert len(signaling_server.active_connections) == 0


class TestHealthCheck:
    """Test health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_ok(self, signaling_server):
        """Test that health check returns OK response."""
        request = Mock(spec=web.Request)
        response = await signaling_server.health_check(request)
        
        assert response.status == 200


class TestWebSocketHandling:
    """Test WebSocket connection handling."""
    
    @pytest.mark.asyncio
    async def test_handle_websocket_creates_connection(self, signaling_server):
        """Test that WebSocket handler creates peer connection."""
        # Mock WebSocket
        mock_ws = Mock(spec=web.WebSocketResponse)
        mock_ws.prepare = AsyncMock()
        
        # Mock the async iteration
        async def mock_ws_iter():
            # Simulate no messages, then close
            return
            yield  # Make it a generator
        
        mock_ws.__aiter__ = lambda self: mock_ws_iter()
        
        # Mock request
        mock_request = Mock(spec=web.Request)
        mock_request.remote = '127.0.0.1'
        mock_request.query = {'user_id': 'test_user', 'language': 'de', 'mode': 'voice'}
        
        with patch('ai_assistant.signaling_server.web.WebSocketResponse', return_value=mock_ws), \
             patch('ai_assistant.signaling_server.PeerConnectionHandler') as mock_handler_class:
            
            mock_handler = Mock()
            mock_handler.close = AsyncMock()
            mock_handler_class.return_value = mock_handler
            
            result = await signaling_server.handle_websocket(mock_request)
            
            # Verify WebSocket was prepared
            mock_ws.prepare.assert_called_once()


class TestMessageHandling:
    """Test message handling."""
    
    @pytest.mark.asyncio
    async def test_handle_offer_message(self, signaling_server):
        """Test handling offer message."""
        mock_handler = Mock()
        mock_handler.handle_offer = AsyncMock()
        mock_handler.connection_id = 'test-123'
        
        message = {
            'type': 'offer',
            'sdp': 'test-sdp-content'
        }
        
        await signaling_server._handle_message(mock_handler, message)
        
        mock_handler.handle_offer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_ice_candidate_message(self, signaling_server):
        """Test handling ICE candidate message."""
        mock_handler = Mock()
        mock_handler.handle_ice_candidate = AsyncMock()
        mock_handler.connection_id = 'test-123'
        
        message = {
            'type': 'ice-candidate',
            'candidate': {
                'candidate': 'test-candidate',
                'sdpMid': '0',
                'sdpMLineIndex': 0
            }
        }
        
        await signaling_server._handle_message(mock_handler, message)
        
        mock_handler.handle_ice_candidate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self, signaling_server):
        """Test handling unknown message type."""
        mock_handler = Mock()
        mock_handler.connection_id = 'test-123'
        
        message = {
            'type': 'unknown-type',
            'data': 'test'
        }
        
        # Should not raise exception
        await signaling_server._handle_message(mock_handler, message)


class TestConnectionManagement:
    """Test connection management."""
    
    @pytest.mark.asyncio
    async def test_active_connections_tracking(self, signaling_server):
        """Test that active connections are tracked."""
        # Initially empty
        assert len(signaling_server.active_connections) == 0
        
        # Add a connection manually
        mock_handler = Mock()
        signaling_server.active_connections['conn-1'] = mock_handler
        
        assert len(signaling_server.active_connections) == 1
        assert 'conn-1' in signaling_server.active_connections
    
    @pytest.mark.asyncio
    async def test_connection_cleanup(self, signaling_server):
        """Test that connections are cleaned up properly."""
        mock_handler = Mock()
        mock_handler.close = AsyncMock()
        
        signaling_server.active_connections['conn-1'] = mock_handler
        
        # Simulate cleanup
        await mock_handler.close()
        del signaling_server.active_connections['conn-1']
        
        assert len(signaling_server.active_connections) == 0


class TestTokenAuthentication:
    """Test Firebase ID token authentication on WebSocket connections."""

    def _make_request(self, query_params: dict) -> Mock:
        """Helper to build a mock aiohttp request with query params."""
        mock_request = Mock(spec=web.Request)
        mock_request.remote = '127.0.0.1'
        mock_request.query = query_params
        return mock_request

    @pytest.mark.asyncio
    async def test_valid_token_overrides_user_id(self, signaling_server):
        """A valid Firebase ID token should replace the client-supplied user_id."""
        mock_ws = Mock(spec=web.WebSocketResponse)
        mock_ws.prepare = AsyncMock()

        async def mock_ws_iter():
            return
            yield

        mock_ws.__aiter__ = lambda self: mock_ws_iter()

        mock_request = self._make_request({
            'user_id': 'spoofed-uid',
            'token': 'valid-token',
            'language': 'en',
            'mode': 'text',
        })

        with patch('ai_assistant.signaling_server.web.WebSocketResponse', return_value=mock_ws), \
             patch('ai_assistant.signaling_server.firebase_auth.verify_id_token',
                   return_value={'uid': 'real-uid-from-token'}) as mock_verify, \
             patch('ai_assistant.signaling_server.PeerConnectionHandler') as mock_handler_class:

            mock_handler = Mock()
            mock_handler.close = AsyncMock()
            mock_handler_class.return_value = mock_handler

            await signaling_server.handle_websocket(mock_request)

            mock_verify.assert_called_once_with('valid-token')
            # The handler must receive the uid from the token, not the spoofed one
            _, kwargs = mock_handler_class.call_args
            assert kwargs['user_id'] == 'real-uid-from-token'

    @pytest.mark.asyncio
    async def test_invalid_token_closes_websocket_with_4401(self, signaling_server):
        """An invalid token should close the WebSocket with code 4401."""
        mock_ws = Mock(spec=web.WebSocketResponse)
        mock_ws.prepare = AsyncMock()
        mock_ws.close = AsyncMock()

        mock_request = self._make_request({
            'user_id': 'any-uid',
            'token': 'bad-token',
        })

        with patch('ai_assistant.signaling_server.web.WebSocketResponse', return_value=mock_ws), \
             patch('ai_assistant.signaling_server.firebase_auth.verify_id_token',
                   side_effect=Exception('Token invalid')):

            await signaling_server.handle_websocket(mock_request)

            mock_ws.close.assert_called_once_with(code=4401, message=b'Unauthorized')

    @pytest.mark.asyncio
    async def test_no_token_uses_client_supplied_user_id(self, signaling_server):
        """When no token is present (local dev), the plain user_id is trusted."""
        mock_ws = Mock(spec=web.WebSocketResponse)
        mock_ws.prepare = AsyncMock()

        async def mock_ws_iter():
            return
            yield

        mock_ws.__aiter__ = lambda self: mock_ws_iter()

        mock_request = self._make_request({
            'user_id': 'local-dev-uid',
            'language': 'de',
            'mode': 'voice',
        })

        with patch('ai_assistant.signaling_server.web.WebSocketResponse', return_value=mock_ws), \
             patch('ai_assistant.signaling_server.firebase_auth.verify_id_token') as mock_verify, \
             patch('ai_assistant.signaling_server.PeerConnectionHandler') as mock_handler_class:

            mock_handler = Mock()
            mock_handler.close = AsyncMock()
            mock_handler_class.return_value = mock_handler

            await signaling_server.handle_websocket(mock_request)

            # verify_id_token must not be called when no token is present
            mock_verify.assert_not_called()
            _, kwargs = mock_handler_class.call_args
            assert kwargs['user_id'] == 'local-dev-uid'
