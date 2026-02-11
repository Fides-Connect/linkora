"""
/api/v1/me/* endpoints
Current user management endpoints.
"""
import logging
from aiohttp import web
from pydantic import ValidationError
from weaviate.classes.query import Filter

from ai_assistant.firestore_service import FirestoreService
from ai_assistant.weaviate_models import UserModelWeaviate
from ai_assistant.hub_spoke_ingestion import HubSpokeIngestion
from ai_assistant.hub_spoke_schema import get_user_collection
from ...deps import get_current_user_id, serialize_datetime

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()


async def get_me(request: web.Request) -> web.Response:
    """GET /api/v1/me - Get current user profile."""
    try:
        user_id = await get_current_user_id(request)
        user = await firestore_service.get_user(user_id)
        
        if user:
            user = serialize_datetime(user)
            return web.json_response(user)
        
        return web.json_response({"error": "User not found"}, status=404)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_me: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_me(request: web.Request) -> web.Response:
    """PATCH /api/v1/me - Update current user profile."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        
        # Check if user exists
        user = await firestore_service.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        
        success = await firestore_service.update_user(user_id, body)
        if success:
            # Sync to Weaviate
            try:
                UserModelWeaviate.update_user(user_id, body)
            except Exception as e:
                logger.error(f"Failed to sync user {user_id} update to Weaviate: {e}")

            return web.json_response({"status": "updated"})
        else:
            return web.json_response({"error": "Failed to update user"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in update_me: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_me: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_my_favorites(request: web.Request) -> web.Response:
    """GET /api/v1/me/favorites - Get current user's favorites."""
    try:
        user_id = await get_current_user_id(request)
        favorites = await firestore_service.get_favorites(user_id)
        favorites = serialize_datetime(favorites)
        return web.json_response(favorites)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_my_favorites: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def add_my_favorite(request: web.Request) -> web.Response:
    """POST /api/v1/me/favorites - Add user to favorites (user_id in body)."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        favorite_user_id = body.get('user_id')
        
        if not favorite_user_id:
            return web.json_response({"error": "Missing user_id in request body"}, status=400)
        
        # Verify the user exists
        user = await firestore_service.get_user(favorite_user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        # Add to favorites
        success = await firestore_service.add_favorite(user_id, favorite_user_id)
        if success:
            return web.json_response({"status": "added"})
        else:
            return web.json_response({"error": "Failed to add favorite"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_my_favorite: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def remove_my_favorite(request: web.Request) -> web.Response:
    """DELETE /api/v1/me/favorites/{user_id} - Remove user from favorites."""
    try:
        user_id = await get_current_user_id(request)
        favorite_user_id = request.match_info['user_id']
        
        success = await firestore_service.remove_favorite(user_id, favorite_user_id)
        if success:
            return web.json_response({"status": "removed"})
        else:
            return web.json_response({"error": "Failed to remove favorite"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_my_favorite: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_my_competencies(request: web.Request) -> web.Response:
    """GET /api/v1/me/competencies - Get current user's competencies."""
    try:
        user_id = await get_current_user_id(request)
        user = await firestore_service.get_user(user_id)
        
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        
        # Return competencies from user object
        competencies = user.get('competencies', [])
        return web.json_response({"competencies": competencies})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_my_competencies: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def add_my_competence(request: web.Request) -> web.Response:
    """POST /api/v1/me/competencies - Add competence to current user."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        competence = body.get('competence')
        
        if not competence or not isinstance(competence, dict) or 'title' not in competence:
            return web.json_response({
                "error": "Missing or invalid competence object. Must include 'title' field."
            }, status=400)
        
        created_competence = await firestore_service.add_competence(user_id, competence)
        if created_competence:
            # Sync to Weaviate
            try:
                coll = get_user_collection()
                res = coll.query.fetch_objects(
                    filters=Filter.by_property("user_id").equal(user_id),
                    limit=1
                )
                if res.objects:
                    user_uuid = str(res.objects[0].uuid)
                    HubSpokeIngestion.create_competence(
                        competence_data=created_competence,
                        user_uuid=user_uuid
                    )
            except Exception as e:
                logger.error(f"Failed to sync new competence to Weaviate: {e}")

            # Fetch and return the updated user object
            user = await firestore_service.get_user(user_id)
            if user:
                user = serialize_datetime(user)
                return web.json_response(user)
            return web.json_response({"error": "Failed to fetch updated user"}, status=500)
        else:
            return web.json_response({"error": "Failed to add competence"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in add_my_competence: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_my_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_my_competence(request: web.Request) -> web.Response:
    """PATCH /api/v1/me/competencies/{competence_id} - Update a competence."""
    try:
        user_id = await get_current_user_id(request)
        competence_id = request.match_info['competence_id']
        body = await request.json()
        
        # Check if competence exists
        competencies_ref = firestore_service._get_collection('users').document(user_id).collection('competencies')
        comp_doc = competencies_ref.document(competence_id).get()
        if not comp_doc.exists:
            return web.json_response({"error": "Competence not found"}, status=404)
        
        success = await firestore_service.update_competence(user_id, competence_id, body)
        if success:
            # Sync to Weaviate
            try:
                comp_doc = competencies_ref.document(competence_id).get()
                if comp_doc.exists:
                    competence_data = comp_doc.to_dict()
                    HubSpokeIngestion.update_competence(competence_data)
            except Exception as e:
                logger.error(f"Failed to sync competence {competence_id} update to Weaviate: {e}")
            
            return web.json_response({"status": "updated"})
        else:
            return web.json_response({"error": "Failed to update competence"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in update_my_competence: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_my_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def remove_my_competence(request: web.Request) -> web.Response:
    """DELETE /api/v1/me/competencies/{competence_id} - Remove competence."""
    try:
        user_id = await get_current_user_id(request)
        competence_id = request.match_info['competence_id']
        
        success = await firestore_service.remove_competence(user_id, competence_id)
        if success:
            # Sync to Weaviate
            try:
                HubSpokeIngestion.remove_competence_by_firestore_id(competence_id)
            except Exception as e:
                logger.error(f"Failed to remove competence {competence_id} from Weaviate: {e}")

            # Fetch and return the updated user object
            user = await firestore_service.get_user(user_id)
            if user:
                user = serialize_datetime(user)
                return web.json_response(user)
            return web.json_response({"error": "Failed to fetch updated user"}, status=500)
        else:
            return web.json_response({"error": "Failed to remove competence"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_my_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)
