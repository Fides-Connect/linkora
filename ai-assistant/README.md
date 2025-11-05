# AI Assistant Service

A containerized AI assistant service that provides real-time voice interaction using WebRTC, Google Cloud Speech-to-Text, Gemini LLM, and Google Cloud Text-to-Speech.

## Features

- **WebRTC Audio Streaming**: Real-time bidirectional audio communication with client applications
- **Speech-to-Text**: Converts incoming audio to text using Google Cloud Speech-to-Text
- **LLM Processing**: Generates intelligent responses using Google Gemini AI
- **Text-to-Speech**: Converts responses to natural-sounding speech using Google Cloud TTS
- **Voice Activity Detection**: Automatically detects speech segments and processes them

## Architecture

```
Client App (ConnectX) <--WebRTC--> AI Assistant Container
                                         |
                                         v
                                  Audio Processor
                                         |
                    +--------------------+--------------------+
                    |                    |                    |
                    v                    v                    v
              Speech-to-Text      Gemini LLM         Text-to-Speech
            (Google Cloud STT)  (Gemini 2.0)    (Google Cloud TTS)
```

## Prerequisites

1. **Google Cloud Platform Account**
   - Enable Cloud Speech-to-Text API
   - Enable Cloud Text-to-Speech API
   - Create a service account and download the JSON key file

2. **Google Gemini API Key**
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

3. **Podman** (or Docker)
   - Install Podman: [https://podman.io/getting-started/installation](https://podman.io/getting-started/installation)

## Setup

### 1. Environment Configuration

Copy the template environment file and fill in your credentials:

```bash
cp .env.template .env
```

Edit `.env` and set:
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to your Google Cloud service account JSON file
- `GEMINI_API_KEY`: Your Gemini API key
- `LANGUAGE_CODE`: Language for speech recognition (default: de-DE)
- `VOICE_NAME`: Voice for speech synthesis (default: de-DE-Wavenet-F)

### 2. Build the Container

```bash
podman build -t ai-assistant -f Containerfile .
```

### 3. Run the Container

```bash
podman run -d \
  --name ai-assistant \
  -p 8080:8080 \
  -v /path/to/your/service-account-key.json:/app/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -e GEMINI_API_KEY=your_gemini_api_key_here \
  -e LANGUAGE_CODE=de-DE \
  -e VOICE_NAME=de-DE-Wavenet-F \
  ai-assistant
```

Or use the environment file:

```bash
podman run -d \
  --name ai-assistant \
  -p 8080:8080 \
  -v /path/to/your/service-account-key.json:/app/credentials.json:ro \
  --env-file .env \
  ai-assistant
```

### 4. Verify the Service

Check if the service is running:

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

## Usage

### WebSocket Connection

Clients connect to the WebRTC signaling server via WebSocket:

```
ws://localhost:8080/ws
```

### Signaling Protocol

The signaling protocol uses JSON messages:

**Client sends offer:**
```json
{
  "type": "offer",
  "sdp": "<SDP offer string>"
}
```

**Server responds with answer:**
```json
{
  "type": "answer",
  "sdp": "<SDP answer string>"
}
```

**ICE candidate exchange:**
```json
{
  "type": "ice-candidate",
  "candidate": {
    "candidate": "<ICE candidate string>",
    "sdpMid": "<media stream ID>",
    "sdpMLineIndex": <index>
  }
}
```

## Audio Processing Pipeline

1. **Audio Reception**: Client streams audio via WebRTC
2. **Voice Activity Detection**: Service detects speech segments
3. **Speech-to-Text**: Converts audio to text
4. **LLM Processing**: Generates response using Gemini
5. **Text-to-Speech**: Converts response to audio
6. **Audio Transmission**: Streams audio back to client via WebRTC

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON | Required |
| `GEMINI_API_KEY` | Gemini API key | Required |
| `LANGUAGE_CODE` | Language for STT/TTS | `de-DE` |
| `VOICE_NAME` | TTS voice name | `de-DE-Wavenet-F` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8080` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Audio Processing Parameters

Edit `audio_processor.py` to adjust:
- `silence_threshold`: Amplitude threshold for silence detection (default: 500)
- `silence_duration`: Seconds of silence to trigger processing (default: 1.5)
- `min_speech_duration`: Minimum speech duration in seconds (default: 0.5)

## Monitoring and Logs

View container logs:

```bash
podman logs -f ai-assistant
```

## Troubleshooting

### Common Issues

1. **Connection refused**
   - Ensure the container is running: `podman ps`
   - Check port mapping: `podman port ai-assistant`

2. **Authentication errors**
   - Verify `GOOGLE_APPLICATION_CREDENTIALS` path
   - Check service account permissions in GCP Console
   - Ensure APIs are enabled

3. **No audio output**
   - Check WebRTC connection state in logs
   - Verify audio codec compatibility
   - Check firewall settings

4. **Transcription errors**
   - Verify `LANGUAGE_CODE` matches spoken language
   - Check audio quality and sample rate (must be 16kHz)
   - Review Google Cloud quotas

## Development

### Running Locally (without container)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
export GEMINI_API_KEY=your_key_here

# Run the service
python main.py
```

### Testing

Test the WebSocket connection:

```bash
# Install websocat
brew install websocat

# Connect to WebSocket
websocat ws://localhost:8080/ws
```

## Performance Considerations

- **Latency**: Total latency ~2-4 seconds (STT + LLM + TTS)
- **Concurrent Connections**: Tested with up to 10 simultaneous connections
- **Memory Usage**: ~200-500 MB per connection
- **CPU Usage**: Moderate, mostly I/O bound

## Security Notes

- Always use HTTPS/WSS in production
- Implement authentication for WebSocket connections
- Rotate API keys regularly
- Use least-privilege service accounts
- Keep dependencies updated

## License

[Your License Here]

## Support

For issues and questions, please open an issue on the repository.
