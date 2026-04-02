"""
API v1 Router
Registers all v1 API endpoints.

In **lite mode** (``AGENT_MODE=lite``) only the endpoints that are meaningful
for a text-only, provider-discovery-only deployment are registered.  All
routes related to voice warmup, service requests, favorites, competency
management, reviews, and user administration are omitted — aiohttp returns
its standard 404 for those paths rather than routing to a disabled handler.
"""
import os

from aiohttp import web
from .endpoints import me, users, service_requests, reviews, auth, ai_conversations, assistant


def register_v1_routes(app: web.Application) -> None:
    """Register all v1 API routes to the application.

    In lite mode only the core subset of routes is registered; full-mode-only
    route groups are skipped entirely.
    """
    is_lite = os.getenv("AGENT_MODE", "full").lower().strip() == "lite"

    # ── Always active (both modes) ──────────────────────────────────────────

    # Auth endpoints
    app.router.add_post('/api/v1/auth/sign-in-google', auth.sign_in_google)
    app.router.add_post('/api/v1/auth/sync', auth.user_sync)
    app.router.add_post('/api/v1/auth/logout', auth.user_logout)

    # Current user — basic profile and settings
    app.router.add_get('/api/v1/me', me.get_me)
    app.router.add_patch('/api/v1/me', me.update_me)
    app.router.add_get('/api/v1/me/settings', me.get_settings)
    app.router.add_patch('/api/v1/me/settings', me.update_settings)

    # AI conversation history (30-day TTL, both modes)
    app.router.add_get('/api/v1/ai-conversations', ai_conversations.list_ai_conversations)
    app.router.add_get(
        '/api/v1/ai-conversations/{conversation_id}/messages',
        ai_conversations.get_ai_conversation_messages,
    )

    if is_lite:
        return

    # ── Full mode only ──────────────────────────────────────────────────────

    # Favorites
    app.router.add_get('/api/v1/me/favorites', me.get_my_favorites)
    app.router.add_post('/api/v1/me/favorites', me.add_my_favorite)
    app.router.add_delete('/api/v1/me/favorites/{user_id}', me.remove_my_favorite)

    # Service-request references on /me
    app.router.add_post('/api/v1/me/outgoing-service-requests', me.add_my_outgoing_service_requests)
    app.router.add_post('/api/v1/me/incoming-service-requests', me.add_my_incoming_service_requests)
    app.router.add_delete('/api/v1/me/outgoing-service-requests', me.remove_my_outgoing_service_requests)
    app.router.add_delete('/api/v1/me/incoming-service-requests', me.remove_my_incoming_service_requests)

    # Provider competencies / onboarding
    app.router.add_get('/api/v1/me/competencies', me.get_my_competencies)
    app.router.add_post('/api/v1/me/competencies', me.create_my_competence)
    app.router.add_patch('/api/v1/me/competencies/{competence_id}', me.update_my_competence)
    app.router.add_delete('/api/v1/me/competencies/{competence_id}', me.remove_my_competence)

    # User management
    app.router.add_post('/api/v1/users', users.create_user)
    app.router.add_get('/api/v1/users/{user_id}', users.get_user)
    app.router.add_delete('/api/v1/users/{user_id}', users.delete_user)

    # Service requests
    app.router.add_get('/api/v1/service-requests', service_requests.get_service_requests)
    app.router.add_post('/api/v1/service-requests', service_requests.create_service_request)
    app.router.add_get('/api/v1/service-requests/{id}', service_requests.get_service_request)
    app.router.add_patch('/api/v1/service-requests/{id}', service_requests.update_service_request)
    app.router.add_patch('/api/v1/service-requests/{id}/status', service_requests.update_service_request_status)
    app.router.add_delete('/api/v1/service-requests/{id}', service_requests.delete_service_request)

    # Chat endpoints (nested under service requests)
    app.router.add_get('/api/v1/service-requests/{id}/chats', service_requests.get_chats)
    app.router.add_post('/api/v1/service-requests/{id}/chats', service_requests.create_chat)
    app.router.add_get('/api/v1/service-requests/{id}/chats/{chat_id}', service_requests.get_chat)
    app.router.add_patch('/api/v1/service-requests/{id}/chats/{chat_id}', service_requests.update_chat)
    app.router.add_delete('/api/v1/service-requests/{id}/chats/{chat_id}', service_requests.delete_chat)

    # Chat message endpoints
    app.router.add_get('/api/v1/service-requests/{id}/chats/{chat_id}/messages', service_requests.get_chat_messages)
    app.router.add_post('/api/v1/service-requests/{id}/chats/{chat_id}/messages', service_requests.create_chat_message)
    app.router.add_get('/api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id}', service_requests.get_chat_message)
    app.router.add_patch('/api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id}', service_requests.update_chat_message)
    app.router.add_delete('/api/v1/service-requests/{id}/chats/{chat_id}/messages/{message_id}', service_requests.delete_chat_message)

    # Reviews
    app.router.add_get('/api/v1/reviews', reviews.get_reviews)
    app.router.add_post('/api/v1/reviews', reviews.create_review)
    app.router.add_get('/api/v1/reviews/{review_id}', reviews.get_review)
    app.router.add_patch('/api/v1/reviews/{review_id}', reviews.update_review)
    app.router.add_delete('/api/v1/reviews/{review_id}', reviews.delete_review)

    # Assistant utility endpoints (voice warmup — voice only)
    app.router.add_post('/api/v1/assistant/greet-warmup', assistant.greet_warmup)
