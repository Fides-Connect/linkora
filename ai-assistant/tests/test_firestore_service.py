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
            req_id = await firestore.create_service_request(request_data)

            # Assert
            assert req_id == 'service_request_123'
            
            # Verify collection was accessed
            mock_db_collection.assert_called_with('service_requests')
            
            # Verify data was set
            mock_doc_ref.set.assert_called_once()
            call_args = mock_doc_ref.set.call_args[0][0]
            assert call_args['service_request_id'] == 'service_request_123'
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
            assert requests[0]['id'] == 'req1'
            assert requests[1]['id'] == 'req2'
            
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
        
        # Act
        success = await firestore.update_service_request_status(request_id, status)
        
        # Assert
        assert success is True
        mock_db_collection.assert_called_with('service_requests')
        mock_db_collection.return_value.document.assert_called_with(request_id)
        
        mock_doc_ref.update.assert_called_once()
        update_args = mock_doc_ref.update.call_args[0][0]
        assert update_args['status'] == status
        assert 'updated_at' in update_args

    @pytest.mark.asyncio
    async def test_add_favorite(self, firestore, mock_db_collection):
        """Test adding a favorite."""
        # Arrange
        user_id = "user1"
        fav_id = "user2"
        
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        # Mock ArrayUnion (it's imported inside the service usually, or we mock the lib)
        # In the service: firestore.ArrayUnion
        # We need to patch firebase_admin.firestore.ArrayUnion
        with patch('firebase_admin.firestore.ArrayUnion') as mock_array_union:
            # Act
            success = await firestore.add_favorite(user_id, fav_id)
            
            # Assert
            assert success is True
            mock_doc_ref.update.assert_called_once()
            mock_array_union.assert_called_with([fav_id])

    @pytest.mark.asyncio
    async def test_remove_favorite(self, firestore, mock_db_collection):
        """Test removing a favorite."""
        # Arrange
        user_id = "user1"
        fav_id = "user2"
        
        mock_doc_ref = Mock()
        mock_db_collection.return_value.document.return_value = mock_doc_ref
        
        with patch('firebase_admin.firestore.ArrayRemove') as mock_array_remove:
            # Act
            success = await firestore.remove_favorite(user_id, fav_id)
            
            # Assert
            assert success is True
            mock_doc_ref.update.assert_called_once()
            mock_array_remove.assert_called_with([fav_id])
    
    @pytest.mark.asyncio
    async def test_get_favorites(self, firestore, mock_db_collection):
        """Test getting favorites with full user details."""
        # Arrange
        user_id = "user1"
        mock_user_doc = Mock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {"favorites": ["fav1", "fav2"]}
        
        mock_db_collection.return_value.document.return_value.get.return_value = mock_user_doc
        
        # Mock get_user to return details for favorites
        with patch.object(firestore, 'get_user') as mock_get_user:
            mock_get_user.side_effect = lambda uid: {
                "user_id": uid,
                "name": f"User {uid}",
                "competencies": []
            } if uid in ["fav1", "fav2"] else None
            
            # Act
            favorites = await firestore.get_favorites(user_id)
            
            # Assert
            assert len(favorites) == 2
            assert favorites[0]['user_id'] == 'fav1'
            assert favorites[0]['name'] == 'User fav1'
            assert favorites[1]['user_id'] == 'fav2'
