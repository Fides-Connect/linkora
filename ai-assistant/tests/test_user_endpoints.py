"""Unit tests for user management endpoints."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from aiohttp.web import Request, Response
from datetime import datetime

from ai_assistant.api.v1.endpoints.auth import user_sync, user_logout, sign_in_google
from ai_assistant.api.v1.endpoints.me import create_my_competence


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
             patch('ai_assistant.api.v1.endpoints.auth.seeding_service') as mock_seeding:
            
            # Setup behavior
            mock_firestore.get_user = AsyncMock(return_value=None)  # User does not exist in Firestore
            mock_firestore.update_user = AsyncMock(return_value=True)
            mock_seeding.seed_new_user = AsyncMock(return_value=True)
            
            # Act
            response = await user_sync(request)
            
            # Assert
            assert response.status == 200
            mock_firestore.get_user.assert_called_once_with("test_user_123")
            mock_seeding.seed_new_user.assert_called_once()
            mock_firestore.update_user.assert_called_once()
            # Note: Weaviate sync now happens inside seeding_service, not directly in user_sync
    
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


class TestSettingsEndpoints:
    """Tests for GET/PATCH /api/v1/me/settings."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_defaults(self):
        """Returns default language and notifications_enabled when user_app_settings is empty."""
        import json
        from ai_assistant.api.v1.endpoints.me import get_settings
        request = Mock(spec=Request)
        with patch('ai_assistant.api.v1.endpoints.me.get_current_user_id', new=AsyncMock(return_value='user1')), \
             patch('ai_assistant.api.v1.endpoints.me.firestore_service') as mock_fs:
            mock_fs.get_user = AsyncMock(return_value={'user_id': 'user1', 'user_app_settings': {}})
            response = await get_settings(request)
        assert response.status == 200
        body = json.loads(response.body)
        assert body['language'] == 'en'
        assert body['notifications_enabled'] is True

    @pytest.mark.asyncio
    async def test_get_settings_returns_stored_values(self):
        """Returns stored language and notifications_enabled."""
        import json
        from ai_assistant.api.v1.endpoints.me import get_settings
        request = Mock(spec=Request)
        with patch('ai_assistant.api.v1.endpoints.me.get_current_user_id', new=AsyncMock(return_value='user1')), \
             patch('ai_assistant.api.v1.endpoints.me.firestore_service') as mock_fs:
            mock_fs.get_user = AsyncMock(return_value={
                'user_id': 'user1',
                'user_app_settings': {'language': 'de', 'notifications_enabled': False},
            })
            response = await get_settings(request)
        assert response.status == 200
        body = json.loads(response.body)
        assert body['language'] == 'de'
        assert body['notifications_enabled'] is False

    @pytest.mark.asyncio
    async def test_get_settings_user_not_found(self):
        """Returns 404 when user does not exist."""
        from ai_assistant.api.v1.endpoints.me import get_settings
        request = Mock(spec=Request)
        with patch('ai_assistant.api.v1.endpoints.me.get_current_user_id', new=AsyncMock(return_value='user1')), \
             patch('ai_assistant.api.v1.endpoints.me.firestore_service') as mock_fs:
            mock_fs.get_user = AsyncMock(return_value=None)
            response = await get_settings(request)
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_update_settings_merges_into_existing(self):
        """PATCH merges the new language while preserving other settings."""
        import json
        from ai_assistant.api.v1.endpoints.me import update_settings
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={'language': 'de'})
        with patch('ai_assistant.api.v1.endpoints.me.get_current_user_id', new=AsyncMock(return_value='user1')), \
             patch('ai_assistant.api.v1.endpoints.me.firestore_service') as mock_fs:
            mock_fs.get_user = AsyncMock(return_value={
                'user_id': 'user1',
                'user_app_settings': {'language': 'en', 'notifications_enabled': True},
            })
            mock_fs.update_user = AsyncMock(return_value=True)
            response = await update_settings(request)
        assert response.status == 200
        body = json.loads(response.body)
        assert body['language'] == 'de'
        assert body['notifications_enabled'] is True  # unchanged
        saved = mock_fs.update_user.call_args[0][1]['user_app_settings']
        assert saved['language'] == 'de'
        assert saved['notifications_enabled'] is True

    @pytest.mark.asyncio
    async def test_update_settings_ignores_unknown_keys(self):
        """Unknown keys in the request body are silently ignored."""
        import json
        from ai_assistant.api.v1.endpoints.me import update_settings
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={'language': 'de', 'evil_key': 'value'})
        with patch('ai_assistant.api.v1.endpoints.me.get_current_user_id', new=AsyncMock(return_value='user1')), \
             patch('ai_assistant.api.v1.endpoints.me.firestore_service') as mock_fs:
            mock_fs.get_user = AsyncMock(return_value={'user_id': 'user1', 'user_app_settings': {}})
            mock_fs.update_user = AsyncMock(return_value=True)
            response = await update_settings(request)
        assert response.status == 200
        saved = mock_fs.update_user.call_args[0][1]['user_app_settings']
        assert 'evil_key' not in saved
        assert saved['language'] == 'de'

    @pytest.mark.asyncio
    async def test_update_settings_notifications_flag(self):
        """PATCH correctly stores notifications_enabled=False."""
        import json
        from ai_assistant.api.v1.endpoints.me import update_settings
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={'notifications_enabled': False})
        with patch('ai_assistant.api.v1.endpoints.me.get_current_user_id', new=AsyncMock(return_value='user1')), \
             patch('ai_assistant.api.v1.endpoints.me.firestore_service') as mock_fs:
            mock_fs.get_user = AsyncMock(return_value={'user_id': 'user1', 'user_app_settings': {}})
            mock_fs.update_user = AsyncMock(return_value=True)
            response = await update_settings(request)
        assert response.status == 200
        body = json.loads(response.body)
        assert body['notifications_enabled'] is False


