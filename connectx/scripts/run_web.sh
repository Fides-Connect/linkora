#!/usr/bin/env bash
set -euo pipefail

# Simple helper to run the ConnectX Flutter web-server using a port from .env
# Usage:
#   ./scripts/run_web.sh            # reads WEB_PORT from .env, defaults to 60099
#   ./scripts/run_web.sh 8080       # explicitly pass a port

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
DEFAULT_PORT=60099

# Allow passing port as first argument
if [ $# -gt 0 ]; then
  WEB_PORT="$1"
else
  WEB_PORT_LINE=""
  if [ -f "$ENV_FILE" ]; then
    WEB_PORT_LINE=$(grep -E '^WEB_PORT=' "$ENV_FILE" || true)
  fi

  if [ -n "$WEB_PORT_LINE" ]; then
    # strip key and any surrounding quotes
    WEB_PORT=$(echo "$WEB_PORT_LINE" | sed 's/^[^=]*=//' | tr -d '"' | tr -d "'" )
  else
    WEB_PORT="$DEFAULT_PORT"
  fi
fi

echo "Using WEB_PORT=${WEB_PORT}"
cd "$PROJECT_ROOT"

# Run flutter web-server with the specified port
CMD=(flutter run -d chrome --web-port="${WEB_PORT}")

echo "Executing: ${CMD[*]}"
exec "${CMD[@]}"
