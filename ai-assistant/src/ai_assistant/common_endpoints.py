import logging
import os
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4
from aiohttp import web
from google.oauth2 import id_token
from google.auth.transport import requests
import aiohttp_cors

logger = logging.getLogger(__name__)

# Simple in-memory session store (needs to be replace with DB)
_sessions: Dict[str, Dict[str, Any]] = {}

def setup_cors(app: web.Application) -> None:
    # allow all origins for dev; tighten in production
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["POST", "OPTIONS"]
        )
    })
    # attach CORS to all routes (call after routes are added)
    for route in list(app.router.routes()):
        cors.add(route)

async def sign_in_google(request: web.Request) -> web.Response:
    """Handles user sign-in via Google OAuth token verification.
    Expects a JSON body with an 'id_token' field. Returns user
    information if the token is valid."""
    try:
        # Parse the request body
        body = await request.json()
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)

        # Verify the token
        request_adapter = requests.Request()
        id_info = id_token.verify_oauth2_token(token, request_adapter, os.getenv('GOOGLE_OAUTH_CLIENT_ID'))

        # Extract user information
        user_id = id_info["sub"]
        email = id_info.get("email")
        name = id_info.get("name")

        # create session id and store session
        # Todo: Replace with persistent session storage
        session_id = str(uuid4())
        _sessions[session_id] = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "created_at": datetime.now().isoformat(),
        }

        # Just for debugging, log current sessions
        # Todo: remove in production
        logger.info(f"Current sessions: {_sessions}")

        # Return user information
        return web.json_response({
            "session_id": session_id,
            "user_id": user_id,
            "email": email,
            "name": name,
            "is_valid": True
        })

    except ValueError as e:
        # Token is invalid
        return web.json_response({"error": "Invalid token", "details": str(e)}, status=401)

    except Exception as e:
        # Handle unexpected errors
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)