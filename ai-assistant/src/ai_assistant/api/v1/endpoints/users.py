"""
/api/v1/users/* endpoints
User management endpoints.
"""
import logging
from datetime import datetime, UTC
from aiohttp import web
from pydantic import ValidationError

from ai_assistant.firestore_service import FirestoreService
from ai_assistant.weaviate_models import UserModelWeaviate
from ...deps import get_current_user_id, serialize_datetime

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()


async def create_user(request: web.Request) -> web.Response:
    """POST /api/v1/users - Creates a new user."""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        success = await firestore_service.create_user(user_id, body)
        if success:
            # Sync to Weaviate
            try:
                body['user_id'] = user_id
                body['created_at'] = datetime.now(UTC)
                UserModelWeaviate.create_user(body)
            except Exception as e:
                logger.error(f"Failed to sync user {user_id} to Weaviate: {e}")
            
            return web.json_response({
                "status": "added",
                "user_id": user_id
            }, status=201)
        else:
            return web.json_response({"error": "Failed to create user"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in create_user: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_user: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_user(request: web.Request) -> web.Response:
    """GET /api/v1/users/{user_id} - Get another user's public profile."""
    try:
        # Require auth to prevent scraping
        await get_current_user_id(request)
        
        target_user_id = request.match_info['user_id']
        user = await firestore_service.get_user(target_user_id)
        
        if user:
            user = serialize_datetime(user)
            return web.json_response(user)
        
        return web.json_response({"error": "User not found"}, status=404)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def delete_user(request: web.Request) -> web.Response:
    """DELETE /api/v1/users/{user_id} - Delete a user and all subcollections.
    
    Authorization: Only the user themselves can delete their account.
    """
    try:
        authenticated_user_id = await get_current_user_id(request)
        user_id = request.match_info.get('user_id')
        
        # Authorization check: user can only delete themselves
        if authenticated_user_id != user_id:
            return web.json_response({
                "error": "Forbidden: You can only delete your own account"
            }, status=403)
        
        success = await firestore_service.delete_user(user_id)
        if success:
            # Delete from Weaviate
            try:
                UserModelWeaviate.delete_user(user_id)
            except Exception as e:
                logger.error(f"Failed to delete user {user_id} from Weaviate: {e}")
            
            return web.json_response({"status": "deleted"})
        else:
            return web.json_response({"error": "Failed to delete user"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_user: {e}")
        return web.json_response({"error": str(e)}, status=500)
