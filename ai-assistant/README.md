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
- ✅ Runs in a containerized environment (Podman/Docker)
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

- **Real-time Voice Processing**: Low-latency voice activity detection and audio streaming
- **Multi-language Support**: Configurable language and voice settings
- **Chat Context**: Maintains conversation history per session
- **Scalable Architecture**: Stateless design for horizontal scaling
- **Production-ready**: Comprehensive error handling and logging

### Technical Features

- WebRTC peer-to-peer connections
- WebSocket signaling server
- Voice Activity Detection (VAD)
- Silence detection and buffering
- Asynchronous processing pipeline
- Health check endpoints
- Docker/Podman containerization

## Quick Start

### Prerequisites

- Podman or Docker installed
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
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Start the Service

```bash
# Using the quickstart script
./quickstart.sh

# Or using the run script
./run.sh start
```

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
                                          │  (VAD, Buffer)   │
                                          └──────────────────┘
                                                   │
                                                   │
                            ┌──────────────────────┼──────────────────────┐
                            │                      │                      │
                            ▼                      ▼                      ▼
                    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
                    │   Google     │      │   Gemini     │      │   Google     │
                    │ Speech-to-   │      │     AI       │      │ Text-to-     │
                    │     Text     │      │   (LLM)      │      │   Speech     │
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
   - Audio processor receives PCM audio frames
   - Voice Activity Detection (VAD) filters silence
   - (Optional) Debug recording saves all received frames to WAV file

3. **Speech Processing**
   - Buffer accumulates audio during speech
   - Silence detection triggers processing
   - Audio segment sent to Google Speech-to-Text

4. **AI Processing**
   - Transcript sent to Gemini AI
   - LLM generates contextual response
   - Response text prepared for synthesis

5. **Audio Synthesis**
   - Text sent to Google Cloud TTS
   - Receives audio chunks in LINEAR16 format
   - Audio queued for streaming

6. **Audio Streaming**
   - Audio output track consumes queue
   - Frames sent via WebRTC to client
   - Proper timing maintained (20ms frames)

### Project Structure

```
ai-assistant/
├── main.py                      # Application entry point
├── signaling_server.py          # WebSocket signaling server
├── peer_connection_handler.py   # WebRTC peer connection management
├── audio_processor.py           # Audio processing pipeline (VAD, STT→LLM→TTS)
├── audio_track.py               # Custom audio output track
├── ai_assistant.py              # Core AI logic (STT, LLM, TTS)
├── Containerfile                # Container image definition
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Docker Compose configuration
├── .env.template                # Environment variable template
├── .gitignore                   # Git ignore rules
├── run.sh                       # Container management script
├── quickstart.sh                # Quick start script
├── test_client.py               # Test client for validation
└── README.md                    # This file
```

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
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GEMINI_API_KEY=your_api_key_here
LANGUAGE_CODE=de-DE
VOICE_NAME=de-DE-Wavenet-F
```

#### 5. Run Locally

```bash
# Start server
python main.py

# Server starts on http://localhost:8080
```

### Container Setup

#### Using Podman (Recommended)

```bash
# Build container
./run.sh build

# Start service
./run.sh start

# View logs
./run.sh logs

# Stop service
./run.sh stop
```

#### Using Podman

```bash
# Build image
podman build -t ai-assistant -f Containerfile .

# Run container
podman run -d \
  --name ai-assistant \
  -p 8080:8080 \
  --env-file .env \
  -v /path/to/service-account.json:/app/credentials.json \
  ai-assistant
```

#### Using Podman Compose

```bash
# Start all services
podman-compose up -d

# View logs
podman-compose logs -f

# Stop services
podman-compose down
```

## Configuration

### Environment Variables

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON | `/app/credentials.json` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGUAGE_CODE` | Language for STT/TTS | `de-DE` |
| `VOICE_NAME` | TTS voice model | `de-DE-Wavenet-F` |
| `PORT` | Server port | `8080` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `SILENCE_DURATION` | Silence threshold (seconds) | `1.5` |
| `SILENCE_THRESHOLD` | Audio level threshold | `500` |

### Available Languages & Voices

#### German (de-DE)
- `de-DE-Wavenet-A` (Female)
- `de-DE-Wavenet-B` (Male)
- `de-DE-Wavenet-C` (Female)
- `de-DE-Wavenet-D` (Male)
- `de-DE-Wavenet-E` (Male)
- `de-DE-Wavenet-F` (Female)

#### English US (en-US)
- `en-US-Wavenet-A` (Male)
- `en-US-Wavenet-B` (Male)
- `en-US-Wavenet-C` (Female)
- `en-US-Wavenet-D` (Male)
- `en-US-Wavenet-E` (Female)
- `en-US-Wavenet-F` (Female)

