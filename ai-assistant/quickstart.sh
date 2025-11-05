#!/bin/bash
# Quick start script for AI Assistant

set -e

echo "🚀 AI Assistant Quick Start"
echo "============================"
echo ""

# Check for required files
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.template to .env and configure it:"
    echo "  cp .env.template .env"
    echo "  # Edit .env with your credentials"
    exit 1
fi

# Source environment
source .env

# Validate required variables
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "❌ Error: Please set GEMINI_API_KEY in .env file"
    exit 1
fi

if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "❌ Error: Google Cloud credentials file not found"
    echo "   Expected at: $GOOGLE_APPLICATION_CREDENTIALS"
    exit 1
fi

echo "✅ Configuration validated"
echo ""

# Build container
echo "🔨 Building container..."
podman build -t ai-assistant -f Containerfile . || {
    echo "❌ Build failed"
    exit 1
}

echo "✅ Build successful"
echo ""

# Stop existing container
echo "🛑 Stopping existing container (if any)..."
podman rm -f ai-assistant 2>/dev/null || true

# Run container
echo "🎬 Starting AI Assistant..."
podman run -d \
    --name ai-assistant \
    -p ${PORT:-8080}:${PORT:-8080} \
    -v "$GOOGLE_APPLICATION_CREDENTIALS:/app/credentials.json:ro" \
    -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
    -e GEMINI_API_KEY="$GEMINI_API_KEY" \
    -e LANGUAGE_CODE="${LANGUAGE_CODE:-de-DE}" \
    -e VOICE_NAME="${VOICE_NAME:-de-DE-Wavenet-F}" \
    -e HOST="${HOST:-0.0.0.0}" \
    -e PORT="${PORT:-8080}" \
    ai-assistant

echo ""
echo "✅ AI Assistant is starting..."
echo ""

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
for i in {1..30}; do
    if curl -s -f http://localhost:${PORT:-8080}/health > /dev/null 2>&1; then
        echo "✅ Service is ready!"
        echo ""
        curl -s http://localhost:${PORT:-8080}/health | python3 -m json.tool
        echo ""
        echo "📡 WebSocket endpoint: ws://localhost:${PORT:-8080}/ws"
        echo "🏥 Health check: http://localhost:${PORT:-8080}/health"
        echo ""
        echo "📋 View logs with: podman logs -f ai-assistant"
        echo "🛑 Stop with: podman stop ai-assistant"
        exit 0
    fi
    sleep 1
done

echo "⚠️  Service didn't respond after 30 seconds"
echo "Check logs with: podman logs ai-assistant"
exit 1
