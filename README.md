# Fides - AI Voice Assistant Platform

A complete voice-based AI assistant platform built with Flutter and Python, featuring real-time WebRTC audio streaming and AI-powered conversations.

## 🎯 Overview

Fides is a modern AI voice assistant platform that enables natural voice conversations with AI. The platform consists of three main components:

1. **ConnectX** - A Flutter mobile application for iOS and Android
2. **AI-Assistant Server** - A Python-based WebRTC server handling AI processing
3. **Weaviate** - Self-hosted vector database for semantic provider matching

The platform uses WebRTC for low-latency real-time audio streaming, with all AI processing (Speech-to-Text, LLM, Text-to-Speech) centralized on the server for security and efficiency.

### Key Features

- 🎙️ **Real-time Voice Interaction** - Natural conversations with minimal latency
- 🔒 **Secure Architecture** - API keys and credentials stay on the server
- ⚡ **WebRTC Streaming** - Direct peer-to-peer audio communication
- 🤖 **AI-Powered** - Uses Google Gemini 2.0, Cloud Speech-to-Text, and Text-to-Speech
- 📱 **Cross-Platform** - Supports iOS and Android devices
- 🐳 **Containerized** - Easy deployment with Docker
- 🚀 **Scalable** - Stateless design for horizontal scaling

## 📁 Project Structure

```
Fides/
├── connectx/              # Flutter mobile application
│   ├── lib/              # Dart source code
│   ├── android/          # Android platform files
│   ├── ios/              # iOS platform files
│   └── README.md         # ConnectX documentation
│
├── ai-assistant/         # Python WebRTC server
│   ├── src/              # Python source code
│   ├── scripts/          # Initialization scripts
│   ├── Dockerfile        # Container definition
│   ├── pyproject.toml    # Python package configuration & dependencies
│   └── README.md         # AI-Assistant documentation
│
├── weaviate/             # Vector database infrastructure
│   ├── docker-compose.yml # Weaviate services
│   └── README.md         # Weaviate setup guide
│
├── helm/                 # Kubernetes Helm charts
│   ├── ai-assistant/     # AI-Assistant Helm chart
│   └── weaviate/         # Weaviate Helm chart
│   └── README.md         # Helm setup guide
│
├── terraform/            # Infrastructure as Code
│   ├── main.tf           # GKE cluster configuration
│   ├── variables.tf      # Terraform variables
│   └── bootstrap/        # Terraform state backend setup
│   └── README.md         # Terraform setup guide
│
├── .github/              # CI/CD workflows
│   └── workflows/        # GitHub Actions
│       ├── cloud-deploy.yml        # GKE deployment
│       ├── ai-assistant-test.yml   # AI-Assistant tests
│       └── connectx-test.yml       # ConnectX tests
│
├── .devcontainer/        # VS Code Dev Container configuration
│   ├── devcontainer.json
│   └── Dockerfile
│
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites

- **For ConnectX (Flutter App):**
  - Flutter SDK (^3.9.2 or higher)
  - iOS or Android device/emulator

- **For AI-Assistant Server:**
  - Python 3.11+
  - Docker
  - Google Cloud Platform account with APIs enabled
  - Google Gemini API key

### 1. Start the AI-Assistant Server

**Option A: Development Mode (No Database)**

```bash
cd ai-assistant

# Configure environment
cp .env.template .env
# Edit .env with your Google Cloud credentials and Gemini API key
# USE_WEAVIATE=false (default for development)

# Start server (docker-compose)
docker-compose up ai-assistant

# Server starts on localhost:8080
```

**Option B: Production Mode (With Weaviate)**

```bash
# Step 1: Start Weaviate vector database
cd weaviate
docker-compose up -d

# Step 2: Initialize database
cd ../ai-assistant
python scripts/init_hub_spoke_schema.py --load-test-data

# Step 3: Configure AI-Assistant
# Edit .env:
#   USE_WEAVIATE=true
#   WEAVIATE_URL=http://localhost:8090

# Step 4: Start server
docker-compose up ai-assistant
```

See [AI-Assistant README](ai-assistant/README.md) and [Weaviate README](weaviate/README.md) for detailed setup instructions.

### 2. Run ConnectX App

```bash
cd connectx

# Install dependencies
flutter pub get

# Configure environment
cp template.env .env
# Edit .env to set AI_ASSISTANT_SERVER_URL

