import logging
import json
from aiohttp import web
from firebase_admin import auth
from .firestore_service import FirestoreService

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()

async def get_current_user_id(request: web.Request) -> str:
    """Extract and verify Firebase ID token from Authorization header."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise web.HTTPUnauthorized(reason="Missing or invalid Authorization header")
    
    token = auth_header.split(' ')[1]
    try:
        # verify_id_token is blocking, might want to run in executor if high load, 
        # but for now standard usage is fine.
        decoded_token = auth.verify_id_token(token)
        return decoded_token['uid']
    except Exception as e:
        logger.warning(f"Auth failed: {e}")
        raise web.HTTPUnauthorized(reason="Invalid authentication token")

async def get_requests(request: web.Request) -> web.Response:
    """GET /requests"""
    try:
        user_id = await get_current_user_id(request)
        requests = await firestore_service.get_requests(user_id)
        # Convert datetime objects to string for JSON serialization
        for r in requests:
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
        return web.json_response(requests)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_requests: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def create_request(request: web.Request) -> web.Response:
    """POST /requests"""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        
        # Enforce userId to be the authenticated user
        body['userId'] = user_id
        # Also ensure userName matches if possible, or trust client? 
        # Client sends everything. We'll trust client for now but override userId.
        
        request_id = await firestore_service.create_request(body)
        if request_id:
            return web.json_response({"id": request_id, "status": "created"}, status=201)
        else:
            return web.json_response({"error": "Failed to create request"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_request: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def update_request_status(request: web.Request) -> web.Response:
    """PUT /requests/{requestId}/status"""
    try:
        user_id = await get_current_user_id(request) # Auth check
        request_id = request.match_info['requestId']
        body = await request.json()
        status = body.get('status')
        
        if not status:
            return web.json_response({"error": "Missing status"}, status=400)
            
        # TODO: Check if user is allowed to update this request (owner or provider)
        # For now, just update.
        
        success = await firestore_service.update_request_status(request_id, status)
        if success:
            return web.json_response({"status": "updated"})
        else:
            return web.json_response({"error": "Failed to update status"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_request_status: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def get_favorites(request: web.Request) -> web.Response:
    """GET /favorites"""
    try:
        user_id = await get_current_user_id(request)
        favorites = await firestore_service.get_favorites(user_id)
        return web.json_response(favorites)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_favorites: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def add_favorite(request: web.Request) -> web.Response:
    """POST /favorites/{id}"""
    try:
        user_id = await get_current_user_id(request)
        supporter_id = request.match_info['id']
        
        # We need to fetch the supporter details to store them in favorites
        # Assuming we can fetch public profile of the supporter from users collection
        supporter_profile = await firestore_service.get_user_profile(supporter_id)
        
        if not supporter_profile:
             return web.json_response({"error": "Supporter not found"}, status=404)

        # Add to favorites
        success = await firestore_service.add_favorite(user_id, supporter_profile)
        if success:
             return web.json_response({"status": "added"})
        else:
             return web.json_response({"error": "Failed to add favorite"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_favorite: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def remove_favorite(request: web.Request) -> web.Response:
    """DELETE /favorites/{id}"""
    try:
        user_id = await get_current_user_id(request)
        supporter_id = request.match_info['id']
        
        success = await firestore_service.remove_favorite(user_id, supporter_id)
        if success:
             return web.json_response({"status": "removed"})
        else:
             return web.json_response({"error": "Failed to remove favorite"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_favorite: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def get_profile(request: web.Request) -> web.Response:
    """GET /profile"""
    try:
        user_id = await get_current_user_id(request)
        profile = await firestore_service.get_user_profile(user_id)
        
        if profile:
            # Handle datetime serialization if any
            for k, v in profile.items():
                if hasattr(v, 'isoformat'):
                    profile[k] = v.isoformat()
            return web.json_response(profile)
        
        # If not found, return 404
        return web.json_response({"error": "Profile not found"}, status=404)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_profile: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def update_profile(request: web.Request) -> web.Response:
    """PUT /profile"""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        
        success = await firestore_service.update_user_profile(user_id, body)
        if success:
             return web.json_response({"status": "updated"})
        else:
             return web.json_response({"error": "Failed to update profile"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_profile: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def add_competence(request: web.Request) -> web.Response:
    """POST /profile/competencies"""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        competence = body.get('competence')
        
        if not competence:
            return web.json_response({"error": "Missing competence"}, status=400)
            
        success = await firestore_service.add_competence(user_id, competence)
        if success:
             return web.json_response({"status": "added"})
        else:
             return web.json_response({"error": "Failed to add competence"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def remove_competence(request: web.Request) -> web.Response:
    """DELETE /profile/competencies/{competence}"""
    try:
        user_id = await get_current_user_id(request)
        competence = request.match_info['competence']
        
        success = await firestore_service.remove_competence(user_id, competence)
        if success:
             return web.json_response({"status": "removed"})
        else:
             return web.json_response({"error": "Failed to remove competence"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def get_other_profile(request: web.Request) -> web.Response:
    """GET /users/{id}/profile"""
    try:
        # We might require auth here too, to prevent scraping
        await get_current_user_id(request)
        
        target_user_id = request.match_info['id']
        profile = await firestore_service.get_user_profile(target_user_id)
        
        if profile:
             # Handle datetime serialization if any
            for k, v in profile.items():
                if hasattr(v, 'isoformat'):
                    profile[k] = v.isoformat()
            return web.json_response(profile)
        
        return web.json_response({"error": "Profile not found"}, status=404)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_other_profile: {e}")
        return web.json_response({"error": str(e)}, status=500)
