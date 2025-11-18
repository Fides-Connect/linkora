"""
Weaviate Database Initialization Script
Initializes Weaviate schema and migrates test data.
"""
import sys
import os
import logging
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ai_assistant.weaviate_config import init_weaviate_schema, WeaviateConnection
from src.ai_assistant.weaviate_models import UserModelWeaviate, ProviderModelWeaviate
from src.ai_assistant.test_data import USER_DATA, SERVICE_PROVIDERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_users():
    """Migrate user data to Weaviate."""
    logger.info("Migrating user data...")
    
    try:
        user_id = UserModelWeaviate.create_user(USER_DATA)
        if user_id:
            logger.info(f"✅ User created: {USER_DATA['name']}")
        else:
            logger.error("❌ Failed to create user")
    except Exception as e:
        logger.error(f"❌ Error migrating users: {e}")


def migrate_providers():
    """Migrate service provider data to Weaviate."""
    logger.info("Migrating service providers...")
    
    success_count = 0
    fail_count = 0
    
    for provider in SERVICE_PROVIDERS:
        try:
            # Map 'id' field to 'provider_id' for consistency
            provider_data = provider.copy()
            if 'id' in provider_data:
                provider_data['provider_id'] = provider_data.pop('id')
            
            provider_id = ProviderModelWeaviate.create_provider(provider_data)
            if provider_id:
                logger.info(f"✅ Provider created: {provider['name']}")
                success_count += 1
            else:
                logger.error(f"❌ Failed to create provider: {provider['name']}")
                fail_count += 1
        except Exception as e:
            logger.error(f"❌ Error creating provider {provider['name']}: {e}")
            fail_count += 1
    
    logger.info(f"Provider migration complete: {success_count} success, {fail_count} failed")


def verify_data():
    """Verify migrated data."""
    logger.info("\nVerifying migrated data...")
    
    # Check user
    user = UserModelWeaviate.get_user_by_id(USER_DATA['user_id'])
    if user:
        logger.info(f"✅ User verified: {user['name']}")
    else:
        logger.error("❌ User verification failed")
    
    # Check providers by category
    categories = set(p['category'] for p in SERVICE_PROVIDERS)
    for category in categories:
        providers = ProviderModelWeaviate.search_providers_by_category(category)
        logger.info(f"✅ Category '{category}': {len(providers)} providers")
    
    # Test vector search
    logger.info("\nTesting vector search...")
    test_queries = [
        "Mein Computer startet nicht",
        "Rasen mähen und Hecke schneiden",
        "Wasserhahn tropft"
    ]
    
    for query in test_queries:
        results = ProviderModelWeaviate.vector_search_providers(query, limit=3)
        logger.info(f"\nQuery: '{query}'")
        for i, provider in enumerate(results, 1):
            score = provider.get('score', 0)
            logger.info(f"  {i}. {provider['name']} ({provider['category']}) - Score: {score:.4f}")


def main():
    """Main initialization function."""
    logger.info("Starting Weaviate initialization...")
    
    try:
        # Initialize schema
        logger.info("Initializing Weaviate schema...")
        init_weaviate_schema()
        logger.info("✅ Schema initialized")
        
        # Migrate data
        migrate_users()
        migrate_providers()
        
        # Verify migration
        verify_data()
        
        logger.info("\n✅ Weaviate initialization complete!")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        raise
    finally:
        # Close Weaviate connection
        WeaviateConnection.close()


if __name__ == "__main__":
    main()
