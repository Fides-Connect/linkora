# Helm Charts

This directory contains Helm charts for deploying Fides components to Kubernetes.

## Charts

### ai-assistant
Deploys the Fides AI Assistant application.

**Features:**
- Configurable resources and replicas
- Environment variables via ConfigMap
- Secrets management for sensitive data
- LoadBalancer service for external access
- Liveness and readiness probes

**Install:**
```bash
helm install ai-assistant ./ai-assistant \
  --set image.tag=latest \
  --set secrets.gcpServiceAccount="$(cat service-account.json)" \
  --set secrets.geminiApiKey="YOUR_KEY" \
  --set secrets.googleOauthClientId="YOUR_CLIENT_ID" \
  --set secrets.adminSecretKey="YOUR_SECRET"
```

### weaviate
Deploys Weaviate vector database.

**Features:**
- Self-hosted Weaviate instance
- Ephemeral storage (configurable)
- ClusterIP service for internal access
- Health checks

**Install:**
```bash
helm install weaviate ./weaviate
```

## Usage

### List releases
```bash
helm list
```

### Upgrade release
```bash
helm upgrade ai-assistant ./ai-assistant --set image.tag=v1.2.3
```

### Uninstall release
```bash
helm uninstall ai-assistant
```

### View values
```bash
helm show values ./ai-assistant
```

## Customization

Edit `values.yaml` in each chart directory to customize:
- Resource limits
- Replica count
- Environment variables
- Service type
- Image repository and tags