# Run on device
flutter run
```

**Usage:** Simply tap the microphone and speak naturally. WebRTC handles all audio routing automatically - no special configuration needed!

See [ConnectX README](connectx/README.md) for detailed setup instructions.

## 👨‍💻 Developer Onboarding

### New Developer Setup

Follow these steps when starting to work on the Fides project:

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd fides
```

#### 2. Set Up Python Environment for AI-Assistant

```bash
# Navigate to ai-assistant directory
cd ai-assistant

# Create and activate virtual environment
python3 -m venv ../.venv
source ../.venv/bin/activate  # On Windows: ..\.venv\Scripts\activate

# Install the package in development mode (this makes imports work properly)
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

**Why install in development mode?**
Installing with `pip install -e .` configures the project as a Python package, allowing imports like `from ai_assistant.hub_spoke_schema import ...` to work correctly throughout the project without manual path manipulation.

#### 3. Configure Google Cloud Credentials

**Create a Service Account:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to IAM & Admin → Service Accounts
3. Create new service account with these roles:
   - Cloud Speech-to-Text User
   - Cloud Text-to-Speech User
4. Create and download JSON key file
5. Place it in `ai-assistant/` directory (it will be ignored by git)

**Enable Required APIs:**
```bash
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
```

**Get Gemini API Key:**
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create new API key
3. Save for next step

#### 4. Configure Environment Variables

```bash
# In ai-assistant directory
cp .env.template .env

# Edit .env with your credentials:
nano .env
```

**Minimum required configuration:**
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key_here
USE_WEAVIATE=false  # Use test data for development
```

#### 5. Set Up Weaviate (Optional - for full stack development)

Only needed if working on database features or testing with real data:

```bash
# Start Weaviate services
cd ../weaviate
docker-compose up -d

# Initialize schema and load test data
cd ../ai-assistant
python scripts/init_hub_spoke_schema.py --load-test-data
```

Update `.env`:
```bash
USE_WEAVIATE=true
WEAVIATE_URL=http://localhost:8090
```

#### 6. Set Up Flutter Environment (for ConnectX development)

```bash
cd ../connectx

# Install dependencies
flutter pub get

# Configure environment
cp template.env .env
# Edit .env to set AI_ASSISTANT_SERVER_URL (default: http://localhost:8080)
```

**Optional - Firebase Setup:**
If working on authentication features, see [ConnectX README](connectx/README.md) for Firebase configuration steps.

#### 7. Verify Everything Works

**Test AI-Assistant Server:**
```bash
cd ai-assistant

# Activate virtual environment if not already activated
source ../.venv/bin/activate

# Run server locally
python -m ai_assistant

# In another terminal, test health endpoint
curl http://localhost:8080/health
# Expected: {"status": "healthy", "active_connections": 0}
```

**Test ConnectX App:**
```bash
cd connectx

# Run on connected device or emulator
flutter run
```

#### 8. Run Tests

**AI-Assistant Tests:**
```bash
cd ai-assistant
source ../.venv/bin/activate
pytest tests/
```

**ConnectX Tests:**
```bash
cd connectx
flutter test
```

### Common Development Tasks

#### Running the Full Stack Locally

```bash
# Terminal 1: Start Weaviate (if needed)
cd weaviate
docker-compose up

# Terminal 2: Start AI-Assistant
cd ai-assistant
source ../.venv/bin/activate
python -m ai_assistant

# Terminal 3: Start ConnectX
cd connectx
flutter run
```

#### Making Code Changes

**Python Code (AI-Assistant):**
- Code is in `ai-assistant/src/ai_assistant/`
- Changes are immediately active (development mode installation)
- Run tests: `pytest tests/`
- Format code: `black src/ tests/`

**Flutter Code (ConnectX):**
- Code is in `connectx/lib/`
- Hot reload: Press `r` in Flutter terminal
- Hot restart: Press `R` in Flutter terminal
- Run tests: `flutter test`

#### Database Management

**Initialize/Reset Database:**
```bash
cd ai-assistant
python scripts/init_hub_spoke_schema.py --load-test-data
```

**Clean Only (no recreation):**
```bash
python scripts/init_hub_spoke_schema.py --clean-only
```

### Troubleshooting Setup Issues

**Import errors in Python:**
- Make sure you installed with `pip install -e .` in the ai-assistant directory
- Verify virtual environment is activated: `which python` should point to `.venv`

**Google Cloud API errors:**
- Check credentials file exists and path is correct
- Verify APIs are enabled in Google Cloud Console
- Test credentials: `gcloud auth application-default print-access-token`

