"""
/api/v1/service-requests/* endpoints
Service request and chat management endpoints.
"""
import logging
from aiohttp import web
from pydantic import ValidationError

from ai_assistant.firestore_service import FirestoreService
from ...deps import get_current_user_id, serialize_datetime

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()


# Service Request Endpoints

async def get_service_requests(request: web.Request) -> web.Response:
    """GET /api/v1/service-requests - Get service requests for current user."""
    try:
        user_id = await get_current_user_id(request)
        requests = await firestore_service.get_service_requests(user_id)
        requests = serialize_datetime(requests)
        return web.json_response(requests)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_service_requests: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def create_service_request(request: web.Request) -> web.Response:
    """POST /api/v1/service-requests - Create a new service request."""
    try:
        user_id = await get_current_user_id(request)
        body = await request.json()
        
        # Enforce seeker_user_id to be the authenticated user
        body['seeker_user_id'] = user_id
        
        service_request_id = await firestore_service.create_service_request(body)
        if service_request_id:
            return web.json_response({
                "service_request_id": service_request_id,
                "status": "created"
            }, status=201)
        else:
            return web.json_response({"error": "Failed to create service request"}, status=500)
    except ValidationError as e:
        logger.warning(f"Validation error in create_service_request: {e}")
        return web.json_response({
            "error": "Validation failed",
            "details": e.errors()
        }, status=400)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_service_request: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_service_request(request: web.Request) -> web.Response:
    """GET /api/v1/service-requests/{id} - Get a specific service request."""
    try:
        await get_current_user_id(request)  # Auth check
        service_request_id = request.match_info['id']
        
        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)
        
        service_request = serialize_datetime(service_request)
        return web.json_response(service_request)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_service_request: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_service_request(request: web.Request) -> web.Response:
    """PATCH /api/v1/service-requests/{id} - Update a service request.
    
    Authorization: Only the creator (seeker) can update the service request.
    """
    try:
        user_id = await get_current_user_id(request)
        service_request_id = request.match_info['id']
        body = await request.json()
        
        # Check authorization - only creator can update
        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)
        
        seeker_id = service_request.get('seeker_user_id')
        if user_id != seeker_id:
            return web.json_response({
                "error": "Forbidden: Only the creator can update this service request"
            }, status=403)
        
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
    """DELETE /api/v1/service-requests/{id} - Delete service request and all subcollections.
    
    Authorization: Only the creator (seeker) can delete the service request.
    """
    try:
        user_id = await get_current_user_id(request)
        service_request_id = request.match_info['id']
        
        # Check authorization - only creator can delete
        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)
        
        seeker_id = service_request.get('seeker_user_id')
        if user_id != seeker_id:
            return web.json_response({
                "error": "Forbidden: Only the creator can delete this service request"
            }, status=403)
        
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


# Chat Endpoints

