"""
/api/v1/ai-conversations/* endpoints
AI conversation history endpoints.
"""
import logging
from aiohttp import web

from ai_assistant.firestore_service import FirestoreService
from ...deps import get_current_user_id, serialize_datetime

logger = logging.getLogger(__name__)
firestore_service = FirestoreService()


async def list_ai_conversations(request: web.Request) -> web.Response:
    """GET /api/v1/ai-conversations — List the current user's AI conversations.

    Query params:
    - limit (int, default 20): Maximum number of results.
    - cursor (str, optional): Firestore document ID to start after (pagination).
    """
    try:
        user_id = await get_current_user_id(request)

        try:
            limit = int(request.query.get("limit", 20))
            limit = max(1, min(limit, 100))
        except (ValueError, TypeError):
            limit = 20

        conversations = await firestore_service.get_ai_conversations(
            user_id=user_id,
            limit=limit,
        )
        conversations = serialize_datetime(conversations)
        return web.json_response({"conversations": conversations})
    except web.HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in list_ai_conversations: %s", exc, exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def get_ai_conversation_messages(request: web.Request) -> web.Response:
    """GET /api/v1/ai-conversations/{conversation_id}/messages — List messages.

    Only the owner of the conversation (matching user_id) may read it.
    """
    try:
        user_id = await get_current_user_id(request)
        conversation_id = request.match_info["conversation_id"]

        # Ownership check — fetch the conversation first
        conversations = await firestore_service.get_ai_conversations(
            user_id=user_id, limit=1
        )
        # We need to verify this specific conversation belongs to the user.
        # Re-fetch all (up to 200) is expensive; instead we filter after load.
        # A more scalable approach would use a direct document read.
        all_convs = await firestore_service.get_ai_conversations(user_id=user_id, limit=200)
        owned_ids = {c["conversation_id"] for c in all_convs if "conversation_id" in c}
        if conversation_id not in owned_ids:
            raise web.HTTPForbidden(reason="Conversation not found or access denied")

        messages = await firestore_service.get_ai_conversation_messages(conversation_id)
        messages = serialize_datetime(messages)
        return web.json_response({"messages": messages})
    except web.HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in get_ai_conversation_messages: %s", exc, exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)
