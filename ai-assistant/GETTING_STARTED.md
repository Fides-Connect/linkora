# 🚀 Getting Started with AI Assistant

This is a quick 5-minute guide to get your AI Assistant running.

## Prerequisites Checklist

Before starting, make sure you have:

- [ ] Google Cloud Platform account with billing enabled
- [ ] Google Cloud service account JSON key file
- [ ] Google Gemini API key
- [ ] Podman installed (or Docker)

## Step 1: Get Your Credentials (10 minutes)

### Google Cloud Service Account

```bash
# 1. Create a project (if you don't have one)
gcloud projects create my-ai-assistant --name="AI Assistant"
gcloud config set project my-ai-assistant

# 2. Enable required APIs
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com

# 3. Create service account
gcloud iam service-accounts create ai-assistant \
    --display-name="AI Assistant Service"

# 4. Grant permissions
PROJECT_ID=$(gcloud config get-value project)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:ai-assistant@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/speech.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:ai-assistant@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/texttospeech.client"

# 5. Download credentials
gcloud iam service-accounts keys create credentials.json \
    --iam-account=ai-assistant@${PROJECT_ID}.iam.gserviceaccount.com

# 6. Move to ai-assistant folder
mv credentials.json /Users/thomas/Projects/Fides/ai-assistant/
```

### Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key (starts with "AI...")

## Step 2: Configure Environment (2 minutes)

```bash
# Go to ai-assistant directory
cd /Users/thomas/Projects/Fides/ai-assistant

# Copy environment template
cp .env.template .env

# Edit .env file
nano .env  # or use your preferred editor
```

Update these values in `.env`:

```bash
# Update this path to your credentials file
GOOGLE_APPLICATION_CREDENTIALS=/Users/thomas/Projects/Fides/ai-assistant/credentials.json

# Paste your Gemini API key here
GEMINI_API_KEY=AIzaSy...your_actual_key_here

# Optional: Customize language and voice
LANGUAGE_CODE=de-DE
VOICE_NAME=de-DE-Wavenet-F
```

## Step 3: Validate Setup (1 minute)

```bash
# Run validation script
python3 validate.py
```

You should see all green checkmarks ✓. If not, fix the issues shown.

## Step 4: Start the Service (2 minutes)

```bash
# Quick start (recommended for first time)
./quickstart.sh

# Or manually
./run.sh start
```

Wait for the message:
```
✅ Service is ready!
📡 WebSocket endpoint: ws://localhost:8080/ws
```

## Step 5: Test It (1 minute)

### Test 1: Health Check

```bash
curl http://localhost:8080/health
```

Expected output:
```json
{
  "status": "healthy",
  "active_connections": 0
}
```

### Test 2: WebSocket Connection

```bash
# Install websocat if needed
brew install websocat

# Test connection
websocat ws://localhost:8080/ws
```

You should see the connection open. Press Ctrl+C to exit.

## ✅ You're Done!

Your AI Assistant is now running and ready to receive connections from ConnectX!

## Common Commands

```bash
# View logs
podman logs -f ai-assistant

# Check status
./run.sh status

# Stop service
./run.sh stop

# Restart service
./run.sh restart

# View all containers
podman ps -a
```

## Next Steps

1. **Keep it running**: The service is now ready for ConnectX integration
2. **Monitor logs**: Watch for any errors in `podman logs -f ai-assistant`
3. **Update ConnectX**: Implement WebRTC client in your Flutter app
4. **Test integration**: Connect ConnectX to `ws://localhost:8080/ws`

## Troubleshooting Quick Fixes

### "Port 8080 already in use"

```bash
# Stop existing container
podman stop ai-assistant
podman rm ai-assistant

# Or use different port
echo "PORT=8081" >> .env
./run.sh start
```

### "Credentials not found"

```bash
# Check file exists
ls -l credentials.json

# Update path in .env
nano .env  # Fix GOOGLE_APPLICATION_CREDENTIALS path
```

### "API key invalid"

```bash
# Verify your Gemini API key
# Visit https://makersuite.google.com/app/apikey
# Create a new key if needed
# Update .env with new key
```

### "Container build fails"

```bash
# Check Podman is running
podman --version
podman machine list  # macOS only

# Start machine if needed
podman machine start

# Try again
./run.sh build
```

## What's Running?

When you start the service, you have:

- **WebSocket Server** on `ws://localhost:8080/ws`
  - Handles signaling for WebRTC
  - Manages client connections

- **Health Endpoint** on `http://localhost:8080/health`
  - Check service status
  - Monitor active connections

- **AI Processing Pipeline**
  - Speech-to-Text (Google Cloud)
  - LLM Processing (Gemini 2.0 Flash)
  - Text-to-Speech (Google Cloud)

## Architecture Overview

```
Your ConnectX App
        │
        │ WebRTC
        │ (Audio Stream)
        ▼
┌──────────────────┐
│  AI Assistant    │ ← Running in container
│  localhost:8080  │
└────────┬─────────┘
         │
         ├─► Google Cloud STT
         ├─► Gemini AI
         └─► Google Cloud TTS
```

## Resources

- **Documentation**: See `README.md` for full API reference
- **Setup Guide**: See `SETUP.md` for detailed instructions
- **Comparison**: See `COMPARISON.md` for Dart vs Python details
- **Summary**: See `PROJECT_SUMMARY.md` for project overview

## Support

If you run into issues:

1. Run `python3 validate.py` to check configuration
2. Check logs: `podman logs ai-assistant`
3. Review `SETUP.md` for detailed troubleshooting
4. Check that all APIs are enabled in Google Cloud Console

---

**Need help?** All documentation is in the `ai-assistant/` folder:
- Start here: `GETTING_STARTED.md` (this file)
- Full docs: `README.md`
- Setup help: `SETUP.md`
- Comparison: `COMPARISON.md`

**Ready to go?** Your AI Assistant is running and waiting for ConnectX! 🎉
