# User Authentication and FCM Integration

## Overview
This implementation adds Firebase Cloud Messaging (FCM) token generation and user data synchronization between the Flutter app and the AI assistant backend server. When a user signs in, the app generates an FCM token and sends it along with user metadata to the backend, which either creates a new user or loads an existing user's profile from the Weaviate database.

**Key Design Decision**: The system uses Firebase `user_id` (UID) as the primary identifier for both user identity and conversation history tracking. This eliminates the need for separate session IDs and provides persistent, user-specific conversation history across reconnections.

## Session Management Architecture

### user_id as the Universal Identifier

**What is user_id?**
- The Firebase UID - a permanent, unique identifier for each user
- Never changes for the lifetime of the user account
- Used consistently across the entire system

**Why use user_id instead of session_id?**

1. **Persistent Conversation History**: User's conversation history is tied to their identity, not a temporary session. They can disconnect and reconnect without losing context.

2. **Simplified Architecture**: One identifier (`user_id`) instead of managing both `user_id` and `session_id`

3. **FCM Token Lookup**: Easy to find a user's FCM token for push notifications by their `user_id`

4. **WebSocket Connection Context**: Each WebSocket connection knows which user it belongs to via the `user_id` query parameter

**Active Users Tracking**:
- In-memory dictionary `_active_users` maps `user_id` → session data (including FCM token)
- Updated on every sign-in/sync
- In production, should be replaced with Redis for distributed systems
- Provides quick lookup for sending push notifications

## Changes Made

### 1. Flutter App (ConnectX)

#### Added Dependencies
- **pubspec.yaml**: Added `firebase_messaging: ^15.1.5` for push notifications

#### New Service: UserService
**File**: `connectx/lib/services/user_service.dart`

A singleton service that manages:
- FCM token initialization and refresh
- User data synchronization with the backend
- User profile caching
- Notification permissions

Key methods:
- `initializeFCM()`: Initializes Firebase Cloud Messaging and requests notification permissions
- `syncUserWithBackend(User)`: Syncs user data with the AI assistant server
- `clearUserData()`: Clears cached user data on sign out

#### Updated: AuthService
**File**: `connectx/lib/services/auth_service.dart`

Changes:
- Integrated `UserService` for FCM initialization
- Updated `_handleAuthStateChanged()` to call `syncUserWithBackend()` instead of the old validation method
- Removed the old `_signInBackend()` method
- Added `_userService.clearUserData()` call in `signOut()`

#### Updated: WebRTCService
**File**: `connectx/lib/services/webrtc_service.dart`

Changes:
- WebSocket connections now include `user_id` query parameter: `ws://server/ws?user_id={firebase_uid}`
- Authenticated connections allow the backend to associate WebRTC streams with specific users
- Enables per-user conversation history in the AI assistant

### 2. Backend (AI Assistant Server)

#### Updated Weaviate Schema
**File**: `ai-assistant/src/ai_assistant/weaviate_config.py`

Extended the User collection schema to include:
- `photo_url`: User's profile photo URL
- `fcm_token`: Firebase Cloud Messaging token for push notifications
- `created_at`: Account creation timestamp
- `last_sign_in`: Last sign-in timestamp

#### Enhanced User Model
**File**: `ai-assistant/src/ai_assistant/weaviate_models.py`

Changes:
- Updated `create_user()` to accept and store new fields (photo_url, fcm_token, created_at, last_sign_in)
- Added `update_user()` method to update user information (FCM token, last sign-in, etc.)

#### New Endpoint: User Sync
**File**: `ai-assistant/src/ai_assistant/common_endpoints.py`

New function: `user_sync(request)`

**Endpoint**: `POST /user/sync`

**Request Body**:
```json
{
  "id_token": "firebase_id_token",
  "user_id": "firebase_user_id",
  "email": "user@example.com",
  "name": "User Name",
  "photo_url": "https://...",
  "fcm_token": "fcm_token_string",
  "created_at": "2025-11-28T12:00:00Z",
  "last_sign_in": "2025-11-28T12:00:00Z"
}
```

**Response**:
```json
{
  "user_id": "firebase_user_id",
  "user_profile": {
    "user_id": "...",
    "email": "...",
    "name": "...",
    "photo_url": "...",
    "fcm_token": "...",
    "has_open_request": false,
    "created_at": "...",
    "last_sign_in": "..."
  },
  "is_new_user": true/false,
  "success": true
}
```

**Behavior**:
1. Verifies the Firebase ID token
2. Checks if user exists in Weaviate database
3. If user exists:
   - Updates `last_sign_in` timestamp
   - Updates `fcm_token` if changed
   - Updates `photo_url` if provided
   - Loads user profile from database
4. If user doesn't exist:
   - Creates new user with all provided metadata
   - Stores in Weaviate database
5. Stores user in `_active_users` (in-memory cache with FCM token)
6. Returns user profile

**Active Users Management**:

New helper functions in `common_endpoints.py`:
- `get_active_user(user_id)`: Get active user data including FCM token
- `get_all_active_users()`: Get all active users
- `remove_active_user(user_id)`: Remove user from active sessions

