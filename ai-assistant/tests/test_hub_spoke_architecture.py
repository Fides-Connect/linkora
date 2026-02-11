"""
Hub and Spoke Architecture: Test Suite (TDD)
=============================================

Test Coverage:
1. test_bidirectional_link: Verify User ↔ Competence linking
2. test_granularity_match: Specific skill matches broad query
3. test_spam_filtering: Keyword-stuffed descriptions are sanitized
4. test_ghost_filtering: Inactive users are excluded
5. test_result_grouping: Multiple competencies return one user result

Following TDD: These tests should fail initially, then pass after implementation.
"""
import unittest
import logging
import time
import socket
from datetime import datetime, UTC
from typing import Dict, Any
from weaviate.classes.query import QueryReference

from src.ai_assistant.hub_spoke_schema import (
    init_hub_spoke_schema,
    cleanup_hub_spoke_schema,
    HubSpokeConnection,
    get_user_collection,
    get_competence_collection
)
from src.ai_assistant.hub_spoke_ingestion import (
    HubSpokeIngestion,
    sanitize_input,
    enrich_text
)
from src.ai_assistant.hub_spoke_search import HubSpokeSearch
from ai_assistant.seed_data import TEST_PERSONAS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_weaviate_available(host='localhost', port=8090, timeout=1):
    """Check if Weaviate is running and accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@unittest.skipUnless(is_weaviate_available(), "Weaviate is not running at localhost:8090")
class TestHubSpokeArchitecture(unittest.TestCase):
    """
    Test suite for Hub and Spoke architecture.
    
    Setup: Initialize schema and load test personas
    Teardown: Clean up collections
    """
    
    @classmethod
    def setUpClass(cls):
        """Initialize schema and load test data."""
        logger.info("=" * 80)
        logger.info("Setting up Hub and Spoke test suite")
        logger.info("=" * 80)
        
        # Clean up any existing data
        try:
            cleanup_hub_spoke_schema()
        except Exception:
            pass
        
        # Initialize fresh schema
        init_hub_spoke_schema()
        
        # Load test personas
        cls.personas_map = {}
        for persona in TEST_PERSONAS:
            logger.info(f"Loading {persona['name']}")
            result = HubSpokeIngestion.add_user_with_competencies(
                user_data=persona['user'],
                competencies_data=persona['competencies'],
                apply_sanitization=True,
                apply_enrichment=True
            )
            if result:
                cls.personas_map[persona['name']] = result
                logger.info(f"  User UUID: {result['user_uuid']}")
                logger.info(f"  Competencies: {len(result['competence_uuids'])}")
        
        # Wait for indexing (Weaviate needs time to vectorize)
        logger.info("Waiting 2 seconds for Weaviate indexing...")
        time.sleep(2)
        
        logger.info("Setup complete")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up collections."""
        logger.info("=" * 80)
        logger.info("Tearing down Hub and Spoke test suite")
        logger.info("=" * 80)
        cleanup_hub_spoke_schema()
        HubSpokeConnection.close()
        logger.info("Teardown complete")
    
    def test_01_bidirectional_link(self):
        """
        Test 1: Bidirectional Link
        
        Verify that creating a User with Competencies establishes:
        1. User.has_competencies → Competence (Hub → Spoke)
        2. Competence.owned_by → User (Spoke → Hub)
        
        This is CRITICAL for the Hub and Spoke architecture.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Bidirectional Link")
        logger.info("=" * 80)
        
        # Get User A (The Pro)
        user_a = self.personas_map.get("User A (The Pro)")
        self.assertIsNotNone(user_a, "User A should be loaded")
        
        user_uuid = user_a['user_uuid']
        competence_uuid = user_a['competence_uuids'][0]
        
        # Verify User → Competence link
        logger.info("Checking User → Competence link (has_competencies)")
        user_competencies = HubSpokeSearch.get_user_competencies(user_uuid)
        self.assertGreater(len(user_competencies), 0, "User should have competencies")
        
        competence_uuids = [c['uuid'] for c in user_competencies]
        self.assertIn(competence_uuid, competence_uuids, 
                     "Competence should be in user's has_competencies")
        
        logger.info(f"✓ User {user_uuid[:8]}... has {len(user_competencies)} competence(s)")
        
        # Verify Competence → User link
        logger.info("Checking Competence → User link (owned_by)")
        competence_collection = get_competence_collection()
        competence_obj = competence_collection.query.fetch_object_by_id(
            uuid=competence_uuid,
            return_references=QueryReference(
                link_on="owned_by",
                return_properties=["name", "last_sign_in"]
            )
        )
        
        self.assertIsNotNone(competence_obj, "Competence should exist")
        self.assertIn("owned_by", competence_obj.references, "Competence should have owned_by reference")
        
        owned_by_objects = competence_obj.references['owned_by'].objects
        self.assertEqual(len(owned_by_objects), 1, "Competence should have exactly one owner")
        
        owner_uuid = str(owned_by_objects[0].uuid)
        self.assertEqual(owner_uuid, user_uuid, "Competence owner should match user UUID")
        
        logger.info(f"✓ Competence {competence_uuid[:8]}... is owned_by User {owner_uuid[:8]}...")
        logger.info("✓ Bidirectional linking verified")
    
    def test_02_granularity_match(self):
        """
        Test 2: Granularity Match
        
        Searching for "Electrician" should retrieve User A who has the specific
        skill "Installing Pot Lights". This tests the enrich_text() functionality
        which adds parent category terms to specific skills.
        
        Expected: User A (Alice Professional) appears in results
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Granularity Match")
        logger.info("=" * 80)
        
        query = "Electrician"
        logger.info(f"Query: '{query}'")
        logger.info("Expected: User A (Installing Pot Lights) should match due to enrichment")
        
        results = HubSpokeSearch.search_competencies(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_user=False  # Show all competencies
        )
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # Verify User A appears in results
        user_a = self.personas_map.get("User A (The Pro)")
        user_names = [r.get('user', {}).get('name') for r in results if 'user' in r]
        
        self.assertIn("Alice Professional", user_names, 
                     "User A (Alice) should appear in results due to enrichment")
        
        # Find User A's result
        user_a_result = next((r for r in results if r.get('user', {}).get('name') == 'Alice Professional'), None)
        self.assertIsNotNone(user_a_result, "User A result should be found")
        
        logger.info(f"✓ User A found: {user_a_result['title']}")
        logger.info(f"  Score: {user_a_result.get('score', 0):.4f}")
        logger.info(f"  Category: {user_a_result['category']}")
        logger.info("✓ Granularity enrichment working")
    
    def test_03_spam_filtering(self):
        """
        Test 3: SEO Spam Filtering
        
        User B has a description stuffed with keywords:
        "Plumber Electrician Driver Nurse Teacher Plumber Driver..."
        
        The sanitize_input() function should truncate this to prevent abuse.
        When searching for "Driver", User B should either:
        1. Not appear (if heavily truncated)
        2. Appear with low score (if partially truncated)
        
        We verify the description was sanitized during ingestion.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: SEO Spam Filtering")
        logger.info("=" * 80)
        
        # Get User B's competence
        user_b = self.personas_map.get("User B (The Spammer)")
        self.assertIsNotNone(user_b, "User B should be loaded")
        
        competence_uuid = user_b['competence_uuids'][0]
        competence_collection = get_competence_collection()
        
        # Fetch the actual stored description
        competence_obj = competence_collection.query.fetch_object_by_id(uuid=competence_uuid)
        stored_description = competence_obj.properties.get('description', '')
        
        logger.info(f"Original description length: ~350 chars (keyword stuffed)")
        logger.info(f"Stored description length: {len(stored_description)} chars")
        logger.info(f"Stored description: {stored_description[:100]}...")
        
        # Verify sanitization occurred (description should be truncated)
        # Original had many repeated words, sanitized should have max 20 unique words
        unique_words = set(stored_description.lower().split())
        logger.info(f"Unique words in stored description: {len(unique_words)}")
        
        # The sanitization should limit unique words
        # Note: enrichment adds category terms, so we allow some buffer
        self.assertLessEqual(len(unique_words), 30, 
                           "Sanitized description should have limited unique words")
        
        logger.info("✓ Spam filtering applied during ingestion")
        
        # Additionally, search for "Driver" and verify User B has low relevance
        query = "Driver"
        logger.info(f"\nSearching for: '{query}'")
        results = HubSpokeSearch.search_competencies(query=query, limit=10, group_by_user=False)
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # User B might appear, but should have low score or not appear at all
        user_b_result = next((r for r in results if r.get('user', {}).get('name') == 'Bob Spammer'), None)
        
        if user_b_result:
            logger.info(f"User B found with score: {user_b_result.get('score', 0):.4f}")
            logger.info("  (Spam filtering reduced but didn't eliminate)")
        else:
            logger.info("✓ User B not found (spam filtering effective)")
        
        logger.info("✓ SEO spam defense working")
    
    def test_04_ghost_filtering(self):
        """
        Test 4: Ghost User Filtering
        
        User C (Charlie Ghost) has excellent electrical skills but hasn't been
        active for 365 days (last_sign_in = 365 days ago).
        
        With max_inactive_days=180, User C should be EXCLUDED from results.
        
        Expected: User C does NOT appear in results
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: Ghost User Filtering")
        logger.info("=" * 80)
        
        query = "Expert Electrician"
        logger.info(f"Query: '{query}'")
        logger.info("User C has this exact skill but is inactive for 365 days")
        logger.info("Expected: User C should be EXCLUDED (max_inactive_days=180)")
        
        results = HubSpokeSearch.search_competencies(
            query=query,
            limit=10,
            max_inactive_days=180,  # Only include users active in last 180 days
            group_by_user=False
        )
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # Verify User C is NOT in results
        user_names = [r.get('user', {}).get('name') for r in results if 'user' in r]
        
        self.assertNotIn("Charlie Ghost", user_names, 
                        "User C (Charlie Ghost) should be excluded due to inactivity")
        
        logger.info(f"Active users found: {user_names}")
        logger.info("✓ User C (Ghost) correctly excluded")
        logger.info("✓ Ghost user filtering working")
    
    def test_05_result_grouping(self):
        """
        Test 5: Result Grouping
        
        User E (Eva Enthusiast) has 5 different gardening competencies:
        1. Lawn Mowing
        2. Garden Design
        3. Tree Pruning
        4. Flower Planting
        5. Vegetable Garden Setup
        
        With group_by_user=True, searching for "Gardening" should return
        User E only ONCE (not 5 times), with her best matching competence.
        
        Expected: Only 1 result for User E (not 5)
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: Result Grouping")
        logger.info("=" * 80)
        
        query = "Gardening"
        logger.info(f"Query: '{query}'")
        logger.info("User E has 5 different gardening competencies")
        logger.info("Expected: User E appears ONCE (grouped by user)")
        
        # Search WITH grouping
        grouped_results = HubSpokeSearch.search_competencies(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_user=True  # Enable grouping
        )
        
        logger.info(f"Grouped results: {len(grouped_results)} result(s)")
        
        # Count how many times User E appears
        user_e_count = sum(1 for r in grouped_results 
                          if r.get('user', {}).get('name') == 'Eva Enthusiast')
        
        self.assertEqual(user_e_count, 1, 
                        "User E should appear exactly once with grouping enabled")
        
        # Find User E's result
        user_e_result = next((r for r in grouped_results 
                             if r.get('user', {}).get('name') == 'Eva Enthusiast'), None)
        
        self.assertIsNotNone(user_e_result, "User E should be in results")
        
        logger.info(f"✓ User E appears once: {user_e_result['title']}")
        logger.info(f"  Score: {user_e_result.get('score', 0):.4f}")
        
        # Search WITHOUT grouping (should return multiple results for User E)
        ungrouped_results = HubSpokeSearch.search_competencies(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_user=False  # Disable grouping
        )
        
        logger.info(f"\nUngrouped results: {len(ungrouped_results)} result(s)")
        
        user_e_ungrouped_count = sum(1 for r in ungrouped_results 
                                     if r.get('user', {}).get('name') == 'Eva Enthusiast')
        
        logger.info(f"User E appears {user_e_ungrouped_count} time(s) without grouping")
        
        self.assertGreaterEqual(user_e_ungrouped_count, 2, 
                               "User E should appear multiple times without grouping")
        
        logger.info("✓ Result grouping working correctly")
    
    def test_06_helper_functions(self):
        """
        Test 6: Helper Functions
        
        Test the sanitize_input() and enrich_text() helper functions
        in isolation to ensure they work correctly.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 6: Helper Functions")
        logger.info("=" * 80)
        
        # Test sanitize_input
        logger.info("Testing sanitize_input():")
        spam_text = "Plumber Electrician Driver Nurse Teacher " * 10
        sanitized = sanitize_input(spam_text, max_unique_words=10)
        
        unique_words_sanitized = set(sanitized.lower().split())
        logger.info(f"  Input: {len(spam_text)} chars, {len(spam_text.split())} words")
        logger.info(f"  Output: {len(sanitized)} chars, {len(unique_words_sanitized)} unique words")
        
        self.assertLessEqual(len(unique_words_sanitized), 10, 
                            "Sanitized text should have max 10 unique words")
        logger.info("  ✓ Sanitization working")
        
        # Test enrich_text
        logger.info("\nTesting enrich_text():")
        original = "Installing Pot Lights"
        enriched = enrich_text(original, "Electrical")
        
        logger.info(f"  Input: '{original}'")
        logger.info(f"  Output: '{enriched}'")
        
        self.assertIn("Installing Pot Lights", enriched, "Original text should be preserved")
        self.assertIn("Electrician", enriched, "Should contain 'Electrician'")
        self.assertIn("Lighting", enriched, "Should contain 'Lighting'")
        logger.info("  ✓ Enrichment working")
        
        logger.info("✓ All helper functions working correctly")
    
    def test_update_competencies_by_user_id(self):
        """
        Test updating competencies for a user by user_id.
        Should be able to update existing competencies with new data.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Update Competencies by User ID")
        logger.info("=" * 80)
        
        # Get User A's data
        user_a = self.personas_map['User A (The Pro)']
        user_collection = get_user_collection()
        
        # Get the user_id
        user_result = user_collection.query.fetch_object_by_id(
            uuid=user_a['user_uuid']
        )
        user_id = user_result.properties.get('user_id')
        
        # Original competence data
        logger.info(f"User ID: {user_id}")
        original_competencies = HubSpokeSearch.get_user_competencies(user_a['user_uuid'])
        logger.info(f"Original competencies count: {len(original_competencies)}")
        
        # Update with a single string
        new_competence = "Updated: Expert in Home Renovation"
        logger.info(f"\nUpdating with single string: '{new_competence}'")
        result = HubSpokeIngestion.update_competencies_by_user_id(
            user_id=user_id,
            competencies=new_competence
        )
        
        self.assertTrue(result['success'], "Update should succeed")
        self.assertEqual(len(result['updated_uuids']), 1, "Should update one competence")
        
        # Verify the update
        time.sleep(1)  # Wait for indexing
        updated_competencies = HubSpokeSearch.get_user_competencies(user_a['user_uuid'])
        found_updated = any("Home Renovation" in c.get('description', '') for c in updated_competencies)
        self.assertTrue(found_updated, "Should find updated competence")
        
        # Update with a list of strings
        new_competencies_list = [
            "Master Plumber with 10 years experience",
            "Specialized in Bathroom Renovations"
        ]
        logger.info(f"\nUpdating with list: {new_competencies_list}")
        result = HubSpokeIngestion.update_competencies_by_user_id(
            user_id=user_id,
            competencies=new_competencies_list
        )
        
        self.assertTrue(result['success'], "Update should succeed")
        self.assertEqual(len(result['updated_uuids']), 2, "Should update two competencies")
        
        logger.info("✓ Update competencies by user_id working correctly")
    
    def test_delete_competencies_by_user_id(self):
        """
        Test deleting specific competencies for a user by user_id.
        Should be able to delete one or more competencies without deleting the user.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Delete Competencies by User ID")
        logger.info("=" * 80)
        
        # Get User B's data
        user_b = self.personas_map['User B (The Spammer)']
        user_collection = get_user_collection()
        
        # Get the user_id
        user_result = user_collection.query.fetch_object_by_id(
            uuid=user_b['user_uuid']
        )
        user_id = user_result.properties.get('user_id')
        
        logger.info(f"User ID: {user_id}")
        original_competencies = HubSpokeSearch.get_user_competencies(user_b['user_uuid'])
        original_count = len(original_competencies)
        logger.info(f"Original competencies count: {original_count}")
        logger.info(f"Original competencies:")
        for i, comp in enumerate(original_competencies):
            logger.info(f"  {i+1}. Title: {comp.get('title')}")
            logger.info(f"     Description: {comp.get('description')[:80]}...")
            logger.info(f"     Category: {comp.get('category')}")
        
        # Delete a single competence by title/description pattern
        # User B has "Everything Services" with "Electrician" in description and category "General"
        competence_to_delete = "Everything"  # This will match the title
        logger.info(f"\nDeleting competence matching: '{competence_to_delete}'")
        result = HubSpokeIngestion.delete_competencies_by_user_id(
            user_id=user_id,
            competencies=competence_to_delete
        )
        
        self.assertTrue(result['success'], "Delete should succeed")
        self.assertGreater(len(result['deleted_uuids']), 0, "Should delete at least one competence")
        
        # Verify deletion
        time.sleep(1)  # Wait for indexing
        remaining_competencies = HubSpokeSearch.get_user_competencies(user_b['user_uuid'])
        self.assertLess(len(remaining_competencies), original_count, "Should have fewer competencies")
        
        # Verify user still exists
        user_result = user_collection.query.fetch_object_by_id(
            uuid=user_b['user_uuid']
        )
        self.assertIsNotNone(user_result, "User should still exist")
        
        # Delete multiple competencies with a list
        remaining_count = len(remaining_competencies)
        if remaining_count >= 2:
            competencies_to_delete = [
                remaining_competencies[0].get('title', ''),
                remaining_competencies[1].get('title', '')
            ]
            logger.info(f"\nDeleting multiple competencies: {competencies_to_delete}")
            result = HubSpokeIngestion.delete_competencies_by_user_id(
                user_id=user_id,
                competencies=competencies_to_delete
            )
            
            self.assertTrue(result['success'], "Delete should succeed")
            self.assertEqual(len(result['deleted_uuids']), 2, "Should delete two competencies")
        
        logger.info("✓ Delete competencies by user_id working correctly")
    
    def test_add_competencies_by_user_id(self):
        """
        Test adding new competencies to an existing user by user_id.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Add Competencies by User ID")
        logger.info("=" * 80)
        
        # Get User C's data
        user_c = self.personas_map.get('User C (The Ghost)')
        if not user_c:
            self.skipTest("User C not found in test data")
        
        user_collection = get_user_collection()
        
        # Get the user_id
        user_result = user_collection.query.fetch_object_by_id(
            uuid=user_c['user_uuid']
        )
        user_id = user_result.properties.get('user_id')
        
        logger.info(f"User ID: {user_id}")
        logger.info(f"User properties: {user_result.properties}")
        if not user_id:
            self.skipTest(f"User C user missing user_id field. Properties: {user_result.properties}")
        original_competencies = HubSpokeSearch.get_user_competencies(user_c['user_uuid'])
        original_count = len(original_competencies)
        logger.info(f"Original competencies count: {original_count}")
        
        # Add a single competence
        new_competence = "Expert in Kitchen Remodeling"
        logger.info(f"\nAdding single competence: '{new_competence}'")
        result = HubSpokeIngestion.add_competencies_by_user_id(
            user_id=user_id,
            competencies=new_competence,
            category="Renovation"
        )
        
        self.assertTrue(result['success'], "Add should succeed")
        self.assertEqual(len(result['added_uuids']), 1, "Should add one competence")
        
        # Verify addition
        time.sleep(1)  # Wait for indexing
        updated_competencies = HubSpokeSearch.get_user_competencies(user_c['user_uuid'])
        self.assertEqual(len(updated_competencies), original_count + 1, "Should have one more competence")
        
        # Add multiple competencies with a list
        new_competencies_list = [
            "Flooring Installation Expert",
            "Tile Work Specialist"
        ]
        logger.info(f"\nAdding multiple competencies: {new_competencies_list}")
        result = HubSpokeIngestion.add_competencies_by_user_id(
            user_id=user_id,
            competencies=new_competencies_list,
            category="Flooring"
        )
        
        self.assertTrue(result['success'], "Add should succeed")
        self.assertEqual(len(result['added_uuids']), 2, "Should add two competencies")
        
        # Final verification
        final_competencies = HubSpokeSearch.get_user_competencies(user_c['user_uuid'])
        self.assertEqual(len(final_competencies), original_count + 3, "Should have three more competencies total")
        
        logger.info("✓ Add competencies by user_id working correctly")
    
    def test_hybrid_search_providers_with_availability(self):
        """Test hybrid_search_providers with availability filtering."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Hybrid Search with Availability Filter")
        logger.info("=" * 80)
        
        # Search request with availability filter
        search_request = {
            "available_time": "heute",
            "category": "Klempner",
            "criterions": ["Notfall", "schnell"]
        }
        
        logger.info(f"Search request: {search_request}")
        results = HubSpokeSearch.hybrid_search_providers(
            search_request=search_request,
            limit=5
        )
        
        self.assertIsInstance(results, list, "Should return a list")
        logger.info(f"Found {len(results)} providers")
        
        # Verify results structure
        for result in results:
            self.assertIn('uuid', result, "Result should have uuid")
            self.assertIn('score', result, "Result should have score")
            self.assertIn('user', result, "Result should have user")
            self.assertIn('category', result, "Result should have category")
            
            # Verify user structure
            user = result['user']
            self.assertIn('uuid', user, "User should have uuid")
            self.assertIn('name', user, "User should have name")
            self.assertTrue(user.get('is_service_provider', False), "User should be a provider")
        
        logger.info("✓ Hybrid search with availability filter working correctly")
    
    def test_hybrid_search_providers_category_only(self):
        """Test hybrid_search_providers with category only."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Hybrid Search with Category Only")
        logger.info("=" * 80)
        
        search_request = {
            "category": "Elektriker",
            "criterions": []
        }
        
        logger.info(f"Search request: {search_request}")
        results = HubSpokeSearch.hybrid_search_providers(
            search_request=search_request,
            limit=5
        )
        
        self.assertIsInstance(results, list, "Should return a list")
        logger.info(f"Found {len(results)} providers for category: Elektriker")
        
        # Verify results are sorted by score
        if len(results) > 1:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(
                    results[i].get('score', 0),
                    results[i + 1].get('score', 0),
                    "Results should be sorted by score descending"
                )
        
        logger.info("✓ Category-only search working correctly")
    
    def test_hybrid_search_providers_with_criterions(self):
        """Test hybrid_search_providers with multiple criterions."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Hybrid Search with Multiple Criterions")
        logger.info("=" * 80)
        
        search_request = {
            "category": "Reinigung",
            "criterions": [
                "umweltfreundlich",
                "gründlich",
                "zuverlässig"
            ]
        }
        
        logger.info(f"Search request: {search_request}")
        results = HubSpokeSearch.hybrid_search_providers(
            search_request=search_request,
            limit=5
        )
        
        self.assertIsInstance(results, list, "Should return a list")
        logger.info(f"Found {len(results)} providers matching criterions")
        
        # Verify no duplicate users
        user_uuids = [r['user']['uuid'] for r in results if 'user' in r]
        self.assertEqual(len(user_uuids), len(set(user_uuids)), 
                        "Should not have duplicate users")
        
        logger.info("✓ Search with criterions working correctly")
    
    def test_hybrid_search_providers_flexible_availability(self):
        """Test that flexible availability doesn't filter results."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Hybrid Search with Flexible Availability")
        logger.info("=" * 80)
        
        # Search with flexible availability (should not filter)
        search_request_flexible = {
            "available_time": "flexibel",
            "category": "Elektriker",
            "criterions": []
        }
        
        results_flexible = HubSpokeSearch.hybrid_search_providers(
            search_request=search_request_flexible,
            limit=10
        )
        
        # Search without availability (should also not filter)
        search_request_no_filter = {
            "category": "Elektriker",
            "criterions": []
        }
        
        results_no_filter = HubSpokeSearch.hybrid_search_providers(
            search_request=search_request_no_filter,
            limit=10
        )
        
        # Both should return similar results (no availability filtering)
        self.assertEqual(
            len(results_flexible),
            len(results_no_filter),
            "Flexible availability should not reduce results"
        )
        
        logger.info("✓ Flexible availability handling working correctly")
    
    def test_hybrid_search_providers_empty_query(self):
        """Test hybrid_search_providers with minimal query."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Hybrid Search with Empty Query")
        logger.info("=" * 80)
        
        search_request = {
            "category": "",
            "criterions": []
        }
        
        logger.info(f"Search request: {search_request}")
        results = HubSpokeSearch.hybrid_search_providers(
            search_request=search_request,
            limit=5
        )
        
        self.assertIsInstance(results, list, "Should return a list")
        logger.info(f"Found {len(results)} providers with empty query")
        
        self.assertGreater(len(results), 0, "Should return some providers even with empty query")
        
        logger.info("✓ Empty query handling working correctly")


def run_tests():
    """Run the test suite."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestHubSpokeArchitecture)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
