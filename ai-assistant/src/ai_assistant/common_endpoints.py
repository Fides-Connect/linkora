import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4
from aiohttp import web
import firebase_admin
from firebase_admin import auth as firebase_auth
import aiohttp_cors

from .weaviate_models import UserModelWeaviate, ChatMessageModelWeaviate

logger = logging.getLogger(__name__)

# Active user sessions - maps user_id to session data
# In production, this should be replaced with Redis or database storage
_active_users: Dict[str, Dict[str, Any]] = {}

# Reference to SignalingServer for cleanup operations (set by main)
_signaling_server = None


def set_signaling_server(server):
    """Set the signaling server reference for cleanup operations."""
    global _signaling_server
    _signaling_server = server


def get_active_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get active user session data by user_id.
    
    Returns None if user is not currently active.
    Useful for looking up FCM tokens for push notifications.
    """
    return _active_users.get(user_id)


def get_all_active_users() -> Dict[str, Dict[str, Any]]:
    """Get all active user sessions.
    
    Returns a dictionary mapping user_id to session data.
    """
    return _active_users.copy()


def remove_active_user(user_id: str) -> bool:
    """Remove a user from active sessions (e.g., on explicit logout).
    
    Returns True if user was removed, False if not found.
    """
    if user_id in _active_users:
        del _active_users[user_id]
        logger.info(f"Removed user from active sessions: {user_id}")
        return True
    return False


async def user_logout(request: web.Request) -> web.Response:
    """Handle user logout - clean up server-side session data.
    
    Expects a JSON body with:
    - id_token: Firebase ID token for verification
    - user_id: Firebase user ID
    
    Returns:
    - success: Boolean indicating if logout was successful
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Verify the Firebase ID token
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)
        
        try:
            decoded_token = firebase_auth.verify_id_token(token)
        except Exception as e:
            return web.json_response({"error": "Invalid token", "details": str(e)}, status=401)
        
        # Extract user_id and options
        user_id = body.get("user_id") or decoded_token["uid"]
        clear_history = body.get("clear_history", False)
        
        # Remove from active users
        removed = remove_active_user(user_id)
        
        # Optionally clear conversation history
        history_cleared = False
        if clear_history:
            assistant_cleared = False
            if _signaling_server:
                assistant_cleared = _signaling_server.cleanup_user_assistant(
                    user_id,
                    clear_persistent=True,
                )
            if assistant_cleared:
                history_cleared = True
                logger.info(f"Cleared conversation history via assistant cleanup for user: {user_id}")
            else:
                history_cleared = ChatMessageModelWeaviate.delete_messages(user_id)
                if history_cleared:
                    logger.info(f"Cleared persisted conversation history for user: {user_id}")
        
        if removed:
            logger.info(f"User logged out: {user_id} (history_cleared={history_cleared})")
        else:
            logger.debug(f"User logout called but user not in active sessions: {user_id}")
        
        return web.json_response({
            "success": True,
            "message": "Logged out successfully",
            "history_cleared": history_cleared
        })
        
    except Exception as e:
        logger.error(f"Error in user_logout: {e}", exc_info=True)
        return web.json_response(
            {"error": "Internal server error", "details": str(e)}, 
            status=500
        )

def setup_cors(app: web.Application) -> None:
    # allow all origins for dev; tighten in production
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["POST", "OPTIONS"]
        )
    })
    # attach CORS to all routes (call after routes are added)
    for route in list(app.router.routes()):
        cors.add(route)

