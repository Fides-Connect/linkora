# GKE Deployment Guide

This guide will help you deploy the Fides AI Assistant and Weaviate to Google Kubernetes Engine (GKE) using Terraform and Helm.

## Prerequisites

- Google Cloud Platform account with a project (`gen-lang-client-0859968110`)
- `gcloud` CLI installed and configured
- `terraform` installed (>= 1.0)
- `kubectl` installed
- `helm` installed (>= 3.0)
- GitHub repository with Actions enabled

## Architecture

- **Infrastructure**: GKE Autopilot cluster in `europe-west3` (Frankfurt)
- **Networking**: Custom VPC with private GKE cluster
- **Container Registry**: Google Container Registry (GCR)
- **Deployment**: Helm charts for ai-assistant and Weaviate
- **CI/CD**: GitHub Actions for automated deployments

## Setup Instructions

### 1. Initial Setup - Create Terraform State Bucket

First, create the GCS bucket to store Terraform state:

```bash
cd terraform/bootstrap
terraform init
terraform plan
terraform apply
```

This creates the bucket: `gen-lang-client-0859968110-tfstate`

### 2. Deploy Infrastructure with Terraform

Deploy the VPC and GKE cluster:

```bash
cd ../  # Back to terraform/ directory
terraform init
terraform plan
terraform apply
```

This will create:
- VPC network (`fides-production-vpc`)
- Subnet with secondary ranges for pods and services
- GKE Autopilot cluster (`fides-production`)
- Firewall rules

**Note**: GKE cluster creation takes ~10-15 minutes.

### 3. Configure kubectl

Get cluster credentials:

```bash
gcloud container clusters get-credentials fides-production \
  --region europe-west3 \
  --project gen-lang-client-0859968110
```

Verify connection:

```bash
kubectl cluster-info
kubectl get nodes
```

### 4. Configure GitHub Secrets

Add the following secrets to your GitHub repository:
(Settings → Secrets and variables → Actions → New repository secret)

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON key | Download from GCP Console → IAM → Service Accounts |
| `GEMINI_API_KEY` | Google Gemini API key | From your `.env` file or GCP Console |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client ID | From your `.env` file or GCP Console |
| `ADMIN_SECRET_KEY` | Admin panel secret | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

**Service Account Permissions Required**:
- Kubernetes Engine Developer
- Storage Object Viewer (for GCR)
- Service Account User

### 5. Manual Deployment (Optional)

If you want to deploy manually before setting up CI/CD:

#### Deploy Weaviate:
```bash
helm upgrade --install weaviate ./helm/weaviate \
  --namespace default \
  --create-namespace \
  --wait
```

#### Build and push Docker image:
```bash
# Authenticate Docker with GCR
gcloud auth configure-docker

# Build image
docker build -f ai-assistant/Dockerfile -t gcr.io/gen-lang-client-0859968110/ai-assistant:latest ai-assistant/

# Push to GCR
docker push gcr.io/gen-lang-client-0859968110/ai-assistant:latest
```

#### Deploy AI Assistant:
```bash
helm upgrade --install ai-assistant ./helm/ai-assistant \
  --namespace default \
  --set image.tag=latest \
  --set secrets.gcpServiceAccount="$(cat path/to/service-account-key.json)" \
  --set secrets.geminiApiKey="YOUR_GEMINI_API_KEY" \
  --set secrets.googleOauthClientId="YOUR_OAUTH_CLIENT_ID" \
  --set secrets.adminSecretKey="YOUR_ADMIN_SECRET_KEY" \
  --wait
```

### 6. Automated Deployment via GitHub Actions

Once secrets are configured, every push to `main` branch with changes in `ai-assistant/` will trigger automatic deployment:

1. Build Docker image with commit SHA tag
2. Push to Google Container Registry
3. Deploy Weaviate (if not already deployed)
4. Deploy/upgrade AI Assistant with new image

Monitor deployment: **Actions** tab in GitHub repository

### 7. Access Your Application

Get the external LoadBalancer IP:

```bash
kubectl get service ai-assistant
```

The application will be available at:
```
http://<EXTERNAL_IP>:8080
```

**Note**: It may take a few minutes for the LoadBalancer IP to be assigned.

## Configuration

### Helm Values

Customize deployment by editing `helm/ai-assistant/values.yaml`:

- **Resources**: CPU/Memory limits
- **Replicas**: Number of pods (currently 1)
- **Environment variables**: Language, voice settings, etc.

### Terraform Variables

Customize infrastructure in `terraform/variables.tf`:

- **region**: Change GCP region
- **cluster_name**: Rename cluster

## Monitoring and Debugging

### View logs:
```bash
# AI Assistant logs
kubectl logs -l app.kubernetes.io/name=ai-assistant -f

# Weaviate logs
kubectl logs -l app.kubernetes.io/name=weaviate -f
```

### Check pod status:
```bash
kubectl get pods
kubectl describe pod <pod-name>
```

### Access pod shell:
```bash
kubectl exec -it <pod-name> -- /bin/bash
```

### View deployment status:
```bash
kubectl get deployments
kubectl get services
```

## Scaling

GKE Autopilot automatically manages node provisioning. To scale application replicas:

```bash
kubectl scale deployment ai-assistant --replicas=3
```

Or update `helm/ai-assistant/values.yaml` and redeploy.

## Cleanup

To destroy all infrastructure:

```bash
# Delete Kubernetes resources
helm uninstall ai-assistant
helm uninstall weaviate

# Destroy GKE cluster and VPC
cd terraform
terraform destroy

# Optionally, delete state bucket
cd bootstrap
terraform destroy
```

## Troubleshooting

### Pod fails to start
- Check logs: `kubectl logs <pod-name>`
- Verify secrets are correct
- Check resource limits

### Cannot connect to Weaviate
- Ensure Weaviate pod is running: `kubectl get pods`
- Check service: `kubectl get svc weaviate`
- Verify network connectivity inside pods

### LoadBalancer IP not assigned
- Wait 5-10 minutes
- Check GCP Console → VPC Network → Firewall rules
- Verify service type is LoadBalancer

### Image pull errors
- Verify GCR authentication: `gcloud auth configure-docker`
- Check image exists: `gcloud container images list`
- Verify service account has Container Registry permissions

## Next Steps

- **SSL/TLS**: Configure Ingress with cert-manager for HTTPS
- **Domain**: Point custom domain to LoadBalancer IP
- **Monitoring**: Set up Cloud Monitoring and logging
- **Persistence**: Enable persistent volumes for Weaviate data
- **Autoscaling**: Configure Horizontal Pod Autoscaler (HPA)
- **Staging Environment**: Duplicate setup for staging

## Support

For issues or questions:
1. Check logs with `kubectl logs`
2. Review GitHub Actions workflow logs
3. Verify all secrets are correctly set
4. Check GCP IAM permissions
