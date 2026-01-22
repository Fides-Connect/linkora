# Helm Charts Documentation

This document covers Kubernetes deployment using Helm charts for the Linkora AI Voice Assistant platform.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Helm Charts](#helm-charts)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [CI/CD Integration](#cicd-integration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The Linkora platform uses Helm charts for Kubernetes deployment, providing:
- Declarative infrastructure management
- Version-controlled deployments
- Easy rollbacks and updates
- Environment-specific configurations
- Integrated secrets management

### Available Charts

1. **ai-assistant**: Backend WebRTC server
2. **weaviate**: Vector database infrastructure

## 📋 Prerequisites

### Tools Required
- **kubectl**: Kubernetes command-line tool
- **Helm**: Version 3.0 or higher
- **gcloud CLI**: For GKE access (if using Google Cloud)

### Infrastructure
- Kubernetes cluster (GKE, EKS, AKS, or local)
- Container registry (GCR, Docker Hub, etc.)
- Load balancer support (for external access)

### Install Tools

```bash
# Install kubectl
brew install kubectl  # macOS
# Or: https://kubernetes.io/docs/tasks/tools/

# Install Helm
brew install helm  # macOS
# Or: https://helm.sh/docs/intro/install/

# Install gcloud (for GKE)
brew install google-cloud-sdk  # macOS
# Or: https://cloud.google.com/sdk/docs/install
```

## 📦 Helm Charts

### AI-Assistant Chart

**Location**: `helm/ai-assistant/`

**Resources Created:**
- Deployment: ai-assistant (configurable replicas)
- Service: LoadBalancer for external access
- ConfigMap: Non-sensitive configuration
- Secrets: API keys and credentials
- HorizontalPodAutoscaler: Auto-scaling rules

**Structure:**
```
helm/ai-assistant/
├── Chart.yaml           # Chart metadata
├── values.yaml          # Default configuration
├── values-prod.yaml     # Production overrides
├── values-dev.yaml      # Development overrides
└── templates/
    ├── deployment.yaml  # Pod specification
    ├── service.yaml     # Network exposure
    ├── configmap.yaml   # Configuration
    ├── secrets.yaml     # Sensitive data
    └── hpa.yaml         # Auto-scaling
```

### Weaviate Chart

**Location**: `helm/weaviate/`

**Resources Created:**
- StatefulSet: weaviate (for data persistence)
- Service: ClusterIP for internal access
- PersistentVolumeClaim: Data storage
- ConfigMap: Weaviate configuration

**Structure:**
```
helm/weaviate/
├── Chart.yaml           # Chart metadata
├── values.yaml          # Default configuration
└── templates/
    ├── statefulset.yaml # Persistent deployment
    ├── service.yaml     # Network access
    └── pvc.yaml         # Storage claim
```

## 🚀 Deployment

### Setup GKE Cluster (Google Cloud)

```bash
# Authenticate
gcloud auth login

# Set project
gcloud config set project <your-project-id>

# Get cluster credentials
gcloud container clusters get-credentials fides-production \
  --region europe-west3

# Verify connection
kubectl cluster-info
kubectl get nodes
```

### Deploy Weaviate

```bash
cd helm

# Install Weaviate
helm install weaviate ./weaviate \
  --namespace default \
  --create-namespace

# Verify deployment
kubectl get pods -l app=weaviate
kubectl get svc weaviate-service

# Wait for ready
kubectl wait --for=condition=ready pod -l app=weaviate --timeout=300s
```

### Initialize Weaviate Schema

```bash
# Port-forward to access Weaviate
kubectl port-forward svc/weaviate-service 8090:80 &

# Run initialization script
cd ../ai-assistant
python scripts/init_hub_spoke_schema.py --load-test-data

# Stop port-forward
kill %1
```

### Deploy AI-Assistant

```bash
cd ../helm

# Create secrets
kubectl create secret generic ai-assistant-secrets \
  --from-literal=gemini-api-key=$GEMINI_API_KEY \
  --from-literal=google-service-account="$(cat ../ai-assistant/service-account.json)" \
  --from-literal=oauth-client-id=$GOOGLE_OAUTH_CLIENT_ID

# Install AI-Assistant
helm install ai-assistant ./ai-assistant \
  --namespace default \
  --set image.repository=gcr.io/<project-id>/ai-assistant \
  --set image.tag=latest

# Verify deployment
kubectl get pods -l app=ai-assistant
kubectl get svc ai-assistant-service

# Wait for ready
kubectl wait --for=condition=ready pod -l app=ai-assistant --timeout=300s
```

### Get External IP

```bash
# Get LoadBalancer IP
kubectl get svc ai-assistant-service

# Example output:
# NAME                  TYPE           EXTERNAL-IP     PORT(S)
# ai-assistant-service  LoadBalancer   34.89.167.123   8080:30123/TCP

# Test connection
curl http://34.89.167.123:8080/health
```

## ⚙️ Configuration

### Environment-Specific Values

**Development (`values-dev.yaml`):**
```yaml
replicaCount: 1

image:
  tag: dev

resources:
  limits:
    cpu: 500m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 512Mi

env:
  LOG_LEVEL: "DEBUG"

autoscaling:
  enabled: false
```

**Production (`values-prod.yaml`):**
```yaml
replicaCount: 3

image:
  tag: latest

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi

env:
  WEAVIATE_URL: "http://weaviate-service:80"
  LOG_LEVEL: "INFO"

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

### Using Value Files

```bash
# Deploy with development values
helm install ai-assistant ./ai-assistant \
  -f ./ai-assistant/values-dev.yaml

# Deploy with production values
helm install ai-assistant ./ai-assistant \
  -f ./ai-assistant/values-prod.yaml

# Override specific values
helm install ai-assistant ./ai-assistant \
  --set replicaCount=5 \
  --set image.tag=v1.2.3
```

### Secrets Management

**Option 1: kubectl create secret**
```bash
kubectl create secret generic ai-assistant-secrets \
  --from-literal=gemini-api-key=$GEMINI_API_KEY \
  --from-file=google-service-account=./service-account.json
```

**Option 2: External Secrets Operator (Recommended for Production)**
```yaml
# external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ai-assistant-secrets
spec:
  secretStoreRef:
    name: gcpsm-secret-store
    kind: ClusterSecretStore
  target:
    name: ai-assistant-secrets
  data:
    - secretKey: gemini-api-key
      remoteRef:
        key: gemini-api-key
```

## 🔄 CI/CD Integration

### GitHub Actions Workflow

The platform uses automated deployment via GitHub Actions:

**Workflow**: `.github/workflows/cloud-deploy.yml`

**Trigger**: Push to `main` branch

**Steps:**
1. Build Docker image
2. Push to Google Container Registry (GCR)
3. Deploy Weaviate (if schema changed)
4. Deploy AI-Assistant with new image
5. Run smoke tests

**Required GitHub Secrets:**
- `GOOGLE_SERVICE_ACCOUNT_JSON`: GCP credentials with GKE/GCR access
- `GEMINI_API_KEY`: Google Gemini API key
- `GOOGLE_OAUTH_CLIENT_ID`: OAuth client ID
- `ADMIN_SECRET_KEY`: Admin interface key

### Manual Deployment

```bash
# Build image
cd ai-assistant
docker build -t gcr.io/<project-id>/ai-assistant:latest .

# Push to registry
docker push gcr.io/<project-id>/ai-assistant:latest

# Upgrade Helm release
helm upgrade ai-assistant ./helm/ai-assistant \
  --set image.tag=latest \
  --reuse-values
```

### Rollback

```bash
# List releases
helm history ai-assistant

# Rollback to previous version
helm rollback ai-assistant

# Rollback to specific revision
helm rollback ai-assistant 3
```

## 📊 Monitoring

### Check Pod Status

```bash
# List all pods
kubectl get pods

# Describe specific pod
kubectl describe pod ai-assistant-xxxxx-yyyyy

# Get pod logs
kubectl logs -f ai-assistant-xxxxx-yyyyy

# Get logs from previous container (if crashed)
kubectl logs ai-assistant-xxxxx-yyyyy --previous
```

### Check Service Status

```bash
# List services
kubectl get svc

# Describe service
kubectl describe svc ai-assistant-service

# Check endpoints
kubectl get endpoints ai-assistant-service
```

### Resource Usage

```bash
# Pod metrics
kubectl top pods

# Node metrics
kubectl top nodes

# HPA status
kubectl get hpa ai-assistant-hpa

# Detailed HPA metrics
kubectl describe hpa ai-assistant-hpa
```

### Application Health

```bash
# Get external IP
EXTERNAL_IP=$(kubectl get svc ai-assistant-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Health check
curl http://$EXTERNAL_IP:8080/health

# Expected: {"status":"healthy","active_connections":0}
```

## 🐛 Troubleshooting

### Pod Fails to Start

**Symptoms**: Pod in CrashLoopBackOff or Error state

**Diagnosis:**
```bash
# Check pod status
kubectl get pods
kubectl describe pod <pod-name>

# Check logs
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
```

**Common Issues:**

1. **Missing secrets:**
   ```bash
   # Verify secrets exist
   kubectl get secrets
   kubectl describe secret ai-assistant-secrets
   ```

2. **Image pull error:**
   ```bash
   # Check image exists
   gcloud container images list --repository=gcr.io/<project-id>
   
   # Verify image pull secret
   kubectl get serviceaccounts default -o yaml
   ```

3. **Resource constraints:**
   ```bash
   # Check node resources
   kubectl describe nodes
   
   # Reduce resource requests in values.yaml
   ```

### Service Not Accessible

**Symptoms**: Can't connect to external IP

**Diagnosis:**
```bash
# Check service
kubectl get svc ai-assistant-service
kubectl describe svc ai-assistant-service

# Check if LoadBalancer IP assigned
# If <pending>, wait a few minutes
```

**Solutions:**

1. **LoadBalancer pending:**
   - Wait 2-5 minutes for IP assignment
   - Check cloud provider load balancer quota
   - Verify GKE cluster has LoadBalancer support

2. **Firewall rules:**
   ```bash
   # For GKE, create firewall rule
   gcloud compute firewall-rules create allow-ai-assistant \
     --allow tcp:8080 \
     --source-ranges 0.0.0.0/0 \
     --target-tags gke-node
   ```

3. **Health check failing:**
   ```bash
   # Port-forward to test directly
   kubectl port-forward svc/ai-assistant-service 8080:8080
   curl http://localhost:8080/health
   ```

### Weaviate Connection Failed

**Symptoms**: AI-Assistant can't connect to Weaviate

**Diagnosis:**
```bash
# Check Weaviate pod
kubectl get pods -l app=weaviate
kubectl logs <weaviate-pod>

# Check service
kubectl get svc weaviate-service

# Test connection from AI-Assistant pod
kubectl exec -it <ai-assistant-pod> -- curl http://weaviate-service:80/v1/meta
```

**Solutions:**

1. **Service name mismatch:**
   - Verify `WEAVIATE_URL=http://weaviate-service:80` in ConfigMap
   - Check service name: `kubectl get svc`

2. **Network policy:**
   ```bash
   # Check network policies
   kubectl get networkpolicies
   ```

3. **Weaviate not ready:**
   ```bash
   # Wait for Weaviate
   kubectl wait --for=condition=ready pod -l app=weaviate --timeout=300s
   ```

### High Latency or Errors

**Symptoms**: Slow responses or intermittent failures

**Diagnosis:**
```bash
# Check pod metrics
kubectl top pods

# Check HPA
kubectl get hpa

# Check logs for errors
kubectl logs -l app=ai-assistant --tail=100
```

**Solutions:**

1. **Scale up:**
   ```bash
   # Manual scaling
   kubectl scale deployment ai-assistant --replicas=5
   
   # Or adjust HPA
   kubectl edit hpa ai-assistant-hpa
   ```

2. **Increase resources:**
   ```bash
   # Edit values.yaml
   resources:
     limits:
       cpu: 2000m
       memory: 4Gi
   
   # Upgrade release
   helm upgrade ai-assistant ./ai-assistant
   ```

3. **Check external APIs:**
   ```bash
   # Test from pod
   kubectl exec -it <ai-assistant-pod> -- \
     curl https://speech.googleapis.com/
   ```

## 🔗 Related Documentation

- [Terraform Documentation](terraform.md) - Infrastructure provisioning
- [AI-Assistant Documentation](ai-assistant.md) - Backend server
- [Weaviate Documentation](weaviate.md) - Vector database
