import os
from aiohttp import web
from google.oauth2 import id_token
from google.auth.transport import requests
import aiohttp_cors

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

async def validate_google_sign_in(request: web.Request) -> web.Response:
    """Validate Google Sign-In token."""
    try:
        # Parse the request body
        body = await request.json()
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)

        # Verify the token
        request_adapter = requests.Request()
        CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"  # Replace with your Google OAuth client ID
        id_info = id_token.verify_oauth2_token(token, request_adapter, os.getenv('GOOGLE_OAUTH_CLIENT_ID'))

        # Extract user information
        user_id = id_info["sub"]
        email = id_info.get("email")
        name = id_info.get("name")

        # Return user information
        return web.json_response({
            "user_id": user_id,
            "email": email,
            "name": name,
            "valid": True
        })

    except ValueError as e:
        # Token is invalid
        return web.json_response({"error": "Invalid token", "details": str(e)}, status=401)

    except Exception as e:
        # Handle unexpected errors
        return web.json_response({"error": "Internal server error", "details": str(e)}, status=500)