"""
Admin Service for Debug and Deployment Management
Provides secure administrative endpoints for monitoring and controlling the backend server.

Security:
- Bearer token authentication via ADMIN_SECRET_KEY environment variable
- All admin endpoints require valid authentication
- Logs all admin actions for audit trail
"""
import logging
import os
import secrets
from datetime import datetime
from typing import Optional, Callable, Any
from functools import wraps
from aiohttp import web

logger = logging.getLogger(__name__)


class AdminAuth:
    """
    Admin authentication middleware using bearer token.
    Token must be set in ADMIN_SECRET_KEY environment variable.
    """
    
    @staticmethod
    def get_admin_secret() -> Optional[str]:
        """Get the admin secret key from environment."""
        return os.getenv('ADMIN_SECRET_KEY')
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a secure random secret key (for initial setup)."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_token(request: web.Request) -> bool:
        """
        Verify the bearer token from the Authorization header.
        
        Args:
            request: The incoming HTTP request
            
        Returns:
            bool: True if token is valid, False otherwise
        """
        admin_secret = AdminAuth.get_admin_secret()
        
        if not admin_secret:
            logger.warning("ADMIN_SECRET_KEY not configured - admin endpoints disabled")
            return False
        
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        return secrets.compare_digest(token, admin_secret)
    
    @staticmethod
    def require_auth(handler: Callable) -> Callable:
        """
        Decorator to require admin authentication for a handler.
        
        Usage:
            @AdminAuth.require_auth
            async def my_admin_handler(self, request):
                # Handler code here
        """
        @wraps(handler)
        async def wrapper(*args, **kwargs) -> web.Response:
            # Handle both bound methods (self, request) and functions (request)
            request = args[1] if len(args) > 1 else args[0]
            
            if not AdminAuth.verify_token(request):
                logger.warning(
                    f"Unauthorized admin access attempt from {request.remote}"
                )
                return web.json_response(
                    {"error": "Unauthorized", "message": "Invalid or missing admin token"},
                    status=401
                )
            
            # Log successful authentication
            logger.info(f"Admin action: {handler.__name__} from {request.remote}")
            
            # Call the actual handler
            return await handler(*args, **kwargs)
        
        return wrapper


