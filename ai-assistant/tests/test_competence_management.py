"""Unit tests for competence management functions
Tests the add, update, and delete competence functions
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.ai_assistant.hub_spoke_ingestion import HubSpokeIngestion


class TestCompetenceManagement(unittest.TestCase):
    """Test suite for competence management functions."""
    
    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_create_competencies_single_string(self, mock_comp_collection, mock_user_collection):
        """Test creating a single competence as a string."""
        # Mock user query result
        mock_user_obj = Mock()
        mock_user_obj.uuid = "user-uuid-123"
        
        mock_query_result = Mock()
        mock_query_result.objects = [mock_user_obj]
        
        mock_user_collection.return_value.query.fetch_objects.return_value = mock_query_result
        
        # Mock create_competence to return UUID
        with patch.object(HubSpokeIngestion, 'create_competence', return_value='comp-uuid-1'):
            result = HubSpokeIngestion.create_competencies_by_user_id(
                user_id="user123",
                competencies="Expert in Plumbing",
                category="Plumbing"
            )
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['added_uuids']), 1)
        self.assertEqual(result['count'], 1)
    
    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_create_competencies_list(self, mock_comp_collection, mock_user_collection):
        """Test creating multiple competencies as a list."""
        # Mock user query result
        mock_user_obj = Mock()
        mock_user_obj.uuid = "user-uuid-123"
        
        mock_query_result = Mock()
        mock_query_result.objects = [mock_user_obj]
        
        mock_user_collection.return_value.query.fetch_objects.return_value = mock_query_result
        
        # Mock create_competence to return different UUIDs
        with patch.object(HubSpokeIngestion, 'create_competence', side_effect=['comp-uuid-1', 'comp-uuid-2']):
            result = HubSpokeIngestion.create_competencies_by_user_id(
                user_id="user123",
                competencies=["Expert in Plumbing", "Bathroom Renovation Specialist"],
                category="Plumbing"
            )
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['added_uuids']), 2)
        self.assertEqual(result['count'], 2)
    
    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_create_competencies_user_not_found(self, mock_comp_collection, mock_user_collection):
        """Test creating competencies when user doesn't exist."""
        # Mock empty query result
        mock_query_result = Mock()
        mock_query_result.objects = []
        
        mock_user_collection.return_value.query.fetch_objects.return_value = mock_query_result
        
        result = HubSpokeIngestion.create_competencies_by_user_id(
            user_id="nonexistent",
            competencies="Some competence"
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], "User not found")
        self.assertEqual(len(result['added_uuids']), 0)
    
    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_update_competencies_replaces_existing(self, mock_comp_collection, mock_user_collection):
        """Test updating competencies replaces all existing ones."""
        # Mock user query result
        mock_user_obj = Mock()
        mock_user_obj.uuid = "user-uuid-123"
        
        mock_query_result = Mock()
        mock_query_result.objects = [mock_user_obj]
        
        mock_user_collection.return_value.query.fetch_objects.return_value = mock_query_result
        
        # Mock existing competencies
        mock_existing_comp1 = Mock()
        mock_existing_comp1.uuid = "old-comp-1"
        mock_existing_comp2 = Mock()
        mock_existing_comp2.uuid = "old-comp-2"
        
        mock_user_with_refs = Mock()
        mock_user_with_refs.references = {
            'has_competencies': Mock(objects=[mock_existing_comp1, mock_existing_comp2])
        }
        
        mock_user_collection.return_value.query.fetch_object_by_id.return_value = mock_user_with_refs
        
        # Mock create_competence to return new UUIDs
        with patch.object(HubSpokeIngestion, 'create_competence', side_effect=['new-comp-1', 'new-comp-2']):
            result = HubSpokeIngestion.update_competencies_by_user_id(
                user_id="user123",
                competencies=[
                    {"title": "Updated Competence 1"},
                    {"title": "Updated Competence 2"},
                ],
            )
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['updated_uuids']), 2)
        
        # Verify old competencies were deleted
        self.assertEqual(mock_comp_collection.return_value.data.delete_by_id.call_count, 2)
    
    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_delete_competencies_by_pattern(self, mock_comp_collection, mock_user_collection):
        """Test deleting competencies by matching pattern."""
        # Mock user query result
        mock_user_obj = Mock()
        mock_user_obj.uuid = "user-uuid-123"
        
        mock_query_result = Mock()
        mock_query_result.objects = [mock_user_obj]
        
        mock_user_collection.return_value.query.fetch_objects.return_value = mock_query_result
        
        # Mock existing competencies
        mock_comp1 = Mock()
        mock_comp1.uuid = "comp-1"
        mock_comp1.properties = {
            'title': 'Plumbing Expert',
            'description': 'Expert in plumbing and water systems',
            'category': 'Plumbing'
        }
        
        mock_comp2 = Mock()
        mock_comp2.uuid = "comp-2"
        mock_comp2.properties = {
            'title': 'Electrical Work',
            'description': 'Electrical installations',
            'category': 'Electrical'
        }
        
        mock_user_with_refs = Mock()
        mock_user_with_refs.references = {
            'has_competencies': Mock(objects=[mock_comp1, mock_comp2])
        }
        
        mock_user_collection.return_value.query.fetch_object_by_id.return_value = mock_user_with_refs
        
        result = HubSpokeIngestion.delete_competencies_by_user_id(
            user_id="user123",
            competencies="Plumbing"  # Should match only the first competence
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['deleted_uuids']), 1)
        self.assertEqual(result['deleted_uuids'][0], 'comp-1')
    
    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_delete_multiple_competencies(self, mock_comp_collection, mock_user_collection):
        """Test deleting multiple competencies with a list of patterns."""
        # Mock user query result
        mock_user_obj = Mock()
        mock_user_obj.uuid = "user-uuid-123"
        
        mock_query_result = Mock()
        mock_query_result.objects = [mock_user_obj]
        
        mock_user_collection.return_value.query.fetch_objects.return_value = mock_query_result
        
        # Mock existing competencies
        mock_comp1 = Mock()
        mock_comp1.uuid = "comp-1"
        mock_comp1.properties = {
            'title': 'Plumbing Expert',
            'description': 'Expert in plumbing',
            'category': 'Plumbing'
        }
        
        mock_comp2 = Mock()
        mock_comp2.uuid = "comp-2"
        mock_comp2.properties = {
            'title': 'Electrical Work',
            'description': 'Electrical installations',
            'category': 'Electrical'
        }
        
        mock_comp3 = Mock()
        mock_comp3.uuid = "comp-3"
        mock_comp3.properties = {
            'title': 'Carpentry',
            'description': 'Wood working',
            'category': 'Carpentry'
        }
        
        mock_user_with_refs = Mock()
        mock_user_with_refs.references = {
            'has_competencies': Mock(objects=[mock_comp1, mock_comp2, mock_comp3])
        }
        
        mock_user_collection.return_value.query.fetch_object_by_id.return_value = mock_user_with_refs
        
        result = HubSpokeIngestion.delete_competencies_by_user_id(
            user_id="user123",
            competencies=["Plumbing", "Electrical"]  # Should match first two
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['deleted_uuids']), 2)
        self.assertIn('comp-1', result['deleted_uuids'])
        self.assertIn('comp-2', result['deleted_uuids'])


