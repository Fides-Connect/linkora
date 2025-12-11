"""
Weaviate Models and Operations
Data models and database operations for users and service providers.
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from weaviate.classes.query import Filter
from .weaviate_config import get_users_collection, get_providers_collection

logger = logging.getLogger(__name__)


class UserModelWeaviate:
    """User data model and operations for Weaviate."""
    
    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> Optional[str]:
        """Create a new user."""
        try:
            collection = get_users_collection()
            
            uuid = collection.data.insert(
                properties={
                    "user_id": user_data.get("user_id"),
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "photo_url": user_data.get("photo_url", ""),
                    "fcm_token": user_data.get("fcm_token", ""),
                    "has_open_request": user_data.get("has_open_request", False),
                    "created_at": user_data.get("created_at", datetime.utcnow()),
                    "last_sign_in": user_data.get("last_sign_in", datetime.utcnow()),
                }
            )
            
            logger.info(f"Created user: {user_data.get('name')}")
            return str(uuid)
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        try:
            collection = get_users_collection()
            
            response = collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )
            
            if response.objects:
                obj = response.objects[0]
                return obj.properties
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None
    
    @staticmethod
    def update_user(user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update existing user."""
        try:
            collection = get_users_collection()
            
            # Find user by user_id
            response = collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )
            
            if not response.objects:
                logger.warning(f"User not found: {user_id}")
                return False
            
            obj = response.objects[0]
            
            # Update user properties
            collection.data.update(
                uuid=obj.uuid,
                properties=update_data
            )
            
            logger.info(f"Updated user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False


class ProviderModelWeaviate:
    """Service provider data model and operations for Weaviate."""
    
    @staticmethod
    def create_provider(provider_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new service provider.
        Weaviate will automatically generate embeddings from the description.
        """
        try:
            collection = get_providers_collection()
            
            uuid = collection.data.insert(
                properties={
                    "provider_id": provider_data.get("provider_id") or provider_data.get("id"),
                    "name": provider_data.get("name"),
                    "category": provider_data.get("category"),
                    "skills": provider_data.get("skills", []),
                    "rating": float(provider_data.get("rating", 0)),
                    "experience_years": int(provider_data.get("experience_years", 0)),
                    "price_range": provider_data.get("price_range", ""),
                    "availability": provider_data.get("availability", ""),
                    "description": provider_data.get("description", ""),
                }
            )
            
            logger.info(f"Created provider: {provider_data.get('name')}")
            return str(uuid)
            
        except Exception as e:
            logger.error(f"Error creating provider: {e}")
            return None
    
    @staticmethod
    def get_provider_by_id(provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider by ID."""
        try:
            collection = get_providers_collection()
            
            response = collection.query.fetch_objects(
                filters=Filter.by_property("provider_id").equal(provider_id),
                limit=1
            )
            
            if response.objects:
                obj = response.objects[0]
                return obj.properties
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching provider: {e}")
            return None
    
    @staticmethod
    def search_providers_by_category(category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search providers by category."""
        try:
            collection = get_providers_collection()
            
            response = collection.query.fetch_objects(
                filters=Filter.by_property("category").equal(category),
                limit=limit
            )
            
            providers = [obj.properties for obj in response.objects]
            logger.info(f"Found {len(providers)} providers in category: {category}")
            return providers
            
        except Exception as e:
            logger.error(f"Error searching providers by category: {e}")
            return []
    
    @staticmethod
    def vector_search_providers(query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search providers using vector similarity.
        Weaviate automatically generates embeddings for the query text.
        """
        try:
            collection = get_providers_collection()
            
            # Perform hybrid search (vector + keyword)
            response = collection.query.hybrid(
                query=query_text,
                limit=limit,
                return_metadata=['score']
            )
            
            providers = []
            for obj in response.objects:
                provider = obj.properties.copy()
                provider['score'] = obj.metadata.score if obj.metadata else 0
                providers.append(provider)
            
            logger.info(f"Vector search found {len(providers)} providers for: '{query_text[:50]}...'")
            return providers
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    @staticmethod
    def get_all_providers(limit: int = 100) -> List[Dict[str, Any]]:
        """Get all providers."""
        try:
            collection = get_providers_collection()
            
            response = collection.query.fetch_objects(limit=limit)
            providers = [obj.properties for obj in response.objects]
            
            logger.info(f"Retrieved {len(providers)} providers")
            return providers
            
        except Exception as e:
            logger.error(f"Error getting all providers: {e}")
            return []
