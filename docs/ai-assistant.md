# AI-Assistant - Backend Server

The AI-Assistant is the Python-based WebRTC server that powers the Linkora voice interaction platform, handling speech recognition, AI processing, and audio synthesis.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Deployment](#deployment)
- [Performance Tuning](#performance-tuning)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The AI-Assistant server is a containerized service that:
- Receives audio streams from clients via WebRTC
- Converts speech to text using Google Cloud Speech API
- Processes queries using Google Gemini 3.0 Flash
- Generates natural-sounding responses using Google Cloud TTS
- Streams audio responses back to clients
- Manages multi-stage conversations
- Synchronizes data between Firestore (Document) and Weaviate (Vector) databases
- Performs semantic provider matching using Weaviate

### Why Server-Side Processing?

**Benefits:**
- 🔒 **Secure**: API credentials stay on server
- ⚡ **Efficient**: Offloaded processing from mobile devices
- 🔋 **Battery-Friendly**: Reduced client resource usage
- 🔄 **Centralized**: Easy updates without app redeployment
- 🌐 **Multi-Platform**: Works with any WebRTC-capable client

## ✨ Features

### Core Capabilities

- **Real-Time Voice Processing**: Low-latency continuous speech recognition
- **Streaming Pipeline**: Full streaming STT → LLM → TTS for minimal latency
- **Multi-Stage Conversations**: Dynamic prompt switching (greeting, triage, finalization)
- **Interrupt Support**: User can interrupt AI responses by speaking
- **Parallel Processing**: Multiple TTS tasks run simultaneously
- **Intelligent Provider Matching**: Weaviate vector search for semantic matching
- **Multi-Language Support**: Configurable language and voice settings
- **Chat Context**: Maintains conversation history per session
- **Scalable Architecture**: Stateless design for horizontal scaling

### Conversation Stages

```
┌──────────┐
│ GREETING │  Personalized greeting, asks user's needs
└────┬─────┘
     │
     ▼
┌──────────┐
│ TRIAGE   │  Service coordinator - asks scoping questions
└────┬─────┘  (not diagnostics)
     │
     │ Auto-transition on search database
     ▼
┌──────────┐
│ FINALIZE │  Presents matched providers, handles feedback
└────┬─────┘
     │
     ▼
┌──────────┐
│COMPLETED │  Confirms request, explains next steps
└──────────┘
```

### Technical Features

- **Native gRPC Streaming**: 30-50% lower latency than REST
- **Streaming APIs**: STT, LLM, and TTS all stream
- **Sentence-Level Parallelization**: TTS processes multiple sentences simultaneously
- **Fully Async**: No thread pool overhead
- **Transcript-Based Interrupts**: Detects user speech to stop AI
- **Health Check Endpoints**: For monitoring and load balancing
- **Docker Containerization**: Easy deployment and scaling

## 🏗️ Architecture

### Component Structure

```
ai-assistant/
├── src/ai_assistant/
│   ├── __main__.py                # Application entry point
│   ├── ai_assistant.py            # Core orchestration layer
│   ├── audio_processor.py         # Audio stream processing
│   ├── audio_track.py             # Audio track handling
│   ├── peer_connection_handler.py # WebRTC management
│   ├── signaling_server.py        # WebSocket signaling
│   ├── app_endpoints.py           # REST API endpoints for App
│   ├── common_endpoints.py        # Shared API endpoints
│   ├── data_provider.py           # Data access abstraction
│   ├── firestore_service.py       # Firestore (Ground Truth) service
│   ├── firestore_schemas.py       # Pydantic schemas for Firestore documents
│   ├── seed_data.py               # Template data for user seeding
│   ├── hub_spoke_schema.py        # Weaviate Hub & Spoke definition
│   ├── hub_spoke_ingestion.py     # Data sync pipeline (Firestore -> Weaviate)
│   ├── hub_spoke_search.py        # Advanced search logic
│   ├── weaviate_config.py         # Weaviate connection config
│   ├── weaviate_models.py         # Weaviate data models
│   ├── api/                       # REST API (v1 routes)
│   │   ├── deps.py                # Dependency injection and auth
│   │   └── v1/
│   │       ├── router.py          # API v1 router
│   │       └── endpoints/         # API endpoint modules
│   │           ├── auth.py        # Authentication endpoints
│   │           ├── me.py          # Current user profile endpoints
│   │           ├── users.py       # User management endpoints
│   │           ├── service_requests.py  # Service request endpoints
│   │           └── reviews.py     # Review endpoints
│   └── services/
│       ├── admin_service.py           # Admin interface
│       ├── conversation_service.py    # Multi-stage conversations
│       ├── response_orchestrator.py   # AI conversation flow
│       ├── llm_service.py             # Gemini LLM integration
│       ├── greeting_service.py        # Greeting generation
│       ├── speech_to_text_service.py  # Google STT integration
│       ├── text_to_speech_service.py  # Google TTS integration
│       ├── tts_playback_manager.py    # TTS playback synchronization
│       ├── notification_service.py    # Event notifications
│       ├── user_seeding_service.py    # User onboarding and seeding
│       └── transcript_processor.py    # Transcript handling
│
├── scripts/
│   ├── init_database.py           # Database initialization (Firestore + Weaviate)
│   ├── delete_weaviate_user.py    # User deletion utility for Weaviate
│   ├── generate_admin_token.py    # Admin authentication
│   ├── test_admin_interface.py    # Admin testing
│   └── test_search_providers.py   # Search testing
│
├── tests/                         # Unit and integration tests

### Data Architecture: Hub & Spoke

The system uses a **Hybrid Database Architecture**:
1.  **Firestore**: Acts as the "Ground Truth" for relational data (Users, Service Requests, Reviews, Chat).
2.  **Weaviate**: Acts as the "Search Engine" for semantic matching (Competencies, Providers).

**Synchronization Flow:**
- Writes go primarily to Firestore.
- `HubSpokeIngestion` service syncs relevant changes (User profile, Competencies) to Weaviate in real-time.
- `init_database.py` script ensures initial sync and test data population.

**Hub & Spoke Model (Weaviate):**
- **Hub**: The `User` object.
- **Spoke**: The `Competence` (skill/service) object.
- **Link**: Bidirectional references (`owned_by` <-> `has_competencies`).
- This allows searching for specific skills ("Spokes") while retrieving the full provider profile ("Hub").
├── Dockerfile                     # Container definition
├── docker-compose.yml             # Development setup
├── pyproject.toml                 # Dependencies
└── main.py                        # Entry point wrapper
```

### Processing Pipeline

```
Audio Stream (WebRTC)
    ↓
AudioProcessor
    ├─→ STT Streaming (gRPC)
    │       ↓
    │   Transcript Buffer
    │       ↓
    └─→ ResponseOrchestrator
            ├─→ ConversationService
            │   ├─→ Stage Management
            │   └─→ Context Tracking
            │
            ├─→ Gemini 3.0 (Streaming)
            │       ↓
            │   AI Response Stream
            │
            ├─→ DataProvider (if needed)
            │   └─→ Weaviate Search
            │
            └─→ TTS (Parallel)
                    ↓
                Audio Chunks
                    ↓
            WebRTC Stream → Client
```

## 🚀 Installation

### Prerequisites

- **Python**: 3.11 or higher
- **Docker**: For containerized deployment
- **Google Cloud Platform**: Account with enabled APIs
- **Google Gemini**: API key

### Step 1: Python Environment Setup

```bash
cd ai-assistant

# Create virtual environment
python3 -m venv ../.venv
source ../.venv/bin/activate  # Windows: ..\.venv\Scripts\activate

# Install in development mode
pip install -e .
pip install -e ".[dev]"
```

**Why development mode (`pip install -e .`)?**  
This makes imports like `from ai_assistant.hub_spoke_schema import ...` work correctly throughout the project without manual path manipulation.

### Step 2: Google Cloud Setup

#### Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to IAM & Admin → Service Accounts
3. Create service account with roles:
   - Cloud Speech-to-Text User
   - Cloud Text-to-Speech User
4. Create and download JSON key file
5. Place in `ai-assistant/` directory

#### Enable Required APIs

```bash
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
```

#### Get Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create new API key
3. Save for environment configuration

### Step 3: Environment Configuration

```bash
# Copy template
cp .env.template .env

# Edit configuration
nano .env
```

**Required Environment Variables:**

```bash
# Google Cloud Credentials
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=path/to/service-account.json

# Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here

# Authentication (for ConnectX integration)
GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com

# Firestore Database Configuration
# Specify which Firestore database to use (e.g., "development", "production")
# This database must be created in your Firestore instance beforehand
# If not set, defaults to "(default)" database
FIRESTORE_DATABASE_NAME=development

# Weaviate Configuration
# Local Weaviate (self-hosted)
WEAVIATE_URL=http://localhost:8090

# Cloud Weaviate (Weaviate Cloud Services - takes precedence over local WEAVIATE_URL)
# WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
# WEAVIATE_API_KEY=your-weaviate-cloud-api-key

# Language and Voice Configuration
# German configuration
LANGUAGE_CODE_DE=de-DE
VOICE_NAME_DE=de-DE-Chirp3-HD-Sulafat
# English configuration
LANGUAGE_CODE_EN=en-US
VOICE_NAME_EN=en-US-Chirp3-HD-Sulafat

# Server Configuration
PORT=8080
LOG_LEVEL=INFO
```

## ⚙️ Configuration

### Weaviate Configuration

The AI Assistant uses Weaviate for provider search and data persistence.

**Deployment Options:**

**Option 1: Local/Self-Hosted (Development)**
```bash
WEAVIATE_URL=http://localhost:8090
```
- Start local Weaviate in Docker: `cd weaviate && docker-compose up`
- See [Weaviate Documentation](weaviate.md) for detailed setup

**Option 2: Weaviate Cloud Services (Production)**
```bash
WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
WEAVIATE_API_KEY=your-weaviate-cloud-api-key
```
- Create cluster at https://console.weaviate.cloud/
- Takes precedence over local WEAVIATE_URL if both are set

**Features:**
- Semantic provider matching using vector embeddings
- Persistent data storage
- Hybrid search (vector + keyword)
- Support for both local and cloud deployments

### Voice Configuration

**Supported Languages:**
- German (`de-DE`) - Configured via `LANGUAGE_CODE_DE` and `VOICE_NAME_DE`
- English (`en-US`) - Configured via `LANGUAGE_CODE_EN` and `VOICE_NAME_EN`

**Configuration:**

Set language and voice parameters in `.env`:

```bash
# German configuration
LANGUAGE_CODE_DE=de-DE
VOICE_NAME_DE=de-DE-Chirp3-HD-Sulafat

# English configuration
LANGUAGE_CODE_EN=en-US
VOICE_NAME_EN=en-US-Chirp3-HD-Sulafat
```

**Available Voices:**

**German (de-DE):**
- `de-DE-Chirp3-HD-Sulafat` - Chirp3 HD model (recommended)
- `de-DE-Neural2-A` - Female
- `de-DE-Neural2-B` - Male
- `de-DE-Neural2-C` - Female
- `de-DE-Neural2-D` - Male

**English (en-US):**
- `en-US-Chirp3-HD-Kore` - Chirp3 HD model (recommended)
- `en-US-Neural2-A` - Female
- `en-US-Neural2-C` - Male
- `en-US-Neural2-E` - Female
- `en-US-Neural2-F` - Male

See [Google TTS Voice List](https://cloud.google.com/text-to-speech/docs/voices) for more options.

## 🏃 Running the Server

### Docker (Recommended)

```bash
cd ai-assistant

# Start server
docker-compose up ai-assistant

# Start in background
docker-compose up -d ai-assistant

# View logs
docker-compose logs -f ai-assistant

# Stop server
docker-compose down
```

**Server starts on**: `http://localhost:8080`

### Local Development

```bash
cd ai-assistant

# Activate virtual environment
source ../.venv/bin/activate

# Run server
python main.py

# Or with auto-reload
python -m uvicorn ai_assistant.main:app --reload --host 0.0.0.0 --port 8080
```

### With Weaviate

```bash
# Terminal 1: Start Weaviate
cd weaviate
docker-compose up -d

# Terminal 2: Initialize database
cd ../ai-assistant
python scripts/init_database.py --load-test-data

# Terminal 3: Start AI-Assistant
docker-compose up ai-assistant
```

## 🔌 API Endpoints

### Health Check & Signaling

```bash
GET /health               # Service health status
WS  /ws                   # WebRTC signaling WebSocket
POST /sign_in_google      # Google authentication exchange
```

### User Management

```bash
POST /user/sync           # Sync user data (Firestore <-> Weaviate)
POST /user/logout         # User logout
GET  /user                # Get current user profile
PUT  /user                # Update current user profile
GET  /users/{id}/user     # Get public profile of another user
```

### Competencies (Skills)

```bash
POST   /user/competencies       # Add competence (triggers Weaviate sync)
DELETE /user/competencies/{id}  # Remove competence
```

### Service Requests

```bash
GET  /service_requests          # List all requests for user
POST /service_requests          # Create new request
PUT  /service_requests/{id}/status # Update status
```

### Favorites

```bash
GET    /favorites               # List favorites
POST   /favorites/{user_id}     # Add favorite
DELETE /favorites/{user_id}     # Remove favorite
```

### Reviews

```bash
POST   /reviews                 # Create review
GET    /reviews/{id}            # Get review details
GET    /reviews/user/{id}       # Get reviews FOR a user
GET    /reviews/reviewer/{id}   # Get reviews BY a reviewer
PATCH  /reviews/{id}            # Update review
DELETE /reviews/{id}            # Delete review
```

### Chat & Messaging

```bash
# Chat Sessions
POST   /provider_candidates/{cid}/chats          # Start chat
GET    /provider_candidates/{cid}/chats/{id}     # Get chat details
PATCH  /provider_candidates/{cid}/chats/{id}     # Update chat
DELETE /provider_candidates/{cid}/chats/{id}     # Delete chat

# Messages
POST   .../chats/{id}/chat_messages              # Send message
GET    .../chats/{id}/chat_messages              # List messages
```

### Admin Interface

```bash
GET /admin/test-search?query=...  # Test provider search
GET /admin/conversations/{uid}    # View conversation history
```

See the API Endpoints section above for available endpoints.

## 🧪 Testing

### Run All Tests

```bash
cd ai-assistant
pytest
```

### Run Specific Test

```bash
pytest tests/test_audio_processor.py
pytest tests/test_conversation_service.py -v
```

### Test Coverage

```bash
pytest --cov=src tests/
pytest --cov=src --cov-report=html tests/
open htmlcov/index.html
```

### Test Categories

**Unit Tests:**
```bash
pytest tests/test_audio_processor.py
pytest tests/test_response_orchestrator.py
pytest tests/test_conversation_service.py
```

**Integration Tests:**
```bash
pytest tests/test_hub_spoke_architecture.py
pytest tests/test_weaviate_models.py
```

**End-to-End Tests:**
```bash
pytest tests/test_ai_assistant.py
```

### Manual Testing

**Test Provider Search:**
```bash
python scripts/test_search_providers.py
```

**Test Admin Interface:**
```bash
# Generate admin token
python scripts/generate_admin_token.py

# Test admin endpoints
python scripts/test_admin_interface.py
```

## 🚀 Deployment

### Docker Container

**Build Image:**
```bash
docker build -t ai-assistant:latest .
```

**Run Container:**
```bash
docker run -d \
  -p 8080:8080 \
  -e GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/secrets/service-account.json \
  -e GEMINI_API_KEY=your_key \
  -v $(pwd)/secrets:/secrets \
  ai-assistant:latest
```

### Kubernetes (GKE)

Uses Helm charts in `/helm/ai-assistant/`:

```bash
# Deploy to GKE
helm install ai-assistant helm/ai-assistant \
  --set image.tag=latest \
  --set secrets.geminiApiKey=$GEMINI_API_KEY \
  --set secrets.googleServiceAccount="$(cat service-account.json)"
```

See [Helm Documentation](helm.md) for detailed deployment instructions.

### Environment-Specific Configuration

**Production:**
```yaml
replicas: 3
resources:
  cpu: 1000m
  memory: 2Gi
WEAVIATE_URL: http://weaviate-service:80
```

## ⚡ Performance Tuning

### Latency Optimization

**Current Performance:**
- STT Latency: ~100-300ms (streaming)
- LLM Latency: ~500-1500ms (streaming)
- TTS Latency: ~200-500ms per sentence
- End-to-End: ~1-2 seconds for first response

**Optimization Techniques:**

1. **Parallel TTS Processing**
   ```python
   # Multiple sentences synthesized simultaneously
   tts_tasks = [synthesize(sentence) for sentence in sentences]
   results = await asyncio.gather(*tts_tasks)
   ```

2. **gRPC Streaming**
   ```python
   # Use native gRPC for 30-50% lower latency
   responses = stt_client.streaming_recognize(audio_generator())
   ```

3. **Sentence-Level Streaming**
   ```python
   # Stream TTS as soon as sentences are complete
   for sentence in llm_stream:
       asyncio.create_task(synthesize_and_stream(sentence))
   ```

### Resource Management

**Connection Limits:**
```python
# In main.py
MAX_CONNECTIONS = 100
TIMEOUT_SECONDS = 300
```

**Memory Usage:**
- Base: ~500MB
- Per Connection: ~50MB
- Recommended: 2GB RAM per instance

**CPU Usage:**
- STT: ~10-20% per stream
- TTS: ~15-25% per synthesis
- LLM: Depends on Google API
- Recommended: 1 CPU per instance

## 🐛 Troubleshooting

### Common Issues

#### Server Won't Start

**Symptoms**: Docker container exits immediately

**Solution**:
```bash
# Check logs
docker-compose logs ai-assistant

# Common issues:
# - Missing environment variables
# - Invalid service account JSON
# - Port 8080 already in use

# Fix port conflict
lsof -i :8080
kill -9 <PID>
```

#### Google Cloud API Errors

**Symptoms**: "403 Forbidden" or "401 Unauthorized"

**Solution**:
1. Verify service account has correct roles
2. Check APIs are enabled in GCP project
3. Validate JSON file path in `.env`
4. Ensure service account JSON is valid

```bash
# Test service account
gcloud auth activate-service-account --key-file=service-account.json
gcloud auth list
```

#### WebRTC Connection Failed

**Symptoms**: Client can't establish connection

**Solution**:
1. Check server is running: `curl http://localhost:8080/health`
2. Verify WebSocket endpoint: `curl -i http://localhost:8080/ws`
3. Check firewall rules allow port 8080
4. Review server logs for connection errors
5. Verify client uses correct server URL

#### Weaviate Connection Failed

**Symptoms**: "Connection refused" to Weaviate

**Solution**:
```bash
# Check Weaviate is running
curl http://localhost:8090/v1/meta

# If not running
cd weaviate
docker-compose up -d

# Verify network connectivity
docker network ls
docker network inspect weaviate-network
```

#### High Latency

**Symptoms**: Slow responses, timeouts

**Solution**:
1. Check network connectivity to Google APIs
2. Verify gRPC streaming is enabled
3. Review logs for processing times
4. Consider scaling to more instances
5. Check Weaviate performance

### Debug Mode

Enable detailed logging:

```bash
# In .env
LOG_LEVEL=DEBUG

# Or at runtime
export LOG_LEVEL=DEBUG
python main.py
```

**Log Levels:**
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages only

### Performance Monitoring

**Built-in Metrics:**
```python
# Response times logged automatically
logger.info(f"STT latency: {stt_time:.2f}s")
logger.info(f"LLM latency: {llm_time:.2f}s")
logger.info(f"TTS latency: {tts_time:.2f}s")
```

**External Monitoring:**
- Prometheus metrics endpoint (if enabled)
- Cloud Monitoring (GKE deployments)
- Application logs

## 🔒 Security Considerations

### API Key Management
- Store keys in environment variables
- Never commit keys to git
- Use Kubernetes secrets in production
- Rotate keys regularly

### Authentication
- Validate Firebase tokens on every request
- Implement rate limiting
- Use HTTPS/TLS in production
- Restrict CORS origins

### Network Security
- Use private networks for Weaviate
- Firewall rules for GKE clusters
- VPN for admin access
- TLS for all external communications

## 🔗 Related Documentation

- [Weaviate Documentation](weaviate.md) - Database setup
- [ConnectX Documentation](connectx.md) - Mobile client
- [Architecture Overview](architecture.md) - System design
