#!/bin/bash
#
# Script to build and run the AI Assistant container with Podman
#

set -e
# Resolve project root (script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_FILE="$PROJECT_ROOT/.env"
ENV_TEMPLATE="$PROJECT_ROOT/.env.template"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}AI Assistant Container Management${NC}"
echo "=================================="

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Warning: .env file not found at $ENV_FILE. Creating from template...${NC}"
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    echo -e "${RED}Please edit $ENV_FILE with your credentials before continuing!${NC}"
    exit 1
fi


# Load environment variables
source "$ENV_FILE"

# Resolve credentials file to absolute path if not already
if [[ "$GOOGLE_APPLICATION_CREDENTIALS" != /* ]]; then
    GOOGLE_APPLICATION_CREDENTIALS="$PROJECT_ROOT/$GOOGLE_APPLICATION_CREDENTIALS"
fi

# Check for required variables
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo -e "${RED}Error: GEMINI_API_KEY not set in .env file${NC}"
    exit 1
fi

if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo -e "${RED}Error: GOOGLE_APPLICATION_CREDENTIALS not set in .env file${NC}"
    exit 1
fi

if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo -e "${RED}Error: Google Cloud credentials file not found at: $GOOGLE_APPLICATION_CREDENTIALS${NC}"
    exit 1
fi

# Detect container engine
detect_container_engine() {
    if command -v docker >/dev/null 2>&1; then
        echo "docker"
    elif command -v podman >/dev/null 2>&1; then
        echo "podman"
    else
        echo "none"
    fi
}

CONTAINER_ENGINE="$(detect_container_engine)"
if [ "$CONTAINER_ENGINE" = "none" ]; then
    echo -e "${RED}Error: Neither Docker nor Podman is installed. Please install one to continue.${NC}"
    exit 1
fi

# Function to build the container
build() {
    echo -e "${GREEN}Building AI Assistant container with $CONTAINER_ENGINE...${NC}"
    $CONTAINER_ENGINE build -t ai-assistant -f Containerfile .
    echo -e "${GREEN}Build complete!${NC}"
}

# Function to run the container
run() {
    echo -e "${GREEN}Starting AI Assistant container...${NC}"
    
    # Stop and remove existing container if it exists
    $CONTAINER_ENGINE rm -f ai-assistant 2>/dev/null || true
    

        $CONTAINER_ENGINE run -d \
            --name ai-assistant \
            -p 80:80 \
            -p 443:443 \
            -p ${PORT:-8080}:${PORT:-8080} \
            -p 10000-10100:10000-10100/udp \
            -v "$GOOGLE_APPLICATION_CREDENTIALS:/app/credentials.json:ro" \
            -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
            -e GEMINI_API_KEY="$GEMINI_API_KEY" \
            -e LANGUAGE_CODE="${LANGUAGE_CODE:-de-DE}" \
            -e VOICE_NAME="${VOICE_NAME:-de-DE-Chirp3-HD-Sulafat}" \
            -e HOST="${HOST:-0.0.0.0}" \
            -e PORT="${PORT:-8080}" \
            -e LOG_LEVEL="${LOG_LEVEL:-INFO}" \
            -e GOOGLE_TTS_API_CONCURRENCY="${GOOGLE_TTS_API_CONCURRENCY:-5}" \
            ai-assistant
    
    echo -e "${GREEN}Container started!${NC}"
    echo -e "WebSocket endpoint: ws://localhost:${PORT:-8080}/ws"
    echo -e "Health check: http://localhost:${PORT:-8080}/health"
}

# Function to stop the container
stop() {
    echo -e "${YELLOW}Stopping AI Assistant container...${NC}"
    $CONTAINER_ENGINE stop ai-assistant
    echo -e "${GREEN}Container stopped${NC}"
}

# Function to view logs
logs() {
    echo -e "${GREEN}Viewing container logs (Ctrl+C to exit)...${NC}"
    $CONTAINER_ENGINE logs -f ai-assistant
}

# Function to check status
status() {
    echo -e "${GREEN}Checking container status...${NC}"
    $CONTAINER_ENGINE ps -a --filter "name=ai-assistant"
    echo ""
    
    # Try to hit health endpoint
    if curl -f -s http://localhost:${PORT:-8080}/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is healthy${NC}"
        curl -s http://localhost:${PORT:-8080}/health | python -m json.tool
    else
        echo -e "${RED}✗ Service is not responding${NC}"
    fi
}

# Main script logic
case "${1:-}" in
    build)
        build
        ;;
    run)
        run
        ;;
    start)
        build
        run
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        run
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {build|run|start|stop|restart|logs|status}"
        echo ""
        echo "Commands:"
        echo "  build   - Build the container image"
        echo "  run     - Run the container (without building)"
        echo "  start   - Build and run the container"
        echo "  stop    - Stop the running container"
        echo "  restart - Stop and start the container"
        echo "  logs    - View container logs"
        echo "  status  - Check container and service status"
        exit 1
        ;;
esac
