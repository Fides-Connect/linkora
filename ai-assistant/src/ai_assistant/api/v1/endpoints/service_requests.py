"""
/api/v1/service-requests/* endpoints
Service request and chat management endpoints.
"""
import asyncio
import logging
from aiohttp import web
from pydantic import ValidationError

from ai_assistant.firestore_service import FirestoreService
from ai_assistant.services.notification_service import (
    notify_service_request_status_change,
    notify_new_service_request,
)
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
        
        created = await firestore_service.create_service_request(body)
        if created:
            service_request_id = created.get('service_request_id', '')
            provider_id = body.get('selected_provider_user_id', '')
            asyncio.ensure_future(
                notify_new_service_request(
                    provider_id=provider_id,
                    service_request_id=service_request_id,
                    category=body.get('category', ''),
                )
            )
            return web.json_response(
                serialize_datetime(created),
                status=201,
            )
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
        
        updated_request = await firestore_service.update_service_request(service_request_id, body)
        if updated_request:
            return web.json_response(serialize_datetime(updated_request))
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


async def update_service_request_status(request: web.Request) -> web.Response:
    """PATCH /api/v1/service-requests/{id}/status - Update status with role-based authorization.

    Allowed transitions by role:
      Provider (selected_provider_user_id):
        pending / waitingForAnswer → accepted, rejected
        accepted → serviceProvided
      Seeker (seeker_user_id):
        pending / waitingForAnswer / accepted → cancelled
        serviceProvided → completed
    """
    try:
        user_id = await get_current_user_id(request)
        service_request_id = request.match_info['id']
        body = await request.json()
        new_status = body.get('status')

        if not new_status:
            return web.json_response({"error": "Missing required field: status"}, status=400)

        service_request = await firestore_service.get_service_request(service_request_id)
        if not service_request:
            return web.json_response({"error": "Service request not found"}, status=404)

        seeker_id = service_request.get('seeker_user_id')
        provider_id = service_request.get('selected_provider_user_id')
        current_status = service_request.get('status')

        is_seeker = user_id == seeker_id
        is_provider = provider_id and user_id == provider_id

        if not is_seeker and not is_provider:
            return web.json_response(
                {"error": "Forbidden: Not a participant of this service request"}, status=403
            )

        PROVIDER_TRANSITIONS = {
            'pending': ['accepted', 'rejected'],
            'waitingForAnswer': ['accepted', 'rejected'],
            'accepted': ['serviceProvided'],
        }
        SEEKER_TRANSITIONS = {
            'pending': ['cancelled'],
            'waitingForAnswer': ['cancelled'],
            'accepted': ['cancelled'],
            'serviceProvided': ['completed'],
        }

        allowed: list[str] = []
        if is_provider:
            allowed += PROVIDER_TRANSITIONS.get(current_status, [])
        if is_seeker:
            allowed += SEEKER_TRANSITIONS.get(current_status, [])

        if new_status not in allowed:
            return web.json_response(
                {"error": f"Transition from '{current_status}' to '{new_status}' is not allowed for this user"},
                status=422
            )

        updated_request = await firestore_service.update_service_request_status(
            service_request_id, new_status
        )
        if updated_request:
            asyncio.ensure_future(
                notify_service_request_status_change(
                    seeker_id=seeker_id or '',
                    provider_id=provider_id,
                    actor_id=user_id,
                    service_request_id=service_request_id,
                    new_status=new_status,
                )
            )
            return web.json_response(serialize_datetime(updated_request))
        else:
            return web.json_response({"error": "Failed to update service request status"}, status=500)
    except web.HTTPException:
        raise
    except ValidationError as e:
        logger.warning(f"Validation error in update_service_request_status: {e}")
        return web.json_response({"error": "Validation failed", "details": e.errors()}, status=400)
    except Exception as e:
        logger.error(f"Error in update_service_request_status: {e}")
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
        required_fields = ['title', 'provider_candidate_id', 'seeker_user_id', 'provider_user_id']
        for field in required_fields:
            if field not in body:
                return web.json_response({
                    "error": f"Missing required field: {field}"
                }, status=400)
        
        provider_candidate_id = body['provider_candidate_id']
        chat_data = {
            'title': body['title'],
            'service_request_id': service_request_id,
            'provider_candidate_id': provider_candidate_id,
            'seeker_user_id': body['seeker_user_id'],
            'provider_user_id': body['provider_user_id']
        }
        
        chat_id = await firestore_service.create_chat(chat_data)
        
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
        
        chat = await firestore_service.get_chat(chat_id)
        
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
        chat_id = request.match_info['chat_id']
        
        # Check if chat exists
        chat = await firestore_service.get_chat(chat_id)
        if not chat:
            return web.json_response({"error": "Chat not found"}, status=404)
        
        body = await request.json()
        updated_chat = await firestore_service.update_chat(chat_id, body)
        
        if not updated_chat:
            return web.json_response({"error": "Failed to update chat"}, status=500)
        
        return web.json_response(serialize_datetime(updated_chat))
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_chat: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_chat(request: web.Request) -> web.Response:
    """DELETE /api/v1/service-requests/{id}/chats/{chat_id} - Delete a chat and all messages."""
    try:
        await get_current_user_id(request)
        chat_id = request.match_info['chat_id']
        
        success = await firestore_service.delete_chat(chat_id)
        
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
        chat_id = request.match_info['chat_id']
        
        # Get limit from query params
        limit = int(request.query.get('limit', 100))
        
        messages = await firestore_service.get_chat_messages(chat_id, limit=limit)
        
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
        chat_id = request.match_info['chat_id']
        
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
        
        message_id = await firestore_service.create_chat_message(chat_id, message_data)
        
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
        chat_id = request.match_info['chat_id']
        message_id = request.match_info['message_id']
        
        message = await firestore_service.get_chat_message(chat_id, message_id)
        
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
        chat_id = request.match_info['chat_id']
        message_id = request.match_info['message_id']
        
        # Check if message exists
        message = await firestore_service.get_chat_message(chat_id, message_id)
        if not message:
            return web.json_response({"error": "Message not found"}, status=404)
        
        body = await request.json()
        updated_message = await firestore_service.update_chat_message(chat_id, message_id, body)
        
        if not updated_message:
            return web.json_response({"error": "Failed to update message"}, status=500)
        
        return web.json_response(serialize_datetime(updated_message))
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_chat_message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


async def delete_chat_message(request: web.Request) -> web.Response:
    """DELETE /api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id} - Delete a message."""
    try:
        await get_current_user_id(request)
        chat_id = request.match_info['chat_id']
        message_id = request.match_info['message_id']
        
        success = await firestore_service.delete_chat_message(chat_id, message_id)
        
        if not success:
            return web.json_response({"error": "Failed to delete message"}, status=500)
        
        return web.json_response({"status": "deleted"})
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_chat_message: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)