**Weaviate connection errors:**
- Check Weaviate is running: `docker ps | grep weaviate`
- Verify URL in `.env` matches docker-compose port
- Check logs: `docker-compose logs weaviate`

**Flutter build errors:**
- Clean build: `flutter clean && flutter pub get`
- Update Flutter: `flutter upgrade`
- Check Flutter doctor: `flutter doctor -v`

For more detailed troubleshooting, see component-specific README files.

## 🏗️ Architecture

### System Overview

```
┌─────────────────┐                           ┌─────────────────┐
│                 │   WebRTC Audio Stream     │                 │
│   ConnectX      │ ◄───────────────────────► │  AI-Assistant   │
│   Flutter App   │                           │     Server      │
│                 │   WebSocket Signaling     │                 │
└─────────────────┘ ◄───────────────────────► └─────────────────┘
         │                                             │
         │                                             │
         ├─ Microphone Input                          ├─ Speech-to-Text
         ├─ Audio Playback                            ├─ LLM Processing (Gemini)
         ├─ User Interface                            ├─ Text-to-Speech
         └─ WebRTC Client                             └─ WebRTC Server
```

### How It Works

1. **Connection Establishment**
   - User taps microphone button in ConnectX app
   - App connects to AI-Assistant server via WebSocket
   - WebRTC peer connection established with audio tracks

2. **Voice Interaction**
   - User speaks into device microphone
   - Audio streams in real-time to server via WebRTC (48kHz native)
   - Server processes audio through AI pipeline:
     - **STT**: Converts speech to text (accepts 48kHz natively)
     - **LLM**: Generates intelligent response using Gemini
     - **TTS**: Synthesizes response into natural speech (48kHz output)
   - Audio response streams back to client (48kHz via WebRTC)
   - Client plays audio automatically through optimal device (earpiece/headphones/speaker)

3. **Session Management**
   - User can stop/start conversations at any time
   - WebRTC connection closes cleanly
   - Resources cleaned up automatically

## 🛠️ Development Environment

### Using VS Code Dev Container

The project includes a complete Flutter development environment using Dev Containers:

```bash
# Open project in VS Code
code .

# Reopen in container
# VS Code will prompt to "Reopen in Container"
# Or use Command Palette: "Dev Containers: Reopen in Container"
```

The Dev Container includes:
- Flutter SDK with all platforms
- Android SDK and emulator
- Chrome for web development
- All necessary tools and extensions

