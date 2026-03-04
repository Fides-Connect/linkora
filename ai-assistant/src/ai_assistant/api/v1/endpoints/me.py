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
        
        updated_user = await firestore_service.update_user(user_id, body)
        if updated_user:
            # Sync to Weaviate
            try:
                UserModelWeaviate.update_user(user_id, body)
            except Exception as e:
                logger.error(f"Failed to sync user {user_id} update to Weaviate: {e}")

            return web.json_response(serialize_datetime(updated_user))
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


async def add_my_outgoing_service_requests(request: web.Request) -> web.Response:
    """POST /api/v1/me/outgoing-service-requests - Add service request IDs to user's outgoing requests."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        request_ids = body.get('request_ids', [])
        
        if not request_ids:
            return web.json_response({"error": "Missing request_ids in request body"}, status=400)
        
        if not isinstance(request_ids, list):
            return web.json_response({"error": "request_ids must be an array"}, status=400)
        
        success = await firestore_service.add_outgoing_service_requests(user_id, request_ids)
        if success:
            return web.json_response({
                "status": "added",
                "count": len(request_ids)
            })
        else:
            return web.json_response({"error": "Failed to add outgoing service requests"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_my_outgoing_service_requests: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def add_my_incoming_service_requests(request: web.Request) -> web.Response:
    """POST /api/v1/me/incoming-service-requests - Add service request IDs to user's incoming requests."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        request_ids = body.get('request_ids', [])
        
        if not request_ids:
            return web.json_response({"error": "Missing request_ids in request body"}, status=400)
        
        if not isinstance(request_ids, list):
            return web.json_response({"error": "request_ids must be an array"}, status=400)
        
        success = await firestore_service.add_incoming_service_requests(user_id, request_ids)
        if success:
            return web.json_response({
                "status": "added",
                "count": len(request_ids)
            })
        else:
            return web.json_response({"error": "Failed to add incoming service requests"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_my_incoming_service_requests: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def remove_my_outgoing_service_requests(request: web.Request) -> web.Response:
    """DELETE /api/v1/me/outgoing-service-requests - Remove service request IDs from user's outgoing requests."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        request_ids = body.get('request_ids', [])
        
        if not request_ids:
            return web.json_response({"error": "Missing request_ids in request body"}, status=400)
        
        if not isinstance(request_ids, list):
            return web.json_response({"error": "request_ids must be an array"}, status=400)
        
        success = await firestore_service.remove_outgoing_service_requests(user_id, request_ids)
        if success:
            return web.json_response({
                "status": "removed",
                "count": len(request_ids)
            })
        else:
            return web.json_response({"error": "Failed to remove outgoing service requests"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_my_outgoing_service_requests: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def remove_my_incoming_service_requests(request: web.Request) -> web.Response:
    """DELETE /api/v1/me/incoming-service-requests - Remove service request IDs from user's incoming requests."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        request_ids = body.get('request_ids', [])
        
        if not request_ids:
            return web.json_response({"error": "Missing request_ids in request body"}, status=400)
        
        if not isinstance(request_ids, list):
            return web.json_response({"error": "request_ids must be an array"}, status=400)
        
        success = await firestore_service.remove_incoming_service_requests(user_id, request_ids)
        if success:
            return web.json_response({
                "status": "removed",
                "count": len(request_ids)
            })
        else:
            return web.json_response({"error": "Failed to remove incoming service requests"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_my_incoming_service_requests: {e}")
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


async def create_my_competence(request: web.Request) -> web.Response:
    """POST /api/v1/me/competencies - Create competence for current user."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        competence = body.get('competence')
        
        if not competence or not isinstance(competence, dict) or 'title' not in competence:
            return web.json_response({
                "error": "Missing or invalid competence object. Must include 'title' field."
            }, status=400)
        
        created_competence = await firestore_service.create_competence(user_id, competence)
        if created_competence:
            # Enrich before writing to Weaviate so the vector and BM25 fields
            # (search_optimized_summary, skills_list, availability_tags) are populated.
            enricher = request.app.get("competence_enricher")
            if enricher is not None:
                try:
                    enriched = await enricher.enrich(created_competence)
                    enriched_fields = {
                        k: enriched[k]
                        for k in (
                            "skills_list",
                            "search_optimized_summary",
                            "availability_tags",
                            "availability_text",
                            "price_per_hour",
                            "category",
                        )
                        if k in enriched
                    }
                    if enriched_fields:
                        competence_id = (
                            created_competence.get("id")
                            or created_competence.get("competence_id")
                        )
                        if competence_id:
                            await firestore_service.update_competence(
                                user_id, competence_id, enriched_fields
                            )
                        created_competence = {**created_competence, **enriched_fields}
                except Exception as enr_exc:
                    logger.error(f"Competence enrichment failed (non-fatal): {enr_exc}")
            # Sync to Weaviate
            try:
                coll = get_user_collection()
                res = coll.query.fetch_objects(
                    filters=Filter.by_property("user_id").equal(user_id),
                    limit=1
                )
                if not res.objects:
                    # Self-heal: Weaviate user is missing — create it from Firestore.
                    firestore_user = await firestore_service.get_user(user_id)
                    if firestore_user:
                        firestore_user.setdefault("user_id", user_id)
                        HubSpokeIngestion.create_user(firestore_user)
                        res = coll.query.fetch_objects(
                            filters=Filter.by_property("user_id").equal(user_id),
                            limit=1
                        )
                        logger.info(f"Self-healed missing Weaviate user for {user_id}")
                if res.objects:
                    user_uuid = str(res.objects[0].uuid)
                    HubSpokeIngestion.create_competence(
                        competence_data=created_competence,
                        user_uuid=user_uuid
                    )
                else:
                    logger.error(f"Weaviate user still not found after self-heal for {user_id}")
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
        logger.warning(f"Validation error in create_my_competence: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_my_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_my_competence(request: web.Request) -> web.Response:
    """PATCH /api/v1/me/competencies/{competence_id} - Update a competence."""
    try:
        user_id = await get_current_user_id(request)
        competence_id = request.match_info['competence_id']
        body = await request.json()
        
        # Check if competence exists
        competence_data = await firestore_service.get_competence(user_id, competence_id)
        if not competence_data:
            return web.json_response({"error": "Competence not found"}, status=404)
        
        updated_competence = await firestore_service.update_competence(user_id, competence_id, body)
        if updated_competence:
            # Sync to Weaviate: remove old entry then re-create with the full
            # updated competence dict (preserves all enriched fields).
            try:
                competence_data = await firestore_service.get_competence(user_id, competence_id)
                if competence_data:
                    HubSpokeIngestion.remove_competence_by_firestore_id(competence_id)
                    coll = get_user_collection()
                    res = coll.query.fetch_objects(
                        filters=Filter.by_property("user_id").equal(user_id),
                        limit=1,
                    )
                    if res.objects:
                        user_uuid = str(res.objects[0].uuid)
                        HubSpokeIngestion.create_competence(
                            competence_data=competence_data,
                            user_uuid=user_uuid,
                        )
            except Exception as e:
                logger.error(f"Failed to sync competence {competence_id} update to Weaviate: {e}")
            
            return web.json_response(serialize_datetime(updated_competence))
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


# ── App settings ─────────────────────────────────────────────────────────────

_ALLOWED_SETTINGS_KEYS: frozenset[str] = frozenset({'language', 'notifications_enabled'})
_DEFAULT_SETTINGS: dict = {'language': 'en', 'notifications_enabled': True}


async def get_settings(request: web.Request) -> web.Response:
    """GET /api/v1/me/settings - Get current user's app settings."""
    try:
        user_id = await get_current_user_id(request)
        user = await firestore_service.get_user(user_id)
        if not user:
            return web.json_response({'error': 'User not found'}, status=404)
        raw_settings = user.get('user_app_settings')
        stored: dict = raw_settings if isinstance(raw_settings, dict) else {}
        # Coerce language: must be a supported string, else fall back to default.
        lang_raw = stored.get('language')
        if isinstance(lang_raw, str):
            normalized_lang = lang_raw.strip().lower()
            language = normalized_lang if normalized_lang in {'en', 'de'} else _DEFAULT_SETTINGS['language']
        else:
            language = _DEFAULT_SETTINGS['language']
        # Coerce notifications_enabled: must be bool, else fall back to default.
        notif_raw = stored.get('notifications_enabled')
        notifications_enabled = notif_raw if isinstance(notif_raw, bool) else _DEFAULT_SETTINGS['notifications_enabled']
        return web.json_response({
            'language': language,
            'notifications_enabled': notifications_enabled,
        })
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error in get_settings: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def update_settings(request: web.Request) -> web.Response:
    """PATCH /api/v1/me/settings - Update current user's app settings."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        if not isinstance(body, dict):
            return web.json_response({'error': 'Request body must be a JSON object'}, status=400)
        user = await firestore_service.get_user(user_id)
        if not user:
            return web.json_response({'error': 'User not found'}, status=404)

        # Normalize and validate language; only 'en' and 'de' are supported.
        if 'language' in body:
            if not isinstance(body['language'], str):
                return web.json_response(
                    {'error': "Field 'language' must be a string"}, status=400
                )
            normalized_lang = body['language'].strip().lower()
            if normalized_lang not in {'en', 'de'}:
                return web.json_response(
                    {'error': "Field 'language' must be one of: 'en', 'de'"}, status=400
                )
            body['language'] = normalized_lang
        if 'notifications_enabled' in body and not isinstance(body['notifications_enabled'], bool):
            return web.json_response(
                {'error': "Field 'notifications_enabled' must be a boolean"}, status=400
            )

        # Guard against corrupt/missing user_app_settings in Firestore.
        existing_settings = user.get('user_app_settings') or {}
        if not isinstance(existing_settings, dict):
            logger.warning(
                "User %s has non-dict user_app_settings (%r); resetting to empty dict",
                user_id, type(existing_settings),
            )
            existing_settings = {}

        # Merge only the allowed keys into the existing settings dict.
        merged: dict = dict(existing_settings)
        updated = False
        for key in _ALLOWED_SETTINGS_KEYS:
            if key in body:
                merged[key] = body[key]
                updated = True

        if updated:
            await firestore_service.update_user(user_id, {'user_app_settings': merged})

        # Sanitize response values to match get_settings behavior:
        # - language must be one of {'en', 'de'}, otherwise fall back to default
        # - notifications_enabled must be a boolean, otherwise fall back to default
        language = merged.get('language', _DEFAULT_SETTINGS['language'])
        if not isinstance(language, str) or language not in {'en', 'de'}:
            language = _DEFAULT_SETTINGS['language']

        notifications_enabled = merged.get(
            'notifications_enabled', _DEFAULT_SETTINGS['notifications_enabled']
        )
        if not isinstance(notifications_enabled, bool):
            notifications_enabled = _DEFAULT_SETTINGS['notifications_enabled']

        return web.json_response({
            'language': language,
            'notifications_enabled': notifications_enabled,
        })
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error in update_settings: {e}')
        return web.json_response({'error': str(e)}, status=500)


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
