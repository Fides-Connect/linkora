"""
Unit tests for FirestoreService.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from ai_assistant.firestore_service import FirestoreService

class TestFirestoreService:
    @pytest.fixture
    def firestore(self):
        """Create a FirestoreService with a mocked client."""
        with patch('firebase_admin.firestore.client') as mock_client:
            service = FirestoreService()
            # Force initialization of the db property
            _ = service.db
            service._db = mock_client.return_value
            yield service

    @pytest.fixture
    def mock_db_collection(self, firestore):
        """Helper to get the mocked collection method."""
        return firestore.db.collection

    @pytest.mark.asyncio
    async def test_create_service_request(self, firestore, mock_db_collection):
        """Test creating a service request."""
        # Arrange
        request_data = {
            "title": "Test Request",
            "seeker_user_id": "user123"
        }
        
        # Mock document reference and set method
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        # Mock _generate_prefixed_id to return a predictable ID
        with patch.object(firestore, '_generate_prefixed_id', return_value='service_request_123'), \
             patch.object(firestore, 'add_outgoing_service_requests', return_value=True) as mock_add_outgoing:
            # Act
            result = await firestore.create_service_request(request_data)

            # Assert
            assert result is not None
            assert isinstance(result, dict)
            assert result['service_request_id'] == 'service_request_123'
            assert result['title'] == 'Test Request'
            assert 'created_at' in result
            assert 'updated_at' in result
            
            # Verify collection was accessed
            mock_db_collection.assert_called_with('service_requests')
            
            # Verify data was set
            mock_doc_ref.set.assert_called_once()
            call_args = mock_doc_ref.set.call_args[0][0]
            assert call_args['title'] == 'Test Request'
            assert 'created_at' in call_args
            assert 'updated_at' in call_args
            
            # Verify outgoing service request was added
            mock_add_outgoing.assert_called_once_with('user123', ['service_request_123'])

    @pytest.mark.asyncio
    async def test_get_service_requests(self, firestore, mock_db_collection):
        """Test fetching service requests for a user."""
        # Arrange
        user_id = "user123"
        
        # Mock responses for queries
        # We need to mock the stream() method of the query
        mock_query_ref = Mock()
        mock_db_collection.return_value.where.return_value = mock_query_ref
        
        # Create mock documents
        doc1 = Mock()
        doc1.id = "req1"
        doc1.to_dict.return_value = {
            "title": "Seeker Request", 
            "seeker_user_id": user_id,
            "created_at": datetime.now(timezone.utc)
        }
        
        doc2 = Mock()
        doc2.id = "req2"
        doc2.to_dict.return_value = {
            "title": "Provider Request", 
            "selected_provider_user_id": user_id,
            "seeker_user_id": "other_user",
            "created_at": datetime.now(timezone.utc)
        }
        
        # Setup stream returns. 
        # First call is for seeker query, second for provider query
        mock_query_ref.stream.side_effect = [[doc1], [doc2]]
        
        # Mock get_user to return names
        with patch.object(firestore, 'get_user') as mock_get_user:
            mock_get_user.side_effect = lambda uid: {"name": "Test User" if uid == user_id else "Other User"}
            
            # Act
            requests = await firestore.get_service_requests(user_id)

            # Assert
            assert len(requests) == 2
            assert requests[0]['service_request_id'] == 'req1'
            assert requests[1]['service_request_id'] == 'req2'
            
            # Verify user hydration
            assert requests[0]['seeker_user_name'] == 'Test User'
            assert requests[1]['seeker_user_name'] == 'Other User'
            assert requests[1]['selected_provider_user_name'] == 'Test User'

    @pytest.mark.asyncio
    async def test_update_service_request_status(self, firestore, mock_db_collection):
        """Test updating service request status."""
        # Arrange
        request_id = "req123"
        status = "accepted"
        
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        # Mock get_service_request to return a valid service request object
        expected_result = {
            'service_request_id': request_id,
            'status': status,
            'title': 'Test Request',
            'updated_at': datetime.now(timezone.utc)
        }
        with patch.object(firestore, 'get_service_request', return_value=expected_result):
            # Act
            result = await firestore.update_service_request_status(request_id, status)
            
            # Assert
            assert result is not None
            assert isinstance(result, dict)
            assert result['service_request_id'] == request_id
            assert result['status'] == status
            mock_db_collection.assert_called_with('service_requests')
            mock_db_collection.return_value.document.assert_called_with(request_id)
            
            mock_doc_ref.update.assert_called_once()
            update_args = mock_doc_ref.update.call_args[0][0]
            assert update_args['status'] == status
            assert 'updated_at' in update_args

    @pytest.mark.asyncio
    async def test_add_favorite(self, firestore, mock_db_collection):
        """Test adding a favorite to subcollection."""
        # Arrange
        user_id = "user1"
        fav_id = "user2"
        
        mock_favorites_collection = Mock()
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value = mock_favorites_collection
        mock_favorites_collection.document.return_value = mock_doc_ref
        
        # Act
        success = await firestore.add_favorite(user_id, fav_id)
        
        # Assert
        assert success is True
        mock_db_collection.return_value.document.assert_called_with(user_id)
        mock_db_collection.return_value.document.return_value.collection.assert_called_with('favorites')
        mock_favorites_collection.document.assert_called_with(fav_id)
        mock_doc_ref.set.assert_called_once()
        # Verify the set call includes user_id and created_at
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args['user_id'] == fav_id
        assert 'created_at' in call_args

    @pytest.mark.asyncio
    async def test_remove_favorite(self, firestore, mock_db_collection):
        """Test removing a favorite from subcollection."""
        # Arrange
        user_id = "user1"
        fav_id = "user2"
        
        mock_favorites_collection = Mock()
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value = mock_favorites_collection
        mock_favorites_collection.document.return_value = mock_doc_ref
        
        # Act
        success = await firestore.remove_favorite(user_id, fav_id)
        
        # Assert
        assert success is True
        mock_db_collection.return_value.document.assert_called_with(user_id)
        mock_db_collection.return_value.document.return_value.collection.assert_called_with('favorites')
        mock_favorites_collection.document.assert_called_with(fav_id)
        mock_doc_ref.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_favorites(self, firestore, mock_db_collection):
        """Test getting favorites from subcollection with full user details."""
        # Arrange
        user_id = "user1"
        
        # Mock favorites subcollection
        mock_favorites_collection = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value = mock_favorites_collection
        
        # Mock favorite documents
        mock_fav_doc1 = Mock()
        mock_fav_doc1.id = "fav1"
        mock_fav_doc2 = Mock()
        mock_fav_doc2.id = "fav2"
        mock_favorites_collection.stream.return_value = [mock_fav_doc1, mock_fav_doc2]
        
        # Mock get_user to return details for favorites
        with patch.object(firestore, 'get_user') as mock_get_user:
            mock_get_user.side_effect = lambda uid: {
                "user_id": uid,
                "name": f"User {uid}",
                "self_introduction": f"Intro for {uid}",
                "competencies": [],
                "average_rating": 4.5,
                "review_count": 10,
                "feedback_positive": [],
                "feedback_negative": []
            } if uid in ["fav1", "fav2"] else None
            
            # Act
            favorites = await firestore.get_favorites(user_id)
            
            # Assert
            assert len(favorites) == 2
            assert favorites[0]['user_id'] == 'fav1'
            assert favorites[0]['name'] == 'User fav1'
            assert favorites[1]['user_id'] == 'fav2'
    
    @pytest.mark.asyncio
    async def test_update_service_request_with_provider_change(self, firestore, mock_db_collection):
        """Test updating service request with provider change updates incoming lists."""
        # Arrange
        request_id = "req123"
        old_provider = "provider1"
        new_provider = "provider2"
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        # Mock existing document with old provider
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'service_request_id': request_id,
            'title': 'Test Request',
            'seeker_user_id': 'seeker1',
            'selected_provider_user_id': old_provider,
            'status': 'pending'
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        update_data = {
            'selected_provider_user_id': new_provider
        }
        
        # Mock methods
        with patch.object(firestore, 'remove_incoming_service_requests', return_value=True) as mock_remove, \
             patch.object(firestore, 'add_incoming_service_requests', return_value=True) as mock_add, \
             patch.object(firestore, 'get_service_request', return_value={'service_request_id': request_id}):
            
            # Act
            result = await firestore.update_service_request(request_id, update_data)
            
            # Assert
            assert result is not None
            mock_remove.assert_called_once_with(old_provider, [request_id])
            mock_add.assert_called_once_with(new_provider, [request_id])
            mock_doc_ref.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_service_request_removes_from_lists(self, firestore, mock_db_collection):
        """Test deleting service request removes it from user lists."""
        # Arrange
        request_id = "req123"
        seeker_id = "seeker1"
        provider_id = "provider1"
        
        # Mock service request document
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'service_request_id': request_id,
            'seeker_user_id': seeker_id,
            'selected_provider_user_id': provider_id
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        # Mock chats query
        mock_chats_query = Mock()
        mock_chats_query.stream.return_value = []
        mock_db_collection.return_value.where.return_value = mock_chats_query
        
        # Mock provider_candidates subcollection
        mock_providers_collection = Mock()
        mock_providers_collection.stream.return_value = []
        mock_doc_ref.collection.return_value = mock_providers_collection
        
        with patch.object(firestore, 'remove_outgoing_service_requests', return_value=True) as mock_remove_outgoing, \
             patch.object(firestore, 'remove_incoming_service_requests', return_value=True) as mock_remove_incoming:
            
            # Act
            success = await firestore.delete_service_request(request_id)
            
            # Assert
            assert success is True
            mock_remove_outgoing.assert_called_once_with(seeker_id, [request_id])
            mock_remove_incoming.assert_called_once_with(provider_id, [request_id])
            mock_doc_ref.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_service_request_with_provider(self, firestore, mock_db_collection):
        """Test creating service request with provider adds to both lists."""
        # Arrange
        request_data = {
            "title": "Test Request",
            "seeker_user_id": "user123",
            "selected_provider_user_id": "provider456"
        }
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        with patch.object(firestore, '_generate_prefixed_id', return_value='service_request_123'), \
             patch.object(firestore, 'add_outgoing_service_requests', return_value=True) as mock_add_outgoing, \
             patch.object(firestore, 'add_incoming_service_requests', return_value=True) as mock_add_incoming:
            
            # Act
            result = await firestore.create_service_request(request_data)
            
            # Assert
            assert result is not None
            mock_add_outgoing.assert_called_once_with('user123', ['service_request_123'])
            mock_add_incoming.assert_called_once_with('provider456', ['service_request_123'])
    
    @pytest.mark.asyncio
    async def test_create_provider_candidate_adds_to_incoming(self, firestore, mock_db_collection):
        """Test creating provider candidate adds service request to provider's incoming list."""
        # Arrange
        service_request_id = "req123"
        candidate_data = {
            "provider_candidate_user_id": "provider1",
            "matching_score": 85.0
        }
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        with patch.object(firestore, '_generate_prefixed_id', return_value='provider_candidate_123'), \
             patch.object(firestore, 'add_incoming_service_requests', return_value=True) as mock_add_incoming:
            
            # Act
            result = await firestore.create_provider_candidate(service_request_id, candidate_data)
            
            # Assert
            assert result is not None
            mock_add_incoming.assert_called_once_with('provider1', ['req123'])
    
    @pytest.mark.asyncio
    async def test_update_provider_candidate_with_user_change(self, firestore, mock_db_collection):
        """Test updating provider candidate with user change updates incoming lists."""
        # Arrange
        service_request_id = "req123"
        provider_candidate_id = "candidate456"
        old_provider = "provider1"
        new_provider = "provider2"
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        # Mock existing document with old provider
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'provider_candidate_id': provider_candidate_id,
            'service_request_id': service_request_id,
            'provider_candidate_user_id': old_provider,
            'matching_score': 80.0
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        update_data = {
            'provider_candidate_user_id': new_provider
        }
        
        # Mock methods
        with patch.object(firestore, 'get_service_request') as mock_get_request, \
             patch.object(firestore, 'remove_incoming_service_requests', return_value=True) as mock_remove, \
             patch.object(firestore, 'add_incoming_service_requests', return_value=True) as mock_add, \
             patch.object(firestore, 'get_provider_candidate', return_value={'candidate_id': provider_candidate_id}):
            
            # Service request has no selected provider yet
            mock_get_request.return_value = {
                'service_request_id': service_request_id,
                'seeker_user_id': 'seeker1',
                'selected_provider_user_id': ''
            }
            
            # Act
            result = await firestore.update_provider_candidate(service_request_id, provider_candidate_id, update_data)
            
            # Assert
            assert result is not None
            mock_remove.assert_called_once_with(old_provider, [service_request_id])
            mock_add.assert_called_once_with(new_provider, [service_request_id])
    
    @pytest.mark.asyncio
    async def test_update_provider_candidate_does_not_remove_selected_provider(self, firestore, mock_db_collection):
        """Test updating provider candidate doesn't remove from incoming if they're the selected provider."""
        # Arrange
        service_request_id = "req123"
        provider_candidate_id = "candidate456"
        old_provider = "provider1"
        new_provider = "provider2"
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        # Mock existing document with old provider
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'provider_candidate_id': provider_candidate_id,
            'service_request_id': service_request_id,
            'provider_candidate_user_id': old_provider,
            'matching_score': 80.0
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        update_data = {
            'provider_candidate_user_id': new_provider
        }
        
        # Mock methods
        with patch.object(firestore, 'get_service_request') as mock_get_request, \
             patch.object(firestore, 'remove_incoming_service_requests', return_value=True) as mock_remove, \
             patch.object(firestore, 'add_incoming_service_requests', return_value=True) as mock_add, \
             patch.object(firestore, 'get_provider_candidate', return_value={'candidate_id': provider_candidate_id}):
            
            # Old provider is the selected provider
            mock_get_request.return_value = {
                'service_request_id': service_request_id,
                'seeker_user_id': 'seeker1',
                'selected_provider_user_id': old_provider
            }
            
            # Act
            result = await firestore.update_provider_candidate(service_request_id, provider_candidate_id, update_data)
            
            # Assert
            assert result is not None
            # Should NOT remove from old provider's incoming since they're selected
            mock_remove.assert_not_called()
            # Should add to new provider's incoming
            mock_add.assert_called_once_with(new_provider, [service_request_id])
    
    @pytest.mark.asyncio
    async def test_delete_provider_candidate_removes_from_incoming(self, firestore, mock_db_collection):
        """Test deleting provider candidate removes service request from provider's incoming list."""
        # Arrange
        service_request_id = "req123"
        provider_candidate_id = "candidate456"
        provider_user_id = "provider1"
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'provider_candidate_id': provider_candidate_id,
            'service_request_id': service_request_id,
            'provider_candidate_user_id': provider_user_id
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        # Mock chats query
        mock_chats_query = Mock()
        mock_chats_query.stream.return_value = []
        mock_db_collection.return_value.where.return_value = mock_chats_query
        
        with patch.object(firestore, 'get_service_request') as mock_get_request, \
             patch.object(firestore, 'remove_incoming_service_requests', return_value=True) as mock_remove:
            
            # Provider is not selected
            mock_get_request.return_value = {
                'service_request_id': service_request_id,
                'seeker_user_id': 'seeker1',
                'selected_provider_user_id': ''
            }
            
            # Act
            success = await firestore.delete_provider_candidate(service_request_id, provider_candidate_id)
            
            # Assert
            assert success is True
            mock_remove.assert_called_once_with(provider_user_id, [service_request_id])
            mock_doc_ref.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_provider_candidate_keeps_selected_provider_in_incoming(self, firestore, mock_db_collection):
        """Test deleting provider candidate doesn't remove from incoming if they're the selected provider."""
        # Arrange
        service_request_id = "req123"
        provider_candidate_id = "candidate456"
        provider_user_id = "provider1"
        
        # Mock document reference
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        mock_doc_snapshot = Mock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'provider_candidate_id': provider_candidate_id,
            'service_request_id': service_request_id,
            'provider_candidate_user_id': provider_user_id
        }
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        # Mock chats query
        mock_chats_query = Mock()
        mock_chats_query.stream.return_value = []
        mock_db_collection.return_value.where.return_value = mock_chats_query
        
        with patch.object(firestore, 'get_service_request') as mock_get_request, \
             patch.object(firestore, 'remove_incoming_service_requests', return_value=True) as mock_remove:
            
            # Provider is selected
            mock_get_request.return_value = {
                'service_request_id': service_request_id,
                'seeker_user_id': 'seeker1',
                'selected_provider_user_id': provider_user_id
            }
            
            # Act
            success = await firestore.delete_provider_candidate(service_request_id, provider_candidate_id)
            
            # Assert
            assert success is True
            # Should NOT remove since they're the selected provider
            mock_remove.assert_not_called()
            mock_doc_ref.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_chat_message_with_valid_participants(self, firestore, mock_db_collection):
        """Test creating a chat message with valid participants."""
        # Arrange
        chat_id = "chat_123"
        message_data = {
            "sender_user_id": "user_alice",
            "receiver_user_id": "user_bob",
            "message": "Hello!"
        }
        
        # Mock chat document
        mock_chat_doc = Mock()
        mock_chat_doc.exists = True
        mock_chat_doc.to_dict.return_value = {
            "seeker_user_id": "user_alice",
            "provider_user_id": "user_bob"
        }
        mock_chat_doc.id = chat_id
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        
        # Mock message document reference
        mock_msg_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value = mock_msg_doc_ref
        
        with patch.object(firestore, '_generate_prefixed_id', return_value='chat_message_456'):
            # Act
            result = await firestore.create_chat_message(chat_id, message_data)
            
            # Assert
            assert result is not None
            assert result['chat_message_id'] == 'chat_message_456'
            assert result['sender_user_id'] == 'user_alice'
            assert result['receiver_user_id'] == 'user_bob'
            mock_msg_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_chat_message_with_invalid_sender(self, firestore, mock_db_collection):
        """Test creating a chat message with invalid sender (not a chat participant)."""
        # Arrange
        chat_id = "chat_123"
        message_data = {
            "sender_user_id": "user_charlie",  # Not a participant
            "receiver_user_id": "user_bob",
            "message": "Hello!"
        }
        
        # Mock chat document
        mock_chat_doc = Mock()
        mock_chat_doc.exists = True
        mock_chat_doc.to_dict.return_value = {
            "seeker_user_id": "user_alice",
            "provider_user_id": "user_bob"
        }
        mock_chat_doc.id = chat_id
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        
        # Act
        result = await firestore.create_chat_message(chat_id, message_data)
        
        # Assert
        assert result is None  # Should fail validation

    @pytest.mark.asyncio
    async def test_create_chat_message_with_same_sender_receiver(self, firestore, mock_db_collection):
        """Test creating a chat message where sender and receiver are the same."""
        # Arrange
        chat_id = "chat_123"
        message_data = {
            "sender_user_id": "user_alice",
            "receiver_user_id": "user_alice",  # Same as sender
            "message": "Hello!"
        }
        
        # Mock chat document
        mock_chat_doc = Mock()
        mock_chat_doc.exists = True
        mock_chat_doc.to_dict.return_value = {
            "seeker_user_id": "user_alice",
            "provider_user_id": "user_bob"
        }
        mock_chat_doc.id = chat_id
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        
        # Act
        result = await firestore.create_chat_message(chat_id, message_data)
        
        # Assert
        assert result is None  # Should fail validation

    @pytest.mark.asyncio
    async def test_create_chat_message_with_nonexistent_chat(self, firestore, mock_db_collection):
        """Test creating a chat message when chat doesn't exist."""
        # Arrange
        chat_id = "chat_999"
        message_data = {
            "sender_user_id": "user_alice",
            "receiver_user_id": "user_bob",
            "message": "Hello!"
        }
        
        # Mock non-existent chat
        mock_chat_doc = Mock()
        mock_chat_doc.exists = False
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        
        # Act
        result = await firestore.create_chat_message(chat_id, message_data)
        
        # Assert
        assert result is None  # Should fail when chat not found
    @pytest.mark.asyncio
    async def test_update_chat_message_with_valid_participants(self, firestore, mock_db_collection):
        """Test updating a chat message with valid participants."""
        # Arrange
        chat_id = "chat_123"
        message_id = "msg_456"
        update_data = {
            "message": "Updated message"
        }
        
        # Mock chat document
        mock_chat_doc = Mock()
        mock_chat_doc.exists = True
        mock_chat_doc.to_dict.return_value = {
            "seeker_user_id": "user_alice",
            "provider_user_id": "user_bob"
        }
        mock_chat_doc.id = chat_id
        
        # Mock message document
        mock_msg_doc = Mock()
        mock_msg_doc.exists = True
        mock_msg_doc.to_dict.return_value = {
            "sender_user_id": "user_alice",
            "receiver_user_id": "user_bob",
            "message": "Original message"
        }
        
        # Setup mock returns
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_msg_doc
        
        # Act
        result = await firestore.update_chat_message(chat_id, message_id, update_data)
        
        # Assert - should succeed and return the updated message
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_chat_message_changing_to_invalid_sender(self, firestore, mock_db_collection):
        """Test updating a chat message with invalid sender."""
        # Arrange
        chat_id = "chat_123"
        message_id = "msg_456"
        update_data = {
            "sender_user_id": "user_charlie"  # Not a participant
        }
        
        # Mock chat document
        mock_chat_doc = Mock()
        mock_chat_doc.exists = True
        mock_chat_doc.to_dict.return_value = {
            "seeker_user_id": "user_alice",
            "provider_user_id": "user_bob"
        }
        mock_chat_doc.id = chat_id
        
        # Mock message document
        mock_msg_doc = Mock()
        mock_msg_doc.exists = True
        mock_msg_doc.to_dict.return_value = {
            "sender_user_id": "user_alice",
            "receiver_user_id": "user_bob",
            "message": "Original message"
        }
        
        # Setup mock returns
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_msg_doc
        
        # Act
        result = await firestore.update_chat_message(chat_id, message_id, update_data)
        
        # Assert
        assert result is None  # Should fail validation

    @pytest.mark.asyncio
    async def test_update_chat_message_making_sender_equal_receiver(self, firestore, mock_db_collection):
        """Test updating a chat message where sender would equal receiver."""
        # Arrange
        chat_id = "chat_123"
        message_id = "msg_456"
        update_data = {
            "sender_user_id": "user_bob"  # Same as receiver
        }
        
        # Mock chat document
        mock_chat_doc = Mock()
        mock_chat_doc.exists = True
        mock_chat_doc.to_dict.return_value = {
            "seeker_user_id": "user_alice",
            "provider_user_id": "user_bob"
        }
        mock_chat_doc.id = chat_id
        
        # Mock message document
        mock_msg_doc = Mock()
        mock_msg_doc.exists = True
        mock_msg_doc.to_dict.return_value = {
            "sender_user_id": "user_alice",
            "receiver_user_id": "user_bob",
            "message": "Original message"
        }
        
        # Setup mock returns
        mock_db_collection.return_value.document.return_value.get.return_value = mock_chat_doc
        mock_db_collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_msg_doc
        
        # Act
        result = await firestore.update_chat_message(chat_id, message_id, update_data)
        
        # Assert
        assert result is None  # Should fail validation

    @pytest.mark.asyncio
    async def test_create_review_for_completed_service_request(self, firestore, mock_db_collection):
        """Test creating a review for a completed service request."""
        # Arrange
        review_data = {
            "service_request_id": "service_request_123",
            "user_id": "user_bob",
            "reviewer_user_id": "user_alice",
            "feedback_raw": "Great work!",
            "feedback_positive": ["Professional"],
            "feedback_negative": [],
            "rating_reliance": 5.0,
            "rating_quality": 5.0,
            "rating_competence": 5.0,
            "rating_response_speed": 5.0
        }
        
        # Mock review document reference
        mock_review_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_review_ref
        
        # Mock get_service_request to return a completed service request
        with patch.object(firestore, 'get_service_request') as mock_get_request, \
             patch.object(firestore, '_generate_prefixed_id', return_value='review_456'):
            mock_get_request.return_value = {
                "service_request_id": "service_request_123",
                "status": "completed",
                "seeker_user_id": "user_alice",
                "title": "Test Request"
            }
            
            # Act
            result = await firestore.create_review(review_data)
            
            # Assert
            assert result is not None
            assert result['review_id'] == 'review_456'
            mock_review_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_review_for_non_completed_service_request(self, firestore, mock_db_collection):
        """Test creating a review for a non-completed service request should fail."""
        # Arrange
        review_data = {
            "service_request_id": "service_request_123",
            "user_id": "user_bob",
            "reviewer_user_id": "user_alice",
            "feedback_raw": "Great work!",
            "feedback_positive": ["Professional"],
            "feedback_negative": [],
            "rating_reliance": 5.0,
            "rating_quality": 5.0,
            "rating_competence": 5.0,
            "rating_response_speed": 5.0
        }
        
        # Mock get_service_request to return a pending service request
        with patch.object(firestore, 'get_service_request') as mock_get_request:
            mock_get_request.return_value = {
                "service_request_id": "service_request_123",
                "status": "pending",
                "seeker_user_id": "user_alice",
                "title": "Test Request"
            }
            
            # Act
            result = await firestore.create_review(review_data)
            
            # Assert
            assert result is None  # Should fail validation

    @pytest.mark.asyncio
    async def test_create_review_for_nonexistent_service_request(self, firestore, mock_db_collection):
        """Test creating a review for a non-existent service request should fail."""
        # Arrange
        review_data = {
            "service_request_id": "service_request_999",
            "user_id": "user_bob",
            "reviewer_user_id": "user_alice",
            "feedback_raw": "Great work!",
            "feedback_positive": ["Professional"],
            "feedback_negative": [],
            "rating_reliance": 5.0,
            "rating_quality": 5.0,
            "rating_competence": 5.0,
            "rating_response_speed": 5.0
        }
        
        # Mock get_service_request to return None (non-existent)
        with patch.object(firestore, 'get_service_request') as mock_get_request:
            mock_get_request.return_value = None
            
            # Act
            result = await firestore.create_review(review_data)
            
            # Assert
            assert result is None  # Should fail validation
