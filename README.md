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
- **[Helm Charts](docs/helm.md)** - Kubernetes deployment
- **[Terraform](docs/terraform.md)** - Infrastructure as code

## 🎯 What is Linkora?

Linkora is a modern AI voice assistant platform that enables natural voice conversations with AI. The platform consists of three main components:

1. **ConnectX** - Flutter mobile application (iOS/Android)
2. **AI-Assistant** - Python WebRTC server for AI processing
3. **Weaviate** - Vector database for semantic provider matching

### Key Features

- 🎙️ Real-time voice interaction with minimal latency
- 🔒 Secure architecture (API keys stay on server)
- ⚡ WebRTC streaming for low latency
- 🤖 Powered by Google Gemini 2.0, Cloud Speech-to-Text, and TTS
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
│   ├── helm.md
│   └── terraform.md
│
├── connectx/             # 📱 Flutter mobile application
│   ├── lib/             # Dart source code
│   ├── android/         # Android platform
│   ├── ios/             # iOS platform
│   └── test/            # Tests
│
├── ai-assistant/         # 🤖 Python WebRTC server
│   ├── src/             # Python source code
│   ├── scripts/         # Utility scripts
│   ├── tests/           # Unit and integration tests
│   ├── Dockerfile       # Container definition
│   └── docker-compose.yml
│
├── weaviate/             # 🗄️ Vector database infrastructure
│   └── docker-compose.yml
│
├── helm/                 # ☸️ Kubernetes Helm charts
│   ├── ai-assistant/    # Backend deployment
│   └── weaviate/        # Database deployment
│
├── terraform/            # 🏗️ Infrastructure as Code
│   ├── main.tf          # GKE cluster configuration
│   ├── variables.tf
│   └── bootstrap/       # State backend setup
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
- **For Backend**: Python 3.11+, Docker, Google Cloud account, Gemini API key

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
cp template.env .env
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
python scripts/init_hub_spoke_schema.py --load-test-data

```

**See**: [Weaviate Documentation](docs/weaviate.md) for detailed configuration.

## 📚 Documentation Overview

All documentation is organized in the [`/docs`](docs/) directory with a consistent structure:

### Getting Started
- **[Getting Started Guide](docs/getting-started.md)** - Quick start for new developers
- **[Architecture Overview](docs/architecture.md)** - System design and technical implementation
- **[Installation Guide](docs/installation.md)** - Comprehensive setup instructions

### Components
- **[ConnectX](docs/connectx.md)** - Mobile application (Flutter)
- **[AI-Assistant](docs/ai-assistant.md)** - Backend server (Python)
- **[Weaviate](docs/weaviate.md)** - Vector database

### Infrastructure
- **[Helm Charts](docs/helm.md)** - Kubernetes deployment
- **[Terraform](docs/terraform.md)** - Infrastructure provisioning
- **[CI/CD Pipeline](docs/ci-cd.md)** - Automated deployment

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
- Kubernetes with Helm charts
- Terraform for infrastructure
- GitHub Actions for CI/CD

**See**: [Helm Documentation](docs/helm.md) and [Terraform Documentation](docs/terraform.md)