class TestUpsertUserUpdatePath(unittest.TestCase):
    """Verify that upsert_user uses data.update() (PATCH) for existing GP objects.

    data.replace() (PUT) wipes cross-references (owned_by, has_competencies)
    which breaks the is_service_provider filter in hybrid search.  data.update()
    (PATCH) preserves references while refreshing the vectorized properties.
    """

    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_existing_competence_uses_update_not_replace(
        self, mock_comp_collection, mock_user_collection
    ):
        """When Competence already exists, update() must be called (not replace()).

        replace() strips the owned_by reference, making the Competence invisible
        to the is_service_provider filter in hybrid search.
        """
        from weaviate.exceptions import UnexpectedStatusCodeError

        user_coll = mock_user_collection.return_value
        comp_coll = mock_comp_collection.return_value

        # User insert succeeds on first try.
        user_coll.data.insert = Mock(return_value=None)
        user_coll.data.reference_add = Mock()

        # Competence insert raises an error indicating the object already exists.
        # The fallback handler checks for 'already exist'/'422' in the message
        # and must call data.update() (PATCH), not data.replace() (PUT).
        comp_coll.data.insert = Mock(
            side_effect=Exception("422 already exists")
        )
        comp_coll.data.update = Mock(return_value=None)
        comp_coll.data.replace = Mock()  # must NOT be called

        HubSpokeIngestion.upsert_user(
            user_data={
                "uuid": "da1839e1-912e-5d8e-9582-6c3b4a3aa517",
                "name": "CakesBerlin",
                "is_service_provider": True,
                "source": "google_places",
            },
            competence_data={
                "uuid": "023ef526-7040-59bf-a3b2-69dc4c76f6a7",
                "competence_id": "gp:ChIJAQCweNBPqEcRsUWIG5LVwQg",
                "title": "CakesBerlin",
                "description": "Custom wedding cakes in Berlin.",
                "search_optimized_summary": "Berlin bakery specialising in custom wedding cakes.",
                "category": "bakery",
            },
        )

        comp_coll.data.update.assert_called_once()
        comp_coll.data.replace.assert_not_called()

    @patch('src.ai_assistant.hub_spoke_ingestion.get_user_collection')
    @patch('src.ai_assistant.hub_spoke_ingestion.get_competence_collection')
    def test_existing_user_uses_update_not_replace(
        self, mock_comp_collection, mock_user_collection
    ):
        """When User already exists, update() must be called (not replace()).

        replace() strips the has_competencies reference.
        """
        from weaviate.exceptions import UnexpectedStatusCodeError

        user_coll = mock_user_collection.return_value
        comp_coll = mock_comp_collection.return_value

        # User insert raises an error indicating the object already exists.
        user_coll.data.insert = Mock(
            side_effect=Exception("422 already exists")
        )
        user_coll.data.update = Mock(return_value=None)
        user_coll.data.replace = Mock()  # must NOT be called

        # Competence insert succeeds.
        comp_coll.data.insert = Mock(return_value=None)
        user_coll.data.reference_add = Mock()

        HubSpokeIngestion.upsert_user(
            user_data={
                "uuid": "da1839e1-912e-5d8e-9582-6c3b4a3aa517",
                "name": "CakesBerlin",
                "is_service_provider": True,
                "source": "google_places",
            },
            competence_data={
                "uuid": "023ef526-7040-59bf-a3b2-69dc4c76f6a7",
                "competence_id": "gp:ChIJAQCweNBPqEcRsUWIG5LVwQg",
                "title": "CakesBerlin",
                "description": "Custom wedding cakes in Berlin.",
                "search_optimized_summary": "Berlin bakery specialising in custom wedding cakes.",
                "category": "bakery",
            },
        )

        user_coll.data.update.assert_called_once()
        user_coll.data.replace.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
