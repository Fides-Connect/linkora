# Weaviate Vector Database

Vector database infrastructure for the Fides AI Assistant service. Provides semantic search for intelligent service provider matching using automatic embeddings and hybrid search.

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Deployment Options](#-deployment-options)
- [Configuration](#-configuration)
- [Common Commands](#-common-commands)
- [Troubleshooting](#-troubleshooting)
- [Advanced](#-advanced)

## 🚀 Quick Start

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Verify Health
```bash
curl http://localhost:8090/v1/meta
```

### 3. Initialize Data
```bash
cd ../ai-assistant
python scripts/init_weaviate.py
```

### 4. Configure AI Assistant
Edit `ai-assistant/.env`:
```bash
USE_WEAVIATE=true
WEAVIATE_URL=http://localhost:8090
```

### 5. Start AI Assistant
```bash
cd ../ai-assistant
docker-compose up
```

**Ports**:
- HTTP: `http://localhost:8090`
- gRPC: `localhost:50051`

## 🌐 Deployment Options

### Local (Development)
✅ Full control, free, private  
✅ Uses `docker-compose.yml` in this directory  
✅ Perfect for development and testing  

**Configuration**:
```bash
USE_WEAVIATE=true
WEAVIATE_URL=http://localhost:8090
```

### Cloud (Production)
✅ Managed hosting, auto-scaling, HA  
✅ Free tier available (14-day sandbox)  
✅ Sign up: https://console.weaviate.cloud/  

**Configuration**:
```bash
USE_WEAVIATE=true
WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
WEAVIATE_API_KEY=your-weaviate-cloud-api-key
```

**Note**: Cloud config takes precedence over local `WEAVIATE_URL`

**Note**: Cloud config takes precedence over local `WEAVIATE_URL`

## ⚙️ Configuration

### Data Schema

**Collections**: `User`, `ServiceProvider`

**ServiceProvider** (vectorized on `description` field):
- Uses `text2vec-model2vec` (minishlab/potion-base-32M)
- Hybrid search: vector similarity + BM25 keyword matching
- Automatic embedding generation on insert

### Docker Services

```yaml
weaviate:           # Vector database (port 8090, 50051)
text2vec-model2vec: # Embedding service (internal)
```

**Network**: `weaviate-network` (shared with AI Assistant)  
**Volume**: `weaviate_data` (persistent storage)

## 🔧 Common Commands

### Service Management
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f weaviate

# Restart
docker-compose restart
```

### Data Management
```bash
# Initialize/reinitialize
cd ../ai-assistant && python scripts/init_weaviate.py

# Backup
docker run --rm -v weaviate_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/weaviate-backup-$(date +%Y%m%d).tar.gz /data

# Clean restart (deletes all data)
docker-compose down -v
docker-compose up -d
cd ../ai-assistant && python scripts/init_weaviate.py
```

### Health Checks
```bash
# Service status
docker-compose ps

# Weaviate health
curl http://localhost:8090/v1/.well-known/ready

# Metadata
curl http://localhost:8090/v1/meta

# Metrics (Prometheus)
curl http://localhost:8090/metrics
```

## 🔍 Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs weaviate

# Common fixes:
docker-compose down && docker-compose up -d  # Clean restart
# Change port in docker-compose.yml if 8090 is in use
# Increase Docker memory to 8GB+
```

### Connection refused
```bash
# Wait for startup (10-15 seconds)
curl http://localhost:8090/v1/.well-known/ready

# If still failing, check logs
docker-compose logs weaviate
```

### No search results
```bash
# Verify data exists
docker-compose exec weaviate weaviate-cli collection list

# Reinitialize if needed
cd ../ai-assistant && python scripts/init_weaviate.py
```

### Data disappeared after restart
```bash
# Check volume exists
docker volume ls | grep weaviate

# Ensure docker-compose.yml has volumes section
# Restart with volume
docker-compose down && docker-compose up -d
```

## 🚀 Advanced

### Production Optimization

**GPU Acceleration**:
```yaml
text2vec-model2vec:
  environment:
    ENABLE_CUDA: 1
```

**Memory Limits**:
```yaml
weaviate:
  deploy:
    resources:
      limits:
        memory: 8G
```

### Security

**Enable Authentication**:
```yaml
weaviate:
  environment:
    AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: false
    AUTHENTICATION_APIKEY_ENABLED: true
    AUTHENTICATION_APIKEY_ALLOWED_KEYS: your-secure-api-key
```

**Restrict Access**:
```yaml
weaviate:
  ports:
    - "127.0.0.1:8090:8080"  # Localhost only
```

### Cloud Migration

To move from local to cloud:
1. Create cluster at https://console.weaviate.cloud/
2. Update `ai-assistant/.env`:
   ```bash
   WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
   WEAVIATE_API_KEY=your-api-key
   ```
3. Initialize: `python scripts/init_weaviate.py`
4. No local Weaviate needed!

---

**Resources**:
- [Weaviate Docs](https://weaviate.io/developers/weaviate)
- [model2vec](https://github.com/MinishLab/model2vec)
- [AI Assistant README](../ai-assistant/README.md)
