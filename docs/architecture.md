# Architecture Overview

This document describes the architecture, design decisions, and technical implementation of the Linkora AI Voice Assistant platform.

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Linkora Platform                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌───────────────┐         ┌──────────────────┐            │
│   │   ConnectX    │◄───────►│  AI-Assistant    │            │
│   │  (Flutter)    │  WebRTC │  (Python)        │            │
│   │               │  Audio  │                  │            │
│   │  - iOS/Android│  Stream │  - STT           │            │
│   │  - UI/UX      │         │  - LLM (Gemini)  │            │
│   │  - WebRTC     │         │  - TTS           │            │
│   │  - Auth       │         │  - WebRTC Server │            │
│   └───────────────┘         └─────────┬────────┘            │
│                                       │                     │
│                                       ▼                     │
│                            ┌──────────────────┐             │
│                            │    Weaviate      │             │
│                            │  (Vector DB)     │             │
│                            │                  │             │
│                            │  - Provider Data │             │
│                            │  - Embeddings    │             │
│                            │  - Hybrid Search │             │
│                            └──────────────────┘             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│               External Services                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌────────────┐  ┌────────────┐  ┌──────────────┐          │
│   │ Google STT │  │ Google TTS │  │ Google Gemini│          │
│   └────────────┘  └────────────┘  └──────────────┘          │
│                                                             │
│   ┌────────────────┐  ┌────────────────────────────────┐    │
│   │ Firebase       │  │ Firebase Cloud Messaging (FCM) │    │
│   │ Auth/Firestore │  │ Push notifications (localised) │    │
│   └────────────────┘  └────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User speaks → ConnectX captures audio → WebRTC stream → AI-Assistant
                                                              ↓
                                                    Google Cloud STT
                                                              ↓
                                                      Text transcript
                                                              ↓
                                                    Gemini LLM
                                                              ↓
                                                      AI response text
                                                              ↓
                                                    Google Cloud TTS
                                                              ↓
AI-Assistant ← WebRTC stream ← Audio response ← ConnectX plays audio
```

## 🎯 Design Principles

### 1. Security First
- **API Keys on Server**: All credentials remain server-side
- **Token-Based Auth**: Firebase JWT tokens for authentication
- **TLS in Production**: Encrypted communication channels
- **Service Account Isolation**: Minimal GCP permissions

### 2. Low Latency
- **WebRTC P2P**: Direct peer-to-peer audio streaming
- **Streaming APIs**: STT, LLM, and TTS all stream responses
- **Async Pipeline**: Non-blocking I/O throughout
- **Parallel Processing**: Multiple TTS tasks run simultaneously
- **Native gRPC**: 30-50% lower latency vs REST

### 3. Scalability
- **Stateless Server**: Horizontally scalable
- **Connection-Based State**: No shared session storage
- **Docker Containers**: Easy deployment and scaling
- **Cloud Ready**: Cloud Run + Compute Engine deployment

### 4. Developer Experience
- **Clear Separation**: Frontend/backend boundaries
- **Standard Tools**: Flutter, Python, Docker
- **Comprehensive Tests**: Unit, integration, and E2E tests
- **CI/CD Automation**: GitHub Actions pipelines

## 📱 ConnectX (Mobile Application)

### Technology Stack
- **Framework**: Flutter 3.9.2+
- **Language**: Dart
- **WebRTC**: flutter_webrtc package
- **Authentication**: Firebase Auth
- **State Management**: Provider pattern
- **Platforms**: iOS, Android

### Key Components

#### Audio Capture & Streaming
```dart
// Captures microphone audio and streams via WebRTC
RTCPeerConnection → MediaStream → WebSocket Signaling
```

#### Authentication Flow
```dart
Firebase Auth → Google Sign-In → JWT Token → Server Validation
```

#### UI Architecture (Feature-First)
```
features/       # Feature modules
├── auth/
│   └── presentation/
└── home/
    ├── data/
    │   ├── repositories/    # Data fetching logic
    │   └── mock_home_data.dart
    └── presentation/
        ├── pages/           # View Layer (Home, Search, Favorites)
        └── viewmodels/      # State Layer (SearchViewModel, HomeTabViewModel)

core/           # Shared resources
├── providers/  # Global providers
└── widgets/    # Shared components (AppBackground)