See the [top-level README sections on Dev Containers](#) for more details.

## 📚 Documentation

Each component has detailed documentation:

- **[ConnectX Documentation](connectx/README.md)** - Flutter app setup, usage, and troubleshooting
- **[AI-Assistant Documentation](ai-assistant/README.md)** - Server setup, configuration, deployment, and API reference
- **[Weaviate Documentation](weaviate/README.md)** - Vector database setup, local and cloud deployment

## 🔧 Configuration

### ConnectX Configuration

```properties
# connectx/.env
AI_ASSISTANT_SERVER_URL=localhost:8080
```

### AI-Assistant Configuration

```bash
# ai-assistant/.env
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key_here
LANGUAGE_CODE=de-DE
VOICE_NAME=de-DE-Chirp3-HD-Sulafat
PORT=8080
LOG_LEVEL=INFO
GOOGLE_TTS_API_CONCURRENCY=5

# Data Provider Mode
USE_WEAVIATE=true                    # true = Weaviate DB, false = local test data

# Local Weaviate (Development)
WEAVIATE_URL=http://localhost:8090

# OR Cloud Weaviate (Production)
# WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
# WEAVIATE_API_KEY=your-weaviate-api-key

# Optional: Record received audio for debugging (creates debug_audio/*.wav files)
DEBUG_RECORD_AUDIO=false
```

## 🧪 Testing

### Test AI-Assistant Server

```bash
cd ai-assistant

# Test with sample audio (16kHz mono WAV file)
python tests/test_client.py --audio-file test.wav

# The test will:
# - Connect via WebRTC
# - Stream your audio file to the server
# - Receive and save the AI response to output.wav
# - Display timing metrics

# Check health endpoint
curl http://localhost:8080/health
```

**Note on Audio Format:**
- Input: 16kHz mono WAV → automatically upsampled by WebRTC to 48kHz
- Processing: Server handles all audio at 48kHz native rate
- Output: 48kHz mono WAV saved as output.wav
- Debug: Set `DEBUG_RECORD_AUDIO=true` to save received audio in `debug_audio/` folder

### Test ConnectX App

```bash
cd connectx

# Run Flutter tests
flutter test

# Run on device for manual testing
flutter run
```

**Troubleshooting Low Audio:**
- Ensure you're speaking clearly into the microphone during testing
- Check that microphone permissions are granted
- Audio levels below RMS 10 are considered silence

## 📦 Deployment

### Local Development Deployment

**AI-Assistant Server:**

```bash
cd ai-assistant

# Using docker-compose (recommended)
docker-compose up ai-assistant

# Or build and run manually
docker build -t ai-assistant -f Dockerfile .
docker run -d \
  --name ai-assistant \
  -p 8080:8080 \
  --env-file .env \
  ai-assistant
```

**ConnectX App:**

```bash
cd connectx

# Android
flutter build apk --release

# iOS
flutter build ios --release
```

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google Cloud Platform for Speech and Language APIs
- Google Gemini for AI capabilities
- Flutter team for the amazing framework
- aiortc for Python WebRTC implementation

## 📞 Support

For issues or questions:

1. Check the component-specific README files
2. Review troubleshooting sections
3. Check server logs for error messages
4. Verify all environment variables are configured correctly

## 📦 Flutter Development Container (Optional)

This project includes a complete Flutter development environment using Docker and VS Code Dev Containers for optional containerized development.

### Dev Container Features

- **Flutter SDK**: Latest stable version with all platforms enabled
- **Android SDK**: Complete Android development setup with emulator support
- **Cross-platform**: Support for iOS, Android, Web, and Desktop development
- **Device Testing**: USB debugging support for physical devices
- **VS Code Integration**: Pre-configured extensions and settings
- **Chrome Browser**: For Flutter web development and testing
- **Ubuntu 24.04**: Modern, stable base with ARM64 optimization

### Dev Container Setup

**Prerequisites:**
- macOS (preferably with Apple Silicon)
- Docker (latest version)
- VS Code with Dev Containers extension
- 8GB+ RAM recommended (16GB+ for smooth emulator performance)

**Instructions:**

1. **Open in VS Code**
   ```bash
   code .
   ```

2. **Start Dev Container**
   - VS Code should prompt to "Reopen in Container" - click **Reopen in Container**
   - Or use Command Palette (`Cmd+Shift+P`) → **Dev Containers: Reopen in Container**
   - Wait for the container to build (first time takes 10-15 minutes)

3. **Verify Setup**
   ```bash
   flutter doctor -v
   ```

### Development Workflows in Container

#### Running on Different Platforms

```bash
# Android Emulator
flutter run

# Web Browser
flutter run -d chrome

# Linux Desktop (within container)
flutter run -d linux
```

#### Physical Android Device Testing

1. **Enable Developer Options** on your Android device
2. **Connect Device**:
   ```bash
   adb devices
   flutter run
   ```

#### Android Emulator

```bash
# List available emulators
flutter emulators

# Launch emulator
flutter emulators --launch Flutter_Emulator

# Run app on emulator
flutter run
```

### Useful Commands

```bash
# Flutter Commands
flutter doctor              # Check setup
flutter devices             # List available devices
flutter clean               # Clean build cache
flutter pub get             # Get dependencies

# Android/ADB Commands
adb devices                 # List connected devices
adb kill-server             # Restart ADB server
adb logcat                  # View device logs

# Container Management
# Use Command Palette: "Dev Containers: Rebuild Container"
```

### Customization

**Adding VS Code Extensions:**

Edit `.devcontainer/devcontainer.json`:
```json
"extensions": [
    "Dart-Code.dart-code",
    "Dart-Code.flutter",
    "your-extension-id"
]
```

**Installing Additional Tools:**

Edit `.devcontainer/Dockerfile`:
```dockerfile
RUN apt-get update && apt-get install -y \
    your-package-name \
    && rm -rf /var/lib/apt/lists/*
```

### Troubleshooting Dev Container

**Container Build Issues:**
- Ensure Docker has enough RAM resources (8GB+)
- Close other resource-intensive applications

**Flutter Doctor Issues:**
```bash
flutter doctor --android-licenses
```

**Device Connection Issues:**
```bash
adb kill-server && adb start-server
adb devices
```

For more details, see the inline comments in `.devcontainer/devcontainer.json` and `.devcontainer/Dockerfile`.