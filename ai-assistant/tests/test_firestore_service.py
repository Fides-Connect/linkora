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
        with patch.object(firestore, '_generate_prefixed_id', return_value='service_request_123'):
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
            mock_db_collection.return_value.document.assert_called_with(user_id)
            mock_db_collection.return_value.document.return_value.collection.assert_called_with('favorites')
