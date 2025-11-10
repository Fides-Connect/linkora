# ConnectX

A Flutter-based AI voice assistant application that uses WebRTC to communicate with an AI-Assistant server for real-time voice interactions.

## Overview

ConnectX provides a conversational AI experience where you can speak naturally and receive AI-generated audio responses. The app uses WebRTC for real-time bidirectional audio streaming with an AI-Assistant server that handles:
- **Speech-to-Text (STT)** - Converts your voice to text
- **LLM Processing** - Generates intelligent responses using Google Gemini
- **Text-to-Speech (TTS)** - Converts AI responses back to speech

### Architecture

```
ConnectX App ←─ WebRTC Audio Stream ─→ AI-Assistant Server
                                         ├─ Speech-to-Text
                                         ├─ LLM Processing (Gemini)
                                         └─ Text-to-Speech
```

All AI processing happens on the server side, making the client lightweight and secure (API keys stay on the server).

## Prerequisites

- Flutter SDK (^3.9.2 or higher)
- Dart SDK
- An iOS or Android device/emulator
- Running AI-Assistant server (see [AI-Assistant README](../ai-assistant/README.md))

## Installation

### 1. Install Dependencies

```bash
cd connectx
flutter pub get
```

### 2. Configure Environment Variables

Copy the template environment file and configure it:

```bash
cp template.env .env
```

Edit `.env` and set the AI-Assistant server URL:

```properties
# AI-Assistant Server WebSocket URL
AI_ASSISTANT_SERVER_URL=ws://localhost:8080/ws

# For remote server, use your server's IP or domain
# AI_ASSISTANT_SERVER_URL=ws://192.168.1.100:8080/ws
```

### 3. Start the AI-Assistant Server

Before running ConnectX, ensure the AI-Assistant server is running:

```bash
cd ../ai-assistant

# Using run script (recommended)
./scripts/run.sh start

# Or directly with Python
python main.py

# Server starts on ws://localhost:8080/ws
```

See the [AI-Assistant README](../ai-assistant/README.md) for server setup instructions.

### 4. Run ConnectX

```bash
cd connectx
flutter run
```

## Usage

1. **Launch the app** on your device or emulator
2. **Tap the microphone button** (bottom right) to start a conversation
3. **Speak your question or message** - audio is streamed to the AI-Assistant server
4. **Listen to the AI response** - audio plays automatically through the device
5. **Tap the stop button** (bottom left) to end the conversation

### Audio Routing

**ConnectX uses WebRTC's automatic audio routing:**
- 📱 **Phone held naturally** - Audio plays through earpiece (default)
- 🎧 **Headphones connected** - Audio automatically routes to headphones
- 📢 **Bluetooth device** - Audio automatically routes to Bluetooth
- 🔇 **Echo cancellation** - Built-in WebRTC audio processing prevents feedback

> **No manual configuration needed!** WebRTC handles all audio routing intelligently, just like phone calls.

### How It Works

1. **Connection**: When you tap the microphone, the app establishes a WebRTC connection with the AI-Assistant server
2. **Audio Streaming**: Your voice is captured and streamed in real-time to the server (48kHz, mono)
3. **Server Processing**: The server performs STT → LLM → TTS processing
4. **Response Playback**: The AI-generated audio response streams back (48kHz) and plays automatically
5. **Cleanup**: When you stop, the WebRTC connection closes cleanly

## Key Technologies

### Dependencies

- **`flutter_webrtc`** - WebRTC peer-to-peer audio streaming with built-in audio processing
- **`web_socket_channel`** - WebSocket signaling for WebRTC
- **`permission_handler`** - Microphone permission management
- **`flutter_dotenv`** - Environment variable configuration

### Architecture Components

- **`webrtc_service.dart`** - Manages WebRTC connection, signaling, and media streams
- **`speech_service.dart`** - High-level interface for speech interactions
- **`main.dart`** - UI and user interaction handling

### Audio Configuration

ConnectX uses **WebRTC's native audio processing** which includes:
- ✅ **Echo Cancellation** - Prevents audio feedback (`echoCancellation: true`)
- ✅ **Noise Suppression** - Reduces background noise (`noiseSuppression: true`)
- ✅ **Auto Gain Control** - Normalizes audio levels (`autoGainControl: true`)
- ✅ **Native Sample Rate** - Uses 48kHz (WebRTC standard, no resampling)
- ✅ **Google Constraints** - Android-specific optimizations (`googEchoCancellation`, etc.)

**Audio Pipeline:**
```
Microphone → WebRTC (48kHz) → Server → Google STT → Gemini LLM → Google TTS → WebRTC (48kHz) → Device Audio
```

