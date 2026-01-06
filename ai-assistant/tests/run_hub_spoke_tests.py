"""
Standalone Test Runner for Hub and Spoke Architecture
======================================================

This script runs the tests without importing the full ai_assistant package
to avoid dependency issues during testing.
"""
import sys
import os

# Add source directories to path
project_root = os.path.join(os.path.dirname(__file__), '..')
src_dir = os.path.join(project_root, 'src')
ai_assistant_dir = os.path.join(src_dir, 'ai_assistant')

# Add directories to sys.path so modules can find each other
sys.path.insert(0, ai_assistant_dir)  # For direct module imports
sys.path.insert(0, src_dir)
sys.path.insert(0, project_root)

# Now we can import directly as modules
import unittest
import logging
import time
from datetime import datetime, UTC
from weaviate.classes.query import QueryReference

# Import hub and spoke modules
import hub_spoke_schema
import hub_spoke_ingestion
import hub_spoke_search

# Import test data
sys.path.insert(0, os.path.join(project_root, 'tests'))
import test_hub_spoke_data

# Extract what we need
init_hub_spoke_schema = hub_spoke_schema.init_hub_spoke_schema
cleanup_hub_spoke_schema = hub_spoke_schema.cleanup_hub_spoke_schema
HubSpokeConnection = hub_spoke_schema.HubSpokeConnection
get_unified_profile_collection = hub_spoke_schema.get_unified_profile_collection
get_competence_entry_collection = hub_spoke_schema.get_competence_entry_collection

HubSpokeIngestion = hub_spoke_ingestion.HubSpokeIngestion
sanitize_input = hub_spoke_ingestion.sanitize_input
enrich_text = hub_spoke_ingestion.enrich_text

HubSpokeSearch = hub_spoke_search.HubSpokeSearch

TEST_PERSONAS = test_hub_spoke_data.TEST_PERSONAS

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


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
        logger.info("Waiting 3 seconds for Weaviate indexing...")
        time.sleep(3)
        
        logger.info("Setup complete\n")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up collections."""
        logger.info("\n" + "=" * 80)
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
        """
        logger.info("=" * 80)
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
        logger.info("✓ Bidirectional linking verified\n")
    
    def test_02_granularity_match(self):
        """
        Test 2: Granularity Match
        
        Searching for "Electrician" should retrieve User A who has the specific
        skill "Installing Pot Lights". This tests the enrich_text() functionality.
        """
        logger.info("=" * 80)
        logger.info("TEST 2: Granularity Match")
        logger.info("=" * 80)
        
        query = "Electrician"
        logger.info(f"Query: '{query}'")
        logger.info("Expected: User A (Installing Pot Lights) should match due to enrichment")
        
        results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_profile=False
        )
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # Verify User A appears in results
        profile_names = [r.get('profile', {}).get('name') for r in results if 'profile' in r]
        
        self.assertIn("Alice Professional", profile_names, 
                     "User A (Alice) should appear in results due to enrichment")
        
        # Find User A's result
        user_a_result = next((r for r in results if r.get('profile', {}).get('name') == 'Alice Professional'), None)
        self.assertIsNotNone(user_a_result, "User A result should be found")
        
        logger.info(f"✓ User A found: {user_a_result['title']}")
        logger.info(f"  Score: {user_a_result.get('score', 0):.4f}")
        logger.info(f"  Category: {user_a_result['category']}")
        logger.info("✓ Granularity enrichment working\n")
    
    def test_03_spam_filtering(self):
        """
        Test 3: SEO Spam Filtering
        
        User B has a keyword-stuffed description.
        The sanitize_input() function should truncate this.
        """
        logger.info("=" * 80)
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
        
        # Verify sanitization occurred
        unique_words = set(stored_description.lower().split())
        logger.info(f"Unique words in stored description: {len(unique_words)}")
        
        # Allow some buffer for enrichment terms
        self.assertLessEqual(len(unique_words), 30, 
                           "Sanitized description should have limited unique words")
        
        logger.info("✓ Spam filtering applied during ingestion\n")
    
    def test_04_ghost_filtering(self):
        """
        Test 4: Ghost User Filtering
        
        User C hasn't been active for 365 days.
        With max_inactive_days=180, User C should be EXCLUDED.
        """
        logger.info("=" * 80)
        logger.info("TEST 4: Ghost User Filtering")
        logger.info("=" * 80)
        
        query = "Expert Electrician"
        logger.info(f"Query: '{query}'")
        logger.info("User C has this exact skill but is inactive for 365 days")
        logger.info("Expected: User C should be EXCLUDED (max_inactive_days=180)")
        
        results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_profile=False
        )
        
        logger.info(f"Results: {len(results)} competence(s) found")
        
        # Verify User C is NOT in results
        profile_names = [r.get('profile', {}).get('name') for r in results if 'profile' in r]
        
        self.assertNotIn("Charlie Ghost", profile_names, 
                        "User C (Charlie Ghost) should be excluded due to inactivity")
        
        logger.info(f"Active users found: {profile_names}")
        logger.info("✓ User C (Ghost) correctly excluded")
        logger.info("✓ Ghost user filtering working\n")
    
    def test_05_result_grouping(self):
        """
        Test 5: Result Grouping
        
        User E has 5 different gardening competences.
        With group_by_profile=True, User E should appear only ONCE.
        """
        logger.info("=" * 80)
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
            group_by_profile=True
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
        
        # Search WITHOUT grouping
        ungrouped_results = HubSpokeSearch.search_competences(
            query=query,
            limit=10,
            max_inactive_days=180,
            group_by_profile=False
        )
        
        logger.info(f"\nUngrouped results: {len(ungrouped_results)} result(s)")
        
        user_e_ungrouped_count = sum(1 for r in ungrouped_results 
                                     if r.get('profile', {}).get('name') == 'Eva Enthusiast')
        
        logger.info(f"User E appears {user_e_ungrouped_count} time(s) without grouping")
        
        self.assertGreaterEqual(user_e_ungrouped_count, 2, 
                               "User E should appear multiple times without grouping")
        
        logger.info("✓ Result grouping working correctly\n")
    
    def test_06_helper_functions(self):
        """
        Test 6: Helper Functions
        
        Test sanitize_input() and enrich_text() in isolation.
        """
        logger.info("=" * 80)
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
        
        logger.info("✓ All helper functions working correctly\n")


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("Hub and Spoke Architecture Test Suite")
    print("Following TDD: Tests define requirements, implementation follows")
    print("=" * 80 + "\n")
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestHubSpokeArchitecture)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED")
        print("Hub and Spoke architecture is working correctly!")
    else:
        print("✗ SOME TESTS FAILED")
        print(f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
    print("=" * 80)
    
    exit(0 if result.wasSuccessful() else 1)
