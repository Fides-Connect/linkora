"""
/api/v1/auth/* endpoints
Authentication and user session management endpoints.
"""
import logging
from datetime import datetime, UTC
from uuid import uuid4
from aiohttp import web
from pydantic import ValidationError
from firebase_admin import auth as firebase_auth

from ai_assistant.firestore_service import FirestoreService
from ai_assistant.weaviate_models import UserModelWeaviate
from ai_assistant.services.user_seeding_service import UserSeedingService
from ai_assistant.common_endpoints import _sessions

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()
seeding_service = UserSeedingService(firestore_service)


async def sign_in_google(request: web.Request) -> web.Response:
    """POST /api/v1/auth/sign-in-google - Handle user sign-in via Firebase ID token.
    
    Expects a JSON body with an 'id_token' field.
    Returns user information if the token is valid.
    """
    try:
        # Parse the request body
        body = await request.json()
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)

        # Verify the Firebase ID token
        decoded_token = firebase_auth.verify_id_token(token)

        # Extract user information
        user_id = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")

        # Create session id and store session
        session_id = str(uuid4())
        _sessions[session_id] = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "created_at": datetime.now().isoformat(),
        }

        logger.info(f"User signed in: {user_id}")

        # Return user information
        return web.json_response({
            "session_id": session_id,
            "user_id": user_id,
            "email": email,
            "name": name,
            "is_valid": True
        })

    except ValueError as e:
        # Token is invalid
        return web.json_response({
            "error": "Invalid token",
            "details": str(e)
        }, status=401)

    except Exception as e:
        # Handle unexpected errors
        return web.json_response({
            "error": "Internal server error",
            "details": str(e)
        }, status=500)


async def user_sync(request: web.Request) -> web.Response:
    """POST /api/v1/auth/sync - Sync user with backend database.
    
    Creates new user if doesn't exist, updates existing user.
    Handles FCM token registration for push notifications.
    """
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        user_data = {
            "user_id": user_id,
            "name": body.get("name", ""),
            "email": body.get("email", ""),
            "photo_url": body.get("photo_url", ""),
            "fcm_token": body.get("fcm_token", ""),
            "is_service_provider": body.get("is_service_provider", False),
            "last_sign_in": datetime.now(UTC),
        }
        
        existing_firestore_user = await firestore_service.get_user(user_id)
        if existing_firestore_user:
            # Remove user_id from update data (it's the document key)
            update_data = {k: v for k, v in user_data.items() if k != "user_id"}
            if not await firestore_service.update_user(user_id, update_data):
                return web.json_response({
                    "error": "Failed to update Firestore user"
                }, status=500)
            
            if UserModelWeaviate.get_user_by_id(user_id):
                if not UserModelWeaviate.update_user(user_id, user_data):
                    return web.json_response({
                        "error": "Failed to update Weaviate user"
                    }, status=500)
            else:
                user_data["created_at"] = datetime.now(UTC)
                if not UserModelWeaviate.create_user(user_data):
                    return web.json_response({
                        "error": "Failed to self-heal/create Weaviate user"
                    }, status=500)
            
            logger.info(f"Updated user: {user_id}")
            status = "updated"
        else:
            try:
                await seeding_service.seed_new_user(
                    user_id=user_id,
                    name=user_data["name"],
                    email=user_data["email"],
                    photo_url=user_data["photo_url"]
                )
                
                # Only update FCM token and last_sign_in after seeding
                # Don't overwrite template data with empty values
                update_data = {
                    "fcm_token": user_data["fcm_token"],
                    "last_sign_in": user_data["last_sign_in"]
                }
                await firestore_service.update_user(user_id, update_data)
                
            except Exception as e:
                logger.error(f"Failed to seed data for new user {user_id}: {e}")
                return web.json_response({
                    "error": f"Failed to seed user: {str(e)}"
                }, status=500)
            
            user_data["created_at"] = datetime.now(UTC)
            if not UserModelWeaviate.create_user(user_data):
                return web.json_response({
                    "error": "Failed to create Weaviate user"
                }, status=500)
            
            logger.info(f"Created new user: {user_id}")
            status = "created"
        
        return web.json_response({
            "status": status,
            "user": {
                "user_id": user_id,
                "name": user_data["name"],
                "email": user_data["email"],
                "photo_url": user_data["photo_url"],
                "fcm_token": user_data["fcm_token"],
            }
        })
    except ValidationError as e:
        logger.warning(f"Validation error in user_sync: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except Exception as e:
        logger.error(f"Error in user_sync: {e}")
        return web.json_response({
            "error": "Internal server error",
            "details": str(e)
        }, status=500)


async def user_logout(request: web.Request) -> web.Response:
    """POST /api/v1/auth/logout - Handle user logout."""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        sessions_to_remove = [
            sid for sid, sess in _sessions.items()
            if sess.get("user_id") == user_id
        ]
        for sid in sessions_to_remove:
            del _sessions[sid]
        
        logger.info(f"User logged out: {user_id}")
        return web.json_response({"status": "logged_out"})
    except Exception as e:
        logger.error(f"Error in user_logout: {e}")
        return web.json_response({
            "error": "Internal server error",
            "details": str(e)
        }, status=500)
