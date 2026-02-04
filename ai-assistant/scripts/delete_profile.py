#!/usr/bin/env python3
"""
Delete Profile Script
Deletes a profile and all their competences from Weaviate.

Usage:
    python scripts/delete_profile.py --profile-id <profile_id>
"""
import sys
import os
import argparse
import logging

# Add parent directory to path to import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ai_assistant.hub_spoke_schema import (
    HubSpokeConnection,
    get_profile_collection,
    get_competence_collection
)
from weaviate.classes.query import Filter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

 # TODO : add remove profile endpoint and remove skills endpoint to admin interface
def delete_profile_by_id(profile_id: str) -> bool:
    """
    Delete a profile and all their competences from Weaviate.
    
    Args:
        profile_id: The profile_id to delete
        
    Returns:
        bool: True if deletion was successful
    """
    try:
        client = HubSpokeConnection.get_client()
        profile_collection = get_profile_collection()
        competence_collection = get_competence_collection()
        
        # Step 1: Find the profile by profile_id
        logger.info(f"Searching for profile with profile_id: {profile_id}")
        result = profile_collection.query.fetch_objects(
            filters=Filter.by_property("profile_id").equal(profile_id),
            limit=1
        )
        
        if not result.objects:
            logger.error(f"No profile found with profile_id: {profile_id}")
            return False
        
        profile_uuid = result.objects[0].uuid
        profile_data = result.objects[0].properties
        logger.info(f"Found profile: {profile_data.get('name')} (UUID: {profile_uuid})")
        
        # Step 2: Find and delete all competences owned by this profile
        logger.info("Searching for competences owned by this profile...")
        competences = competence_collection.query.fetch_objects(
            return_references=["owned_by"],
            limit=1000  # Adjust if profile has more competences
        )
        
        deleted_competences = 0
        for comp in competences.objects:
            # Check if this competence is owned by our profile
            if hasattr(comp, 'references') and 'owned_by' in comp.references:
                owned_by_refs = comp.references['owned_by'].objects
                if owned_by_refs and str(owned_by_refs[0].uuid) == str(profile_uuid):
                    competence_uuid = comp.uuid
                    comp_title = comp.properties.get('title', 'Unknown')
                    logger.info(f"  Deleting competence: {comp_title} (UUID: {competence_uuid})")
                    competence_collection.data.delete_by_id(competence_uuid)
                    deleted_competences += 1
        
        logger.info(f"Deleted {deleted_competences} competence(s)")
        
        # Step 3: Delete the profile
        logger.info(f"Deleting profile: {profile_data.get('name')}")
        profile_collection.data.delete_by_id(profile_uuid)
        
        logger.info("✓ Profile deletion complete!")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting profile: {e}")
        return False
    finally:
        HubSpokeConnection.close()


def main():
    parser = argparse.ArgumentParser(description='Delete a profile from Weaviate')
    parser.add_argument('--profile-id', required=True, help='Profile ID to delete')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Confirmation prompt
    if not args.confirm:
        print(f"\n⚠️  WARNING: This will permanently delete profile with profile_id: {args.profile_id}")
        print("   This action cannot be undone!")
        response = input("\nAre you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Deletion cancelled.")
            return
    
    # Execute deletion
    success = delete_profile_by_id(args.profile_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
