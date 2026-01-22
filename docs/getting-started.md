# Getting Started with Linkora

This guide will help you get the Linkora AI Voice Assistant platform up and running quickly.

## 🎯 What is Linkora?

Linkora is a complete voice-based AI assistant platform that enables natural voice conversations with AI. The platform consists of:

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

## 📋 Prerequisites

### For All Developers
- Git
- Text editor or IDE (VS Code recommended)
- Basic understanding of REST APIs and WebRTC

### For Mobile Development (ConnectX)
- Flutter SDK (^3.9.2 or higher)
- Dart SDK
- iOS/Android device or emulator
- Xcode (for iOS) or Android Studio (for Android)

### For Backend Development (AI-Assistant)
- Python 3.11+
- Docker and Docker Compose
- Google Cloud Platform account
- Google Gemini API key

### For Infrastructure/DevOps
- Kubernetes knowledge
- Helm 3+
- Terraform
- gcloud CLI

## 🚀 Quick Start (Development Mode)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Fides
```

### Step 2: Start the AI-Assistant Server

**Simple Development Setup (No Database):**

```bash
cd ai-assistant

# Copy environment template
cp .env.template .env

# Edit .env and add your credentials:
# - GOOGLE_SERVICE_ACCOUNT_JSON_PATH
# - GEMINI_API_KEY
# Set USE_WEAVIATE=false for development mode
nano .env

# Start server with Docker
docker-compose up ai-assistant

# Server starts on localhost:8080
```

See [AI-Assistant Documentation](ai-assistant.md) for detailed setup.

### Step 3: Run the ConnectX App

```bash
cd connectx

# Install dependencies
flutter pub get

# Copy environment template
cp template.env .env

# Configure server URL (use your machine's IP for Android emulator)
# Edit .env and set:
# AI_ASSISTANT_SERVER_URL=192.168.1.100:8080
nano .env

# Run on device
flutter run
```

See [ConnectX Documentation](connectx.md) for detailed setup including Firebase configuration.

### Step 4: Test the Connection

1. Open the ConnectX app on your device
2. Sign in with Google or Email
3. Tap the microphone button
4. Speak naturally
5. Receive AI-generated voice responses

**That's it!** WebRTC handles all audio routing automatically.

## 🔧 Development Environment Setup

### Python Environment (Backend Developers)

```bash
cd ai-assistant

# Create virtual environment
python3 -m venv ../.venv
source ../.venv/bin/activate  # On Windows: ..\.venv\Scripts\activate

# Install in development mode
pip install -e .
pip install -e ".[dev]"
```

**Why development mode?**  
Installing with `pip install -e .` makes imports like `from ai_assistant.hub_spoke_schema import ...` work correctly throughout the project.

### Google Cloud Setup

**1. Create Service Account:**
- Go to [Google Cloud Console](https://console.cloud.google.com)
- Navigate to IAM & Admin → Service Accounts
- Create service account with:
  - Cloud Speech-to-Text User
  - Cloud Text-to-Speech User
- Download JSON key file
- Place in `ai-assistant/` directory

**2. Enable Required APIs:**
```bash
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
```

**3. Get Gemini API Key:**
- Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
- Create new API key
- Add to `.env` file

### Firebase Setup (Mobile App)

```bash
cd connectx

# Configure Firebase
flutterfire configure --project=<your-project-id>

# Download google-services.json for Android
# Place in: connectx/android/app/google-services.json

# Add SHA-1 fingerprint to Firebase Console
keytool -list -v -alias androiddebugkey \
  -keystore ~/.android/debug.keystore \
  -storepass android -keypass android
```

See [ConnectX Documentation](connectx.md#firebase-setup) for complete Firebase configuration.

## 📦 Production Setup with Weaviate

For production with semantic provider matching:

### Step 1: Start Weaviate

```bash
cd weaviate
docker-compose up -d

# Verify health
curl http://localhost:8090/v1/meta
```

### Step 2: Initialize Database

```bash
cd ../ai-assistant
python scripts/init_hub_spoke_schema.py --load-test-data
```

### Step 3: Configure AI-Assistant

Edit `ai-assistant/.env`:
```bash
USE_WEAVIATE=true
WEAVIATE_URL=http://localhost:8090  # When running locally
```

### Step 4: Start AI-Assistant

```bash
docker-compose up ai-assistant
```

See [Weaviate Documentation](weaviate.md) for detailed configuration options.

## 🧪 Running Tests

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

See [Testing Guide](testing.md) for comprehensive testing documentation.

## 🐛 Common Issues

### Port Already in Use
```bash
# Find process using port 8080
lsof -i :8080
kill -9 <PID>
```

### Docker Build Fails
```bash
# Clean Docker cache
docker system prune -a
docker-compose build --no-cache
```

### WebRTC Connection Failed
- Check server URL in ConnectX `.env`
- For Android emulator, use your machine's IP, not `localhost`
- Verify AI-Assistant server is running: `curl http://localhost:8080/health`

### Firebase Authentication Issues
- Verify SHA-1 fingerprint is added in Firebase Console
- Check `GOOGLE_OAUTH_CLIENT_ID` in `.env`
- Ensure backend and app use same Firebase project

See [Troubleshooting Guide](troubleshooting.md) for more solutions.

## 📚 Next Steps

### For Developers

1. **Understand the Architecture**  
   Read [Architecture Overview](architecture.md) to understand system design

2. **Explore Components**  
   - [ConnectX Documentation](connectx.md) - Mobile app details
   - [AI-Assistant Documentation](ai-assistant.md) - Backend details
   - [Weaviate Documentation](weaviate.md) - Database details

3. **Learn the API**  
   Review [API Reference](api-reference.md) for integration details

4. **Set Up Your IDE**  
   - VS Code: Install Flutter, Python, Docker extensions
   - Configure code formatters and linters

### For DevOps

**Infrastructure Setup**  
- [Terraform Documentation](terraform.md) - GKE cluster provisioning
- [Helm Documentation](helm.md) - Kubernetes deployments