services/       # core business logic
├── speech_service.dart
└── webrtc_service.dart
```

### WebRTC Implementation

**Peer Connection Setup:**
1. Connect to signaling server via WebSocket
2. Exchange SDP offers/answers
3. Exchange ICE candidates
4. Establish direct P2P connection
5. Stream audio bidirectionally

**Audio Pipeline:**
```
Microphone → AudioRecord → RTC DataChannel → Network → Server
Server → Network → RTC DataChannel → AudioTrack → Speaker
```

## 🤖 AI-Assistant (Backend Server)

### Technology Stack
- **Language**: Python 3.14+
- **Framework**: aiohttp (async, WebSocket + HTTP)
- **WebRTC**: aiortc library
- **APIs**: Google Cloud STT/TTS, Gemini
- **Database**: Weaviate (vector search)
- **Container**: Docker

### Architecture Layers

#### 1. WebRTC Layer
```python
# Handles WebRTC peer connections
PeerConnectionHandler
├── handle_offer()      # Process SDP offers
├── handle_ice()        # Handle ICE candidates
└── manage_tracks()     # Audio track management
```

#### 2. Audio Processing Layer
```python
# Processes audio streams
AudioProcessor
├── stream_to_stt()     # Speech-to-Text streaming
├── detect_speech()     # Voice activity detection
└── handle_audio()      # Audio frame processing
```

#### 3. AI Orchestration Layer
```python
# Manages AI conversation flow
ResponseOrchestrator
├── process_transcript() # Handle STT output
├── generate_response()  # LLM processing
├── synthesize_speech()  # TTS generation
└── manage_conversation_stage()
```

#### 4. Conversation Management Layer
```python
# Multi-stage conversation flow
ConversationService
├── GREETING     # Initial user greeting
├── TRIAGE       # Information gathering
├── FINALIZE     # Provider presentation
└── COMPLETED    # Session wrap-up
```

#### 5. Data Layer
```python
# Provider search and matching
DataProvider
├── search_providers()   # Weaviate hybrid search
├── embed_query()        # Vector embeddings
└── rank_results()       # Relevance scoring
```

### Conversation Stages

```
┌──────────┐
│ GREETING │  "Hello [Name], how can I help you?"
└────┬─────┘
     │ User describes need
     ▼
┌──────────┐
│ TRIAGE   │  Asks scoping questions (size, timing, etc.)
└────┬─────┘
     │ User provides details
     │ Agent says "search database"
     ▼
┌──────────┐
│ FINALIZE │  Presents matched providers, handles feedback
└────┬─────┘
     │ User accepts/rejects
     ▼
┌──────────┐
│COMPLETED │  Confirms and ends session
└──────────┘
```

### Streaming Pipeline

**Optimized for Low Latency:**
```
Audio → STT Stream → Transcript Buffer → LLM Stream → Sentence Splitter
                                                              ↓
                                            Parallel TTS Tasks (async)
                                                              ↓
                                            Audio Chunks → WebRTC Stream
```

**Key Optimizations:**
- **Sentence-Level Parallelization**: Multiple TTS tasks run concurrently
- **No Thread Pools**: Pure async/await (lower overhead)
- **gRPC Streaming**: Native streaming for Google APIs
- **Interrupt Handling**: Stop TTS on user speech detection

## 🗄️ Weaviate (Vector Database)

### Purpose
Semantic search for service provider matching using:
- Vector embeddings (text2vec-model2vec)
- Hybrid search (vector + BM25)
- Automatic embedding generation

### Schema

**ServiceProvider Collection:**
```python
{
    "name": str,              # Provider name
    "description": str,       # Service description (vectorized)
    "category": str,          # Service category
    "phone": str,             # Contact phone
    "email": str,             # Contact email
    "city": str,              # Location
    "relevance_score": float  # Search relevance (0-1)
}
```

**User Collection:**
```python
{
    "uid": str,               # Firebase UID
    "email": str,             # User email
    "name": str,              # Display name
    "created_at": datetime    # Account creation
}
```

### Search Algorithm

**Hybrid Search:**
```python
# Combines vector similarity and keyword matching
search_providers(query, filters)
    → text2vec-model2vec embedding
    → Vector similarity search (0.7 weight)
    → BM25 keyword search (0.3 weight)
    → Combined relevance scoring
    → Filtered by category/location
    → Top 5 results
