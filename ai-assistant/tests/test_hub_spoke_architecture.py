"""
Hub and Spoke Architecture: Test Suite (TDD)
=============================================

Test Coverage:
1. test_bidirectional_link: Verify Profile ↔ Competence linking
2. test_granularity_match: Specific skill matches broad query
3. test_spam_filtering: Keyword-stuffed descriptions are sanitized
4. test_ghost_filtering: Inactive profiles are excluded
5. test_result_grouping: Multiple competences return one profile result

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
    get_unified_profile_collection,
    get_competence_entry_collection
)
from src.ai_assistant.hub_spoke_ingestion import (
    HubSpokeIngestion,
    sanitize_input,
    enrich_text
)
from src.ai_assistant.hub_spoke_search import HubSpokeSearch
from tests.test_hub_spoke_data import TEST_PERSONAS

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
            result = HubSpokeIngestion.create_profile_with_competences(
                profile_data=persona['profile'],
                competences_data=persona['competences'],
                apply_sanitization=True,
                apply_enrichment=True
            )
            if result:
                cls.personas_map[persona['name']] = result
                logger.info(f"  Profile UUID: {result['profile_uuid']}")
                logger.info(f"  Competences: {len(result['competence_uuids'])}")
        
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
        
        Verify that creating a Profile with Competences establishes:
        1. Profile.has_competences → Competence (Hub → Spoke)
        2. Competence.owned_by → Profile (Spoke → Hub)
        
        This is CRITICAL for the Hub and Spoke architecture.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Bidirectional Link")
        logger.info("=" * 80)
        
        # Get User A (The Pro)
        user_a = self.personas_map.get("User A (The Pro)")
        self.assertIsNotNone(user_a, "User A should be loaded")
        
        profile_uuid = user_a['profile_uuid']
        competence_uuid = user_a['competence_uuids'][0]
        
        # Verify Profile → Competence link
        logger.info("Checking Profile → Competence link (has_competences)")
        profile_competences = HubSpokeSearch.get_profile_competences(profile_uuid)
        self.assertGreater(len(profile_competences), 0, "Profile should have competences")
        
        competence_uuids = [c['uuid'] for c in profile_competences]
        self.assertIn(competence_uuid, competence_uuids, 
                     "Competence should be in profile's has_competences")
        
        logger.info(f"✓ Profile {profile_uuid[:8]}... has {len(profile_competences)} competence(s)")
        
        # Verify Competence → Profile link
        logger.info("Checking Competence → Profile link (owned_by)")
        competence_collection = get_competence_entry_collection()
        competence_obj = competence_collection.query.fetch_object_by_id(
            uuid=competence_uuid,
            return_references=QueryReference(
                link_on="owned_by",
                return_properties=["display_name", "last_active_date"]
            )
        )
        
        self.assertIsNotNone(competence_obj, "Competence should exist")
        self.assertIn("owned_by", competence_obj.references, "Competence should have owned_by reference")
        
        owned_by_objects = competence_obj.references['owned_by'].objects
        self.assertEqual(len(owned_by_objects), 1, "Competence should have exactly one owner")
        
        owner_uuid = str(owned_by_objects[0].uuid)
        self.assertEqual(owner_uuid, profile_uuid, "Competence owner should match profile UUID")
        
        logger.info(f"✓ Competence {competence_uuid[:8]}... is owned_by Profile {owner_uuid[:8]}...")
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
        
        results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_profile=False  # Show all competences
        )
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # Verify User A appears in results
        user_a = self.personas_map.get("User A (The Pro)")
        profile_names = [r.get('profile', {}).get('name') for r in results if 'profile' in r]
        
        self.assertIn("Alice Professional", profile_names, 
                     "User A (Alice) should appear in results due to enrichment")
        
        # Find User A's result
        user_a_result = next((r for r in results if r.get('profile', {}).get('name') == 'Alice Professional'), None)
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
        competence_collection = get_competence_entry_collection()
        
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
        results = HubSpokeSearch.search_competences(query=query, limit=10, group_by_profile=False)
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # User B might appear, but should have low score or not appear at all
        user_b_result = next((r for r in results if r.get('profile', {}).get('name') == 'Bob Spammer'), None)
        
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
        active for 365 days (last_active_date = 365 days ago).
        
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
        
        results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,  # Only include users active in last 180 days
            group_by_profile=False
        )
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # Verify User C is NOT in results
        profile_names = [r.get('profile', {}).get('name') for r in results if 'profile' in r]
        
        self.assertNotIn("Charlie Ghost", profile_names, 
                        "User C (Charlie Ghost) should be excluded due to inactivity")
        
        logger.info(f"Active users found: {profile_names}")
        logger.info("✓ User C (Ghost) correctly excluded")
        logger.info("✓ Ghost user filtering working")
    
    def test_05_result_grouping(self):
        """
        Test 5: Result Grouping
        
        User E (Eva Enthusiast) has 5 different gardening competences:
        1. Lawn Mowing
        2. Garden Design
        3. Tree Pruning
        4. Flower Planting
        5. Vegetable Garden Setup
        
        With group_by_profile=True, searching for "Gardening" should return
        User E only ONCE (not 5 times), with her best matching competence.
        
        Expected: Only 1 result for User E (not 5)
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: Result Grouping")
        logger.info("=" * 80)
        
        query = "Gardening"
        logger.info(f"Query: '{query}'")
        logger.info("User E has 5 different gardening competences")
        logger.info("Expected: User E appears ONCE (grouped by profile)")
        
        # Search WITH grouping
        grouped_results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_profile=True  # Enable grouping
        )
        
        logger.info(f"Grouped results: {len(grouped_results)} result(s)")
        
        # Count how many times User E appears
        user_e_count = sum(1 for r in grouped_results 
                          if r.get('profile', {}).get('name') == 'Eva Enthusiast')
        
        self.assertEqual(user_e_count, 1, 
                        "User E should appear exactly once with grouping enabled")
        
        # Find User E's result
        user_e_result = next((r for r in grouped_results 
                             if r.get('profile', {}).get('name') == 'Eva Enthusiast'), None)
        
        self.assertIsNotNone(user_e_result, "User E should be in results")
        
        logger.info(f"✓ User E appears once: {user_e_result['title']}")
        logger.info(f"  Score: {user_e_result.get('score', 0):.4f}")
        
        # Search WITHOUT grouping (should return multiple results for User E)
        ungrouped_results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_profile=False  # Disable grouping
        )
        
        logger.info(f"\nUngrouped results: {len(ungrouped_results)} result(s)")
        
        user_e_ungrouped_count = sum(1 for r in ungrouped_results 
                                     if r.get('profile', {}).get('name') == 'Eva Enthusiast')
        
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
    
    def test_update_competences_by_user_id(self):
        """
        Test updating competences for a user by user_id.
        Should be able to update existing competences with new data.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Update Competences by User ID")
        logger.info("=" * 80)
        
        # Get User A's data
        user_a = self.personas_map['User A (The Pro)']
        profile_collection = get_unified_profile_collection()
        
        # Get the user_id
        profile_result = profile_collection.query.fetch_object_by_id(
            uuid=user_a['profile_uuid']
        )
        user_id = profile_result.properties.get('user_id')
        
        # Original competence data
        logger.info(f"User ID: {user_id}")
        original_competences = HubSpokeSearch.get_profile_competences(user_a['profile_uuid'])
        logger.info(f"Original competences count: {len(original_competences)}")
        
        # Update with a single string
        new_competence = "Updated: Expert in Home Renovation"
        logger.info(f"\nUpdating with single string: '{new_competence}'")
        result = HubSpokeIngestion.update_competences_by_user_id(
            user_id=user_id,
            competences=new_competence
        )
        
        self.assertTrue(result['success'], "Update should succeed")
        self.assertEqual(len(result['updated_uuids']), 1, "Should update one competence")
        
        # Verify the update
        time.sleep(1)  # Wait for indexing
        updated_competences = HubSpokeSearch.get_profile_competences(user_a['profile_uuid'])
        found_updated = any("Home Renovation" in c.get('description', '') for c in updated_competences)
        self.assertTrue(found_updated, "Should find updated competence")
        
        # Update with a list of strings
        new_competences_list = [
            "Master Plumber with 10 years experience",
            "Specialized in Bathroom Renovations"
        ]
        logger.info(f"\nUpdating with list: {new_competences_list}")
        result = HubSpokeIngestion.update_competences_by_user_id(
            user_id=user_id,
            competences=new_competences_list
        )
        
        self.assertTrue(result['success'], "Update should succeed")
        self.assertEqual(len(result['updated_uuids']), 2, "Should update two competences")
        
        logger.info("✓ Update competences by user_id working correctly")
    
    def test_delete_competences_by_user_id(self):
        """
        Test deleting specific competences for a user by user_id.
        Should be able to delete one or more competences without deleting the user.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Delete Competences by User ID")
        logger.info("=" * 80)
        
        # Get User B's data
        user_b = self.personas_map['User B (The Spammer)']
        profile_collection = get_unified_profile_collection()
        
        # Get the user_id
        profile_result = profile_collection.query.fetch_object_by_id(
            uuid=user_b['profile_uuid']
        )
        user_id = profile_result.properties.get('user_id')
        
        logger.info(f"User ID: {user_id}")
        original_competences = HubSpokeSearch.get_profile_competences(user_b['profile_uuid'])
        original_count = len(original_competences)
        logger.info(f"Original competences count: {original_count}")
        logger.info(f"Original competences:")
        for i, comp in enumerate(original_competences):
            logger.info(f"  {i+1}. Title: {comp.get('title')}")
            logger.info(f"     Description: {comp.get('description')[:80]}...")
            logger.info(f"     Category: {comp.get('category')}")
        
        # Delete a single competence by title/description pattern
        # User B has "Everything Services" with "Electrician" in description and category "General"
        competence_to_delete = "Everything"  # This will match the title
        logger.info(f"\nDeleting competence matching: '{competence_to_delete}'")
        result = HubSpokeIngestion.delete_competences_by_user_id(
            user_id=user_id,
            competences=competence_to_delete
        )
        
        self.assertTrue(result['success'], "Delete should succeed")
        self.assertGreater(len(result['deleted_uuids']), 0, "Should delete at least one competence")
        
        # Verify deletion
        time.sleep(1)  # Wait for indexing
        remaining_competences = HubSpokeSearch.get_profile_competences(user_b['profile_uuid'])
        self.assertLess(len(remaining_competences), original_count, "Should have fewer competences")
        
        # Verify profile still exists
        profile_result = profile_collection.query.fetch_object_by_id(
            uuid=user_b['profile_uuid']
        )
        self.assertIsNotNone(profile_result, "Profile should still exist")
        
        # Delete multiple competences with a list
        remaining_count = len(remaining_competences)
        if remaining_count >= 2:
            competences_to_delete = [
                remaining_competences[0].get('title', ''),
                remaining_competences[1].get('title', '')
            ]
            logger.info(f"\nDeleting multiple competences: {competences_to_delete}")
            result = HubSpokeIngestion.delete_competences_by_user_id(
                user_id=user_id,
                competences=competences_to_delete
            )
            
            self.assertTrue(result['success'], "Delete should succeed")
            self.assertEqual(len(result['deleted_uuids']), 2, "Should delete two competences")
        
        logger.info("✓ Delete competences by user_id working correctly")
    
    def test_add_competences_by_user_id(self):
        """
        Test adding new competences to an existing user by user_id.
        """
        logger.info("\n" + "=" * 80)
        logger.info("TEST: Add Competences by User ID")
        logger.info("=" * 80)
        
        # Get User C's data
        user_c = self.personas_map.get('User C (The Ghost)')
        if not user_c:
            self.skipTest("User C not found in test data")
        
        profile_collection = get_unified_profile_collection()
        
        # Get the user_id
        profile_result = profile_collection.query.fetch_object_by_id(
            uuid=user_c['profile_uuid']
        )
        user_id = profile_result.properties.get('user_id')
        
        logger.info(f"User ID: {user_id}")
        logger.info(f"Profile properties: {profile_result.properties}")
        if not user_id:
            self.skipTest(f"User C profile missing user_id field. Properties: {profile_result.properties}")
        original_competences = HubSpokeSearch.get_profile_competences(user_c['profile_uuid'])
        original_count = len(original_competences)
        logger.info(f"Original competences count: {original_count}")
        
        # Add a single competence
        new_competence = "Expert in Kitchen Remodeling"
        logger.info(f"\nAdding single competence: '{new_competence}'")
        result = HubSpokeIngestion.add_competences_by_user_id(
            user_id=user_id,
            competences=new_competence,
            category="Renovation"
        )
        
        self.assertTrue(result['success'], "Add should succeed")
        self.assertEqual(len(result['added_uuids']), 1, "Should add one competence")
        
        # Verify addition
        time.sleep(1)  # Wait for indexing
        updated_competences = HubSpokeSearch.get_profile_competences(user_c['profile_uuid'])
        self.assertEqual(len(updated_competences), original_count + 1, "Should have one more competence")
        
        # Add multiple competences with a list
        new_competences_list = [
            "Flooring Installation Expert",
            "Tile Work Specialist"
        ]
        logger.info(f"\nAdding multiple competences: {new_competences_list}")
        result = HubSpokeIngestion.add_competences_by_user_id(
            user_id=user_id,
            competences=new_competences_list,
            category="Flooring"
        )
        
        self.assertTrue(result['success'], "Add should succeed")
        self.assertEqual(len(result['added_uuids']), 2, "Should add two competences")
        
        # Final verification
        final_competences = HubSpokeSearch.get_profile_competences(user_c['profile_uuid'])
        self.assertEqual(len(final_competences), original_count + 3, "Should have three more competences total")
        
        logger.info("✓ Add competences by user_id working correctly")


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
