"""
/api/v1/auth/* endpoints
Authentication and user session management endpoints.
"""
import logging
from datetime import datetime, timedelta, UTC
from uuid import uuid4
from aiohttp import web
from pydantic import ValidationError
from firebase_admin import auth as firebase_auth

from ai_assistant.firestore_service import FirestoreService
from ai_assistant.hub_spoke_ingestion import HubSpokeIngestion
from ai_assistant.weaviate_models import UserModelWeaviate
from ai_assistant.services.user_seeding_service import UserSeedingService

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

        # Verify the Firebase ID token, including revocation check.
        # Requires the runtime SA to have firebaseauth.users.get
        # (custom role: projects/linkora-dev/roles/firebaseAuthTokenChecker).
        decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)

        # Extract user information
        user_id = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")

        logger.info(f"User signed in: {user_id}")

        # Return user information
        return web.json_response({
            "user_id": user_id,
            "email": email,
            "name": name,
            "is_valid": True
        })

    except firebase_auth.RevokedIdTokenError:
        return web.json_response({
            "error": "Token has been revoked",
        }, status=401)

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
            # Session-only update — never overwrite backend-managed fields like
            # is_service_provider (set by AI onboarding / PATCH /me, not by the
            # client, which always defaults to False).
            # Also: never overwrite an existing FCM token with an empty value —
            # prevents a race on app startup where getToken() hasn't resolved yet.
            session_update = {
                "email": user_data["email"],
                "last_sign_in": user_data["last_sign_in"],
            }
            # Never overwrite an existing name or photo with an empty value —
            # prevents a race on app startup where Firebase Auth hasn't fully
            # resolved the user profile yet (displayName briefly null).
            if user_data["name"]:
                session_update["name"] = user_data["name"]
            if user_data["photo_url"]:
                session_update["photo_url"] = user_data["photo_url"]
            if user_data["fcm_token"]:
                session_update["fcm_token"] = user_data["fcm_token"]
            updated_user = await firestore_service.update_user(user_id, session_update)
            if not updated_user:
                return web.json_response({
                    "error": "Failed to update Firestore user"
                }, status=500)

            # Keep the hub-spoke Weaviate User node in sync with Firestore's
            # is_service_provider so provider-search filters stay correct.
            is_sp = existing_firestore_user.get("is_service_provider", False)

            # Self-healing guard: if Firestore says False but the user already
            # has competencies (e.g. added via dev script or a previous session
            # where the Firestore write was missed), auto-upgrade to True so
            # they appear in provider searches without manual intervention.
            if not is_sp:
                try:
                    competencies = await firestore_service.get_competencies(user_id)
                    if competencies:
                        is_sp = True
                        await firestore_service.update_user(user_id, {"is_service_provider": True})
                        logger.info(
                            "user_sync: auto-upgraded is_service_provider=True for %s "
                            "(has %d competencies but flag was False)",
                            user_id,
                            len(competencies),
                        )
                except Exception as upgrade_exc:
                    logger.error(
                        "user_sync: failed to auto-upgrade is_service_provider for %s: %s",
                        user_id,
                        upgrade_exc,
                    )

            hub_updated = HubSpokeIngestion.update_user_hub_properties(
                user_id, {"is_service_provider": is_sp}
            )
            if not hub_updated:
                # Hub node is missing — self-heal by recreating it from Firestore
                # so this user appears in provider-search results immediately.
                logger.warning(
                    "user_sync: Weaviate hub node missing for user_id=%s — self-healing",
                    user_id,
                )
                try:
                    user_data_for_weaviate = {**existing_firestore_user, "user_id": user_id}
                    HubSpokeIngestion.create_user(user_data_for_weaviate)
                    # Re-sync all competencies so provider-search cross-references exist.
                    all_competencies = await firestore_service.get_competencies(user_id)
                    if all_competencies:
                        from ai_assistant.firestore_schemas import derive_availability_tags
                        for comp in all_competencies:
                            cid = comp.get("competence_id")
                            if cid:
                                avail_docs = await firestore_service.get_availability_times(
                                    user_id, competence_id=cid
                                )
                                if avail_docs:
                                    comp["availability_tags"] = derive_availability_tags(avail_docs[0])
                        HubSpokeIngestion.update_competencies_by_user_id(user_id, all_competencies)
                    logger.info("user_sync: self-heal complete for user_id=%s", user_id)
                except Exception as heal_exc:
                    logger.error(
                        "user_sync: self-heal failed for user_id=%s: %s", user_id, heal_exc
                    )

            if UserModelWeaviate.get_user_by_id(user_id):
                # Ensure the Firestore-authoritative is_service_provider value
                # (not the client-sent default=False) is written to Weaviate.
                user_data["is_service_provider"] = is_sp
                if not UserModelWeaviate.update_user(user_id, user_data):
                    # A6: Weaviate outage must not fail login — log and continue.
                    logger.warning(
                        "user_sync: Weaviate update_user failed for %s — "
                        "search index may be stale; will self-heal on next login",
                        user_id,
                    )
            else:
                if not UserModelWeaviate.create_user(user_data):
                    # A6: Weaviate outage must not fail login — log and continue.
                    logger.warning(
                        "user_sync: Weaviate create_user failed for %s — "
                        "search index node missing; will retry on next login",
                        user_id,
                    )

            # B10: Detect mid-onboarding abandonment: user is marked as provider
            # but has zero competencies (closed app before completing onboarding).
            onboarding_incomplete = False
            if is_sp:
                try:
                    existing_comps = await firestore_service.get_competencies(user_id)
                    if len(existing_comps) == 0:
                        onboarding_incomplete = True
                        logger.info(
                            "user_sync: user %s is a provider with 0 competencies — "
                            "onboarding_incomplete=True in response",
                            user_id,
                        )
                except Exception as comp_check_exc:
                    logger.warning(
                        "user_sync: could not check competencies for %s: %s",
                        user_id, comp_check_exc,
                    )

            logger.info(f"Updated user: {user_id}")
            status = "updated"
        else:
            try:
                await seeding_service.seed_new_user(
                    user_id=user_id,
                    name=user_data["name"],
                    email=user_data["email"],
                    photo_url=user_data["photo_url"],
                    enricher=request.app.get("competence_enricher"),
                )
                
                # Only update FCM token and last_sign_in after seeding
                # Don't overwrite template data with empty values.
                # Initialise last_time_asked_being_provider 60 days ago so
                # the first completed conversation triggers the provider pitch.
                update_data = {
                    "fcm_token": user_data["fcm_token"],
                    "last_sign_in": user_data["last_sign_in"],
                    "last_time_asked_being_provider": datetime.now(UTC) - timedelta(days=60),
                }
                await firestore_service.update_user(user_id, update_data)
                
            except Exception as e:
                logger.error(f"Failed to seed data for new user {user_id}: {e}")
                return web.json_response({
                    "error": f"Failed to seed user: {str(e)}"
                }, status=500)
            
            logger.info(f"Created new user: {user_id}")
            status = "created"
            onboarding_incomplete = False  # new users always start clean
        
        return web.json_response({
            "status": status,
            "onboarding_incomplete": onboarding_incomplete,
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
        
        logger.info(f"User logged out: {user_id}")
        return web.json_response({"status": "logged_out"})
    except Exception as e:
        logger.error(f"Error in user_logout: {e}")
        return web.json_response({
            "error": "Internal server error",
            "details": str(e)
        }, status=500)
