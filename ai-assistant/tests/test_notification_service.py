"""Unit tests for NotificationService."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from firebase_admin import messaging

from ai_assistant.services.notification_service import (
    NotificationService,
    notify_provider_match,
    notify_request_completed,
    notify_conversation_update,
    notify_service_request_status_change,
    notify_new_service_request,
)


class TestNotificationService:
    """Tests for NotificationService."""
    
    @pytest.mark.asyncio
    async def test_send_to_token_success(self):
        """Test sending notification to a valid FCM token."""
        with patch('ai_assistant.services.notification_service.messaging.send_each_async') as mock_send:
            # Mock BatchResponse with successful SendResponse
            mock_response = Mock()
            mock_response.success = True
            mock_response.message_id = "message_id_123"
            mock_batch = Mock()
            mock_batch.responses = [mock_response]
            mock_send.return_value = mock_batch
            
            result = await NotificationService.send_to_token(
                fcm_token="test_token_123",
                title="Test Title",
                body="Test Body",
                data={"key": "value"}
            )
            
            assert result is True
            assert mock_send.called
            
            # Check message structure (now it's a list of messages)
            call_args = mock_send.call_args[0][0][0]  # First arg, first message
            assert isinstance(call_args, messaging.Message)
            assert call_args.notification.title == "Test Title"
            assert call_args.notification.body == "Test Body"
            assert call_args.data == {"key": "value"}
            assert call_args.token == "test_token_123"
    
    @pytest.mark.asyncio
    async def test_send_to_token_empty_token(self):
        """Test sending notification with empty token fails gracefully."""
        result = await NotificationService.send_to_token(
            fcm_token="",
            title="Test",
            body="Test"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_token_unregistered_error(self):
        """Test handling of unregistered FCM token."""
        with patch('ai_assistant.services.notification_service.messaging.send') as mock_send:
            mock_send.side_effect = messaging.UnregisteredError("Token unregistered")
            
            result = await NotificationService.send_to_token(
                fcm_token="invalid_token",
                title="Test",
                body="Test"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_token_general_error(self):
        """Test handling of general errors."""
        with patch('ai_assistant.services.notification_service.messaging.send') as mock_send:
            mock_send.side_effect = Exception("Network error")
            
            result = await NotificationService.send_to_token(
                fcm_token="test_token",
                title="Test",
                body="Test"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_user_success(self):
        """Test sending notification to user by user_id."""
        mock_user = {
            "user_id": "user_123",
            "name": "Test User",
            "fcm_token": "valid_token_123"
        }
        
        with patch('ai_assistant.services.notification_service.UserModelWeaviate.get_user_by_id') as mock_get_user, \
             patch('ai_assistant.services.notification_service.messaging.send_each_async') as mock_send:
            
            mock_get_user.return_value = mock_user
            
            # Mock BatchResponse with successful SendResponse
            mock_response = Mock()
            mock_response.success = True
            mock_response.message_id = "message_id_123"
            mock_batch = Mock()
            mock_batch.responses = [mock_response]
            mock_send.return_value = mock_batch
            
            result = await NotificationService.send_to_user(
                user_id="user_123",
                title="Test Title",
                body="Test Body"
            )
            
            assert result is True
            mock_get_user.assert_called_with("user_123")
            assert mock_send.called
    
    @pytest.mark.asyncio
    async def test_send_to_user_not_found(self):
        """Test sending notification to non-existent user."""
        with patch('ai_assistant.services.notification_service.UserModelWeaviate.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = None
            
            result = await NotificationService.send_to_user(
                user_id="nonexistent_user",
                title="Test",
                body="Test"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_user_no_fcm_token(self):
        """Test sending notification to user without FCM token."""
        mock_user = {
            "user_id": "user_123",
            "name": "Test User",
            "fcm_token": ""  # No token
        }
        
        with patch('ai_assistant.services.notification_service.UserModelWeaviate.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            result = await NotificationService.send_to_user(
                user_id="user_123",
                title="Test",
                body="Test"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_multiple_users(self):
        """Test sending notification to multiple users."""
        with patch('ai_assistant.services.notification_service.UserModelWeaviate.get_attributes_by_filter') as mock_get_attrs, \
             patch('ai_assistant.services.notification_service.NotificationService.send_multicast') as mock_multicast:
            
            # Mock token fetching - user_2 has no token
            mock_get_attrs.return_value = {
                "user_1": "token_1",
                "user_2": None,  # No token
                "user_3": "token_3"
            }
            
            # Mock multicast response
            mock_resp_1 = Mock()
            mock_resp_1.success = True
            mock_resp_2 = Mock()
            mock_resp_2.success = True
            
            mock_multicast.return_value = {
                "success_count": 2,
                "failure_count": 0,
                "responses": [mock_resp_1, mock_resp_2]
            }
            
            results = await NotificationService.send_to_multiple_users(
                user_ids=["user_1", "user_2", "user_3"],
                title="Test",
                body="Test"
            )
            
            assert results == {
                "user_1": True,
                "user_2": False,  # No token
                "user_3": True
            }
            assert mock_get_attrs.called
            assert mock_multicast.called

    
    @pytest.mark.asyncio
    async def test_send_multicast_success(self):
        """Test sending multicast notification."""
        mock_response = Mock()
        mock_response.success_count = 3
        mock_response.failure_count = 1
        mock_response.responses = [Mock()] * 4
        
        with patch('ai_assistant.services.notification_service.messaging.send_each_for_multicast_async') as mock_multicast:
            mock_multicast.return_value = mock_response
            
            result = await NotificationService.send_multicast(
                fcm_tokens=["token1", "token2", "token3", "token4"],
                title="Multicast Test",
                body="Test Body"
            )
            
            assert result["success_count"] == 3
            assert result["failure_count"] == 1
            assert len(result["responses"]) == 4
    
    @pytest.mark.asyncio
    async def test_send_multicast_empty_tokens(self):
        """Test multicast with empty token list."""
        result = await NotificationService.send_multicast(
            fcm_tokens=[],
            title="Test",
            body="Test"
        )
        
        assert result["success_count"] == 0
        assert result["failure_count"] == 0
        assert result["responses"] == []


class TestConvenienceFunctions:
    """Tests for convenience notification functions."""
    
    @pytest.mark.asyncio
    async def test_notify_provider_match(self):
        """Test provider match notification."""
        with patch('ai_assistant.services.notification_service.NotificationService.send_to_user') as mock_send:
            mock_send.return_value = True
            
            result = await notify_provider_match(
                user_id="user_123",
                provider_name="John's Plumbing",
                category="plumber"
            )
            
            assert result is True
            assert mock_send.called
            
            # Check call arguments
            call_kwargs = mock_send.call_args[1]
            assert "Provider Found!" in call_kwargs["title"]
            assert "John's Plumbing" in call_kwargs["body"]
            assert call_kwargs["data"]["type"] == "provider_match"
    
    @pytest.mark.asyncio
    async def test_notify_request_completed(self):
        """Test request completed notification."""
        with patch('ai_assistant.services.notification_service.NotificationService.send_to_user') as mock_send:
            mock_send.return_value = True
            
            result = await notify_request_completed(user_id="user_123")
            
            assert result is True
            assert mock_send.called
            
            call_kwargs = mock_send.call_args[1]
            assert "Completed" in call_kwargs["title"]
            assert call_kwargs["data"]["type"] == "request_completed"
    
    @pytest.mark.asyncio
    async def test_notify_conversation_update(self):
        """Test conversation update notification."""
        with patch('ai_assistant.services.notification_service.NotificationService.send_to_user') as mock_send:
            mock_send.return_value = True
            
            result = await notify_conversation_update(
                user_id="user_123",
                message="AI has a response for you"
            )
            
            assert result is True
            assert mock_send.called
            
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["body"] == "AI has a response for you"
            assert call_kwargs["data"]["type"] == "conversation_update"


class TestServiceRequestStatusNotifications:
    """Tests for notify_service_request_status_change helper."""

    @pytest.fixture
    def mock_send_to_user(self):
        with patch(
            'ai_assistant.services.notification_service.NotificationService.send_to_user',
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = True
            yield mock

    async def test_seeker_notified_on_accepted(self, mock_send_to_user):
        """Seeker receives notification when provider accepts."""
        await notify_service_request_status_change(
            seeker_id='seeker_1',
            provider_id='provider_1',
            actor_id='provider_1',
            service_request_id='req_abc',
            new_status='accepted',
        )
        assert mock_send_to_user.call_count == 1
        kwargs = mock_send_to_user.call_args[1]
        assert kwargs['user_id'] == 'seeker_1'
        assert kwargs['data']['type'] == 'service_request_status_change'
        assert kwargs['data']['service_request_id'] == 'req_abc'
        assert kwargs['data']['new_status'] == 'accepted'

    async def test_provider_notified_on_cancelled(self, mock_send_to_user):
        """Provider receives notification when seeker cancels."""
        await notify_service_request_status_change(
            seeker_id='seeker_1',
            provider_id='provider_1',
            actor_id='seeker_1',
            service_request_id='req_abc',
            new_status='cancelled',
        )
        assert mock_send_to_user.call_count == 1
        kwargs = mock_send_to_user.call_args[1]
        assert kwargs['user_id'] == 'provider_1'
        assert kwargs['data']['new_status'] == 'cancelled'

    async def test_provider_notified_on_payment_completed(self, mock_send_to_user):
        """Provider receives notification when seeker confirms payment."""
        await notify_service_request_status_change(
            seeker_id='seeker_1',
            provider_id='provider_1',
            actor_id='seeker_1',
            service_request_id='req_abc',
            new_status='paymentCompleted',
        )
        assert mock_send_to_user.call_count == 1
        kwargs = mock_send_to_user.call_args[1]
        assert kwargs['user_id'] == 'provider_1'

    async def test_actor_does_not_receive_own_notification(self, mock_send_to_user):
        """The user who triggered the change is not notified."""
        # seeker cancels — they are the actor, so only provider should be notified
        await notify_service_request_status_change(
            seeker_id='seeker_1',
            provider_id='seeker_1',   # edge case: same ID
            actor_id='seeker_1',
            service_request_id='req_abc',
            new_status='cancelled',
        )
        assert mock_send_to_user.call_count == 0

    async def test_unknown_status_sends_no_notification(self, mock_send_to_user):
        """An unrecognised status does not trigger any notification."""
        await notify_service_request_status_change(
            seeker_id='seeker_1',
            provider_id='provider_1',
            actor_id='provider_1',
            service_request_id='req_abc',
            new_status='unknownStatus',
        )
        mock_send_to_user.assert_not_called()

    async def test_no_provider_on_cancelled_does_not_crash(self, mock_send_to_user):
        """Cancelling a request with no provider yet completes without error."""
        await notify_service_request_status_change(
            seeker_id='seeker_1',
            provider_id=None,
            actor_id='seeker_1',
            service_request_id='req_abc',
            new_status='cancelled',
        )
        mock_send_to_user.assert_not_called()


class TestNotifyNewServiceRequest:
    """Tests for notify_new_service_request helper."""

    @pytest.fixture
    def mock_send_to_user(self):
        with patch(
            'ai_assistant.services.notification_service.NotificationService.send_to_user',
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = True
            yield mock

    async def test_provider_notified_on_new_request(self, mock_send_to_user):
        """Provider receives a notification when a new service request is created."""
        await notify_new_service_request(
            provider_id='provider_1',
            service_request_id='req_new',
            category='Plumbing',
        )
        mock_send_to_user.assert_called_once()
        kwargs = mock_send_to_user.call_args[1]
        assert kwargs['user_id'] == 'provider_1'
        assert kwargs['data']['type'] == 'new_service_request'
        assert kwargs['data']['service_request_id'] == 'req_new'
        assert 'Plumbing' in kwargs['body']

    async def test_no_provider_id_sends_nothing(self, mock_send_to_user):
        """Empty provider_id silently skips the notification."""
        await notify_new_service_request(
            provider_id='',
            service_request_id='req_new',
        )
        mock_send_to_user.assert_not_called()

    async def test_no_category_omits_category_text(self, mock_send_to_user):
        """Notification body is still valid when no category is provided."""
        await notify_new_service_request(
            provider_id='provider_1',
            service_request_id='req_new',
        )
        kwargs = mock_send_to_user.call_args[1]
        assert '()' not in kwargs['body']
