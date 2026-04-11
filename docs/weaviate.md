# Weaviate Vector Database

Weaviate is the vector database infrastructure for the Linkora AI-Assistant, providing semantic search capabilities for intelligent service provider matching.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Deployment Options](#deployment-options)
- [Configuration](#configuration)
- [Data Management](#data-management)
- [Search Capabilities](#search-capabilities)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

## 🎯 Overview

> **Full mode only.** Weaviate is used exclusively when `AGENT_MODE=full`. In lite mode (`AGENT_MODE=lite`), provider search is handled by the Google Places API and no Weaviate connection is required.

Weaviate provides:
- **Semantic Search**: Vector-based similarity search using embeddings
- **Hybrid Search**: Combined vector and keyword (BM25) search
- **Automatic Embeddings**: On-the-fly embedding generation using text2vec-model2vec
- **Persistent Storage**: Docker volume for data persistence
- **RESTful API**: Easy integration with AI-Assistant

### Why Weaviate?

- ✅ Built specifically for semantic search
- ✅ Automatic embedding generation
- ✅ Hybrid search (vector + keyword)
- ✅ Easy Docker deployment
- ✅ RESTful and gRPC APIs
- ✅ Self-hosted or cloud options

## ✨ Features

### Core Capabilities

- **Vector Search**: Semantic similarity using ML embeddings
- **Keyword Search**: Traditional BM25 full-text search
- **Hybrid Search**: Weighted combination of vector and keyword
- **Auto-Vectorization**: Automatic embedding on data insert
- **Filtering**: Category, location, and custom filters
- **Relevance Scoring**: Normalized 0-1 relevance scores

### Data Schema

**Hub-Spoke Model:**

The platform uses a hub-spoke schema where each provider (`User` hub) owns one or more skills (`Competence` spokes). Search targets `Competence` nodes and traverses cross-references to return the full provider profile.

**User (hub):**
```json
{
  "uid": "firebase-uid",
  "name": "Provider Name",
  "email": "contact@provider.com",
  "city": "Berlin",
  "is_service_provider": true,
  "search_optimized_summary": "Compact vectorized summary (vectorized)"
}
```

**Competence (spoke):**
```json
{
  "skill_name": "Bathroom renovation",
  "skill_description": "Full bathroom tile and plumbing (vectorized)",
  "skill_category": "Handwerk",
  "owned_by": ["<User UUID>"]
}
```

## 🚀 Quick Start

### Step 1: Start Weaviate Services

```bash
cd weaviate
docker-compose up -d
```

**Services Started:**
- `weaviate`: Main database (ports 8090, 50051)
- `text2vec-model2vec`: Embedding service (internal)

### Step 2: Verify Health

```bash
# Check service health
curl http://localhost:8090/v1/.well-known/ready

# Get metadata
curl http://localhost:8090/v1/meta

# Expected: JSON response with version info
```

### Step 3: Initialize Schema and Data

```bash
cd ../ai-assistant
python scripts/init_database.py --load-test-data
```

**This script:**
- Creates `User` and `ServiceProvider` collections
- Configures vectorization settings
- Loads test provider data
- Verifies setup

### Step 4: Configure AI-Assistant

Edit `ai-assistant/.env`:
```bash
WEAVIATE_URL=http://localhost:8090
```

### Step 5: Test Connection

```bash
cd ../ai-assistant
python scripts/test_search_providers.py

# Should return matched providers
```

## 🌐 Deployment Options

### Option 1: Local Development (Recommended)

✅ **Pros:**
- Full control over data and configuration
- Free and private
- No external dependencies
- Perfect for development and testing

**Setup:**
```bash
cd weaviate
docker-compose up -d
```

**Configuration (in `ai-assistant/.env`):**
```bash
WEAVIATE_URL=http://localhost:8090
```

**Ports:**
- HTTP: `http://localhost:8090`
- gRPC: `localhost:50051`

### Option 2: Weaviate Cloud Services (WCS)

✅ **Pros:**
- Managed hosting with auto-scaling
- High availability and backups
- No local infrastructure
- Free tier available (14-day sandbox)

**Setup:**

1. **Create Cloud Cluster:**
   - Go to https://console.weaviate.cloud/
   - Sign up and create new cluster
   - Note your cluster URL and API key

2. **Initialize Cloud Database:**
   ```bash
   cd ai-assistant
   python scripts/init_database.py --load-test-data
   ```

3. **Configure AI-Assistant (in `.env`):**
   ```bash
   WEAVIATE_CLUSTER_URL=https://your-cluster.weaviate.network
   WEAVIATE_API_KEY=your-weaviate-cloud-api-key
   ```

**Note**: Cloud configuration (`WEAVIATE_CLUSTER_URL`) takes precedence over local `WEAVIATE_URL`.

### Option 3: Compute Engine VM (Production)

See [Deployment Documentation](deployment.md) for the full Compute Engine setup.

## ⚙️ Configuration

### Docker Compose Setup

```yaml
# weaviate/docker-compose.yml

services:
  weaviate:
    image: cr.weaviate.io/semitechnologies/weaviate:1.27.4
    ports:
      - "8090:8080"  # HTTP
      - "50051:50051" # gRPC
    environment:
      CLUSTER_HOSTNAME: 'node1'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'text2vec-model2vec'
      ENABLE_MODULES: 'text2vec-model2vec'
      MODEL2VEC_INFERENCE_API: 'http://text2vec-model2vec:8080'
    volumes:
      - weaviate_data:/var/lib/weaviate
    networks:
      - weaviate-network

  text2vec-model2vec:
    image: cr.weaviate.io/semitechnologies/text2vec-model2vec:latest
    environment:
      ENABLE_CUDA: 0  # Set to 1 for GPU acceleration
    networks:
      - weaviate-network

networks:
  weaviate-network:
    name: weaviate-network

volumes:
  weaviate_data:
```

### Vectorization Settings

The platform uses a hub-spoke schema. Vectorization is applied to the `Competence` spoke (skill description) and to the `User` hub (`search_optimized_summary`):

```python
# Competence spoke — vectorize skill_description for semantic search
{
    "class": "Competence",
    "vectorizer": "text2vec-model2vec",
    "moduleConfig": {
        "text2vec-model2vec": {
            "vectorizeClassName": False,
            "properties": ["skill_description"]
        }
    }
}

# User hub — vectorize search_optimized_summary
{
    "class": "User",
    "vectorizer": "text2vec-model2vec",
    "moduleConfig": {
        "text2vec-model2vec": {
            "vectorizeClassName": False,
            "properties": ["search_optimized_summary"]
        }
    }
}
```

**Embedding Model:**
- Model: `minishlab/potion-base-32M`
- Dimensions: 256
- Languages: Multilingual (includes German)

### Network Configuration

**Shared Network:**
- Name: `weaviate-network`
- Allows AI-Assistant to communicate with Weaviate
- AI-Assistant docker-compose references this network

**When AI-Assistant in Docker:**
```bash
WEAVIATE_URL=http://weaviate:8080  # Use service name
```

**When AI-Assistant runs locally:**
```bash
WEAVIATE_URL=http://localhost:8090
```

## 📊 Data Management

### Initialize/Reinitialize Database

```bash
cd ai-assistant
python scripts/init_database.py --load-test-data
```

**Options:**
- `--load-test-data`: Load sample providers (default: true)
- `--skip-test-data`: Skip loading test data

### Query Providers

```python
from ai_assistant.data_provider import DataProvider

data_provider = DataProvider()

# Search for providers
results = data_provider.search_providers(
    query="need a plumber for bathroom",
    filters={"city": "Berlin"}
)

for provider in results:
    print(f"{provider.name}: {provider.relevance_score}")
```

### Backup Data

```bash
# Backup Weaviate volume
docker run --rm \
  -v weaviate_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/weaviate-backup-$(date +%Y%m%d).tar.gz /data
```

### Restore Data

```bash
# Stop Weaviate
cd weaviate
docker-compose down

# Restore volume
docker run --rm \
  -v weaviate_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/weaviate-backup-20260121.tar.gz -C /

# Start Weaviate
docker-compose up -d
```

### Clean Restart (Delete All Data)

```bash
cd weaviate

# Stop services and remove volume
docker-compose down -v

# Start fresh
docker-compose up -d

# Reinitialize
cd ../ai-assistant
python scripts/init_database.py --load-test-data
```

## 🔍 Search Capabilities

### Hybrid Search Algorithm

Weaviate combines two search methods:

1. **Vector Search (70% weight)**
   - Semantic similarity using embeddings
   - Understands meaning and context
   - Example: "bathroom repair" matches "plumbing services"

2. **Keyword Search / BM25 (30% weight)**
   - Traditional full-text search
   - Exact word matching
   - Example: "Berlin" must appear in text

**Combined Result:**
```
relevance_score = (0.7 × vector_score) + (0.3 × bm25_score)
```

### Search Examples

**Basic Search:**
```python
results = data_provider.search_providers(
    query="need a plumber",
    top_k=5
)
```

**Filtered Search:**
```python
results = data_provider.search_providers(
    query="bathroom renovation",
    filters={"city": "Berlin", "category": "Plumbing"},
    top_k=3
)
```

**Search with Category Detection:**
```python
# AI-Assistant automatically detects category from query
# "I need an electrician" → category="Electrical"
results = search_with_category_detection(
    query="I need an electrician in Munich"
)
```

### Relevance Scoring

Scores are normalized to 0-1 range:
- **0.8-1.0**: Excellent match
- **0.6-0.8**: Good match
- **0.4-0.6**: Fair match
- **0.2-0.4**: Weak match
- **0.0-0.2**: Poor match

## 🔧 Common Commands

### Service Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f weaviate

# Check status
docker-compose ps
```

### Health Checks

```bash
# Service ready check
curl http://localhost:8090/v1/.well-known/ready

# Expected: {"status": "ok"}

# Metadata and version
curl http://localhost:8090/v1/meta

# Prometheus metrics (if enabled)
curl http://localhost:8090/metrics
```

### Data Inspection

```bash
# List collections (requires weaviate-client)
python -c "
import weaviate
client = weaviate.Client('http://localhost:8090')
print(client.schema.get())
"

# Count objects in collection
python -c "
import weaviate
client = weaviate.Client('http://localhost:8090')
result = client.query.aggregate('ServiceProvider').with_meta_count().do()
print(result)
"
```

## 🐛 Troubleshooting

### Services Won't Start

**Symptoms**: Docker containers exit or won't start

**Solution:**
```bash
# Check logs
docker-compose logs weaviate
docker-compose logs text2vec-model2vec

# Common issues and fixes:

# 1. Port already in use
lsof -i :8090
kill -9 <PID>
# Or change port in docker-compose.yml

# 2. Insufficient memory
# Increase Docker memory to 8GB+
# Docker Desktop → Preferences → Resources

# 3. Volume issues
docker-compose down -v
docker volume rm weaviate_data
docker-compose up -d
```

### Connection Refused

**Symptoms**: Can't connect to Weaviate

**Solution:**
```bash
# 1. Check if services are running
docker-compose ps

# 2. Wait for startup (10-15 seconds)
sleep 15
curl http://localhost:8090/v1/.well-known/ready

# 3. Check logs for errors
docker-compose logs weaviate

# 4. Verify network
docker network inspect weaviate-network

# 5. Test connection from AI-Assistant container
docker-compose run ai-assistant curl http://weaviate:8080/v1/meta
```

### No Search Results

**Symptoms**: Search returns empty results

**Solution:**
```bash
# 1. Verify data exists
curl http://localhost:8090/v1/objects

# 2. Check collection exists
curl http://localhost:8090/v1/schema

# 3. Reinitialize if needed
cd ../ai-assistant
python scripts/init_database.py --load-test-data

# 4. Test search directly
python scripts/test_search_providers.py
```

### Data Disappeared After Restart

**Symptoms**: Data lost after docker-compose restart

**Solution:**
```bash
# 1. Verify volume exists
docker volume ls | grep weaviate

# 2. Ensure docker-compose.yml has volumes section
# volumes:
#   weaviate_data:

# 3. Check volume is mounted
docker-compose config

# 4. Restart with volume
docker-compose down
docker-compose up -d

# If data is truly lost, restore from backup
# or reinitialize:
python scripts/init_database.py --load-test-data
```

### Slow Search Performance

**Symptoms**: High latency on searches

**Solution:**
1. **Check resource usage:**
   ```bash
   docker stats weaviate
   ```

2. **Increase resources in docker-compose.yml:**
   ```yaml
   weaviate:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 4G
   ```

3. **Enable GPU acceleration (if available):**
   ```yaml
   text2vec-model2vec:
     environment:
       ENABLE_CUDA: 1
   ```

4. **Reduce result count:**
   ```python
   results = search_providers(query, top_k=3)  # Instead of 10
   ```

## 🚀 Advanced Topics

### Production Optimization

**Resource Limits:**
```yaml
weaviate:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
```

**GPU Acceleration:**
```yaml
text2vec-model2vec:
  environment:
    ENABLE_CUDA: 1
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Monitoring

**Prometheus Metrics:**
```yaml
weaviate:
  environment:
    PROMETHEUS_MONITORING_ENABLED: 'true'
```

**Access metrics:**
```bash
curl http://localhost:8090/metrics
```

**Key Metrics:**
- `weaviate_objects_total`: Total objects
- `weaviate_queries_total`: Total queries
- `weaviate_query_duration_seconds`: Query latency

### Custom Embedding Models

To use a different embedding model:

1. **Update docker-compose.yml:**
   ```yaml
   text2vec-model2vec:
     environment:
       MODEL_NAME: 'your-model-name'
   ```

2. **Update schema in init script:**
   ```python
   "moduleConfig": {
       "text2vec-model2vec": {
           "model": "your-model-name"
       }
   }
   ```

### Multi-Tenancy

For isolating data per tenant:

```python
# Create tenant
client.schema.create_class_tenant(
    class_name="User",
    tenants=[{"name": "tenant1"}]
)

# Query with tenant
results = client.query.get(
    "User",
    ["uid", "name"]
).with_tenant("tenant1").do()
```

## 🔗 Related Documentation

- [AI-Assistant Documentation](ai-assistant.md) - Backend integration
- [Architecture Overview](architecture.md) - System design
- [Weaviate Official Docs](https://weaviate.io/developers/weaviate)