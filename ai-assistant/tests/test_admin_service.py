"""
Tests for Admin Service
Tests authentication, authorization, and all admin endpoints.
"""
import pytest
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.ai_assistant.services.admin_service import AdminService, AdminAuth
from src.ai_assistant.weaviate_models import UserModelWeaviate, ProviderModelWeaviate
from src.ai_assistant.services.notification_service import NotificationService


class TestAdminAuth:
    """Test AdminAuth authentication and authorization."""
    
    def test_generate_secret(self):
        """Test secure secret generation."""
        secret1 = AdminAuth.generate_secret()
        secret2 = AdminAuth.generate_secret()
        
        assert len(secret1) > 32
        assert len(secret2) > 32
        assert secret1 != secret2  # Should be random
    
    def test_get_admin_secret_from_env(self):
        """Test retrieving admin secret from environment."""
        test_secret = "test_secret_token_123"
        
        with patch.dict(os.environ, {'ADMIN_SECRET_KEY': test_secret}):
            secret = AdminAuth.get_admin_secret()
            assert secret == test_secret
    
    def test_verify_token_with_valid_token(self):
        """Test token verification with valid token."""
        test_secret = "valid_token_123"
        
        with patch.dict(os.environ, {'ADMIN_SECRET_KEY': test_secret}):
            request = Mock()
            request.headers.get.return_value = f'Bearer {test_secret}'
            
            assert AdminAuth.verify_token(request) is True
    
    def test_verify_token_with_invalid_token(self):
        """Test token verification with invalid token."""
        test_secret = "valid_token_123"
        
        with patch.dict(os.environ, {'ADMIN_SECRET_KEY': test_secret}):
            request = Mock()
            request.headers.get.return_value = 'Bearer wrong_token'
            
            assert AdminAuth.verify_token(request) is False
    
    def test_verify_token_without_bearer_prefix(self):
        """Test token verification without Bearer prefix."""
        test_secret = "valid_token_123"
        
        with patch.dict(os.environ, {'ADMIN_SECRET_KEY': test_secret}):
            request = Mock()
            request.headers.get.return_value = test_secret  # Missing "Bearer "
            
            assert AdminAuth.verify_token(request) is False
    
    def test_verify_token_when_secret_not_configured(self):
        """Test token verification when ADMIN_SECRET_KEY not set."""
        with patch.dict(os.environ, {}, clear=True):
            request = Mock()
            request.headers.get.return_value = 'Bearer some_token'
            
            assert AdminAuth.verify_token(request) is False


class TestAdminService:
    """Test AdminService functionality."""
    
    def test_admin_service_initialization(self):
        """Test AdminService initialization."""
        mock_signaling_server = Mock()
        admin_service = AdminService(signaling_server=mock_signaling_server)
        
        assert admin_service.signaling_server == mock_signaling_server
        assert isinstance(admin_service.startup_time, datetime)
    
    def test_get_system_info(self):
        """Test get_system_info returns correct structure."""
        mock_signaling_server = Mock()
        mock_signaling_server.active_connections = [1, 2, 3]
        mock_signaling_server.total_connections = 10
        
        with patch.dict(os.environ, {
            'LANGUAGE_CODE': 'en-US',
            'VOICE_NAME': 'en-US-Neural2-C',
        }):
            admin_service = AdminService(signaling_server=mock_signaling_server)
            info = admin_service.get_system_info()
            
            assert info['status'] == 'running'
            assert info['version'] == '1.0.0'
            assert 'uptime_seconds' in info
            assert info['environment']['language_code'] == 'en-US'
            assert info['websocket_connections']['active'] == 3
    
    @pytest.mark.asyncio
    async def test_health_endpoint_authorized(self):
        """Test health endpoint with valid authentication."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        
        with patch.object(AdminAuth, 'verify_token', return_value=True):
            response = await admin_service.health_detailed(request)
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_health_endpoint_unauthorized(self):
        """Test health endpoint rejects unauthorized requests."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        
        with patch.object(AdminAuth, 'verify_token', return_value=False):
            response = await admin_service.health_detailed(request)
            assert response.status == 401
    
    @pytest.mark.asyncio
    async def test_get_stats_endpoint(self):
        """Test stats endpoint returns database statistics."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        
        mock_users = [
            {'user_id': '1', 'fcm_token': 'token1'},
            {'user_id': '2', 'fcm_token': ''},
        ]
        mock_providers = [{'provider_id': '1'}]
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(UserModelWeaviate, 'get_all_users', return_value=mock_users), \
             patch.object(ProviderModelWeaviate, 'get_all_providers', return_value=mock_providers):
            
            response = await admin_service.get_stats(request)
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_list_users_endpoint(self):
        """Test list users endpoint."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.query = Mock()
        request.query.get = Mock(return_value='50')
        
        mock_users = [{
            'user_id': 'user1',
            'name': 'John Doe',
            'email': 'john@example.com',
            'fcm_token': 'token123',
            'has_open_request': False,
            'last_sign_in': datetime(2025, 12, 10, 10, 0, 0, tzinfo=timezone.utc),
            'created_at': datetime(2025, 12, 1, 8, 0, 0, tzinfo=timezone.utc),
        }]
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(UserModelWeaviate, 'get_all_users', return_value=mock_users):
            
            response = await admin_service.list_users(request)
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_get_user_detail_found(self):
        """Test get user detail endpoint when user exists."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.match_info = {'user_id': 'user123'}
        
        mock_user = {
            'user_id': 'user123',
            'name': 'John Doe',
            'email': 'john@example.com',
            'fcm_token': 'token123456789',
            'has_open_request': False,
        }
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(UserModelWeaviate, 'get_user_by_id', return_value=mock_user):
            
            response = await admin_service.get_user_detail(request)
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_get_user_detail_not_found(self):
        """Test get user detail when user doesn't exist."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.match_info = {'user_id': 'nonexistent'}
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(UserModelWeaviate, 'get_user_by_id', return_value=None):
            
            response = await admin_service.get_user_detail(request)
            assert response.status == 404
    
    @pytest.mark.asyncio
    async def test_send_notification_to_specific_users(self):
        """Test sending notification to specific users."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.json = AsyncMock(return_value={
            'user_ids': ['user1', 'user2'],
            'title': 'Test',
            'body': 'Test message'
        })
        
        mock_results = {'user1': True, 'user2': True}
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(NotificationService, 'send_to_multiple_users', 
                         new_callable=AsyncMock, return_value=mock_results):
            
            response = await admin_service.send_notification(request)
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_send_notification_missing_fields(self):
        """Test sending notification with missing required fields."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.json = AsyncMock(return_value={'title': 'Test'})  # Missing 'body'
        
        with patch.object(AdminAuth, 'verify_token', return_value=True):
            response = await admin_service.send_notification(request)
            assert response.status == 400
    
    @pytest.mark.asyncio
    async def test_test_notification_endpoint(self):
        """Test sending a test notification."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.json = AsyncMock(return_value={
            'fcm_token': 'test_token_123',
            'title': 'Test',
            'body': 'Test message'
        })
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(NotificationService, 'send_to_token',
                         new_callable=AsyncMock, return_value=True):
            
            response = await admin_service.test_notification(request)
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_test_notification_missing_token(self):
        """Test sending test notification without FCM token."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.json = AsyncMock(return_value={'title': 'Test', 'body': 'Test'})
        
        with patch.object(AdminAuth, 'verify_token', return_value=True):
            response = await admin_service.test_notification(request)
            assert response.status == 400
    
    def test_register_routes(self):
        """Test that all routes are registered."""
        from aiohttp import web
        admin_service = AdminService()
        app = web.Application()
        
        admin_service.register_routes(app)
        
        # Check that routes were added
        routes = [route.resource.canonical for route in app.router.routes()]
        
        assert '/admin/health' in routes
        assert '/admin/stats' in routes
        assert '/admin/users' in routes
        assert '/admin/providers' in routes


