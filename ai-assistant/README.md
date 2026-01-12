# AI Assistant - Real-Time Voice AI Service

A containerized AI assistant service that provides real-time voice interaction capabilities using WebRTC, Google Cloud APIs, and Google Gemini AI.

## 📑 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Usage & API](#usage--api)
- [Testing](#testing)
- [Deployment](#deployment)
- [Admin Debug Interface](#admin-debug-interface)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Client Integration](#client-integration)

## Overview

### What This Service Does

This AI assistant service:
- ✅ Receives audio streams from clients via WebRTC
- ✅ Converts speech to text using Google Cloud Speech API
- ✅ Processes queries using Google Gemini 2.0 Flash
- ✅ Generates natural-sounding responses using Google Cloud TTS
- ✅ Streams audio responses back to clients via WebRTC
- ✅ Runs in a containerized environment (Docker)
- ✅ Handles multiple concurrent connections

### Why This Service

**Benefits:**
- 🔒 **Secure**: No API credentials in client applications
- ⚡ **Efficient**: Offloaded processing from mobile devices
- 🔋 **Battery-friendly**: Reduced client-side resource usage
- 🔄 **Centralized**: Easy updates without app redeployment
- 🌐 **Multi-platform**: Works with any WebRTC-capable client

## Features

### Core Capabilities

- **Real-time Voice Processing**: Low-latency continuous speech recognition and audio streaming
- **Multi-Stage Conversations**: Dynamic prompt switching across greeting, triage, and finalization stages
- **Optimized Streaming Pipeline**: Full streaming STT → LLM → TTS for minimal latency
- **Interrupt Support**: User can interrupt AI responses by speaking
- **Parallel Processing**: Multiple TTS tasks run simultaneously for faster responses
- **Intelligent Provider Matching**: Weaviate vector search for semantic provider matching
- **Multi-language Support**: Configurable language and voice settings
- **Chat Context**: Maintains conversation history per session
- **Scalable Architecture**: Stateless design for horizontal scaling
- **Production-ready**: Comprehensive error handling and logging
- **Database**: Self-hosted Weaviate with automatic embeddings for smart provider search

### Conversation Stages

The AI Assistant implements a **three-stage conversation flow** with automatic transitions:

```
┌──────────┐
│ GREETING │ Personalized greeting by name, asks user's needs
└────┬─────┘
     │
     ▼
┌──────────┐
│ TRIAGE   │ Service coordinator mode - asks scoping questions
└────┬─────┘  (size, timing, requirements - not diagnostics)
     │
     │ Agent says "database durchsuchen" → Auto-transition
     ▼
┌──────────┐
│ FINALIZE │ Presents matched providers, handles acceptance/rejection
└────┬─────┘
     │
     ▼
┌──────────┐
│COMPLETED │ Confirms request, explains next steps, says goodbye
└──────────┘
```

**Key Features:**
- **Automatic stage transitions** - No manual intervention required
- **Context preservation** - All conversation data maintained across stages
- **Smart provider search** - Category detection and relevance scoring
- **Dynamic prompts** - Each stage uses optimized behavior and instructions

### Technical Features

- WebRTC peer-to-peer connections
- WebSocket signaling server
- Continuous speech-to-text streaming
- Transcript-based interrupt detection
- **Native gRPC Streaming**: Uses async gRPC for Google Cloud APIs (30-50% lower latency than REST)
- **Streaming APIs**: STT, LLM, and TTS all use streaming for lower latency
- **Sentence-level parallelization**: TTS processes multiple sentences simultaneously
- Fully async/await architecture with no thread pool overhead
- Asynchronous processing pipeline with detailed timing metrics
- Health check endpoints
- Docker containerization

## Quick Start

### Prerequisites

- Docker installed
- Google Cloud Platform account with enabled APIs:
  - Cloud Speech-to-Text API
  - Cloud Text-to-Speech API
  - (Optional) Generative Language API for Gemini
- Python 3.11+ (for local development)

### 1. Initial Setup

```bash
# Navigate to the ai-assistant directory
cd ai-assistant

# Copy environment template
cp .env.template .env

# Edit .env with your credentials
nano .env
```

**Required in `.env`:**
```bash
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Start the Service

**Development mode (with test data):**
```bash
# Navigate to ai-assistant directory
cd ai-assistant

# Start the service
docker-compose up ai-assistant

# Or using the run script
./scripts/run.sh start
```

**Production mode (with Weaviate):**

*Option A: Local Weaviate (self-hosted)*
```bash
# Step 1: Start Weaviate services (in separate directory)
cd /path/to/fides/weaviate
docker-compose up -d

# Step 2: Configure .env
USE_WEAVIATE=true
WEAVIATE_URL=http://localhost:8090

# Step 3: Initialize database with test data
cd /path/to/fides/ai-assistant
python scripts/init_weaviate.py

# Step 4: Start AI assistant
docker-compose up ai-assistant
```

*Option B: Weaviate Cloud Services (managed)*
```bash
# Step 1: Create cluster at https://console.weaviate.cloud/

# Step 2: Configure .env
USE_WEAVIATE=true
WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
WEAVIATE_API_KEY=your-weaviate-cloud-api-key

# Step 3: Initialize cloud database
python scripts/init_weaviate.py

# Step 4: Start AI assistant (no local Weaviate needed!)
docker-compose up ai-assistant
```

**Note**: See `/weaviate/README.md` for detailed Weaviate setup instructions.

### 3. Verify It's Running

```bash
# Check health endpoint
curl http://localhost:8080/health

# Expected response:
# {"status": "healthy", "active_connections": 0}
```

### 4. Test with Client

```bash
# Run test client with a 16kHz audio file
python tests/test_client.py --audio-file test_audio.wav

# Audio pipeline: 16kHz → WebRTC upsamples to 48kHz → Server processes at 48kHz → TTS at 48kHz
# Output saved to output.wav at 48kHz
```

## Architecture

### System Overview

```
┌─────────────┐         WebSocket          ┌──────────────────┐
│   Client    │ ◄─────── Signaling ───────► │ Signaling Server │
│  (WebRTC)   │                             └──────────────────┘
└─────────────┘                                      │
       │                                             │
       │ WebRTC Audio Stream                         │
       ▼                                             ▼
┌─────────────┐                           ┌──────────────────┐
│  Peer Conn  │ ───────────────────────── │ Peer Connection  │
│   Handler   │                           │     Handler      │
└─────────────┘                           └──────────────────┘
                                                   │
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │ Audio Processor  │
                                          │ (STT Streaming)  │
                                          └──────────────────┘
                                                   │
                                                   │ Continuous Audio
                                                   ▼
                                          ┌──────────────────┐
                                          │  Streaming STT   │
                                          │  (Google Cloud)  │
                                          │  [Async gRPC]    │
                                          └──────────────────┘
                                                   │ Transcript chunks
                                                   ▼
                                          ┌──────────────────┐
                                          │  Streaming LLM   │
                                          │  (Gemini AI)     │
                                          └──────────────────┘
                                                   │ Response chunks
                                                   ▼
                                          ┌──────────────────┐
                                          │  Parallel TTS    │
                                          │  (Per Sentence)  │
                                          │  [Async gRPC]    │
                                          └──────────────────┘
                                                   │
                            ┌──────────────────────┼──────────────────────┐
                            │ Audio Chunk 1        │ Audio Chunk 2        │ Audio Chunk 3
                            ▼                      ▼                      ▼
                    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
                    │  Audio Queue │      │  Audio Queue │      │  Audio Queue │
                    │  (Immediate) │      │  (Immediate) │      │  (Immediate) │
                    └──────────────┘      └──────────────┘      └──────────────┘
                            │                      │                      │
                            └──────────────────────┴──────────────────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Audio Output    │
                                          │      Track       │
                                          └──────────────────┘
                                                   │
                                                   │ WebRTC Audio Stream
                                                   ▼
                                          ┌──────────────────┐
                                          │     Client       │
                                          └──────────────────┘
```

### Data Flow

1. **Connection Establishment**
   - Client connects via WebSocket to signaling server
   - WebRTC negotiation (SDP offer/answer exchange)
   - ICE candidate exchange for NAT traversal

2. **Audio Capture**
   - Client sends audio stream via WebRTC
   - Audio processor receives PCM audio frames (48kHz)
   - Audio continuously streamed to Google Speech-to-Text
   - (Optional) Debug recording saves all received frames to WAV file

3. **Speech Processing (Continuous Streaming)**
   - Audio continuously sent to Google Speech-to-Text **streaming API via async gRPC**
   - Transcript chunks (interim and final) received in real-time
   - Final transcripts trigger AI processing
   - Interim transcripts enable interrupt detection

4. **AI Processing (Streaming)**
   - Transcript sent to Gemini AI **with streaming enabled**
   - LLM generates response **sentence-by-sentence**
   - Each sentence boundary triggers parallel TTS processing
   - Response chunks forwarded immediately

5. **Audio Synthesis (Parallel)**
   - Multiple sentences sent to Google Cloud TTS **in parallel via async gRPC**
   - Each sentence synthesized as separate task
   - Audio chunks received and queued immediately
   - No waiting for complete LLM response

6. **Audio Streaming**
   - Audio output track consumes queue
   - Frames sent via WebRTC to client
   - Proper timing maintained (20ms frames)

### Project Structure

```
ai-assistant/
├── main.py                      # Application entry point
├── Dockerfile                   # Container image definition
├── docker-compose.yml           # Docker Compose configuration
├── requirements.txt             # Python dependencies
├── .env.template                # Environment variable template
├── .gitignore                   # Git ignore rules
├── scripts/
│   ├── run.sh                   # Container management script
│   └── cloud-deploy.sh          # Cloud deployment script
├── src/
│   └── ai_assistant/
│       ├── __init__.py          # Package initialization
│       ├── __main__.py          # Application entry point
│       ├── ai_assistant.py      # Core AI logic (STT, LLM, TTS)
│       ├── audio_processor.py   # Audio processing pipeline (Continuous STT→LLM→TTS)
│       ├── audio_track.py       # Custom audio output track
│       ├── peer_connection_handler.py  # WebRTC peer connection management
│       └── signaling_server.py  # WebSocket signaling server
├── tests/
│   ├── __init__.py              # Test package marker
│   └── test_client.py           # WebRTC test client
└── README.md                    # This file
```

### gRPC Implementation

The service uses **native async gRPC streaming** for all Google Cloud API communications, providing significant performance benefits over traditional REST APIs:

**Key Benefits:**
- ⚡ **30-50% lower latency** - Binary protocol (Protobuf) over HTTP/2 vs JSON over HTTP/1.1
- 🔄 **Native bidirectional streaming** - Real-time data flow in both directions
- 🚀 **No thread pool overhead** - Pure async/await architecture eliminates context switching
- 💪 **Better resource utilization** - Connection pooling and multiplexing built-in
- 🛡️ **Improved reliability** - Automatic reconnection and flow control

**Implementation Details:**
- `SpeechAsyncClient` for Speech-to-Text streaming recognition
- `TextToSpeechAsyncClient` for Text-to-Speech synthesis
- Direct async iteration over gRPC streams
- Simplified codebase with ~80 fewer lines of threading code

For more technical details, see [`GRPC_MIGRATION.md`](GRPC_MIGRATION.md).

## Setup & Installation

### Local Development Setup

#### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

#### 2. Configure Google Cloud

**Create Service Account:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to IAM & Admin → Service Accounts
3. Create new service account
4. Grant permissions:
   - Cloud Speech-to-Text User
   - Cloud Text-to-Speech User
5. Create and download JSON key

**Enable APIs:**
```bash
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
```

#### 3. Get Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create new API key
3. Copy key to `.env` file

#### 4. Configure Environment

```bash
# Copy template
cp .env.template .env

# Edit with your values
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/path/to/service-account.json
GEMINI_API_KEY=your_api_key_here
LANGUAGE_CODE=de-DE
VOICE_NAME=de-DE-Chirp3-HD-Sulafat
```

#### 5. Run Locally

```bash
# Start server
python main.py

# Server starts on http://localhost:8080
```

### Container Setup

#### Using run.sh Script (Recommended)

```bash
# Build container
./scripts/run.sh build

# Start service
./scripts/run.sh start

# View logs
./scripts/run.sh logs

# Stop service
./scripts/run.sh stop
```

#### Using Docker Directly

```bash
# Build image
docker build -t ai-assistant -f Dockerfile .

# Run container
docker run -d \
  --name ai-assistant \
  -p 8080:8080 \
  --env-file .env \
  -v /path/to/service-account.json:/app/credentials.json \
  ai-assistant
```

#### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Configuration

### Environment Variables

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` | Path to GCP service account JSON | `/app/credentials.json` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_WEAVIATE` | Use Weaviate vector database (`true`) or local test data (`false`) | `true` |
| `WEAVIATE_URL` | Local Weaviate URL (self-hosted deployment) | `http://localhost:8090` |
| `WEAVIATE_CLUSTER_URL` | Weaviate Cloud Services cluster URL (cloud deployment) | - |
| `WEAVIATE_API_KEY` | Weaviate Cloud Services API key (cloud deployment) | - |
| `LANGUAGE_CODE` | Language for STT/TTS | `de-DE` |
| `VOICE_NAME` | TTS voice model | `de-DE-Chirp3-HD-Sulafat` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8080` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `GOOGLE_TTS_API_CONCURRENCY` | Max. conncurrent requests to Google TTS API  | `5` |
| `DEBUG_RECORD_AUDIO` | Record received audio to WAV files | `false` |

### Data Provider Modes

The AI Assistant supports two data provider modes for flexibility:

#### 1. Local Test Data Mode (Default)
- **Use Case**: Development, testing, demos without database
- **Configuration**: `USE_WEAVIATE=false` or unset
- **Features**: 
  - Uses in-memory test data (`test_data.py`)
  - 10 pre-configured service providers
  - Keyword-based category detection
  - Simple scoring algorithm
  - No external dependencies

#### 2. Weaviate Mode (Production)
- **Use Case**: Production deployment with vector search
- **Configuration**: `USE_WEAVIATE=true` + deployment option
- **Deployment Options**:
  - **Local (Development)**: Self-hosted with `WEAVIATE_URL` (see `/weaviate` directory)
  - **Cloud (Production)**: Managed WCS with `WEAVIATE_CLUSTER_URL` + `WEAVIATE_API_KEY`
- **Features**:
  - Semantic similarity matching with automatic embeddings
  - Hybrid search (vector + keyword)
  - Scalable provider database
  - Same code for both local and cloud deployments

**Switching modes**: Set `USE_WEAVIATE=true` in `.env` and configure your deployment option. The code automatically adapts with zero changes required.

### Available Languages & Voices

#### German (de-DE)
- `de-DE-Wavenet-A` (Female)
- `de-DE-Wavenet-B` (Male)
- `de-DE-Wavenet-C` (Female)
- `de-DE-Wavenet-D` (Male)
- `de-DE-Wavenet-E` (Male)
- `de-DE-Wavenet-F` (Female)
- `de-DE-Chirp3-HD-Sulafat` (Female, High Quality) - **Default**

#### English US (en-US)
- `en-US-Wavenet-A` (Male)
- `en-US-Wavenet-B` (Male)
- `en-US-Wavenet-C` (Female)
- `en-US-Wavenet-D` (Male)
- `en-US-Wavenet-E` (Female)
- `en-US-Wavenet-F` (Female)

[See full list](https://cloud.google.com/text-to-speech/docs/voices)

### Audio Configuration

**WebRTC Audio Pipeline:**
```
Client (48kHz) → WebRTC → Server (48kHz) → STT (accepts any rate) → LLM → TTS (48kHz output) → Server (48kHz) → WebRTC → Client (48kHz)
```

**No resampling occurs** - audio stays at 48kHz throughout the pipeline for optimal quality.

**Input (from Client):**
- Sample Rate: 48000 Hz (WebRTC native)
- Channels: 1 (mono)
- Format: LINEAR16 PCM
- Bit Depth: 16-bit
- Frame Size: 20ms (960 samples)

**Output (to Client):**
- Sample Rate: 48000 Hz (WebRTC native)
- Channels: 1 (mono)
- Format: LINEAR16 PCM
- Frame Size: 20ms (960 samples)

**Processing:**
- Google Cloud STT accepts 48kHz natively
- Google Cloud TTS configured for 48kHz output
- No resampling = better quality + lower latency

## Usage & API

### WebSocket Signaling API

#### Endpoint
```
ws://localhost:8080/ws
```

#### Connection Flow

1. **Client Connects**
   ```javascript
   const ws = new WebSocket('ws://localhost:8080/ws');
   ```

2. **Send WebRTC Offer**
   ```json
   {
     "type": "offer",
     "sdp": "v=0\r\no=- ... [SDP offer]"
   }
   ```

3. **Receive Answer**
   ```json
   {
     "type": "answer",
     "sdp": "v=0\r\no=- ... [SDP answer]"
   }
   ```

4. **Exchange ICE Candidates**
   ```json
   {
     "type": "ice-candidate",
     "candidate": {
       "candidate": "...",
       "sdpMid": "...",
       "sdpMLineIndex": 0
     }
   }
   ```

### HTTP Health Check

#### Endpoint
```
GET http://localhost:8080/health
```

#### Response
```json
{
  "status": "healthy",
  "active_connections": 2
}
```

### Google Sign-In: /sign_in_google

#### Endpoint
```
POST http://localhost:8080/sign_in_google
```

#### Purpose
Verify a Google ID token (obtained from client-side Google Sign-In), create a short-lived server session, and return basic user info and validation status.

#### Request
- Content-Type: application/json
- Body:
```json
{ "id_token": "<JWT ID token from Google Sign-In>" }
```

#### Successful Response (200)
```json
{
  "session_id": "uuid-string",
  "user_id": "google-sub",
  "email": "user@example.com",
  "name": "User Name",
  "is_valid": true
}
```

#### Error Responses
- 400 Bad Request: Missing or malformed `id_token`.
  ```json
  { "error": "Missing id_token" }
  ```
- 401 Unauthorized: Invalid or expired token.
  ```json
  { "error": "Invalid token", "details": "..." }
  ```
- 500 Internal Server Error: Unexpected server error.
  ```json
  { "error": "Internal server error", "details": "..." }
  ```

#### Notes & Security
- The server validates the token against the configured Google OAuth client ID (env var `GOOGLE_OAUTH_CLIENT_ID`). Ensure this is set in your `.env`.
- Use HTTPS/WSS in production when sending ID tokens to the endpoint.
- Current implementation stores sessions in-memory for demo purposes — replace with persistent session storage (database or Redis) in production.
- Do not expose server-side credentials to clients.

## Testing

### Test WebRTC Connection

Test the WebRTC connection with a sample audio file:

```bash
# From project root
python tests/test_client.py --audio-file path/to/audio.wav

# With custom server URL
python tests/test_client.py --server ws://192.168.1.100:8080/ws --audio-file test.wav

# Specify test duration
python tests/test_client.py --audio-file test.wav --duration 60
```

### Audio File Requirements

The test client requires a WAV file with:
- **Sample Rate**: 16000 Hz (16 kHz)
- **Channels**: 1 (mono)
- **Sample Width**: 16-bit (2 bytes)
- **Format**: PCM

**Audio Pipeline:**
1. Client sends 16kHz audio from your input file
2. WebRTC automatically upsamples to 48kHz for transmission (WebRTC standard)
3. Server receives 48kHz audio (WebRTC native rate)
4. Server processes at 48kHz (Google STT accepts 48kHz natively)
5. Google TTS generates 48kHz audio
6. Server sends 48kHz to client via WebRTC
7. Client receives 48kHz audio
8. Debug recordings (if enabled) save received audio at 48kHz

**Key point:** No resampling occurs on the server. Audio arrives at 48kHz from WebRTC and stays at 48kHz throughout the entire pipeline for optimal quality.

Convert audio to the correct input format:

```bash
# Using ffmpeg (input file → 16kHz mono for test client)
ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 output.wav

# Using sox  
sox input.mp3 -r 16000 -c 1 -b 16 output.wav

# Note: WebRTC will upsample to 48kHz automatically
```

### Test Workflow

1. **Start the Service**
   ```bash
   # Local
   python main.py
   
   # Or container
   ./scripts/run.sh start
   ```

2. **Run Test Client**
   ```bash
   python tests/test_client.py --audio-file test.wav
   ```

3. **Check Output**
   - Test client will connect via WebRTC
   - Send audio from the WAV file
   - Receive and save response to `output.wav`

### Writing New Tests

#### Unit Tests

Place unit tests in the `tests/` directory with `test_` prefix:

```python
# tests/test_audio_processor.py
import unittest
from ai_assistant.audio_processor import AudioProcessor

class TestAudioProcessor(unittest.TestCase):
    def test_continuous_streaming(self):
        # Test continuous STT streaming
        pass
    
    def test_interrupt_detection(self):
        # Test interrupt when user speaks during AI response
        pass
```

Run with:
```bash
python -m unittest discover tests/
```

#### Integration Tests

For integration tests, use the test client as a template:

```python
# tests/test_integration.py
from test_client import TestClient
import asyncio

async def test_full_pipeline():
    client = TestClient()
    await client.run("test_audio.wav", duration=10)
```

### Troubleshooting Tests

#### Import Errors

If you get import errors when running tests:

```bash
# Install package in development mode
pip install -e .
```

#### Connection Errors

If test client can't connect:

1. Check service is running: `curl http://localhost:8080/health`
2. Verify WebSocket URL is correct
3. Check firewall settings
4. Review service logs: `./scripts/run.sh logs`

#### Audio Issues

If audio test fails:

1. Verify audio file format (16kHz, mono, 16-bit)
2. Check Google Cloud credentials
3. Ensure APIs are enabled
4. Review service logs for errors

### Manual Testing

#### Test Health Endpoint
```bash
curl http://localhost:8080/health
```

#### Test WebSocket Connection
```bash
# Using websocat
websocat ws://localhost:8080/ws

# Send test message
{"type": "ping"}
```

### Debugging

#### Enable Debug Logging
```bash
# In .env
LOG_LEVEL=DEBUG
```

#### View Detailed Logs
```bash
# Docker
docker logs -f ai-assistant

# Local
python main.py 2>&1 | tee debug.log
```

### Continuous Integration

For CI/CD pipelines:

```yaml
# .github/workflows/test.yml (example)
- name: Run Unit Tests
  run: python -m unittest discover tests/

- name: Test Container Build
  run: ./scripts/run.sh build
```

### Common Test Scenarios

| Scenario | Command | Expected Result |
|----------|---------|-----------------|
| Health check | `curl http://localhost:8080/health` | Status 200, JSON response |
| WebSocket connect | `websocat ws://localhost:8080/ws` | Connection established |
| Audio processing | `python tests/test_client.py --audio-file test.wav` | Response audio generated |

### Future Test Considerations

Consider adding:
- Unit tests for each module
- Integration tests for full pipeline
- Load testing for concurrent connections
- Audio quality tests
- Latency benchmarks
- Error handling tests
- Mock tests for Google Cloud APIs

## Deployment

### Cloud Deployment to Google Cloud Platform

The AI Assistant includes an automated deployment script for Google Cloud Platform that handles all configuration and deployment steps.

#### Quick Start

```bash
# One-command deployment to Compute Engine
./scripts/cloud-deploy.sh deploy

# Check deployment status
./scripts/cloud-deploy.sh status

# View all available commands
./scripts/cloud-deploy.sh help
```

#### Prerequisites

1. **Install Google Cloud SDK**
   ```bash
   # macOS with Homebrew
   brew install google-cloud-sdk
   
   # Add to ~/.zshrc
   export PATH=/opt/homebrew/share/google-cloud-sdk/bin:"$PATH"
   ```

2. **Configure gcloud**
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud config set compute/region europe-west3
   gcloud config set compute/zone europe-west3-a
   gcloud auth configure-docker gcr.io
   ```

3. **Enable Required APIs** in Google Cloud Console:
   - Compute Engine API
   - Container Registry API
   - Cloud Speech-to-Text API
   - Cloud Text-to-Speech API

4. **Set up environment variables** in `.env`:
   ```bash
   GEMINI_API_KEY=your-api-key
   LANGUAGE_CODE=de-DE
   VOICE_NAME=de-DE-Chirp3-HD-Sulafat
   LOG_LEVEL=INFO
   ```

#### Deployment Script Commands

| Command | Description |
|---------|-------------|
| `deploy` | Full deployment (build + push + deploy) |
| `build` | Build container image for AMD64 |
| `push` | Push image to Google Container Registry |
| `deploy-ce [vm-name] [type]` | Deploy to Compute Engine |
| `start [vm-name]` | Start a stopped VM |
| `stop [vm-name]` | Stop a running VM |
| `delete [vm-name]` | Delete a VM |
| `status [vm-name]` | Show VM status and health |
| `logs [vm-name]` | View VM logs |
| `config` | Show current configuration |

#### Platform Comparison

| Platform | WebRTC Support | Cost | Best For |
|----------|---------------|------|----------|
| **Compute Engine** ✅ | Full (UDP+TCP) | ~$24/month | **Production** |
| Cloud Run ❌ | TCP only | Pay-per-use | Testing only |

**Why Compute Engine?** WebRTC requires UDP ports for peer-to-peer connections. Cloud Run only supports HTTP/HTTPS (TCP), making WebRTC impossible. The deployment script automatically:
- Builds AMD64-compatible images
- Configures firewall rules (TCP:8080, UDP:49152-65535)
- Sets up service accounts
- Validates deployment health

#### Machine Types & Costs

| Machine Type | vCPUs | Memory | Cost/Month* | Use Case |
|--------------|-------|--------|-------------|----------|
| e2-micro | 2 | 1 GB | ~$7 | Testing only |
| e2-small | 2 | 2 GB | ~$13 | Light usage |
| **e2-medium** | 2 | 4 GB | **~$24** | **Recommended** |
| e2-standard-2 | 2 | 8 GB | ~$48 | Heavy usage |

*Europe-west3 region, running 24/7. Stop VM when not in use to pay only storage costs (~$0.40/month).

#### Daily Operations

```bash
# Check status and get endpoints
./scripts/cloud-deploy.sh status

# Stop VM to save costs (when not in use)
./scripts/cloud-deploy.sh stop

# Start VM again
./scripts/cloud-deploy.sh start

# View logs
./scripts/cloud-deploy.sh logs
```

#### Deployment Output

After successful deployment, you'll receive:
```
External IP: 34.89.201.196
Health endpoint: http://34.89.201.196:8080/health
WebSocket endpoint: ws://34.89.201.196:8080/ws
```

Update your client `.env` file:
```properties
AI_ASSISTANT_SERVER_URL=ws://34.89.201.196:8080/ws
```

#### Custom Deployment

Deploy with custom VM name and machine type:
```bash
./scripts/cloud-deploy.sh deploy-ce my-ai-assistant e2-standard-2
```

#### Cost Optimization

1. **Stop when not in use**: Reduces cost from ~$24/month to ~$0.40/month
   ```bash
   ./scripts/cloud-deploy.sh stop
   ```

2. **Use smaller machine**: For testing/development
   ```bash
   ./scripts/cloud-deploy.sh deploy-ce ai-assistant-vm e2-small
   ```

3. **Delete when not needed**: Zero cost
   ```bash
   ./scripts/cloud-deploy.sh delete
   ```

### Local Development

For local development and testing:

```bash
# Using the run script
./scripts/run.sh start

# Or manually with Docker
docker-compose up
```

### Manual Cloud Deployment

If you need custom configuration beyond the deployment script:

#### Google Compute Engine (Manual)

```bash
# Build for AMD64 architecture (required for Cloud)
docker build --platform linux/amd64 -t gcr.io/PROJECT_ID/ai-assistant -f Dockerfile .

# Push to registry
docker push gcr.io/PROJECT_ID/ai-assistant

# Create VM with container
gcloud compute instances create-with-container ai-assistant-vm \
  --container-image=gcr.io/PROJECT_ID/ai-assistant \
  --container-env=GEMINI_API_KEY=...,LANGUAGE_CODE=de-DE,VOICE_NAME=de-DE-Chirp3-HD-Sulafat \
  --machine-type=e2-medium \
  --zone=europe-west3-a \
  --tags=ai-assistant \
  --service-account=SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com \
  --scopes=cloud-platform

# Configure firewall for WebRTC
gcloud compute firewall-rules create allow-ai-assistant \
  --allow tcp:8080,udp:49152-65535 \
  --target-tags=ai-assistant \
  --source-ranges=0.0.0.0/0
```

#### Troubleshooting Deployment

**Container won't start:**
```bash
# Check logs
./scripts/cloud-deploy.sh logs

# Wait 1-2 minutes for container to start
./scripts/cloud-deploy.sh status
```

**Health check fails:**
```bash
# Verify firewall rules
gcloud compute firewall-rules describe allow-ai-assistant

# Test from local machine
curl http://<EXTERNAL_IP>:8080/health
```

**WebRTC connection fails:**
- Ensure firewall allows UDP ports 49152-65535
- Verify VM has external IP
- Check client can reach VM IP:8080
- Verify NAT/firewall on client side allows UDP

**Architecture mismatch:**
The deployment script automatically builds for AMD64. If building manually on Apple Silicon (ARM64), always use:
```bash
docker build --platform linux/amd64 ...
```

### Scaling Considerations

#### Horizontal Scaling
- Service is stateless (except chat history)
- Can run multiple instances behind load balancer
- WebSocket connections sticky to single instance
- Use Redis for shared chat history (optional)

#### Vertical Scaling
- Memory: 512MB minimum, 1-2GB recommended per instance
- CPU: 1 vCPU minimum, 2 vCPU recommended
- Network: Ensure sufficient bandwidth for audio streams

#### Load Balancing
- Use WebSocket-aware load balancer
- Enable sticky sessions
- Configure health checks
- Set appropriate timeouts (>60s for WebSocket)

## Admin Debug Interface

The AI Assistant includes a secure admin interface for debugging, monitoring, and managing deployed servers.

### Quick Start

1. **Generate an admin secret key:**
   ```bash
   python scripts/generate_admin_token.py
   ```

2. **Add to your `.env` file:**
   ```
   ADMIN_SECRET_KEY=your_generated_secret_key_here
   ```

3. **Access admin endpoints:**
   ```bash
   export ADMIN_SECRET_KEY='your_generated_secret_key_here'
   curl -H "Authorization: Bearer $ADMIN_SECRET_KEY" http://localhost:8080/admin/health
   ```

### Available Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/health` | GET | Detailed health check with system info |
| `/admin/stats` | GET | Database and system statistics |
| `/admin/users` | GET | List all users |
| `/admin/users/{user_id}` | GET | Get specific user details |
| `/admin/providers` | GET | List all service providers |
| `/admin/notifications/send` | POST | Send push notifications |
| `/admin/notifications/test` | POST | Test notification to FCM token |
| `/admin/logs` | GET | View recent log entries |

### Common Admin Tasks

**Check server health:**
```bash
curl -H "Authorization: Bearer $ADMIN_SECRET_KEY" http://localhost:8080/admin/health | jq
```

**Send broadcast notification:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ADMIN_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Maintenance Notice",
    "body": "Server will be down for maintenance at 2 AM"
  }' \
  http://localhost:8080/admin/notifications/send
```

**View database statistics:**
```bash
curl -H "Authorization: Bearer $ADMIN_SECRET_KEY" http://localhost:8080/admin/stats | jq '.database'
```

**Test admin interface:**
```bash
python scripts/test_admin_interface.py
```

For complete documentation, see [docs/ADMIN_INTERFACE.md](docs/ADMIN_INTERFACE.md).

### Security Best Practices

1. **Use HTTPS/WSS in production**
   ```bash
   # Configure TLS certificate
   --set-env-vars SSL_CERT_PATH=/certs/fullchain.pem \
   --set-env-vars SSL_KEY_PATH=/certs/privkey.pem
   ```

2. **Implement authentication**
   - Add JWT token validation
   - Verify client credentials
   - Rate limit requests

3. **Secure credentials**
   - Use secret management (GCP Secret Manager, AWS Secrets Manager)
   - Rotate credentials regularly
   - Never commit credentials to version control

4. **Network security**
   - Use firewall rules
   - Enable VPC/private networks
   - Configure security groups

## Performance

### Latency Breakdown

**Deployment: Google Cloud (same region as APIs, optimized streaming pipeline)**

#### Time to First Audio (Optimized with gRPC Streaming)

The system uses **native async gRPC streaming and parallel processing** to minimize latency:

| Stage | Typical Latency | Pipeline Mode | Notes |
|-------|----------------|---------------|-------|
| Network RTT | 10-50ms | Sequential | Client to server round-trip |
| Speech-to-Text (gRPC streaming) | 200-500ms | Sequential | First transcript chunk via async gRPC |
| Gemini LLM (streaming) | 300-800ms | Sequential | First sentence generated |
| Text-to-Speech (gRPC parallel) | 150-400ms | **Parallel** | First sentence via async gRPC |
| Audio Streaming | 50-150ms | Sequential | WebRTC buffer + network |
| **Time to First Audio** | **~0.7-1.9 seconds** | **gRPC Optimized** | User hears response start |

#### Key Optimizations

**gRPC Streaming Benefits:**
- ⚡ **Native async gRPC**: 30-50% lower latency vs REST (binary Protobuf over HTTP/2)
- ✅ **STT Streaming**: Transcript chunks received continuously via bidirectional gRPC
- ✅ **LLM Streaming**: Response generated sentence-by-sentence
- ✅ **Parallel TTS**: Multiple sentences synthesized simultaneously via async gRPC
- ✅ **Zero thread overhead**: Pure async/await eliminates executor/queue latency
- ✅ **Immediate Audio Queue**: Audio chunks played as soon as generated
- ✅ **Interrupt Detection**: User can interrupt AI by speaking

**Note:** Response timing:
- Time to first audio: **~0.7-1.9 seconds** from when user stops speaking
- Continuous STT processes audio immediately (no silence detection delay)
- Interruption detected within ~100-200ms via interim transcripts

**Optimization recommendations:**
- Deploy service in same GCP region as Cloud APIs (e.g., `us-central1`)
- Use Google Cloud's internal network for API calls
- Enable HTTP/2 keepalive for persistent connections

### Resource Usage

#### Per Connection

| Resource | Usage | Notes |
|----------|-------|-------|
| Memory | 200-500 MB | Includes audio buffers (48kHz) |
| CPU | 10-30% | Mostly I/O bound |
| Network | ~128 kbps | Bi-directional 48kHz audio |
| Disk | Minimal | Logs only (optional debug WAV at 48kHz) |

#### System Requirements

| Connections | Memory | CPU | Network |
|-------------|--------|-----|---------|
| 1-5 | 2 GB | 2 cores | 1 Mbps |
| 5-10 | 4 GB | 4 cores | 2 Mbps |
| 10-20 | 8 GB | 8 cores | 4 Mbps |

### Optimization Tips

1. **Reduce Latency**
   - Use regional API endpoints
   - Enable HTTP/2 for Google APIs
   - Cache common responses

2. **Improve Quality**
   - Use higher quality TTS voices
   - Implement noise suppression
   - Add audio normalization

3. **Scale Better**
   - Use connection pooling
   - Implement request batching
   - Add caching layer (Redis)
   - Use CDN for static assets

## Troubleshooting

### Common Issues

#### Container Won't Start

**Problem:** Container exits immediately
```bash
# Check logs
docker logs ai-assistant

# Common causes:
# 1. Missing environment variables
# 2. Invalid credentials file
# 3. Port already in use
```

**Solution:**
```bash
# Verify .env file
cat .env | grep -v "^#"

# Check port availability
netstat -an | grep 8080

# Restart container
./run.sh restart
```

#### WebSocket Connection Fails

**Problem:** Client can't connect to WebSocket

**Diagnosis:**
```bash
# Test endpoint
websocat ws://localhost:8080/ws

# Check firewall
sudo firewall-cmd --list-all

# Verify service is running
curl http://localhost:8080/health
```

**Solution:**
- Ensure correct URL (ws:// not wss:// for local)
- Check firewall rules
- Verify port forwarding
- Check container network mode

#### No Audio Response

**Problem:** Connection works but no audio returned

**Diagnosis:**
```bash
# Enable debug logging
LOG_LEVEL=DEBUG

# Check for API errors in logs
docker logs ai-assistant | grep ERROR

# Verify API credentials
gcloud auth application-default print-access-token
```

**Solution:**
- Verify Google Cloud APIs are enabled
- Check API quotas and limits
- Ensure service account has correct permissions
- Validate audio format (16kHz, mono, LINEAR16)

#### High Latency

**Problem:** Slow response times

**Diagnosis:**
```bash
# Check system resources
top
df -h

# Monitor network
iftop

# Check API performance
time curl -X POST https://speech.googleapis.com/v1/...
```

**Solution:**
- Use regional API endpoints
- Increase container resources
- Check network bandwidth
- Monitor Google Cloud quotas

#### Audio Quality Issues

**Problem:** Distorted or choppy audio

**Possible Causes:**
- Incorrect sample rate
- Network packet loss
- Buffer underruns

**Solution:**
```bash
# Verify audio format
# Input: WebRTC sends 48kHz, mono audio
# Processing: Server processes at 48kHz
# Output: TTS generates 48kHz, mono, LINEAR16
```

### Debug Checklist

- [ ] Health endpoint returns 200
- [ ] WebSocket connection establishes
- [ ] Audio track added to peer connection
- [ ] Continuous STT receiving audio
- [ ] STT returning transcripts (interim and final)
- [ ] LLM generating responses
- [ ] TTS synthesizing audio
- [ ] Audio queue has frames
- [ ] Client receiving audio packets

### Getting Help

**Logs:**
```bash
# Full debug logs
docker logs ai-assistant > debug.log 2>&1

# Filter for errors
docker logs ai-assistant 2>&1 | grep -i error

# Follow live logs
docker logs -f ai-assistant
```

**System Info:**
```bash
# Container info
docker inspect ai-assistant

# Resource usage
docker stats ai-assistant

# Network info
docker port ai-assistant
```

## Client Integration

### Flutter/Dart Integration

#### 1. Add WebRTC Dependencies

```yaml
# pubspec.yaml
dependencies:
  flutter_webrtc: ^0.9.36
  web_socket_channel: ^2.4.0
```

#### 2. Implement WebRTC Client

```dart
// lib/services/ai_assistant_service.dart
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';

class AIAssistantService {
  late RTCPeerConnection _peerConnection;
  late WebSocketChannel _signaling;
  MediaStream? _localStream;
  
  final String serverUrl;
  
  AIAssistantService({this.serverUrl = 'ws://localhost:8080/ws'});
  
  Future<void> connect() async {
    // Initialize WebSocket signaling
    _signaling = WebSocketChannel.connect(Uri.parse(serverUrl));
    
    // Create peer connection
    final configuration = {
      'iceServers': [
        {'urls': 'stun:stun.l.google.com:19302'},
      ]
    };
    _peerConnection = await createPeerConnection(configuration);
    
    // Get user media (microphone)
    _localStream = await navigator.mediaDevices.getUserMedia({
      'audio': {
        'sampleRate': 16000,
        'channelCount': 1,
      }
    });
    
    // Add local stream to peer connection
    _localStream!.getTracks().forEach((track) {
      _peerConnection.addTrack(track, _localStream!);
    });
    
    // Handle incoming audio
    _peerConnection.onTrack = (RTCTrackEvent event) {
      if (event.track.kind == 'audio') {
        // Play received audio
        final remoteStream = event.streams[0];
        // Attach to audio element or player
      }
    };
    
    // Handle ICE candidates
    _peerConnection.onIceCandidate = (RTCIceCandidate candidate) {
      _signaling.sink.add(jsonEncode({
        'type': 'ice-candidate',
        'candidate': {
          'candidate': candidate.candidate,
          'sdpMid': candidate.sdpMid,
          'sdpMLineIndex': candidate.sdpMLineIndex,
        }
      }));
    };
    
    // Create and send offer
    final offer = await _peerConnection.createOffer();
    await _peerConnection.setLocalDescription(offer);
    
    _signaling.sink.add(jsonEncode({
      'type': 'offer',
      'sdp': offer.sdp,
    }));
    
    // Listen for signaling messages
    _signaling.stream.listen((message) async {
      final data = jsonDecode(message);
      
      if (data['type'] == 'answer') {
        await _peerConnection.setRemoteDescription(
          RTCSessionDescription(data['sdp'], 'answer')
        );
      } else if (data['type'] == 'ice-candidate') {
        await _peerConnection.addCandidate(
          RTCIceCandidate(
            data['candidate']['candidate'],
            data['candidate']['sdpMid'],
            data['candidate']['sdpMLineIndex'],
          )
        );
      }
    });
  }
  
  Future<void> disconnect() async {
    await _localStream?.dispose();
    await _peerConnection.close();
    await _signaling.sink.close();
  }
}
```

#### 3. Use in Your App

```dart
// main.dart or your voice interaction screen
import 'package:flutter/material.dart';
import 'services/ai_assistant_service.dart';

class VoiceAssistantScreen extends StatefulWidget {
  @override
  _VoiceAssistantScreenState createState() => _VoiceAssistantScreenState();
}

class _VoiceAssistantScreenState extends State<VoiceAssistantScreen> {
  late AIAssistantService _assistantService;
  bool _isConnected = false;
  
  @override
  void initState() {
    super.initState();
    _assistantService = AIAssistantService(
      serverUrl: 'ws://your-server:8080/ws'
    );
  }
  
  Future<void> _startConversation() async {
    try {
      await _assistantService.connect();
      setState(() => _isConnected = true);
    } catch (e) {
      print('Connection error: $e');
    }
  }
  
  Future<void> _stopConversation() async {
    await _assistantService.disconnect();
    setState(() => _isConnected = false);
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('AI Assistant')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              _isConnected ? Icons.mic : Icons.mic_off,
              size: 100,
              color: _isConnected ? Colors.green : Colors.grey,
            ),
            SizedBox(height: 20),
            ElevatedButton(
              onPressed: _isConnected ? _stopConversation : _startConversation,
              child: Text(_isConnected ? 'Stop' : 'Start Conversation'),
            ),
          ],
        ),
      ),
    );
  }
  
  @override
  void dispose() {
    _assistantService.disconnect();
    super.dispose();
  }
}
```

### Best Practices

1. **Error Handling**
   - Handle connection failures gracefully
   - Implement automatic reconnection with exponential backoff
   - Show user-friendly error messages

2. **User Experience**
   - Request microphone permissions early
   - Show connection status clearly
   - Provide visual feedback during voice activity
   - Handle audio playback properly

3. **Performance**
   - Use appropriate audio quality settings
   - Monitor connection quality
   - Implement audio buffering if needed
   - Clean up resources on disconnect

4. **Security**
   - Use WSS (secure WebSocket) in production
   - Implement authentication if needed
   - Validate server certificates
   - Don't expose credentials in client code