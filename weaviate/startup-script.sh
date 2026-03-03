#!/bin/bash
# Startup script for the Weaviate Compute Engine VM.
# Run once automatically on VM creation (via --metadata-from-file startup-script=...).
# The CI/CD pipeline will keep /opt/weaviate/docker-compose.yml up to date after that.
set -euo pipefail

LOG_FILE="/var/log/weaviate-startup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Weaviate VM startup: $(date) ==="

# ── 1. Install Docker ──────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg lsb-release

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo "Docker installed."
else
  echo "Docker already installed, skipping."
fi

# ── 2. Create app directory ────────────────────────────────────────────────────
mkdir -p /opt/weaviate

# ── 3. Write docker-compose.yml (initial version; CI keeps it updated) ─────────
cat > /opt/weaviate/docker-compose.yml << 'COMPOSE'
version: '4.0'

services:
  weaviate:
    image: cr.weaviate.io/semitechnologies/weaviate:1.32.2
    container_name: weaviate
    ports:
      - "8080:8080"   # Weaviate HTTP API
      - "50051:50051" # Weaviate gRPC
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'text2vec-model2vec'
      ENABLE_MODULES: 'text2vec-model2vec'
      MODEL2VEC_INFERENCE_API: 'http://text2vec-model2vec:8080'
      CLUSTER_HOSTNAME: 'node1'
    volumes:
      - weaviate_data:/var/lib/weaviate
    networks:
      - weaviate-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/v1/.well-known/ready"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 30s

  text2vec-model2vec:
    image: cr.weaviate.io/semitechnologies/model2vec-inference:minishlab-potion-base-32M
    container_name: text2vec-model2vec
    networks:
      - weaviate-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/.well-known/ready"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s

networks:
  weaviate-network:
    name: weaviate-network
    driver: bridge

volumes:
  weaviate_data:
    name: weaviate_data
COMPOSE

# ── 4. Create systemd service so Weaviate restarts on VM reboot ────────────────
cat > /etc/systemd/system/weaviate.service << 'SERVICE'
[Unit]
Description=Weaviate Vector Database (Docker Compose)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/weaviate
ExecStart=/usr/bin/docker compose up -d --pull always
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable weaviate

# ── 5. Pull images and start Weaviate ─────────────────────────────────────────
echo "Pulling Weaviate images (this may take a few minutes)..."
cd /opt/weaviate
docker compose pull
docker compose up -d

echo "=== Weaviate startup complete: $(date) ==="
echo "Weaviate API: http://$(curl -s ifconfig.me):8080"
echo "Check health: curl http://localhost:8080/v1/.well-known/ready"