class AdminService:
    """
    Admin service providing system information and administrative actions.
    """
    
    def __init__(self, signaling_server=None):
        """
        Initialize admin service.
        
        Args:
            signaling_server: Reference to the SignalingServer instance for stats
        """
        self.signaling_server = signaling_server
        self.startup_time = datetime.utcnow()
        logger.info("Admin service initialized")
    
    def get_system_info(self) -> dict[str, Any]:
        """Get system information and statistics."""
        uptime = datetime.utcnow() - self.startup_time
        
        info = {
            "status": "running",
            "version": "1.0.0",
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_human": str(uptime),
            "startup_time": self.startup_time.isoformat(),
            "environment": {
                "language_code": os.getenv('LANGUAGE_CODE', 'de-DE'),
                "voice_name": os.getenv('VOICE_NAME', 'de-DE-Chirp3-HD-Sulafat'),
                "log_level": os.getenv('LOG_LEVEL', 'INFO'),
                "use_weaviate": os.getenv('USE_WEAVIATE', 'true'),
                "debug_record_audio": os.getenv('DEBUG_RECORD_AUDIO', 'false'),
            }
        }
        
        # Add WebSocket statistics if available
        if self.signaling_server:
            info["websocket_connections"] = {
                "active": len(getattr(self.signaling_server, 'active_connections', [])),
                "total_served": getattr(self.signaling_server, 'total_connections', 0),
            }
        
        return info
    
    @AdminAuth.require_auth
    async def health_detailed(self, request: web.Request) -> web.Response:
        """
        GET /admin/health
        Detailed health check with system information.
        """
        try:
            info = self.get_system_info()
            return web.json_response({
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "system": info
            })
        except Exception as e:
            logger.error(f"Error getting health info: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def get_stats(self, request: web.Request) -> web.Response:
        """
        GET /admin/stats
        Get system statistics and metrics.
        """
        try:
            from ..weaviate_models import UserModelWeaviate, ProviderModelWeaviate
            
            # Get database statistics
            users = UserModelWeaviate.get_all_users(limit=1000)
            providers = ProviderModelWeaviate.get_all_providers(limit=1000)
            
            stats = {
                "database": {
                    "total_users": len(users),
                    "total_providers": len(providers),
                    "users_with_fcm_token": sum(1 for u in users if u.get('fcm_token')),
                },
                "system": self.get_system_info()
            }
            
            return web.json_response(stats)
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return web.json_response({
                "error": "Failed to get statistics",
                "message": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def send_notification(self, request: web.Request) -> web.Response:
        """
        POST /admin/notifications/send
        Send push notification to specific users or all users.
        
        Request body:
        {
            "user_ids": ["user1", "user2"],  // Optional, omit to send to all users
            "title": "Notification Title",
            "body": "Notification body text",
            "data": {"key": "value"},  // Optional custom data
            "priority": "high"  // Optional: "high" or "normal"
        }
        """
        try:
            from ..services.notification_service import NotificationService
            from ..weaviate_models import UserModelWeaviate
            
            body = await request.json()
            
            title = body.get('title')
            message = body.get('body')
            
            if not title or not message:
                return web.json_response({
                    "error": "Missing required fields",
                    "message": "Both 'title' and 'body' are required"
                }, status=400)
            
            user_ids = body.get('user_ids')
            data = body.get('data', {})
            priority = body.get('priority', 'high')
            
            # Send to specific users or all users
            if user_ids:
                results = await NotificationService.send_to_multiple_users(
                    user_ids=user_ids,
                    title=title,
                    body=message,
                    data=data,
                    priority=priority
                )
                
                successful = sum(1 for v in results.values() if v)
                
                return web.json_response({
                    "success": True,
                    "sent_to": successful,
                    "total_users": len(user_ids),
                    "results": results
                })
            else:
                # Send to all users with FCM tokens
                all_users = UserModelWeaviate.get_all_users(limit=10000)
                user_ids_all = [u['user_id'] for u in all_users if u.get('fcm_token')]
                
                if not user_ids_all:
                    return web.json_response({
                        "success": False,
                        "message": "No users with FCM tokens found"
                    })
                
                results = await NotificationService.send_to_multiple_users(
                    user_ids=user_ids_all,
                    title=title,
                    body=message,
                    data=data,
                    priority=priority
                )
                
                successful = sum(1 for v in results.values() if v)
                
                return web.json_response({
                    "success": True,
                    "sent_to": successful,
                    "total_users": len(user_ids_all),
                    "broadcast": True
                })
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return web.json_response({
                "error": "Failed to send notification",
                "message": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def list_users(self, request: web.Request) -> web.Response:
        """
        GET /admin/users?limit=100
        List all users in the system.
        """
        try:
            from ..weaviate_models import UserModelWeaviate
            
            limit = int(request.query.get('limit', 100))
            users = UserModelWeaviate.get_all_users(limit=limit)
            
            # Remove sensitive data and format for display
            users_display = []
            for user in users:
                users_display.append({
                    "user_id": user.get('user_id'),
                    "name": user.get('name'),
                    "email": user.get('email'),
                    "has_fcm_token": bool(user.get('fcm_token')),
                    "has_open_request": user.get('has_open_request', False),
                    "last_sign_in": user.get('last_sign_in').isoformat() if user.get('last_sign_in') else None,
                    "created_at": user.get('created_at').isoformat() if user.get('created_at') else None,
                })
            
            return web.json_response({
                "users": users_display,
                "count": len(users_display),
                "limit": limit
            })
            
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return web.json_response({
                "error": "Failed to list users",
                "message": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def get_user_detail(self, request: web.Request) -> web.Response:
        """
        GET /admin/users/{user_id}
        Get detailed information about a specific user.
        """
        try:
            from ..weaviate_models import UserModelWeaviate
            
            user_id = request.match_info.get('user_id')
            
            if not user_id:
                return web.json_response({
                    "error": "Missing user_id"
                }, status=400)
            
            user = UserModelWeaviate.get_user_by_id(user_id)
            
            if not user:
                return web.json_response({
                    "error": "User not found"
                }, status=404)
            
            # Format user data
            user_display = {
                "user_id": user.get('user_id'),
                "name": user.get('name'),
                "email": user.get('email'),
                "photo_url": user.get('photo_url'),
                "has_fcm_token": bool(user.get('fcm_token')),
                "fcm_token_preview": user.get('fcm_token', '')[:20] + '...' if user.get('fcm_token') else None,
                "has_open_request": user.get('has_open_request', False),
                "last_sign_in": user.get('last_sign_in').isoformat() if user.get('last_sign_in') else None,
                "created_at": user.get('created_at').isoformat() if user.get('created_at') else None,
            }
            
            return web.json_response(user_display)
            
        except Exception as e:
            logger.error(f"Error getting user detail: {e}")
            return web.json_response({
                "error": "Failed to get user detail",
                "message": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def list_providers(self, request: web.Request) -> web.Response:
        """
        GET /admin/providers?limit=100
        List all service providers in the system.
        """
        try:
            from ..weaviate_models import ProviderModelWeaviate
            
            limit = int(request.query.get('limit', 100))
            providers = ProviderModelWeaviate.get_all_providers(limit=limit)
            
            return web.json_response({
                "providers": providers,
                "count": len(providers),
                "limit": limit
            })
            
        except Exception as e:
            logger.error(f"Error listing providers: {e}")
            return web.json_response({
                "error": "Failed to list providers",
                "message": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def test_notification(self, request: web.Request) -> web.Response:
        """
        POST /admin/notifications/test
        Send a test notification to a specific FCM token.
        
        Request body:
        {
            "fcm_token": "device_token_here",
            "title": "Test Notification",
            "body": "This is a test"
        }
        """
        try:
            from ..services.notification_service import NotificationService
            
            body = await request.json()
            
            fcm_token = body.get('fcm_token')
            title = body.get('title', 'Test Notification')
            message = body.get('body', 'This is a test notification from admin panel')
            
            if not fcm_token:
                return web.json_response({
                    "error": "Missing fcm_token"
                }, status=400)
            
            success = await NotificationService.send_to_token(
                fcm_token=fcm_token,
                title=title,
                body=message,
                data={"type": "test", "timestamp": datetime.utcnow().isoformat()}
            )
            
            return web.json_response({
                "success": success,
                "message": "Test notification sent" if success else "Failed to send notification"
            })
            
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return web.json_response({
                "error": "Failed to send test notification",
                "message": str(e)
            }, status=500)
    
    @AdminAuth.require_auth
    async def get_logs(self, request: web.Request) -> web.Response:
        """
        GET /admin/logs?lines=100
        Get recent log entries (if log file exists).
        """
        try:
            lines = int(request.query.get('lines', 100))
            log_file = os.getenv('LOG_FILE')
            
            if not log_file or not os.path.exists(log_file):
                return web.json_response({
                    "message": "Log file not configured or not found",
                    "log_file": log_file
                })
            
            # Read last N lines from log file
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
            
            return web.json_response({
                "logs": recent_lines,
                "total_lines": len(all_lines),
                "showing": len(recent_lines)
            })
            
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            return web.json_response({
                "error": "Failed to read logs",
                "message": str(e)
            }, status=500)
    
    def register_routes(self, app: web.Application):
        """
        Register all admin routes to the application.
        
        Args:
            app: The aiohttp web application
        """
        # Health and stats
        app.router.add_get('/admin/health', self.health_detailed)
        app.router.add_get('/admin/stats', self.get_stats)
        
        # User management
        app.router.add_get('/admin/users', self.list_users)
        app.router.add_get('/admin/users/{user_id}', self.get_user_detail)
        
        # Provider management
        app.router.add_get('/admin/providers', self.list_providers)
        
        # Notifications
        app.router.add_post('/admin/notifications/send', self.send_notification)
        app.router.add_post('/admin/notifications/test', self.test_notification)
        
        # Logs
        app.router.add_get('/admin/logs', self.get_logs)
        
        logger.info("Admin routes registered")
