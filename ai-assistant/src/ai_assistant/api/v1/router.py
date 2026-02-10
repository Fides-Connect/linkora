"""
API v1 Router
Registers all v1 API endpoints.
"""
from aiohttp import web
from .endpoints import me, users, service_requests, reviews, auth


def register_v1_routes(app: web.Application):
    """Register all v1 API routes to the application."""
    
    # Auth endpoints
    app.router.add_post('/api/v1/auth/sign-in-google', auth.sign_in_google)
    app.router.add_post('/api/v1/auth/sync', auth.user_sync)
    app.router.add_post('/api/v1/auth/logout', auth.user_logout)
    
    # Current user (/me) endpoints
    app.router.add_get('/api/v1/me', me.get_me)
    app.router.add_patch('/api/v1/me', me.update_me)
    app.router.add_get('/api/v1/me/favorites', me.get_my_favorites)
    app.router.add_post('/api/v1/me/favorites', me.add_my_favorite)
    app.router.add_delete('/api/v1/me/favorites/{user_id}', me.remove_my_favorite)
    app.router.add_get('/api/v1/me/competencies', me.get_my_competencies)
    app.router.add_post('/api/v1/me/competencies', me.add_my_competence)
    app.router.add_patch('/api/v1/me/competencies/{competence_id}', me.update_my_competence)
    app.router.add_delete('/api/v1/me/competencies/{competence_id}', me.remove_my_competence)
    
    # User management endpoints
    app.router.add_post('/api/v1/users', users.create_user)
    app.router.add_get('/api/v1/users/{user_id}', users.get_user)
    app.router.add_delete('/api/v1/users/{user_id}', users.delete_user)
    
    # Service request endpoints
    app.router.add_get('/api/v1/service-requests', service_requests.get_service_requests)
    app.router.add_post('/api/v1/service-requests', service_requests.create_service_request)
    app.router.add_get('/api/v1/service-requests/{id}', service_requests.get_service_request)
    app.router.add_patch('/api/v1/service-requests/{id}', service_requests.update_service_request)
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
    
    # Review endpoints
    app.router.add_get('/api/v1/reviews', reviews.get_reviews)
    app.router.add_post('/api/v1/reviews', reviews.create_review)
    app.router.add_get('/api/v1/reviews/{review_id}', reviews.get_review)
    app.router.add_patch('/api/v1/reviews/{review_id}', reviews.update_review)
    app.router.add_delete('/api/v1/reviews/{review_id}', reviews.delete_review)