These functions enable:
- Looking up FCM tokens for push notifications
- Tracking currently active users
- Session cleanup on explicit logout

#### Updated: SignalingServer
**File**: `ai-assistant/src/ai_assistant/signaling_server.py`

Changes:
- WebSocket handler now accepts `user_id` query parameter
- Passes `user_id` to `PeerConnectionHandler` for user context
- Logs authenticated vs anonymous connections

#### Updated: PeerConnectionHandler
**File**: `ai-assistant/src/ai_assistant/peer_connection_handler.py`

Changes:
- Added `user_id` field to track which user owns the connection
- Enables future features like user-specific notifications

#### Updated: AIAssistant
**File**: `ai-assistant/src/ai_assistant/ai_assistant.py`

Changes:
- Renamed `session_id` parameter to `user_id`
- Uses `user_id` as the key for conversation history storage
- Each user has persistent conversation history across reconnections
- Anonymous users use "anonymous" as the key (shared history)

#### Updated Main Server
**File**: `ai-assistant/src/ai_assistant/__main__.py`

Changes:
- Imported `user_sync` function
- Registered route: `POST /user/sync`
- Added logging for the new endpoint

## Flow Diagram

```
User Signs In
     ↓
Firebase Authentication (gets Firebase UID)
     ↓
AuthService.initialize()
     ↓
UserService.initializeFCM()
  - Request notification permissions
  - Get FCM token
  - Listen for token refresh
     ↓
AuthService._handleAuthStateChanged(user)
     ↓
UserService.syncUserWithBackend(user)
  - Get Firebase ID token
  - Prepare user data (user_id, email, name, photo, FCM token, timestamps)
  - POST to /user/sync
     ↓
Backend: user_sync()
  - Verify ID token
  - Check if user exists in Weaviate
     ↓
  If New User:
    - Create user in Weaviate database
    - Store in _active_users with FCM token
    - Return user_profile + is_new_user=true
     ↓
  If Existing User:
    - Update FCM token, last_sign_in, photo_url in Weaviate
    - Store in _active_users with FCM token
    - Load user profile from database
    - Return user_profile + is_new_user=false
     ↓
Flutter App:
  - Store user profile locally
  - When connecting WebRTC: ws://server/ws?user_id={firebase_uid}
     ↓
Backend: WebSocket Connection
  - Extract user_id from query params
  - Create PeerConnectionHandler with user_id
  - AIAssistant uses user_id for conversation history
     ↓
User's conversation history persists across sessions!
```

## Key Benefits of user_id-based Architecture

1. **Persistent History**: Users maintain their conversation context across app restarts and reconnections

2. **Simplified System**: One identifier instead of managing both user_id and session_id

3. **Push Notifications Ready**: Easy lookup of FCM tokens via `get_active_user(user_id)`

4. **User Context Everywhere**: WebSocket connections, AI conversations, and database records all use the same identifier

5. **Scalability**: Easy to migrate from in-memory storage to Redis/database by replacing `_active_users` dict

## Environment Configuration

### Flutter App (.env)
```env
AI_ASSISTANT_SERVER_URL=your-server:8080
GOOGLE_OAUTH_CLIENT_ID=your-client-id
```

### Backend (.env)
```env
WEAVIATE_URL=http://localhost:8090
# OR for cloud deployment:
WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
WEAVIATE_API_KEY=your-api-key
```

## Next Steps

1. **Run Flutter pub get**:
   ```bash
   cd connectx
   flutter pub get
   ```

2. **Update Weaviate Schema** (if database already exists):
   ```bash
   cd ai-assistant
   python scripts/init_weaviate.py
   ```

3. **Test the Integration**:
   - Start the AI assistant server
   - Run the Flutter app
   - Sign in with Google
   - Verify in logs that:
     - FCM token is generated
     - User sync request is sent
     - Backend creates/updates user in database
     - User profile is returned

## Security Considerations

- Firebase ID tokens are verified on the backend before any data is processed
- `user_id` is extracted from verified Firebase tokens to prevent spoofing
- FCM tokens are securely stored in Weaviate database
- WebSocket `user_id` query param should be validated against Firebase auth (future enhancement)
- CORS is configured (currently allowing all origins for development)
- `_active_users` is currently in-memory (should be replaced with Redis/database for production with TTL)

## Future Enhancements

1. **Production Session Storage**: Replace `_active_users` dict with Redis (with TTL for automatic cleanup)
2. **WebSocket Auth**: Validate `user_id` query param against Firebase ID token for WebSocket connections
3. **Push Notifications**: Implement endpoints to send notifications using stored FCM tokens
4. **User Profile Updates**: Add endpoints for users to update their profile information
5. **Conversation History Persistence**: Store conversation history in database instead of in-memory
6. **Session Cleanup**: Implement automatic cleanup of inactive users
7. **Rate Limiting**: Add rate limiting per user_id
8. **Analytics**: Track user engagement, conversation metrics, and feature usage by user_id
