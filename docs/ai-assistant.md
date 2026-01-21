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
- Processes queries using Google Gemini 2.0 Flash
- Generates natural-sounding responses using Google Cloud TTS
- Streams audio responses back to clients
- Manages multi-stage conversations
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
     │ Auto-transition on "database durchsuchen"
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
│   ├── data_provider.py           # Weaviate integration
│   ├── user_endpoints.py          # User management API
│   ├── common_endpoints.py        # Shared API endpoints
│   ├── weaviate_models.py         # Database models
│   ├── hub_spoke_schema.py        # Database schema
│   ├── hub_spoke_search.py        # Search implementation
│   ├── hub_spoke_ingestion.py     # Data ingestion
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
│       └── transcript_processor.py    # Transcript handling
│
├── scripts/
│   ├── init_hub_spoke_schema.py   # Database initialization
│   ├── generate_admin_token.py    # Admin authentication
│   ├── test_admin_interface.py    # Admin testing
│   └── test_search_providers.py   # Search testing
│
├── tests/                         # Unit and integration tests
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
            ├─→ Gemini 2.0 (Streaming)
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

# Weaviate Configuration
USE_WEAVIATE=true  # Required: System exclusively uses Weaviate

# Local Weaviate
WEAVIATE_URL=http://localhost:8090

# Cloud Weaviate (optional, takes precedence over WEAVIATE_URL)
# WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
# WEAVIATE_API_KEY=your-weaviate-cloud-api-key

# Server Configuration
PORT=8080
LOG_LEVEL=INFO
```

## ⚙️ Configuration

### Development vs Production

**Development Mode (No Database):**
```bash
USE_WEAVIATE=false
```
- Uses in-memory test data
- No Weaviate dependency
- Fast startup
- Good for testing

**Production Mode (With Weaviate):**
```bash
USE_WEAVIATE=true
WEAVIATE_URL=http://localhost:8090
```
- Full provider search
- Persistent data
- Semantic matching
- Requires Weaviate running

See [Weaviate Documentation](weaviate.md) for database setup.

### Voice Configuration

**Language & Voice Settings:**

```python
# In src/ai_assistant/ai_assistant.py (AIAssistant.__init__)

# Language code (BCP-47)
LANGUAGE_CODE = "de-DE"  # German
# LANGUAGE_CODE = "en-US"  # English

# TTS voice configuration (passed to AIAssistant constructor)
voice_name = 'de-DE-Chirp3-HD-Sulafat'  # Current default

# Alternative voices:
# voice_name = 'de-DE-Neural2-D'  # Male voice
# voice_name = 'de-DE-Neural2-C'  # Female voice
```

**Available Voices:**
- `de-DE-Chirp3-HD-Sulafat` - Chirp3 HD model (current default)
- `de-DE-Neural2-A` - Female
- `de-DE-Neural2-B` - Male
- `de-DE-Neural2-C` - Female
- `de-DE-Neural2-D` - Male

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
python scripts/init_hub_spoke_schema.py --load-test-data

# Terminal 3: Start AI-Assistant
docker-compose up ai-assistant
```

## 🔌 API Endpoints

### Health Check

```bash
GET /health

# Response
{
  "status": "healthy",
  "active_connections": 0
}
```

### WebSocket Signaling

```bash
WS /ws

# Messages format
{
  "type": "offer|answer|ice",
  "sdp": "<sdp-string>",
  "candidate": "<ice-candidate>"
}
```

### User Management

```bash
# Get current user
GET /api/users/me
Authorization: Bearer <firebase-token>

# Update user profile
PUT /api/users/me
Authorization: Bearer <firebase-token>
Body: {"name": "John Doe", "email": "john@example.com"}
```

### Provider Search (Admin)

```bash
# Search providers
POST /api/providers/search
Authorization: Bearer <admin-token>
Body: {
  "query": "plumber",
  "filters": {"city": "Berlin"}
}

# Response
{
  "providers": [
    {
      "name": "Berlin Plumbing",
      "description": "Professional plumbing services",
      "relevance_score": 0.92,
      "phone": "+49 30 1234567",
      "email": "info@berlinplumbing.de",
      "city": "Berlin"
    }
  ]
}
```

### Admin Interface

```bash
# Test provider search
GET /admin/test-search?query=plumber&user_id=user123
Authorization: Bearer <admin-token>

# View conversation history
GET /admin/conversations/<user_id>
Authorization: Bearer <admin-token>
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

**Development:**
```yaml
replicas: 1
resources:
  cpu: 500m
  memory: 1Gi
USE_WEAVIATE: false
```

**Production:**
```yaml
replicas: 3
resources:
  cpu: 1000m
  memory: 2Gi
USE_WEAVIATE: true
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

### Scaling Strategy

**Horizontal Scaling:**
```bash
# Increase replicas
kubectl scale deployment ai-assistant --replicas=5
```

**Load Balancing:**
- Use Kubernetes LoadBalancer service
- No session affinity required (stateless)
- Health checks on `/health` endpoint

**Auto-Scaling:**
```yaml
# HorizontalPodAutoscaler
minReplicas: 2
maxReplicas: 10
targetCPUUtilizationPercentage: 70
```

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

---

**Next Steps**: [Weaviate Documentation](weaviate.md) | [ConnectX Documentation](connectx.md)
