import logging
from aiohttp import web
from firebase_admin import auth as firebase_auth
import aiohttp_cors

logger = logging.getLogger(__name__)

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
    """Handles user sign-in via Firebase ID token verification.
    Expects a JSON body with an 'id_token' field. Returns user
    information if the token is valid."""
    try:
        # Parse the request body
        body = await request.json()
        token = body.get("id_token")
        if not token:
            return web.json_response({"error": "Missing id_token"}, status=400)

        # Verify the Firebase ID token
        # This automatically fetches and caches Google's public certificates
        decoded_token = firebase_auth.verify_id_token(token)

        # Extract user information
        user_id = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")

        # Return user information
        return web.json_response({
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