**This is the standard WebRTC approach** used by apps like Google Meet, Discord, and Zoom.

## Environment Variables

ConnectX uses a `.env` file for configuration. This file should be placed in the project root and is excluded from version control.

### Required Variables

```properties
# AI-Assistant Server WebSocket URL (Required)
AI_ASSISTANT_SERVER_URL=ws://localhost:8080/ws
```

### Configuration Tips

- **Local Development**: Use `ws://localhost:8080/ws`
- **Local Network**: Use `ws://192.168.x.x:8080/ws` (your computer's IP)
- **Production**: Use `wss://your-domain.com/ws` (secure WebSocket)

> **Note:** The `.env` file is excluded from version control via `.gitignore`. Never commit sensitive information to your repository.

## Troubleshooting

### Connection Issues

**Problem: "WebRTC connection fails"**
- Ensure the AI-Assistant server is running
- Check that `AI_ASSISTANT_SERVER_URL` in `.env` matches your server address
- Verify network connectivity between device and server
- Check firewall settings

**Problem: "No audio received from server"**
- Check server logs for errors
- Verify Google Cloud credentials are configured on the server
- Ensure `GEMINI_API_KEY` is valid on the server
- Check server's `LANGUAGE_CODE` and `VOICE_NAME` settings

**Problem: "Microphone not working"**
- Grant microphone permissions in device settings
- On iOS: Settings → ConnectX → Microphone
- On Android: Settings → Apps → ConnectX → Permissions
- Test microphone in other apps to verify it works

### Debug Logging

The app includes extensive logging. Check the console output for detailed information:

```
SpeechService: Initializing WebRTC service
WebRTC: Connecting to ws://localhost:8080/ws
WebRTC: Connection state: RTCPeerConnectionStateConnected
SpeechService: Received remote audio stream
SpeechService: Remote audio stream is now playing through speakers
```

### Common Issues

1. **Echo or Feedback**: 
   - **WebRTC handles this automatically** with built-in echo cancellation
   - Should not occur with default configuration
   - If persistent, try using headphones
   - Check that `echoCancellation: true` is set in `webrtc_service.dart`

2. **Can't hear the AI response**:
   - Check device volume
   - Verify audio routing (try headphones to test)
   - Check server logs for TTS errors
   - Ensure remote audio track is enabled

3. **Audio quality issues**:
   - Check network quality/bandwidth
   - Verify 48kHz sample rate is maintained throughout
   - Review WebRTC constraints in `webrtc_service.dart`
   - Check server TTS configuration

4. **Audio routing unexpected**:
   - **This is normal WebRTC behavior**
   - Plugging in headphones switches automatically
   - Bluetooth connects automatically
   - Proximity sensor may affect routing
   - Same behavior as phone calls

## Benefits of WebRTC Architecture

- **Simplified Client**: Single WebRTC connection instead of multiple API clients
- **Reduced Latency**: Direct peer-to-peer audio streaming
- **Better Security**: API keys and credentials stay on the server
- **Cost Efficiency**: Centralized API usage on the server
- **Scalability**: Easy to add load balancing and handle multiple clients

## Platform Support

- ✅ iOS (10.0+)
- ✅ Android (5.0+)
- ⚠️ Web (WebRTC supported but not fully tested)
- ❌ Desktop (not currently supported)

## Development

### Project Structure

```
connectx/
├── lib/
│   ├── main.dart                    # App entry point and UI
│   ├── services/
│   │   ├── webrtc_service.dart     # WebRTC connection management
│   │   └── speech_service.dart     # Speech interaction wrapper
│   └── widgets/
│       └── particle_sphere.dart    # Animated UI component
├── .env                            # Environment configuration (not in git)
├── template.env                    # Environment template
├── pubspec.yaml                    # Dependencies
└── README.md                       # This file
```
└── README.md                       # This file
```

### Running Tests

```bash
flutter test
```

### Building for Production

**Android:**
```bash
flutter build apk --release
```

**iOS:**
```bash
flutter build ios --release
```

## Contributing

This is part of the Fides project. For contribution guidelines, see the main repository documentation.

## Additional Resources

- [Flutter WebRTC Documentation](https://pub.dev/packages/flutter_webrtc)
- [WebRTC Standards](https://webrtc.org/)
- [AI-Assistant Server Documentation](../ai-assistant/README.md)

## Support

For issues or questions:
1. Check this README and troubleshooting section
2. Review server logs for error messages
3. Verify all environment variables are set correctly
4. Check network connectivity between client and server

---

**Note:** ConnectX requires the AI-Assistant server to be running and properly configured with Google Cloud credentials and a Gemini API key.
