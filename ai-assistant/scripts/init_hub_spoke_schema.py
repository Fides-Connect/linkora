#!/usr/bin/env python3
"""
Initialize Hub and Spoke Schema
================================

This script initializes the new Hub and Spoke architecture schema in Weaviate.
It cleans up old collections and creates the new UnifiedProfile and CompetenceEntry collections.

Usage:
    python scripts/init_hub_spoke_schema.py [--load-test-data]

Options:
    --load-test-data    Load test personas after schema initialization
"""
import os
import sys
import argparse
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

from ai_assistant.hub_spoke_schema import (
    init_hub_spoke_schema,
    cleanup_hub_spoke_schema,
    HubSpokeConnection
)
from ai_assistant.hub_spoke_ingestion import HubSpokeIngestion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_test_data():
    """Load test personas into the database."""
    sys.path.insert(0, os.path.join(project_root, 'tests'))
    from test_hub_spoke_data import TEST_PERSONAS
    
    logger.info("Loading test personas...")
    
    for persona in TEST_PERSONAS:
        logger.info(f"Creating {persona['name']}")
        result = HubSpokeIngestion.create_profile_with_competences(
            profile_data=persona['profile'],
            competences_data=persona['competences'],
            apply_sanitization=True,
            apply_enrichment=True
        )
        if result:
            logger.info(f"  ✓ Profile UUID: {result['profile_uuid']}")
            logger.info(f"  ✓ Competences: {len(result['competence_uuids'])}")
        else:
            logger.error(f"  ✗ Failed to create {persona['name']}")
    
    logger.info("Test data loaded successfully")


def main():
    parser = argparse.ArgumentParser(
        description='Initialize Hub and Spoke schema in Weaviate'
    )
    parser.add_argument(
        '--load-test-data',
        action='store_true',
        help='Load test personas after schema initialization'
    )
    parser.add_argument(
        '--clean-only',
        action='store_true',
        help='Only clean up existing collections without creating new ones'
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("=" * 80)
        logger.info("Hub and Spoke Schema Initialization")
        logger.info("=" * 80)
        
        # Step 1: Clean up old collections
        logger.info("\n[Step 1/3] Cleaning up existing collections...")
        try:
            cleanup_hub_spoke_schema()
            logger.info("✓ Cleanup complete")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        
        if args.clean_only:
            logger.info("\nClean-only mode: Skipping schema creation")
            return 0
        
        # Step 2: Initialize new schema
        logger.info("\n[Step 2/3] Initializing Hub and Spoke schema...")
        init_hub_spoke_schema()
        logger.info("✓ Schema initialized successfully")
        
        # Step 3: Load test data (optional)
        if args.load_test_data:
            logger.info("\n[Step 3/3] Loading test data...")
            load_test_data()
            logger.info("✓ Test data loaded successfully")
        else:
            logger.info("\n[Step 3/3] Skipping test data (use --load-test-data to load)")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ Initialization Complete")
        logger.info("=" * 80)
        logger.info("\nNew Collections Created:")
        logger.info("  - UnifiedProfile (Hub)")
        logger.info("  - CompetenceEntry (Spoke)")
        logger.info("\nYou can now use the Hub and Spoke architecture!")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n✗ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Close connection
        HubSpokeConnection.close()


if __name__ == '__main__':
    sys.exit(main())
