# Linkora - AI Voice Assistant Platform

A complete voice-based AI assistant platform built with Flutter and Python, featuring real-time WebRTC audio streaming and AI-powered conversations.

## 🎯 Quick Links

### 📚 Documentation
- **[Getting Started Guide](docs/getting-started.md)** - Start here for initial setup
- **[Architecture Overview](docs/architecture.md)** - Understand the system design

### 🛠️ Component Documentation
- **[ConnectX (Mobile App)](docs/connectx.md)** - Flutter application
- **[AI-Assistant (Backend)](docs/ai-assistant.md)** - Python WebRTC server
- **[Weaviate (Database)](docs/weaviate.md)** - Vector database

### 🚀 Infrastructure
- **[Deployment](docs/deployment.md)** - Cloud Run + Compute Engine setup

## 🎯 What is Linkora?

Linkora is a modern AI voice assistant platform that enables natural voice conversations with AI. The platform consists of three main components:

1. **ConnectX** - Flutter mobile application (iOS/Android)
2. **AI-Assistant** - Python WebRTC server for AI processing
3. **Weaviate** - Vector database for semantic provider matching

### Key Features

- 🎙️ Real-time voice interaction with minimal latency
- 🔒 Secure architecture (API keys stay on server)
- ⚡ WebRTC streaming for low latency
- 🤖 Powered by Google Gemini 3.0, Cloud Speech-to-Text, and TTS
- 📱 Cross-platform (iOS and Android)
- 🐳 Containerized for easy deployment
- 🚀 Horizontally scalable stateless design


## 📁 Repository Structure

```
Fides/
├── docs/                 # 📖 Comprehensive documentation
│   ├── README.md        # Documentation index
│   ├── getting-started.md
│   ├── architecture.md
│   ├── connectx.md
│   ├── ai-assistant.md
│   ├── weaviate.md
│   └── deployment.md
│
├── connectx/             # 📱 Flutter mobile application
│   ├── lib/             # Dart source code
│   ├── android/         # Android platform
│   ├── ios/             # iOS platform
│   └── test/            # Tests
│
├── ai-assistant/         # 🤖 Python WebRTC server
│   ├── src/             # Python source code
│   ├── scripts/         # Utility scripts (incl. download_models.py)
│   ├── tests/           # Unit and integration tests
│   ├── models/          # Bundled ML models (Git LFS — run `git lfs pull`)
│   ├── Dockerfile       # Container definition
│   └── docker-compose.yml
│
├── weaviate/             # 🗄️ Weaviate docker-compose + VM startup script
│
├── .github/              # 🔄 CI/CD workflows
│   └── workflows/
│       ├── cloud-deploy.yml
│       ├── ai-assistant-test.yml
│       └── connectx-test.yml
│
└── .devcontainer/        # 🐳 VS Code Dev Container
    ├── devcontainer.json
    └── Dockerfile
```

## 🚀 Quick Start

### Prerequisites

- **For Mobile App**: Flutter SDK (^3.9.2+), iOS/Android device
- **For Backend**: Python 3.14+, Docker, Google Cloud account, Gemini API key
- **Git LFS**: required to pull bundled ML model weights (see below)

### 0. Clone with Git LFS

