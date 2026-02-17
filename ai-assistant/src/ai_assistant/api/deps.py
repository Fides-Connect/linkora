"""API dependencies and utilities."""
import logging
from aiohttp import web
from firebase_admin import auth

logger = logging.getLogger(__name__)


async def get_current_user_id(request: web.Request) -> str:
    """Extract and verify Firebase ID token from Authorization header.
    
    Args:
        request: The aiohttp request object
        
    Returns:
        str: The authenticated user ID
        
    Raises:
        web.HTTPUnauthorized: If authentication fails
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise web.HTTPUnauthorized(reason="Missing or invalid Authorization header")
    
    token = auth_header.split(' ')[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token['uid']
    except Exception as e:
        logger.warning(f"Auth failed: {e}")
        raise web.HTTPUnauthorized(reason="Invalid authentication token")


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
