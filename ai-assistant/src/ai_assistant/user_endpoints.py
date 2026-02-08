"""User management endpoints for sync and logout."""
import logging
from datetime import datetime, UTC
from aiohttp import web
from .weaviate_models import UserModelWeaviate
from .firestore_service import FirestoreService
from .services.user_seeding_service import UserSeedingService

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()
seeding_service = UserSeedingService(firestore_service)

# Simple in-memory session store (imported from common_endpoints)
from .common_endpoints import _sessions


async def user_sync(request: web.Request) -> web.Response:
    """Sync user with backend database.
    
    Creates new user if doesn't exist, updates existing user.
    Handles FCM token registration for push notifications.
    
    Expected JSON body:
    {
        "user_id": "firebase_uid",
        "name": "User Name",
        "email": "user@example.com",
        "photo_url": "https://...",
        "fcm_token": "fcm_device_token"
    }
    """
    try:
        body = await request.json()
        user_id = body.get("user_id")
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        # Prepare user data
        user_data = {
            "user_id": user_id,
            "name": body.get("name", ""),
            "email": body.get("email", ""),
            "photo_url": body.get("photo_url", ""),
            "fcm_token": body.get("fcm_token", ""),
            "is_service_provider": body.get("is_service_provider", False),
            "last_sign_in": datetime.now(UTC),
        }
        
        # Firestore data (exclude user_id as it's the document key)
        firestore_data = {k: v for k, v in user_data.items() if k != "user_id"}
        
        # check if user exists in Firestore
        existing_firestore_user = await firestore_service.get_user(user_id)

        if existing_firestore_user:
            # Update existing user
            await firestore_service.update_user(user_id, firestore_data)
            
            # Update Weaviate (Self-healing: create if missing)
            if UserModelWeaviate.get_user_by_id(user_id):
                UserModelWeaviate.update_user(user_id, user_data)
            else:
                user_data["created_at"] = datetime.now(UTC)
                UserModelWeaviate.create_user(user_data)
            
            logger.info(f"Updated user: {user_id}")
            status = "updated"
        else:
            # Create new user
            # 1. Seed initial data (Competencies, etc.)
            try:
                await seeding_service.seed_new_user(
                    user_id=user_id,
                    name=user_data["name"], 
                    email=user_data["email"],
                    photo_url=user_data["photo_url"]
                )
            except Exception as e:
                logger.error(f"Failed to seed data for new user {user_id}: {e}")

            # 2. Update with latest fields (FCM token, is_service_provider)
            await firestore_service.update_user(user_id, firestore_data)

            # 3. Create in Weaviate
            user_data["created_at"] = datetime.now(UTC)
            UserModelWeaviate.create_user(user_data)
            
            logger.info(f"Created new user: {user_id}")
            status = "created"

        # Prepare response
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
    
    except Exception as e:
        logger.error(f"Error in user_sync: {e}")
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)


async def user_logout(request: web.Request) -> web.Response:
    """Handle user logout.
    
    Expected JSON body:
    {
        "user_id": "firebase_uid"
    }
    """
    try:
        body = await request.json()
        user_id = body.get("user_id")
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        # Remove user from sessions
        sessions_to_remove = [sid for sid, sess in _sessions.items() if sess.get("user_id") == user_id]
        for sid in sessions_to_remove:
            del _sessions[sid]
        
        logger.info(f"User logged out: {user_id}")
        return web.json_response({"status": "logged_out"})
    
    except Exception as e:
        logger.error(f"Error in user_logout: {e}")
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)