[See full list](https://cloud.google.com/text-to-speech/docs/voices)

### Audio Configuration

**Input Requirements:**
- Sample Rate: 16000 Hz
- Channels: 1 (mono)
- Format: LINEAR16 PCM
- Bit Depth: 16-bit

**Output Format:**
- Sample Rate: 24000 Hz
- Channels: 1 (mono)
- Format: LINEAR16 PCM
- Frame Duration: 20ms

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

### WebRTC Audio Tracks

#### Input Track (Client → Server)
- **Media Type:** `audio`
- **Sample Rate:** 16000 Hz
- **Channels:** Mono
- **Frame Size:** 20ms (320 samples)

#### Output Track (Server → Client)
- **Media Type:** `audio`
- **Sample Rate:** 24000 Hz
- **Channels:** Mono
- **Frame Size:** 20ms (480 samples)

## Testing

### Using Test Client

```bash
# Basic test
python test_client.py

# With specific audio file
python test_client.py --audio-file recording.wav

# With custom server URL
python test_client.py --server ws://192.168.1.100:8080/ws
```

### Manual Testing

#### 1. Test Health Endpoint
```bash
curl http://localhost:8080/health
```

#### 2. Test WebSocket Connection
```bash
# Using websocat
websocat ws://localhost:8080/ws

# Send test message
{"type": "ping"}
```

#### 3. Test with Browser Client
```html
<!DOCTYPE html>
<html>
<head>
    <title>AI Assistant Test</title>
</head>
<body>
    <button id="start">Start Call</button>
    <script src="test-client.js"></script>
</body>
</html>
```

### Debugging

#### Enable Debug Logging
```bash
# In .env
LOG_LEVEL=DEBUG
```

#### View Detailed Logs
```bash
# Podman
podman logs -f ai-assistant

# Local
python main.py 2>&1 | tee debug.log
```

#### Common Test Scenarios

| Scenario | Command | Expected Result |
|----------|---------|-----------------|
| Health check | `curl http://localhost:8080/health` | Status 200, JSON response |
| WebSocket connect | `websocat ws://localhost:8080/ws` | Connection established |
| Audio processing | `python test_client.py --audio-file test.wav` | Response audio generated |

## Deployment

### Production Deployment

#### Google Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-assistant

# Deploy to Cloud Run
gcloud run deploy ai-assistant \
  --image gcr.io/PROJECT_ID/ai-assistant \
  --platform managed \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=... \
  --set-secrets GOOGLE_APPLICATION_CREDENTIALS=...
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

**Deployment: Google Cloud (same region as APIs, no silence detection)**

| Stage | Typical Latency | Notes |
|-------|----------------|-------|
| Network RTT | 10-50ms | Client to server round-trip |
| Speech-to-Text | 300-800ms | Google Cloud Speech API (streaming) |
| Gemini LLM | 400-1200ms | Response generation time |
| Text-to-Speech | 200-600ms | Google Cloud TTS synthesis |
| Audio Streaming | 50-150ms | WebRTC buffer + network |
| **Total** | **~1-3 seconds** | End-to-end response time |

**Note:** With Voice Activity Detection (VAD) enabled (default):
- Add 1.0-2.0s for silence detection (configurable via `SILENCE_DURATION`)
- Total latency: ~2-5 seconds

**Optimization recommendations:**
- Deploy service in same GCP region as Cloud APIs (e.g., `us-central1`)
- Use Google Cloud's internal network for API calls
- Disable VAD for real-time streaming (set `SILENCE_DURATION=0`)
- Enable HTTP/2 keepalive for persistent connections

### Resource Usage

#### Per Connection

| Resource | Usage | Notes |
|----------|-------|-------|
| Memory | 200-500 MB | Includes audio buffers |
| CPU | 10-30% | Mostly I/O bound |
| Network | ~64 kbps | Bi-directional audio |
| Disk | Minimal | Logs only |

#### System Requirements

| Connections | Memory | CPU | Network |
|-------------|--------|-----|---------|
| 1-5 | 2 GB | 2 cores | 1 Mbps |
| 5-10 | 4 GB | 4 cores | 2 Mbps |
| 10-20 | 8 GB | 8 cores | 4 Mbps |

### Optimization Tips

1. **Reduce Latency**
   - Lower `SILENCE_DURATION` (trade-off: may cut off speech)
   - Use regional API endpoints
   - Enable HTTP/2 for Google APIs
   - Cache common responses

2. **Improve Quality**
   - Increase `SILENCE_DURATION` for complete sentences
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
podman logs ai-assistant

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
podman logs ai-assistant | grep ERROR

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
- Reduce `SILENCE_DURATION`
- Increase container resources
- Check network bandwidth
- Monitor Google Cloud quotas

#### Audio Quality Issues

**Problem:** Distorted or choppy audio

**Possible Causes:**
- Incorrect sample rate
- Network packet loss
- Buffer underruns
- VAD threshold too low

**Solution:**
```bash
# Adjust silence threshold in .env
SILENCE_THRESHOLD=800  # Increase for better detection

# Verify audio format
# Input should be: 16kHz, mono, LINEAR16
# Output will be: 24kHz, mono, LINEAR16
```

### Debug Checklist

- [ ] Health endpoint returns 200
- [ ] WebSocket connection establishes
- [ ] Audio track added to peer connection
- [ ] VAD detecting voice activity
- [ ] STT returning transcripts
- [ ] LLM generating responses
- [ ] TTS synthesizing audio
- [ ] Audio queue has frames
- [ ] Client receiving audio packets

### Getting Help

**Logs:**
```bash
# Full debug logs
podman logs ai-assistant > debug.log 2>&1

# Filter for errors
podman logs ai-assistant 2>&1 | grep -i error

# Follow live logs
podman logs -f ai-assistant
```

**System Info:**
```bash
# Container info
podman inspect ai-assistant

# Resource usage
podman stats ai-assistant

# Network info
podman port ai-assistant
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