```

### Deployment Options

**Local (Development):**
- Docker Compose setup
- Port 8090 (HTTP), 50051 (gRPC)
- Persistent volume storage

**Cloud (Production):**
- Weaviate Cloud Services
- Managed hosting, auto-scaling
- Free tier available

## 🔄 Data Flow

### Complete Request Flow

```
1. User Authentication
   ConnectX → Firebase Auth → JWT Token → AI-Assistant validates

2. WebRTC Connection
   ConnectX → WebSocket Signaling → SDP Exchange → P2P Connection

3. Voice Input
   Microphone → ConnectX → WebRTC Audio → AI-Assistant

4. Speech-to-Text
   Audio Stream → Google Cloud STT (gRPC) → Text Transcript

5. LLM Processing
   Transcript → Gemini → AI Response

6. Provider Search (if needed)
   Query → Weaviate Hybrid Search → Top Providers

7. Text-to-Speech
   Response Text → Google Cloud TTS (parallel) → Audio Chunks

8. Audio Response
   Audio Chunks → WebRTC Stream → ConnectX → Speaker

9. Push Notifications (async, out-of-band)
   Service Request status change → NotificationService → FCM → ConnectX (background/foreground)
   Each recipient's language (EN/DE) is fetched from Firestore before the notification is sent.
```

## 🚀 Deployment Architecture

### Development Environment
```
localhost:8080    → AI-Assistant
localhost:8090    → Weaviate
localhost:60099   → ConnectX Web (optional)
```

### Production (Cloud Run + Compute Engine)
```
Cloud Run: ai-assistant (europe-west3, 1–3 instances)
├── Secrets via Secret Manager (gemini-api-key, admin-secret-key)
└── Workload Identity → Speech, TTS, Firebase, Firestore

Compute Engine VM: weaviate-vm (e2-medium, europe-west3-a)
└── Docker Compose: Weaviate + text2vec-model2vec
```

### CI/CD Pipeline
```
GitHub → Actions → Build → Test → Docker Build → Artifact Registry → Cloud Run deploy
                                             └── weaviate/** change → SSH → docker compose up
```

## 🔐 Security Architecture

### Authentication Flow
```
User → Google Sign-In → Firebase Auth → JWT Token
    ↓
AI-Assistant validates token with Firebase Admin SDK
    ↓
Token contains: uid, email, name, exp
    ↓
Server creates User in Weaviate (if new)
    ↓
Session authenticated
```

### API Key Management
- **Client**: No API keys (only OAuth client ID)
- **Server**: All credentials in environment variables
- **GCP**: Service account with minimal permissions
- **Secrets**: Secret Manager in production

### Network Security
- **TLS**: Required in production
- **WebRTC**: DTLS encryption for media
- **Firewall**: GCE firewall rules restrict Weaviate port access
- **CORS**: Configured for allowed origins

## 📊 Performance Characteristics

### Latency Targets
- **STT Latency**: ~100-300ms (streaming)
- **LLM Latency**: ~500-1500ms (streaming)
- **TTS Latency**: ~200-500ms (per sentence)
- **End-to-End**: ~1-2 seconds (first response)

### Scalability
- **Connections**: 100+ concurrent per instance
- **Horizontal Scaling**: Add replicas as needed
- **Database**: Weaviate handles millions of vectors
- **Stateless**: No session affinity required

### Resource Requirements
- **AI-Assistant**: 1 CPU, 2GB RAM per instance
- **Weaviate**: 2 CPU, 4GB RAM (production)
- **ConnectX**: <50MB app size, minimal battery drain

## 🛠️ Technology Choices

### Why Flutter?
- Cross-platform (iOS/Android)
- Excellent WebRTC support
- Fast development
- Native performance
- Hot reload for rapid iteration

### Why Python + FastAPI?
- Excellent async support
- Rich AI/ML ecosystem
- aiortc for WebRTC
- Fast development
- Easy integration with Google Cloud

### Why Weaviate?
- Built for semantic search
- Automatic embeddings
- Hybrid search (vector + keyword)
- Easy Docker deployment
- RESTful API

### Why WebRTC?
- Low latency P2P communication
- Native browser/mobile support
- Bidirectional audio streaming
- NAT traversal built-in
- Industry standard