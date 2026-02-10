import logging
from datetime import datetime, UTC
from aiohttp import web
from firebase_admin import auth
from pydantic import ValidationError
from .firestore_service import FirestoreService

# Weaviate imports
from .weaviate_models import UserModelWeaviate
from .hub_spoke_ingestion import HubSpokeIngestion
from .hub_spoke_schema import get_user_collection
from weaviate.classes.query import Filter

from .services.user_seeding_service import UserSeedingService
from .common_endpoints import _sessions

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()
seeding_service = UserSeedingService(firestore_service)

def serialize_datetime(obj):
    """Recursively serialize datetime objects to ISO format strings."""
    if isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj

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

async def get_service_requests(request: web.Request) -> web.Response:
    """GET /service_requests"""
    try:
        user_id = await get_current_user_id(request)
        requests = await firestore_service.get_requests(user_id)
        # Convert datetime objects to string for JSON serialization
        requests = serialize_datetime(requests)
        return web.json_response(requests)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_service_requests: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def add_service_request(request: web.Request) -> web.Response:
    """POST /service_requests"""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        
        # Enforce seeker_user_id to be the authenticated user
        body['seeker_user_id'] = user_id
        
        service_request_id = await firestore_service.add_service_request(body)
        if service_request_id:
            return web.json_response({"service_request_id": service_request_id, "status": "created"}, status=201)
        else:
            return web.json_response({"error": "Failed to create service request"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in add_service_request: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_service_request: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def update_service_request_status(request: web.Request) -> web.Response:
    """PUT /service_requests/{service_request_id}/status"""
    try:
        user_id = await get_current_user_id(request) # Auth check
        service_request_id = request.match_info['service_request_id']
        body = await request.json()
        status = body.get('status')
        
        if not status:
            return web.json_response({"error": "Missing status"}, status=400)
            
        # Check if user is allowed to update this request (owner or provider)
        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)
            
        seeker_id = service_request.get('seeker_user_id')
        provider_id = service_request.get('selected_provider_user_id')
        
        if user_id != seeker_id and user_id != provider_id:
             return web.json_response({"error": "Unauthorized to update this service request"}, status=403)
        
        success = await firestore_service.update_request_status(service_request_id, status)
        if success:
            return web.json_response({"status": "updated"})
        else:
            return web.json_response({"error": "Failed to update service request status"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_service_request_status: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def update_service_request(request: web.Request) -> web.Response:
    """PUT /service_requests/{service_request_id} - Full update of service request.
    
    Authorization: Only the creator (seeker) can update the service request.
    """
    try:
        user_id = await get_current_user_id(request)
        service_request_id = request.match_info['service_request_id']
        body = await request.json()
        
        # Check authorization - only creator can update
        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)
        
        seeker_id = service_request.get('seeker_user_id')
        if user_id != seeker_id:
            return web.json_response({"error": "Forbidden: Only the creator can update this service request"}, status=403)
        
        success = await firestore_service.update_service_request(service_request_id, body)
        if success:
            return web.json_response({"status": "updated"})
        else:
            return web.json_response({"error": "Failed to update service request"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in update_service_request: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_service_request: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def delete_service_request(request: web.Request) -> web.Response:
    """DELETE /service_requests/{service_request_id} - Delete service request and all subcollections.
    
    Authorization: Only the creator (seeker) can delete the service request.
    """
    try:
        user_id = await get_current_user_id(request)
        service_request_id = request.match_info['service_request_id']
        
        # Check authorization - only creator can delete
        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)
        
        seeker_id = service_request.get('seeker_user_id')
        if user_id != seeker_id:
            return web.json_response({"error": "Forbidden: Only the creator can delete this service request"}, status=403)
        
        success = await firestore_service.delete_service_request(service_request_id)
        if success:
            return web.json_response({"status": "deleted"})
        else:
            return web.json_response({"error": "Failed to delete service request"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_service_request: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def get_favorites(request: web.Request) -> web.Response:
    """GET /favorites"""
    try:
        user_id = await get_current_user_id(request)
        favorites = await firestore_service.get_favorites(user_id)
        # Handle datetime serialization
        favorites = serialize_datetime(favorites)
        return web.json_response(favorites)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_favorites: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def add_favorite(request: web.Request) -> web.Response:
    """POST /favorites/{user_id}"""
    try:
        user_id = await get_current_user_id(request)
        favorite_user_id = request.match_info['user_id']
        
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
        logger.error(f"Error in add_favorite: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def remove_favorite(request: web.Request) -> web.Response:
    """DELETE /favorites/{user_id}"""
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
        logger.error(f"Error in remove_favorite: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def get_user(request: web.Request) -> web.Response:
    """GET /user"""
    try:
        user_id = await get_current_user_id(request)
        user = await firestore_service.get_user(user_id)
        
        if user:
            # Handle datetime serialization
            user = serialize_datetime(user)
            return web.json_response(user)
        
        # If not found, return 404
        return web.json_response({"error": "User not found"}, status=404)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_user: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def update_user(request: web.Request) -> web.Response:
    """PUT /user"""
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
                # We reuse the body, assuming fields match or UserModelWeaviate handles it safely
                UserModelWeaviate.update_user(user_id, body)
            except Exception as e:
                logger.error(f"Failed to sync user {user_id} update to Weaviate: {e}")

            return web.json_response({"status": "updated"})
        else:
             return web.json_response({"error": "Failed to update user"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in update_user: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_user: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def add_user(request: web.Request) -> web.Response:
    """POST /users - Create a new user."""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        
        success = await firestore_service.add_user(user_id, body)
        if success:
            # Sync to Weaviate
            try:
                body['user_id'] = user_id
                body['created_at'] = datetime.now(UTC)
                UserModelWeaviate.add_user(body)
            except Exception as e:
                logger.error(f"Failed to sync user {user_id} to Weaviate: {e}")
            
            return web.json_response({"status": "created", "user_id": user_id}, status=201)
        else:
            return web.json_response({"error": "Failed to create user"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in add_user: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_user: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def delete_user(request: web.Request) -> web.Response:
    """DELETE /users/{user_id} - Delete a user and all subcollections.
    
    Authorization: Only the user themselves can delete their account.
    """
    try:
        authenticated_user_id = await get_current_user_id(request)
        user_id = request.match_info.get('user_id')
        
        # Authorization check: user can only delete themselves
        if authenticated_user_id != user_id:
            return web.json_response({"error": "Forbidden: You can only delete your own account"}, status=403)
        
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

async def add_competence(request: web.Request) -> web.Response:
    """POST /user/competencies"""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        competence = body.get('competence')
        
        if not competence or not isinstance(competence, dict) or 'title' not in competence:
            return web.json_response({"error": "Missing or invalid competence object. Must include 'title' field."}, status=400)
            
        created_competence = await firestore_service.add_competence(user_id, competence)
        if created_competence:
            # Sync to Weaviate
            try:
                # Need Weaviate User UUID
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
                # Handle datetime serialization
                user = serialize_datetime(user)
                return web.json_response(user)
            return web.json_response({"error": "Failed to fetch updated user"}, status=500)
        else:
             return web.json_response({"error": "Failed to add competence"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in add_competence: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def remove_competence(request: web.Request) -> web.Response:
    """DELETE /user/competencies/{competence_id}"""
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
                # Handle datetime serialization
                user = serialize_datetime(user)
                return web.json_response(user)
            return web.json_response({"error": "Failed to fetch updated user"}, status=500)
        else:
             return web.json_response({"error": "Failed to remove competence"}, status=500)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def update_competence(request: web.Request) -> web.Response:
    """PUT /user/competencies/{competence_id} - Update a competence.
    
    Authorization: Only the owner can update their competence.
    """
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
                # Update in Weaviate by fetching the updated data
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
        logger.warning(f"Validation error in update_competence: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_competence: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def get_other_user(request: web.Request) -> web.Response:
    """GET /users/{user_id}/user"""
    try:
        # We might require auth here too, to prevent scraping
        await get_current_user_id(request)
        
        target_user_id = request.match_info['user_id']
        user = await firestore_service.get_user(target_user_id)
        
        if user:
            # Handle datetime serialization
            user = serialize_datetime(user)
            return web.json_response(user)
        
        return web.json_response({"error": "User not found"}, status=404)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_other_user: {e}")
        return web.json_response({"error": str(e)}, status=500)

# --- Review Endpoints ---

async def add_review(request: web.Request) -> web.Response:
    """Create a new review.
    
    POST /reviews
    Body: {
        "service_request_id": "service_request_xyz",
        "user_id": "user_abc",
        "reviewer_user_id": "user_def",
        "rating": 5,
        "positive_feedback": ["Punctual", "Professional"],
        "negative_feedback": [],
        "comment": "Optional text comment"
    }
    """
    try:
        reviewer_user_id = await get_current_user_id(request)
        body = await request.json()
        
        # Validate required fields
        required_fields = ['service_request_id', 'user_id', 'rating']
        for field in required_fields:
            if field not in body:
                return web.json_response({"error": f"Missing required field: {field}"}, status=400)
        
        # Validate rating
        rating = body.get('rating')
        if not isinstance(rating, (int, float)) or rating < 1 | rating > 5:
            return web.json_response({"error": "Rating must be between 1 and 5"}, status=400)
        
        from datetime import datetime
        review_data = {
            'service_request_id': body['service_request_id'],
            'user_id': body['user_id'],
            'reviewer_user_id': reviewer_user_id,  # Use authenticated user
            'rating': rating,
            'positive_feedback': body.get('positive_feedback', []),
            'negative_feedback': body.get('negative_feedback', []),
            'comment': body.get('comment', ''),
            'created_at': datetime.utcnow()
        }
        
        review_id = await firestore_service.create_review(review_data)
        
        if not review_id:
            return web.json_response({"error": "Failed to create review"}, status=500)
        
        return web.json_response({
            "review_id": review_id,
            "status": "created"
        }, status=201)
    except ValidationError as e:
        logger.warning(f"Validation error in add_review: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_review(request: web.Request) -> web.Response:
    """Get a review by ID.
    
    GET /reviews/{review_id}
    """
    try:
        await get_current_user_id(request)
        review_id = request.match_info.get('review_id')
        
        review = await firestore_service.get_review(review_id)
        
        if not review:
            return web.json_response({"error": "Review not found"}, status=404)
        
        # Handle datetime serialization
        review = serialize_datetime(review)
        return web.json_response(review)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_reviews_for_user(request: web.Request) -> web.Response:
    """Get all reviews for a user (as reviewee).
    
    GET /reviews/user/{user_id}
    """
    try:
        await get_current_user_id(request)
        user_id = request.match_info.get('user_id')
        
        reviews = await firestore_service.get_reviews_by_user(user_id)
        
        # Handle datetime serialization
        reviews = serialize_datetime(reviews)
        return web.json_response({"reviews": reviews})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reviews for user: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_reviews_by_reviewer(request: web.Request) -> web.Response:
    """Get all reviews written by a reviewer.
    
    GET /reviews/reviewer/{reviewer_user_id}
    """
    try:
        await get_current_user_id(request)
        reviewer_user_id = request.match_info.get('reviewer_user_id')
        
        reviews = await firestore_service.get_reviews_by_reviewer(reviewer_user_id)
        
        # Handle datetime serialization
        reviews = serialize_datetime(reviews)
        return web.json_response({"reviews": reviews})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reviews by reviewer: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_reviews_for_service_request(request: web.Request) -> web.Response:
    """Get all reviews for a service request.
    
    GET /reviews/service_request/{service_request_id}
    """
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info.get('service_request_id')
        
        reviews = await firestore_service.get_reviews_by_request(service_request_id)
        
        # Handle datetime serialization
        reviews = serialize_datetime(reviews)
        return web.json_response({"reviews": reviews})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reviews for service request: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def update_review(request: web.Request) -> web.Response:
    """Update a review.
    
    PATCH /reviews/{review_id}
    Body: {
        "rating": 4,
        "positive_feedback": ["Updated"],
        "comment": "Updated comment"
    }
    """
    try:
        await get_current_user_id(request)
        review_id = request.match_info.get('review_id')
        body = await request.json()
        
        # Check if review exists
        review = await firestore_service.get_review(review_id)
        if not review:
            return web.json_response({"error": "Review not found"}, status=404)
        
        # Validate rating if provided
        if 'rating' in body:
            rating = body['rating']
            if not isinstance(rating, (int, float)) | rating < 1 | rating > 5:
                return web.json_response({"error": "Rating must be between 1 and 5"}, status=400)
        
        success = await firestore_service.update_review(review_id, body)
        
        if not success:
            return web.json_response({"error": "Failed to update review"}, status=500)
        
        return web.json_response({"status": "updated"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_review(request: web.Request) -> web.Response:
    """Delete a review.
    
    DELETE /reviews/{review_id}
    """
    try:
        await get_current_user_id(request)
        review_id = request.match_info.get('review_id')
        
        success = await firestore_service.delete_review(review_id)
        
        if not success:
            return web.json_response({"error": "Failed to delete review"}, status=500)
        
        return web.json_response({"status": "deleted"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


# --- Chat Endpoints ---

async def create_chat(request: web.Request) -> web.Response:
    """Create a new chat.
    
    POST /provider_candidates/{provider_candidate_id}/chats
    Body: {
        "title": "Chat title",
        "service_request_id": "service_request_xyz"
    }
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        body = await request.json()
        
        # Validate required fields
        required_fields = ['title', 'service_request_id']
        for field in required_fields:
            if field not in body:
                return web.json_response({"error": f"Missing required field: {field}"}, status=400)
        
        chat_data = {
            'title': body['title'],
            'service_request_id': body['service_request_id']
        }
        
        chat_id = await firestore_service.create_chat(provider_candidate_id, chat_data)
        
        if not chat_id:
            return web.json_response({"error": "Failed to create chat"}, status=500)
        
        return web.json_response({
            "chat_id": chat_id,
            "provider_candidate_id": provider_candidate_id,
            "status": "created"
        }, status=201)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chat(request: web.Request) -> web.Response:
    """Get a chat by ID.
    
    GET /provider_candidates/{provider_candidate_id}/chats/{chat_id}
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        
        chat = await firestore_service.get_chat(provider_candidate_id, chat_id)
        
        if not chat:
            return web.json_response({"error": "Chat not found"}, status=404)
        
        # Handle datetime serialization
        chat = serialize_datetime(chat)
        return web.json_response(chat)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chats_for_service_request(request: web.Request) -> web.Response:
    """Get all chats for a service request.
    
    GET /service_requests/{service_request_id}/chats
    """
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info.get('service_request_id')
        
        chats = await firestore_service.get_chats_by_request(service_request_id)
        
        # Handle datetime serialization
        chats = serialize_datetime(chats)
        return web.json_response({"chats": chats})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chats for service request: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chats_for_provider_candidate(request: web.Request) -> web.Response:
    """Get all chats for a specific provider_candidate.
    
    GET /provider_candidates/{provider_candidate_id}/chats
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        
        # We need the service_request_id from query params
        service_request_id = request.query.get('service_request_id')
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        chats = await firestore_service.get_chats_by_provider_candidate(provider_candidate_id, service_request_id)
        
        # Handle datetime serialization
        chats = serialize_datetime(chats)
        return web.json_response({"chats": chats})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chats for provider_candidate: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def update_chat(request: web.Request) -> web.Response:
    """Update a chat.
    
    PATCH /provider_candidates/{provider_candidate_id}/chats/{chat_id}
    Query params: service_request_id
    Body: {
        "title": "Updated title"
    }
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        # Check if chat exists
        chat = await firestore_service.get_chat(provider_candidate_id, chat_id, service_request_id)
        if not chat:
            return web.json_response({"error": "Chat not found"}, status=404)
        
        body = await request.json()
        
        success = await firestore_service.update_chat(provider_candidate_id, chat_id, service_request_id, body)
        
        if not success:
            return web.json_response({"error": "Failed to update chat"}, status=500)
        
        return web.json_response({"status": "updated"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_chat(request: web.Request) -> web.Response:
    """Delete a chat and all its messages.
    
    DELETE /provider_candidates/{provider_candidate_id}/chats/{chat_id}
    Query params: service_request_id
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        success = await firestore_service.delete_chat(provider_candidate_id, chat_id, service_request_id)
        
        if not success:
            return web.json_response({"error": "Failed to delete chat"}, status=500)
        
        return web.json_response({"status": "deleted"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


# --- Chat Message Endpoints ---

async def create_chat_message(request: web.Request) -> web.Response:
    """Create a new chat message.
    
    POST /provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages
    Query params: service_request_id
    Body: {
        "receiver_user_id": "user_def",
        "message": "Hello!"
    }
    """
    try:
        sender_user_id = await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        body = await request.json()
        
        # Validate required fields
        required_fields = ['receiver_user_id', 'message']
        for field in required_fields:
            if field not in body:
                return web.json_response({"error": f"Missing required field: {field}"}, status=400)
        
        message_data = {
            'sender_user_id': sender_user_id,  # Use authenticated user
            'receiver_user_id': body['receiver_user_id'],
            'message': body['message']
        }
        
        message_id = await firestore_service.create_chat_message(provider_candidate_id, chat_id, service_request_id, message_data)
        
        if not message_id:
            return web.json_response({"error": "Failed to create message"}, status=500)
        
        return web.json_response({
            "chat_message_id": message_id,
            "status": "created"
        }, status=201)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chat_messages(request: web.Request) -> web.Response:
    """Get all messages for a chat.
    
    GET /provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages?service_request_id=xxx&limit=100
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        # Get limit from query params
        limit = int(request.query.get('limit', 100))
        
        messages = await firestore_service.get_chat_messages(provider_candidate_id, chat_id, service_request_id, limit=limit)
        
        # Handle datetime serialization
        messages = serialize_datetime(messages)
        return web.json_response({"messages": messages})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chat_message(request: web.Request) -> web.Response:
    """Get a specific chat message.
    
    GET /provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages/{chat_message_id}?service_request_id=xxx
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        message_id = request.match_info.get('chat_message_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        message = await firestore_service.get_chat_message(provider_candidate_id, chat_id, service_request_id, message_id)
        
        if not message:
            return web.json_response({"error": "Message not found"}, status=404)
        
        # Handle datetime serialization
        message = serialize_datetime(message)
        return web.json_response(message)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def update_chat_message(request: web.Request) -> web.Response:
    """Update a chat message.
    
    PATCH /provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages/{chat_message_id}?service_request_id=xxx
    Body: {
        "message": "Updated message text"
    }
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        message_id = request.match_info.get('chat_message_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        # Check if message exists
        message = await firestore_service.get_chat_message(provider_candidate_id, chat_id, service_request_id, message_id)
        if not message:
            return web.json_response({"error": "Message not found"}, status=404)
        
        body = await request.json()
        
        success = await firestore_service.update_chat_message(provider_candidate_id, chat_id, service_request_id, message_id, body)
        
        if not success:
            return web.json_response({"error": "Failed to update message"}, status=500)
        
        return web.json_response({"status": "updated"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_chat_message(request: web.Request) -> web.Response:
    """Delete a chat message.
    
    DELETE /provider_candidates/{provider_candidate_id}/chats/{chat_id}/chat_messages/{chat_message_id}?service_request_id=xxx
    """
    try:
        await get_current_user_id(request)
        provider_candidate_id = request.match_info.get('provider_candidate_id')
        chat_id = request.match_info.get('chat_id')
        message_id = request.match_info.get('chat_message_id')
        service_request_id = request.query.get('service_request_id')
        
        if not service_request_id:
            return web.json_response({"error": "Missing service_request_id query parameter"}, status=400)
        
        success = await firestore_service.delete_chat_message(provider_candidate_id, chat_id, service_request_id, message_id)
        
        if not success:
            return web.json_response({"error": "Failed to delete message"}, status=500)
        
        return web.json_response({"status": "deleted"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)

# --- User Sync and Logout Endpoints ---

async def user_sync(request: web.Request) -> web.Response:
    """Sync user with backend database.
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
            if not await firestore_service.update_user(user_id, user_data):
                return web.json_response({"error": "Failed to update Firestore user"}, status=500)
            if UserModelWeaviate.get_user_by_id(user_id):
                if not UserModelWeaviate.update_user(user_id, user_data):
                    return web.json_response({"error": "Failed to update Weaviate user"}, status=500)
            else:
                user_data["created_at"] = datetime.now(UTC)
                if not UserModelWeaviate.add_user(user_data):
                    return web.json_response({"error": "Failed to self-heal/create Weaviate user"}, status=500)
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
            except Exception as e:
                logger.error(f"Failed to seed data for new user {user_id}: {e}")
            if not await firestore_service.update_user(user_id, user_data):
                return web.json_response({"error": "Failed to create/update Firestore user"}, status=500)
            user_data["created_at"] = datetime.now(UTC)
            if not UserModelWeaviate.add_user(user_data):
                return web.json_response({"error": "Failed to create Weaviate user"}, status=500)
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
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)

async def user_logout(request: web.Request) -> web.Response:
    """Handle user logout."""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        sessions_to_remove = [sid for sid, sess in _sessions.items() if sess.get("user_id") == user_id]
        for sid in sessions_to_remove:
            del _sessions[sid]
        logger.info(f"User logged out: {user_id}")
        return web.json_response({"status": "logged_out"})
    except Exception as e:
        logger.error(f"Error in user_logout: {e}")
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)