This repo uses [Git LFS](https://git-lfs.com) to store the cross-encoder model weights (~87 MB).
Install LFS once and pull the files after cloning:

```bash
# Install (macOS)
brew install git-lfs
git lfs install          # registers LFS hooks globally (run once per machine)

# After cloning the repo
git lfs pull             # downloads model.safetensors and any other LFS-tracked files
```

If you skip `git lfs pull`, the `model.safetensors` file will be a 134-byte pointer and the
backend will fall back to downloading the model from HuggingFace Hub at first startup.

> **First-time setup without LFS access**: run `python ai-assistant/scripts/download_models.py`
> to download the model files directly from HuggingFace Hub into `ai-assistant/models/`.

### 1. Start the Backend Server

```bash
cd ai-assistant

# Copy and configure environment
cp .env.template .env
# Edit .env with your credentials

# Start with Docker
docker-compose up ai-assistant

# Server starts on localhost:8080
```

**See**: [AI-Assistant Documentation](docs/ai-assistant.md) for detailed setup.

### 2. Run the Mobile App

```bash
cd connectx

# Install dependencies
flutter pub get

# Configure environment
cp .env.template .env
# Edit .env with server URL

# Run on device
flutter run
```

**See**: [ConnectX Documentation](docs/connectx.md) for detailed setup including Firebase configuration.

### 3. Start Weaviate

The AI Assistant requires Weaviate for provider search and data persistence:

```bash
# Start Weaviate
cd weaviate
docker-compose up -d

# Initialize database
cd ../ai-assistant
python scripts/init_database.py --load-test-data

```

**See**: [Weaviate Documentation](docs/weaviate.md) for detailed configuration.

## 📚 Documentation Overview

All documentation is organized in the [`/docs`](docs/) directory with a consistent structure:

### Getting Started
- **[Getting Started Guide](docs/getting-started.md)** - Quick start for new developers
- **[Architecture Overview](docs/architecture.md)** - System design and technical implementation

### Components
- **[ConnectX](docs/connectx.md)** - Mobile application (Flutter)
- **[AI-Assistant](docs/ai-assistant.md)** - Backend server (Python)
- **[Weaviate](docs/weaviate.md)** - Vector database

### Infrastructure
- **[Deployment](docs/deployment.md)** - Cloud Run + Compute Engine

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Linkora Platform                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌───────────────┐         ┌──────────────────┐            │
│   │   ConnectX    │◄───────►│  AI-Assistant    │            │
│   │  (Flutter)    │  WebRTC │  (Python)        │            │
│   │               │  Audio  │                  │            │
│   │  - iOS        │  Stream │  - STT           │            │
│   │  - Android    │         │  - LLM (Gemini)  │            │
│   │  - WebRTC     │         │  - TTS           │            │
│   │  - Firebase   │         │  - WebRTC Server │            │
│   └───────────────┘         └─────────┬────────┘            │
│                                       │                     │
│                                       ▼                     │
│                            ┌──────────────────┐             │
│                            │    Weaviate      │             │
│                            │  (Vector DB)     │             │
│                            │  - Provider Data │             │
│                            │  - Embeddings    │             │
│                            │  - Hybrid Search │             │
│                            └──────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

**Read more**: [Architecture Overview](docs/architecture.md)

## 🧪 Testing

### Backend Tests
```bash
cd ai-assistant
pytest
pytest --cov=src tests/  # With coverage
```

### Frontend Tests
```bash
cd connectx
flutter test
```

## 🚀 Deployment

### Development
- Docker Compose for local development
- See [Getting Started Guide](docs/getting-started.md)

### Production
- Cloud Run (AI-Assistant) + Compute Engine VM (Weaviate)
- GitHub Actions for CI/CD

**See**: [Deployment Documentation](docs/deployment.md)

## 🔧 CI/CD & DevContainer

### GitHub Actions Workflows

The project includes automated CI/CD pipelines:

1. **ConnectX Test** - Builds and tests Flutter app in devcontainer
2. **AI-Assistant Test** - Runs Python backend tests
3. **Build DevContainer** - Pre-builds and caches the development container
4. **Cloud Deploy** - Deploys to Cloud Run/Compute Engine on successful tests

### DevContainer Cache & Rebuild

To speed up CI builds, we cache the devcontainer image. Here's how to manage it:

#### Normal Builds (Uses Cache)
Automatic - no action needed. The CI will use cached layers to speed up builds (1-2 min instead of 10 min).

#### Force Rebuild from Scratch

**Option 1: Manual Workflow Trigger (Recommended)**
1. Go to GitHub → Actions tab
2. Select "Build & Test ConnectX APK" or "Build and Cache DevContainer"
3. Click "Run workflow"
4. Check ✅ **"Force rebuild without cache"**
5. Click "Run workflow"

**Option 2: Commit Message Trigger**
Include `[rebuild]` or `[no-cache]` in your commit message:
```bash
git commit -m "Update dependencies [rebuild]"
git push
```

**Option 3: Delete Cache via GitHub CLI**
```bash
gh cache delete devcontainer-cache --repo Fides-Connect/Fides
```

**Option 4: GitHub UI**
1. Go to your repo → Settings → Actions → Caches
2. Find and delete the devcontainer cache

#### When to Force Rebuild?
- After major Dockerfile changes
- When cache corruption is suspected
- After updating system dependencies (Java, Android SDK, etc.)
- To verify a clean build without cached layers

### CI Space Optimizations

The CI is optimized to prevent "No space left on device" errors:

- **Minimal Docker image**: Only essential packages installed
- **Aggressive cleanup**: Removes unused tools, docs, caches between steps
- **Smart caching**: Reuses devcontainer layers across builds
- **Single platform build**: Builds only ARM64 APK for testing
- **Gradle cache cleanup**: Removes build artifacts after APK creation

**Current space savings**: ~17-19 GB freed per CI run