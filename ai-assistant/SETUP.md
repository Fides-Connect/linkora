# AI Assistant - Setup Guide

## Overview

This AI Assistant service replaces the `speech_service.dart` and `gemini_service.dart` functionality from the ConnectX Flutter app with a containerized Python service. It provides:

1. **WebRTC Audio Streaming** - Real-time bidirectional audio
2. **Speech-to-Text** - Google Cloud Speech API
3. **LLM Processing** - Google Gemini 2.0 Flash
4. **Text-to-Speech** - Google Cloud TTS API
5. **Voice Activity Detection** - Automatic speech segment detection

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ConnectX App                                │
│                       (Flutter/Dart Client)                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ WebRTC (Audio Stream)
                            │ WebSocket (Signaling)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AI Assistant Container                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Signaling Server (WebSocket)                   │   │
│  │                    Port: 8080/ws                            │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │         Peer Connection Handler (WebRTC)                    │   │
│  │  • ICE negotiation  • SDP exchange  • Media routing         │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼────────────────────────────────────┐   │
│  │              Audio Processor Pipeline                       │   │
│  │                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │   │
│  │  │   Incoming   │  │    Voice     │  │   Silence    │     │   │
│  │  │ Audio Stream │─▶│   Activity   │─▶│  Detection   │     │   │
│  │  │  (WebRTC)    │  │  Detection   │  │   (1.5s)     │     │   │
│  │  └──────────────┘  └──────────────┘  └──────┬───────┘     │   │
│  │                                              │              │   │
│  │                                              ▼              │   │
│  │                                   ┌──────────────────┐     │   │
│  │                                   │  Audio Buffer    │     │   │
│  │                                   │ (PCM 16kHz mono) │     │   │
│  │                                   └────────┬─────────┘     │   │
│  └──────────────────────────────────────────┬─────────────────┘   │
│                                             │                      │
│  ┌──────────────────────────────────────────▼─────────────────┐   │
│  │                    AI Assistant Core                        │   │
│  │                                                              │   │
│  │  Step 1: Speech-to-Text                                     │   │
│  │  ┌────────────────────────────────────────────────┐         │   │
│  │  │   Google Cloud Speech-to-Text API             │         │   │
│  │  │   • Language: de-DE                            │         │   │
│  │  │   • Sample Rate: 16kHz                         │         │   │
│  │  │   • Encoding: LINEAR16                         │         │   │
│  │  └───────────────────┬────────────────────────────┘         │   │
│  │                      │ Transcript                            │   │
│  │                      ▼                                       │   │
│  │  Step 2: LLM Processing                                     │   │
│  │  ┌────────────────────────────────────────────────┐         │   │
│  │  │   Google Gemini 2.0 Flash API                 │         │   │
│  │  │   • Model: gemini-2.0-flash-exp               │         │   │
│  │  │   • Temperature: 0.7                           │         │   │
│  │  │   • Max Tokens: 1024                           │         │   │
│  │  └───────────────────┬────────────────────────────┘         │   │
│  │                      │ Response Text                         │   │
│  │                      ▼                                       │   │
│  │  Step 3: Text-to-Speech                                     │   │
│  │  ┌────────────────────────────────────────────────┐         │   │
│  │  │   Google Cloud Text-to-Speech API             │         │   │
│  │  │   • Voice: de-DE-Wavenet-F                     │         │   │
│  │  │   • Encoding: LINEAR16                         │         │   │
│  │  │   • Sample Rate: 16kHz                         │         │   │
│  │  └───────────────────┬────────────────────────────┘         │   │
│  │                      │ Audio Chunks                          │   │
│  └──────────────────────┼───────────────────────────────────────┘   │
│                         │                                           │
│  ┌──────────────────────▼───────────────────────────────────────┐  │
│  │              Audio Output Track                              │  │
│  │         Queues and streams audio via WebRTC                  │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────────────┘
                          │ WebRTC (Audio Response)
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ConnectX App                                     │
│               Receives and plays audio response                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Setup

### Prerequisites

1. **Google Cloud Platform Account**
   - Project with billing enabled
   - Service account with appropriate permissions
   
2. **Enable Required APIs**
   ```bash
   gcloud services enable speech.googleapis.com
   gcloud services enable texttospeech.googleapis.com
   ```