class TestSignInGoogleEndpoint:
    """Tests for sign_in_google endpoint."""

    @pytest.mark.asyncio
    async def test_sign_in_google_success(self):
        """Valid token returns user info with status 200."""
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={"id_token": "valid-token"})
        decoded = {"uid": "user123", "email": "user@example.com", "name": "Test User"}

        with patch('ai_assistant.api.v1.endpoints.auth.firebase_auth') as mock_auth:
            mock_auth.verify_id_token.return_value = decoded
            response = await sign_in_google(request)

        import json
        assert response.status == 200
        body = json.loads(response.body)
        assert body["user_id"] == "user123"
        assert body["is_valid"] is True
        mock_auth.verify_id_token.assert_called_once_with("valid-token", check_revoked=True)

    @pytest.mark.asyncio
    async def test_sign_in_google_revoked_token_returns_401(self):
        """Revoked token returns 401 with a clear error message."""
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={"id_token": "revoked-token"})

        with patch('ai_assistant.api.v1.endpoints.auth.firebase_auth') as mock_auth:
            mock_auth.RevokedIdTokenError = Exception
            mock_auth.verify_id_token.side_effect = mock_auth.RevokedIdTokenError("Token revoked")
            response = await sign_in_google(request)

        import json
        assert response.status == 401
        body = json.loads(response.body)
        assert "revoked" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_sign_in_google_invalid_token_returns_401(self):
        """Cryptographically invalid token returns 401."""
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={"id_token": "bad-token"})

        with patch('ai_assistant.api.v1.endpoints.auth.firebase_auth') as mock_auth:
            mock_auth.RevokedIdTokenError = type('RevokedIdTokenError', (ValueError,), {})
            mock_auth.verify_id_token.side_effect = ValueError("Invalid token")
            response = await sign_in_google(request)

        import json
        assert response.status == 401
        body = json.loads(response.body)
        assert body["error"] == "Invalid token"

    @pytest.mark.asyncio
    async def test_sign_in_google_missing_token_returns_400(self):
        """Missing id_token field returns 400."""
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={})

        response = await sign_in_google(request)

        import json
        assert response.status == 400
        body = json.loads(response.body)
        assert "id_token" in body["error"]
class TestCreateMyCompetenceEndpoint:
    """Tests for create_my_competence — focused on the Weaviate self-heal path."""

    def _make_request(self, user_id: str = "user-123"):
        request = Mock(spec=Request)
        request.json = AsyncMock(return_value={"competence": {"title": "Flutter Development"}})
        request.app = {}
        return request

    @pytest.mark.asyncio
    async def test_create_competence_syncs_to_weaviate_when_user_exists(self):
        """Happy path: Weaviate user found → create_competence called directly."""
        request = self._make_request()

        mock_user_obj = MagicMock()
        mock_user_obj.uuid = "weaviate-uuid-1"
        mock_weaviate_res = MagicMock()
        mock_weaviate_res.objects = [mock_user_obj]

        with patch("ai_assistant.api.v1.endpoints.me.get_current_user_id", new_callable=AsyncMock, return_value="user-123"), \
             patch("ai_assistant.api.v1.endpoints.me.firestore_service") as mock_fs, \
             patch("ai_assistant.api.v1.endpoints.me.get_user_collection") as mock_coll_fn, \
             patch("ai_assistant.api.v1.endpoints.me.HubSpokeIngestion") as mock_hub:

            mock_fs.get_user = AsyncMock(return_value={"user_id": "user-123", "name": "Test"})
            mock_fs.create_competence = AsyncMock(return_value={"competence_id": "c1", "title": "Flutter Development"})

            mock_coll = MagicMock()
            mock_coll.query.fetch_objects.return_value = mock_weaviate_res
            mock_coll_fn.return_value = mock_coll

            response = await create_my_competence(request)

        assert response.status == 200
        mock_hub.create_competence.assert_called_once()
        # create_user (self-heal) must NOT have been called
        mock_hub.create_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_competence_self_heals_when_weaviate_user_missing(self):
        """Self-heal path: Weaviate user missing → create_user called, then create_competence."""
        request = self._make_request()

        # First fetch_objects call returns empty (user not in Weaviate)
        empty_res = MagicMock()
        empty_res.objects = []
        # After self-heal (create_user), second fetch returns the new user
        healed_obj = MagicMock()
        healed_obj.uuid = "weaviate-uuid-healed"
        healed_res = MagicMock()
        healed_res.objects = [healed_obj]

        with patch("ai_assistant.api.v1.endpoints.me.get_current_user_id", new_callable=AsyncMock, return_value="user-123"), \
             patch("ai_assistant.api.v1.endpoints.me.firestore_service") as mock_fs, \
             patch("ai_assistant.api.v1.endpoints.me.get_user_collection") as mock_coll_fn, \
             patch("ai_assistant.api.v1.endpoints.me.HubSpokeIngestion") as mock_hub:

            mock_fs.get_user = AsyncMock(return_value={"user_id": "user-123", "name": "Test"})
            mock_fs.create_competence = AsyncMock(return_value={"competence_id": "c1", "title": "Flutter Development"})

            mock_coll = MagicMock()
            # First call → empty; second call (after self-heal) → healed
            mock_coll.query.fetch_objects.side_effect = [empty_res, healed_res]
            mock_coll_fn.return_value = mock_coll

            response = await create_my_competence(request)

        assert response.status == 200
        # Self-heal: create_user must have been called exactly once
        mock_hub.create_user.assert_called_once()
        # Competence must still be synced after self-heal
        mock_hub.create_competence.assert_called_once()