async def get_chats(request: web.Request) -> web.Response:
    """GET /api/v1/service-requests/{id}/chats - Get all chats for a service request."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        
        chats = await firestore_service.get_chats_by_request(service_request_id)
        chats = serialize_datetime(chats)
        return web.json_response({"chats": chats})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_chats: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def create_chat(request: web.Request) -> web.Response:
    """POST /api/v1/service-requests/{id}/chats - Create a new chat."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        body = await request.json()
        
        # Validate required fields
        required_fields = ['title', 'provider_candidate_id']
        for field in required_fields:
            if field not in body:
                return web.json_response({
                    "error": f"Missing required field: {field}"
                }, status=400)
        
        provider_candidate_id = body['provider_candidate_id']
        chat_data = {
            'title': body['title'],
            'service_request_id': service_request_id
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
        logger.error(f"Error in create_chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chat(request: web.Request) -> web.Response:
    """GET /api/v1/service-requests/{id}/chats/{chat_id} - Get a specific chat."""
    try:
        await get_current_user_id(request)
        chat_id = request.match_info['chat_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        chat = await firestore_service.get_chat(provider_candidate_id, chat_id)
        
        if not chat:
            return web.json_response({"error": "Chat not found"}, status=404)
        
        chat = serialize_datetime(chat)
        return web.json_response(chat)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def update_chat(request: web.Request) -> web.Response:
    """PATCH /api/v1/service-requests/{id}/chats/{chat_id} - Update a chat."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        # Check if chat exists
        chat = await firestore_service.get_chat(provider_candidate_id, chat_id, service_request_id)
        if not chat:
            return web.json_response({"error": "Chat not found"}, status=404)
        
        body = await request.json()
        success = await firestore_service.update_chat(
            provider_candidate_id, chat_id, service_request_id, body
        )
        
        if not success:
            return web.json_response({"error": "Failed to update chat"}, status=500)
        
        return web.json_response({"status": "updated"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_chat(request: web.Request) -> web.Response:
    """DELETE /api/v1/service-requests/{id}/chats/{chat_id} - Delete a chat and all messages."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        success = await firestore_service.delete_chat(
            provider_candidate_id, chat_id, service_request_id
        )
        
        if not success:
            return web.json_response({"error": "Failed to delete chat"}, status=500)
        
        return web.json_response({"status": "deleted"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


# Chat Message Endpoints

async def get_chat_messages(request: web.Request) -> web.Response:
    """GET /api/v1/service-requests/{id}/chats/{chat_id}/messages - Get all messages for a chat."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        # Get limit from query params
        limit = int(request.query.get('limit', 100))
        
        messages = await firestore_service.get_chat_messages(
            provider_candidate_id, chat_id, service_request_id, limit=limit
        )
        
        messages = serialize_datetime(messages)
        return web.json_response({"messages": messages})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_chat_messages: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def create_chat_message(request: web.Request) -> web.Response:
    """POST /api/v1/service-requests/{id}/chats/{chat_id}/messages - Create a new message."""
    try:
        sender_user_id = await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        body = await request.json()
        
        # Validate required fields
        required_fields = ['receiver_user_id', 'message']
        for field in required_fields:
            if field not in body:
                return web.json_response({
                    "error": f"Missing required field: {field}"
                }, status=400)
        
        message_data = {
            'sender_user_id': sender_user_id,  # Use authenticated user
            'receiver_user_id': body['receiver_user_id'],
            'message': body['message']
        }
        
        message_id = await firestore_service.create_chat_message(
            provider_candidate_id, chat_id, service_request_id, message_data
        )
        
        if not message_id:
            return web.json_response({"error": "Failed to create message"}, status=500)
        
        return web.json_response({
            "chat_message_id": message_id,
            "status": "created"
        }, status=201)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_chat_message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_chat_message(request: web.Request) -> web.Response:
    """GET /api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id} - Get a specific message."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        message_id = request.match_info['message_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        message = await firestore_service.get_chat_message(
            provider_candidate_id, chat_id, service_request_id, message_id
        )
        
        if not message:
            return web.json_response({"error": "Message not found"}, status=404)
        
        message = serialize_datetime(message)
        return web.json_response(message)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_chat_message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def update_chat_message(request: web.Request) -> web.Response:
    """PATCH /api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id} - Update a message."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        message_id = request.match_info['message_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        # Check if message exists
        message = await firestore_service.get_chat_message(
            provider_candidate_id, chat_id, service_request_id, message_id
        )
        if not message:
            return web.json_response({"error": "Message not found"}, status=404)
        
        body = await request.json()
        success = await firestore_service.update_chat_message(
            provider_candidate_id, chat_id, service_request_id, message_id, body
        )
        
        if not success:
            return web.json_response({"error": "Failed to update message"}, status=500)
        
        return web.json_response({"status": "updated"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_chat_message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_chat_message(request: web.Request) -> web.Response:
    """DELETE /api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id} - Delete a message."""
    try:
        await get_current_user_id(request)
        service_request_id = request.match_info['id']
        chat_id = request.match_info['chat_id']
        message_id = request.match_info['message_id']
        
        # Get provider_candidate_id from query params
        provider_candidate_id = request.query.get('provider_candidate_id')
        if not provider_candidate_id:
            return web.json_response({
                "error": "Missing provider_candidate_id query parameter"
            }, status=400)
        
        success = await firestore_service.delete_chat_message(
            provider_candidate_id, chat_id, service_request_id, message_id
        )
        
        if not success:
            return web.json_response({"error": "Failed to delete message"}, status=500)
        
        return web.json_response({"status": "deleted"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_chat_message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)