3. **Create Service Account**
   ```bash
   gcloud iam service-accounts create ai-assistant \
       --display-name="AI Assistant Service Account"
   
   # Grant necessary roles
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:ai-assistant@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/speech.client"
   
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:ai-assistant@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/texttospeech.client"
   
   # Create and download key
   gcloud iam service-accounts keys create credentials.json \
       --iam-account=ai-assistant@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

4. **Get Gemini API Key**
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Save it securely

5. **Install Podman**
   ```bash
   # macOS
   brew install podman
   podman machine init
   podman machine start
   
   # Linux
   # Follow instructions at https://podman.io/getting-started/installation
   ```

### Configuration

1. **Copy Environment Template**
   ```bash
   cd ai-assistant
   cp .env.template .env
   ```

2. **Edit `.env` File**
   ```bash
   # Update these values
   GOOGLE_APPLICATION_CREDENTIALS=/Users/thomas/Projects/Fides/ai-assistant/credentials.json
   GEMINI_API_KEY=your_actual_api_key_here
   
   # Optional customization
   LANGUAGE_CODE=de-DE
   VOICE_NAME=de-DE-Wavenet-F
   PORT=8080
   ```

3. **Place Credentials File**
   ```bash
   # Copy your downloaded credentials.json to the ai-assistant directory
   cp ~/Downloads/credentials.json /Users/thomas/Projects/Fides/ai-assistant/
   ```

### Building and Running

#### Option 1: Quick Start (Recommended)

```bash
cd ai-assistant
./quickstart.sh
```

This script will:
- Validate your configuration
- Build the container image
- Start the service
- Wait for it to be ready
- Display connection information

#### Option 2: Manual Steps

```bash
cd ai-assistant

# Build
podman build -t ai-assistant -f Containerfile .

# Run
podman run -d \
    --name ai-assistant \
    -p 8080:8080 \
    -v $(pwd)/credentials.json:/app/credentials.json:ro \
    --env-file .env \
    ai-assistant

# Check status
podman logs -f ai-assistant
```

#### Option 3: Using Run Script

```bash
cd ai-assistant

# Build and start
./run.sh start

# Other commands
./run.sh logs      # View logs
./run.sh status    # Check status
./run.sh stop      # Stop service
./run.sh restart   # Restart service
```

### Verification

1. **Health Check**
   ```bash
   curl http://localhost:8080/health
   ```
   
   Expected response:
   ```json
   {
     "status": "healthy",
     "active_connections": 0
   }
   ```

2. **WebSocket Connection**
   ```bash
   # Install websocat if needed
   brew install websocat
   
   # Test WebSocket
   websocat ws://localhost:8080/ws
   ```

3. **View Logs**
   ```bash
   podman logs -f ai-assistant
   ```

### Testing

Run the test client (requires Python environment):

```bash
# Install dependencies
pip install -r requirements.txt

# Run test (requires a 16kHz mono WAV file)
python test_client.py --audio-file test_audio.wav

# Or without audio file (will need microphone access)
python test_client.py
```

## Integration with ConnectX

### Current vs New Architecture

**Before (Direct Google Cloud):**
```
ConnectX App
    ├─ speech_service.dart (STT + TTS)
    ├─ gemini_service.dart (LLM)
    └─ Direct API calls to Google Cloud
```

**After (Containerized Service):**
```
ConnectX App
    └─ WebRTC connection to AI Assistant
        └─ AI Assistant Container
            ├─ STT
            ├─ LLM
            └─ TTS
```

### Benefits of Containerization

1. **Centralized Credentials** - No API keys in mobile app
2. **Easier Updates** - Update backend without app release
3. **Better Resource Management** - Server-side processing
4. **Enhanced Security** - No client-side API exposure
5. **Scalability** - Can handle multiple clients
6. **Consistent Behavior** - Same processing across all clients

### Migration Path

The ConnectX app will need to be updated to:

1. **Replace Direct API Calls** with WebRTC connection
2. **Remove Dependencies**:
   - `google_speech` package
   - `google_generative_ai` package
   - Direct gRPC calls
   
3. **Add WebRTC Support**:
   - WebSocket for signaling
   - WebRTC peer connection
   - Audio streaming

You mentioned you'll handle this later, which is perfect. The AI Assistant is ready and waiting for ConnectX to connect!

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON | - | Yes |
| `GEMINI_API_KEY` | Gemini API key | - | Yes |
| `LANGUAGE_CODE` | Language for STT/TTS | `de-DE` | No |
| `VOICE_NAME` | TTS voice name | `de-DE-Wavenet-F` | No |
| `HOST` | Server bind address | `0.0.0.0` | No |
| `PORT` | Server port | `8080` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |

### Audio Processing Parameters

Edit `audio_processor.py` to customize:

```python
# Voice activity detection
self.silence_threshold = 500  # Amplitude threshold
self.silence_duration = 1.5   # Seconds of silence to trigger
self.min_speech_duration = 0.5  # Minimum speech length

