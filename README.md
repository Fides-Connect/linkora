# Fides - AI Voice Assistant Platform

A complete voice-based AI assistant platform built with Flutter and Python, featuring real-time WebRTC audio streaming and AI-powered conversations.

## 🎯 Overview

Fides is a modern AI voice assistant platform that enables natural voice conversations with AI. The platform consists of two main components:

1. **ConnectX** - A Flutter mobile application for iOS and Android
2. **AI-Assistant Server** - A Python-based WebRTC server handling AI processing

The platform uses WebRTC for low-latency real-time audio streaming, with all AI processing (Speech-to-Text, LLM, Text-to-Speech) centralized on the server for security and efficiency.

### Key Features

- 🎙️ **Real-time Voice Interaction** - Natural conversations with minimal latency
- 🔒 **Secure Architecture** - API keys and credentials stay on the server
- ⚡ **WebRTC Streaming** - Direct peer-to-peer audio communication
- 🤖 **AI-Powered** - Uses Google Gemini 2.0, Cloud Speech-to-Text, and Text-to-Speech
- 📱 **Cross-Platform** - Supports iOS and Android devices
- 🐳 **Containerized** - Easy deployment with Docker/Podman
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
│   ├── Containerfile     # Container definition
│   ├── requirements.txt  # Python dependencies
│   └── README.md         # AI-Assistant documentation
│
├── scripts/              # Utility scripts
│   ├── generateOAuth2Token.py  # OAuth token generator
│   └── dev-helper.sh    # Development helper script
│
├── .devcontainer/        # VS Code Dev Container configuration
│   ├── devcontainer.json
│   └── Containerfile
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
  - Podman or Docker
  - Google Cloud Platform account with APIs enabled
  - Google Gemini API key

### 1. Start the AI-Assistant Server

```bash
cd ai-assistant

# Configure environment
cp .env.template .env
# Edit .env with your Google Cloud credentials and Gemini API key

# Start server
./quickstart.sh

# Server starts on ws://localhost:8080/ws
```

See [AI-Assistant README](ai-assistant/README.md) for detailed setup instructions.

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

## 🔧 Configuration

### ConnectX Configuration

```properties
# connectx/.env
AI_ASSISTANT_SERVER_URL=ws://localhost:8080/ws
```

### AI-Assistant Configuration

```bash
# ai-assistant/.env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key_here
LANGUAGE_CODE=de-DE
VOICE_NAME=de-DE-Wavenet-F
PORT=8080
LOG_LEVEL=INFO
```

## 🧪 Testing

### Test AI-Assistant Server

```bash
cd ai-assistant

# Test with sample audio
python tests/test_client.py --audio-file test.wav

# Check health endpoint
curl http://localhost:8080/health
```

### Test ConnectX App

```bash
cd connectx

# Run Flutter tests
flutter test

# Run on device for manual testing
flutter run
```

## 📦 Deployment

### Deploy AI-Assistant Server

The server can be deployed using containers:

```bash
cd ai-assistant

# Build container
podman build -t ai-assistant -f Containerfile .

# Run container
podman run -d \
  --name ai-assistant \
  -p 8080:8080 \
  --env-file .env \
  ai-assistant
```

See [AI-Assistant Deployment Guide](ai-assistant/README.md#deployment) for production deployment options.

### Build ConnectX for Production

```bash
cd connectx

# Android
flutter build apk --release

# iOS
flutter build ios --release
```

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues and pull requests.

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

---

**Built with ❤️ for natural voice AI interactions**

---

## 📦 Flutter Development Container (Optional)

This project includes a complete Flutter development environment using Podman/Docker and VS Code Dev Containers for optional containerized development.

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
- Podman or Docker (latest version)
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

Edit `.devcontainer/Containerfile`:
```dockerfile
RUN apt-get update && apt-get install -y \
    your-package-name \
    && rm -rf /var/lib/apt/lists/*
```

### Troubleshooting Dev Container

**Container Build Issues:**
- Ensure Podman Machine has enough RAM allocated (8GB+)
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

For more details, see the inline comments in `.devcontainer/devcontainer.json` and `.devcontainer/Containerfile`.