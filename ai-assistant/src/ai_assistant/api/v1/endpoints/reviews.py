"""
/api/v1/reviews/* endpoints
Review management endpoints.
"""
import logging
from datetime import datetime
from aiohttp import web
from pydantic import ValidationError

from ai_assistant.firestore_service import FirestoreService
from ...deps import get_current_user_id, serialize_datetime

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()


async def get_reviews(request: web.Request) -> web.Response:
    """GET /api/v1/reviews - Get reviews with optional filters.
    
    Query params:
    - user_id: Get reviews for a specific user (as reviewee)
    - reviewer_id: Get reviews by a specific reviewer
    - service_request_id: Get reviews for a specific service request
    """
    try:
        await get_current_user_id(request)
        
        user_id = request.query.get('user_id')
        reviewer_id = request.query.get('reviewer_id')
        service_request_id = request.query.get('service_request_id')
        
        if user_id:
            reviews = await firestore_service.get_reviews_by_user(user_id)
        elif reviewer_id:
            reviews = await firestore_service.get_reviews_by_reviewer(reviewer_id)
        elif service_request_id:
            reviews = await firestore_service.get_reviews_by_request(service_request_id)
        else:
            # Return empty list if no filter specified
            reviews = []
        
        reviews = serialize_datetime(reviews)
        return web.json_response({"reviews": reviews})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_reviews: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def create_review(request: web.Request) -> web.Response:
    """POST /api/v1/reviews - Create a new review.
    
    Body: {
        "service_request_id": "service_request_xyz",
        "user_id": "user_abc",
        "rating_response_speed": 5,
        "feedback_positive": ["Punctual", "Professional"],
        "feedback_negative": [],
        "feedback_raw": "Optional raw feedback"
    }
    """
    try:
        reviewer_user_id = await get_current_user_id(request)
        body = await request.json()
        
        # Validate required fields
        required_fields = ['service_request_id', 'user_id', 'rating']
        for field in required_fields:
            if field not in body:
                return web.json_response({
                    "error": f"Missing required field: {field}"
                }, status=400)
        
        # Validate rating
        rating = body.get('rating')
        if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
            return web.json_response({
                "error": "Rating must be between 1 and 5"
            }, status=400)
        
        review_data = {
            'service_request_id': body['service_request_id'],
            'user_id': body['user_id'],
            'reviewer_user_id': reviewer_user_id,  # Use authenticated user
            'rating': rating,
            'feedback_positive': body.get('feedback_positive', []),
            'feedback_negative': body.get('feedback_negative', []),
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
        logger.warning(f"Validation error in create_review: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_review(request: web.Request) -> web.Response:
    """GET /api/v1/reviews/{review_id} - Get a specific review."""
    try:
        await get_current_user_id(request)
        review_id = request.match_info.get('review_id')
        
        review = await firestore_service.get_review(review_id)
        
        if not review:
            return web.json_response({"error": "Review not found"}, status=404)
        
        review = serialize_datetime(review)
        return web.json_response(review)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def update_review(request: web.Request) -> web.Response:
    """PATCH /api/v1/reviews/{review_id} - Update a review.
    
    Body: {
        "rating_competence": 4,
        "feedback_positive": ["Updated"],
        "feedback_raw": "Updated raw feedback"
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
            if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
                return web.json_response({
                    "error": "Rating must be between 1 and 5"
                }, status=400)
        
        success = await firestore_service.update_review(review_id, body)
        
        if not success:
            return web.json_response({"error": "Failed to update review"}, status=500)
        
        return web.json_response({"status": "updated"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_review(request: web.Request) -> web.Response:
    """DELETE /api/v1/reviews/{review_id} - Delete a review."""
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
        logger.error(f"Error in delete_review: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)