# Audio format
self.sample_rate = 16000  # Must be 16kHz for Google Cloud
```

### Available Voices

Common German voices:
- `de-DE-Wavenet-F` (Female, high quality)
- `de-DE-Wavenet-M` (Male, high quality)  
- `de-DE-Neural2-F` (Female, neural)
- `de-DE-Neural2-M` (Male, neural)
- `de-DE-Chirp-HD-F` (Female, highest quality)

[Full list](https://cloud.google.com/text-to-speech/docs/voices)

## Monitoring and Debugging

### View Logs

```bash
# Follow logs
podman logs -f ai-assistant

# Last 100 lines
podman logs --tail 100 ai-assistant

# With timestamps
podman logs -t ai-assistant
```

### Check Resource Usage

```bash
# Container stats
podman stats ai-assistant

# Detailed info
podman inspect ai-assistant
```

### Debug Mode

For more verbose logging, update `.env`:
```bash
LOG_LEVEL=DEBUG
```

Then restart:
```bash
./run.sh restart
```

## Troubleshooting

### Container won't start

1. Check logs:
   ```bash
   podman logs ai-assistant
   ```

2. Verify credentials:
   ```bash
   # Check file exists
   ls -l credentials.json
   
   # Validate JSON
   cat credentials.json | python -m json.tool
   ```

3. Test API access:
   ```bash
   # Set credentials
   export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/credentials.json
   
   # Test with gcloud
   gcloud auth activate-service-account --key-file=credentials.json
   gcloud auth list
   ```

### WebSocket connection fails

1. Check if container is running:
   ```bash
   podman ps
   ```

2. Verify port mapping:
   ```bash
   podman port ai-assistant
   ```

3. Test with curl:
   ```bash
   curl -v http://localhost:8080/health
   ```

### Audio not processing

1. Check audio format:
   - Must be 16kHz sample rate
   - Mono channel
   - LINEAR16 encoding

2. Adjust voice detection:
   - Lower `silence_threshold` if not detecting speech
   - Increase `min_speech_duration` if processing noise

3. Check API quotas in Google Cloud Console

### High latency

Typical latency breakdown:
- Voice detection: 1.5s (configurable)
- STT: 0.5-1.5s
- LLM: 0.5-2s
- TTS: 0.5-1s
- **Total: ~3-6 seconds**

To reduce:
- Decrease `silence_duration` in `audio_processor.py`
- Use faster Gemini model (already using flash)
- Optimize network connection
- Use regional endpoints

## Production Deployment

### Security Considerations

1. **Use HTTPS/WSS**
   ```bash
   # Add TLS certificate to container
   # Update to use secure WebSocket (wss://)
   ```

2. **Add Authentication**
   - Implement token-based auth in signaling server
   - Validate client credentials

3. **Rate Limiting**
   - Add request limits per client
   - Implement quota management

4. **Firewall Rules**
   ```bash
   # Only allow from specific IPs
   # Configure in cloud provider
   ```

### Scaling

For multiple concurrent users:

```bash
# Run multiple instances
for i in {1..5}; do
    podman run -d \
        --name ai-assistant-$i \
        -p $((8080+i)):8080 \
        --env-file .env \
        ai-assistant
done

# Use load balancer (nginx, haproxy, etc.)
```

### Persistent Logs

```bash
podman run -d \
    --name ai-assistant \
    -p 8080:8080 \
    -v $(pwd)/logs:/app/logs \
    --env-file .env \
    ai-assistant
```

## Next Steps

1. ✅ **Container is ready** - AI Assistant service is complete
2. ⏳ **Update ConnectX** - Modify Flutter app to use WebRTC
3. 🔄 **Test Integration** - Verify end-to-end communication
4. 🚀 **Deploy** - Move to production environment

## Support

For issues:
1. Check logs: `podman logs ai-assistant`
2. Review this guide
3. Check Google Cloud Console for API issues
4. Open issue on repository

---

**Note:** This service completely replaces the functionality of `speech_service.dart` and `gemini_service.dart`, centralizing all AI processing in a secure, scalable container.