async def sign_in_google(request: web.Request) -> web.Response:
    """Handles user sign-in via Firebase ID token verification.
    Expects a JSON body with an 'id_token' field. Returns user
    information if the token is valid."""
    try:
        # Parse the request body
        body = await request.json()
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)

        # Verify the Firebase ID token
        # This automatically fetches and caches Google's public certificates
        decoded_token = firebase_auth.verify_id_token(token)

        # Extract user information
        user_id = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")

        # Store active user session
        # Todo: Replace with persistent session storage (Redis/DB)
        _active_users[user_id] = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "signed_in_at": datetime.now().isoformat(),
        }

        logger.info(f"User signed in: {email} (user_id: {user_id})")
        logger.debug(f"Active users: {len(_active_users)}")

        # Return user information
        return web.json_response({
            "user_id": user_id,
            "email": email,
            "name": name,
            "is_valid": True
        })

    except ValueError as e:
        # Token is invalid
        return web.json_response({"error": "Invalid token", "details": str(e)}, status=401)

    except Exception as e:
        # Handle unexpected errors
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)


async def user_sync(request: web.Request) -> web.Response:
    """Handles user registration/login and data synchronization.
    
    Expects a JSON body with:
    - id_token: Firebase ID token for verification
    - user_id: Firebase user ID
    - email: User email
    - name: User display name
    - photo_url: User photo URL (optional)
    - fcm_token: Firebase Cloud Messaging token (optional)
    - created_at: Account creation timestamp (optional)
    - last_sign_in: Last sign-in timestamp (optional)
    
    Returns:
    - user_profile: User data from database
    - is_new_user: Boolean indicating if this is a new user registration
    - user_id: User identifier (used for session/conversation tracking)
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Verify the Firebase ID token
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)
        
        try:
            decoded_token = firebase_auth.verify_id_token(token)
        except Exception as e:
            return web.json_response({"error": "Invalid token", "details": str(e)}, status=401)
        
        # Extract user information
        user_id = body.get("user_id") or decoded_token["uid"]
        email = body.get("email") or decoded_token.get("email")
        name = body.get("name") or decoded_token.get("name")
        photo_url = body.get("photo_url")
        fcm_token = body.get("fcm_token")
        created_at = body.get("created_at")
        last_sign_in = body.get("last_sign_in")
        
        # Check if user exists in database
        existing_user = UserModelWeaviate.get_user_by_id(user_id)
        
        is_new_user = False
        user_profile = None
        
        if existing_user:
            # User exists - update their information
            logger.info(f"Existing user signing in: {email}")
            
            update_data = {
                "last_sign_in": last_sign_in or datetime.now().isoformat(),
            }
            
            # Update FCM token if provided and different
            if fcm_token and existing_user.get("fcm_token") != fcm_token:
                update_data["fcm_token"] = fcm_token
                logger.info(f"Updated FCM token for user: {email}")
            
            # Update photo URL if provided
            if photo_url:
                update_data["photo_url"] = photo_url
            
            UserModelWeaviate.update_user(user_id, update_data)
            
            # Get updated user profile
            user_profile = UserModelWeaviate.get_user_by_id(user_id)
            
        else:
            # New user - create in database
            logger.info(f"New user registering: {email}")
            is_new_user = True
            
            user_data = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "photo_url": photo_url,
                "fcm_token": fcm_token,
                "has_open_request": False,
                "created_at": created_at or datetime.now().isoformat(),
                "last_sign_in": last_sign_in or datetime.now().isoformat(),
            }
            
            uuid = UserModelWeaviate.create_user(user_data)
            
            if uuid:
                user_profile = UserModelWeaviate.get_user_by_id(user_id)
            else:
                return web.json_response(
                    {"error": "Failed to create user in database"}, 
                    status=500
                )
        
        # Store active user session
        _active_users[user_id] = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "fcm_token": fcm_token,
            "synced_at": datetime.now().isoformat(),
        }
        
        logger.info(f"User sync completed for: {email} (user_id: {user_id}, new={is_new_user})")
        logger.debug(f"Active users: {len(_active_users)}")
        
        return web.json_response({
            "user_id": user_id,
            "user_profile": user_profile,
            "is_new_user": is_new_user,
            "success": True,
        })
        
    except Exception as e:
        logger.error(f"Error in user_sync: {e}", exc_info=True)
        return web.json_response(
            {"error": "Internal server error", "details": str(e)}, 
            status=500
        )