class TestAdminServiceErrorHandling:
    """Test error handling in admin service."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_with_exception(self):
        """Test health endpoint handles exceptions gracefully."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(admin_service, 'get_system_info', side_effect=Exception("Test error")):
            
            response = await admin_service.health_detailed(request)
            assert response.status == 500
    
    @pytest.mark.asyncio
    async def test_stats_endpoint_with_database_error(self):
        """Test stats endpoint handles database errors."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(UserModelWeaviate, 'get_all_users',
                         side_effect=Exception("Database error")):
            
            response = await admin_service.get_stats(request)
            assert response.status == 500
    
    @pytest.mark.asyncio
    async def test_notification_endpoint_with_fcm_error(self):
        """Test notification endpoint handles sending errors."""
        admin_service = AdminService()
        request = Mock()
        request.remote = '127.0.0.1'
        request.json = AsyncMock(return_value={
            'user_ids': ['user1'],
            'title': 'Test',
            'body': 'Test message'
        })
        
        with patch.object(AdminAuth, 'verify_token', return_value=True), \
             patch.object(NotificationService, 'send_to_multiple_users',
                         side_effect=Exception("FCM error")):
            
            response = await admin_service.send_notification(request)
            assert response.status == 500


class TestAdminServiceIntegration:
    """Integration tests for admin service."""
    
    @pytest.mark.asyncio
    async def test_full_authentication_flow(self):
        """Test complete authentication flow."""
        test_secret = AdminAuth.generate_secret()
        admin_service = AdminService()
        
        request = Mock()
        request.headers.get.return_value = f'Bearer {test_secret}'
        request.remote = '127.0.0.1'
        
        with patch.dict(os.environ, {'ADMIN_SECRET_KEY': test_secret}):
            # Should be authorized
            assert AdminAuth.verify_token(request) is True
            
            # Endpoints should work
            with patch.object(UserModelWeaviate, 'get_all_users', return_value=[]), \
                 patch.object(ProviderModelWeaviate, 'get_all_providers', return_value=[]):
                
                response = await admin_service.get_stats(request)
                assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_invalid_token_blocks_all_endpoints(self):
        """Test that invalid token blocks access to all endpoints."""
        test_secret = AdminAuth.generate_secret()
        admin_service = AdminService()
        
        request = Mock()
        request.headers.get.return_value = 'Bearer invalid_token'
        request.remote = '127.0.0.1'
        request.query = Mock()
        request.query.get = Mock(return_value='10')
        request.match_info = {'user_id': 'user123'}
        request.json = AsyncMock(return_value={})
        
        with patch.dict(os.environ, {'ADMIN_SECRET_KEY': test_secret}):
            # All endpoints should return 401
            assert (await admin_service.health_detailed(request)).status == 401
            assert (await admin_service.get_stats(request)).status == 401
            assert (await admin_service.list_users(request)).status == 401
            assert (await admin_service.get_user_detail(request)).status == 401
            assert (await admin_service.send_notification(request)).status == 401
            assert (await admin_service.test_notification(request)).status == 401
