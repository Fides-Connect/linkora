# Helm Charts

Kubernetes deployment charts for the Fides AI Assistant platform.

## 📁 Contents

- **`ai-assistant/`** - AI Assistant WebRTC server deployment
- **`weaviate/`** - Weaviate vector database deployment

## 🚀 Deployment

Deployment to GKE is automated via GitHub Actions. When changes are merged to `main`, the workflow:

1. Builds and pushes Docker images to GCR
2. Deploys Weaviate using `helm/weaviate`
3. Deploys AI Assistant using `helm/ai-assistant`

See [.github/workflows/cloud-deploy.yml](../.github/workflows/cloud-deploy.yml) for the complete CI/CD pipeline.

## 🔐 Required Secrets

The following GitHub repository secrets must be configured:

- `GOOGLE_SERVICE_ACCOUNT_JSON` - GCP service account with GKE/GCR permissions
- `GEMINI_API_KEY` - Google Gemini API key
- `GOOGLE_OAUTH_CLIENT_ID` - OAuth client ID for authentication
- `ADMIN_SECRET_KEY` - Admin interface authentication key

## 📚 Related Documentation

- [AI Assistant README](../ai-assistant/README.md)
- [Weaviate README](../weaviate/README.md)
- [Terraform README](../terraform/README.md)