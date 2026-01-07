"""
Weaviate Models and Operations
Data models using Hub and Spoke architecture.
Maps legacy User/Provider operations to UnifiedProfile/CompetenceEntry.
"""
import logging
from datetime import datetime, UTC
from typing import List, Dict, Optional, Any
from weaviate.classes.query import Filter
from .weaviate_config import get_users_collection, get_providers_collection

# Handle both package and direct imports for hub_spoke
try:
    from .hub_spoke_ingestion import HubSpokeIngestion
    from .hub_spoke_search import HubSpokeSearch
except ImportError:
    from hub_spoke_ingestion import HubSpokeIngestion
    from hub_spoke_search import HubSpokeSearch

logger = logging.getLogger(__name__)


class UserModelWeaviate:
    """User data model and operations for Weaviate."""
    
    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> Optional[str]:
        """Create a new user (UnifiedProfile)."""
        try:
            collection = get_users_collection()
            
            # Map old User fields to UnifiedProfile fields
            uuid = collection.data.insert(
                properties={
                    "user_id": user_data.get("user_id"),
                    "name": user_data.get("name") or user_data.get("display_name", ""),
                    "email": user_data.get("email"),
                    "type": "client",  # Default type for users
                    "photo_url": user_data.get("photo_url", ""),
                    "fcm_token": user_data.get("fcm_token", ""),
                    "has_open_request": user_data.get("has_open_request", False),
                    "created_at": user_data.get("created_at", datetime.now(UTC)),
                    "last_sign_in": user_data.get("last_sign_in", datetime.now(UTC)),
                    "last_active_date": user_data.get("last_active_date", datetime.now(UTC).isoformat()),
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
                user = obj.properties.copy()
                # Add backward compatibility: map display_name -> name
                if 'display_name' in user and 'name' not in user:
                    user['name'] = user['display_name']
                return user
            
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
            
            # Map name -> display_name if present
            if 'name' in update_data and 'display_name' not in update_data:
                update_data['display_name'] = update_data['name']
            
            # Update last_active_date on any update
            update_data['last_active_date'] = datetime.now(UTC).isoformat()
            
            # Merge existing properties with update data to preserve unmodified fields
            merged_properties = {**obj.properties, **update_data}
            
            # Update user properties
            collection.data.update(
                uuid=obj.uuid,
                properties=merged_properties
            )
            
            logger.info(f"Updated user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    

    @staticmethod
    def get_all_users(limit: int = 100) -> List[Dict[str, Any]]:
        """Get all users."""
        try:
            collection = get_users_collection()
            
            response = collection.query.fetch_objects(limit=limit)
            users = []
            for obj in response.objects:
                user = obj.properties.copy()
                # Add backward compatibility: map display_name -> name
                if 'display_name' in user and 'name' not in user:
                    user['name'] = user['display_name']
                users.append(user)
            
            logger.info(f"Retrieved {len(users)} users")
            return users
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []


    @staticmethod
    def get_attributes_by_filter(
        filter_attr: str,
        filter_values: List[Any],
        return_attr: str
    ) -> Dict[Any, Optional[Any]]:
        """
        Get specified attributes for users matching filter criteria.
        
        Args:
            filter_attr: The attribute name to filter by (e.g., "user_id")
            filter_values: List of values to match (e.g., list of user IDs)
            return_attr: The attribute name to return (e.g., "fcm_token")
            
        Returns:
            Dict mapping filter values to their corresponding return attribute values.
            Returns None for values where no match is found.
            
        Example:
            >>> UserModelWeaviate.get_attributes_by_filter(
            ...     filter_attr="user_id",
            ...     filter_values=["user1", "user2", "user3"],
            ...     return_attr="fcm_token"
            ... )
            {'user1': 'token_abc', 'user2': 'token_xyz', 'user3': None}
        """
        try:
            if not filter_attr or not filter_values or not return_attr:
                return {}
            
            collection = get_users_collection()
            filters = Filter.by_property(filter_attr).contains_any(filter_values)
            
            # Fetch all matching objects in one query
            response = collection.query.fetch_objects(
                filters=filters,
                limit=len(filter_values)
            )
            
            # Build result map
            result_map = {value: None for value in filter_values}
            for obj in response.objects:
                filter_value = obj.properties.get(filter_attr)
                if filter_value in result_map:
                    result_map[filter_value] = obj.properties.get(return_attr)
            
            logger.info(f"Retrieved {sum(1 for v in result_map.values() if v is not None)}/{len(filter_values)} {return_attr} values by {filter_attr}")
            return result_map
            
        except Exception as e:
            logger.error(f"Error getting attributes by filter: {e}")
            return {value: None for value in filter_values}


class ProviderModelWeaviate:
    """Service provider data model and operations for Weaviate."""
    
    

    @staticmethod
    def get_provider_by_id(provider_id: str) -> Optional[Dict[str, Any]]:
        """Get provider by ID (searches UnifiedProfile by user_id)."""
        try:
            collection = get_users_collection()  # UnifiedProfile
            
            response = collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(provider_id),
                limit=1
            )
            
            if response.objects:
                obj = response.objects[0]
                provider = obj.properties.copy()
                # Map display_name -> name for backward compatibility
                if 'display_name' in provider:
                    provider['name'] = provider['display_name']
                provider['provider_id'] = provider.get('user_id')
                return provider
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching provider: {e}")
            return None
    

    @staticmethod
    def search_providers_by_category(category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search providers by category using hub_spoke search."""
        try:
            # Use HubSpokeSearch to find competences in this category
            results = HubSpokeSearch.search_competences(
                query=category,
                limit=limit,
                max_inactive_days=180,
                group_by_profile=True  # One result per provider
            )
            
            # Map to provider format
            providers = []
            for result in results:
                profile = result.get('profile', {})
                provider = {
                    'provider_id': profile.get('uuid'),
                    'name': profile.get('name'),
                    'category': result.get('category'),
                    'description': result.get('description'),
                    'skills': result.get('keywords', []),
                }
                providers.append(provider)
            
            logger.info(f"Found {len(providers)} providers in category: {category}")
            return providers
            
        except Exception as e:
            logger.error(f"Error searching providers by category: {e}")
            return []
    

    @staticmethod
    def vector_search_providers(query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search providers using hybrid search (vector + keyword).
        Uses hub_spoke architecture with ghost filtering and grouping.
        """
        try:
            # Use HubSpokeSearch for hybrid search
            results = HubSpokeSearch.search_competences(
                query=query_text,
                limit=limit,
                max_inactive_days=180,  # Exclude inactive providers
                group_by_profile=True   # One result per provider
            )
            
            # Map to provider format for backward compatibility
            providers = []
            for result in results:
                profile = result.get('profile', {})
                provider = {
                    'provider_id': profile.get('uuid'),
                    'name': profile.get('name'),
                    'category': result.get('category'),
                    'description': result.get('description'),
                    'skills': result.get('keywords', []),
                    'score': result.get('score', 0),
                }
                providers.append(provider)
            
            logger.info(f"Vector search found {len(providers)} providers for: '{query_text[:50]}...'")
            return providers
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    
    @staticmethod
    def get_all_providers(limit: int = 100) -> List[Dict[str, Any]]:
        """Get all providers (UnifiedProfile with type='provider')."""
        try:
            collection = get_users_collection()  # UnifiedProfile
            
            response = collection.query.fetch_objects(
                filters=Filter.by_property("type").equal("provider"),
                limit=limit
            )
            
            providers = []
            for obj in response.objects:
                provider = obj.properties.copy()
                # Map display_name -> name for backward compatibility
                if 'display_name' in provider:
                    provider['name'] = provider['display_name']
                provider['provider_id'] = provider.get('user_id')
                providers.append(provider)
            
            logger.info(f"Retrieved {len(providers)} providers")
            return providers
            
        except Exception as e:
            logger.error(f"Error getting all providers: {e}")
            return []
