# Cloud Deployment

This document describes how to provision and maintain the production infrastructure on Google Cloud.

## Architecture

```
Flutter App (ConnectX)
        │ WebRTC / WebSocket
        ▼
┌─────────────────────────────────┐
│  Cloud Run: ai-assistant        │  europe-west3  ~$20-50/mo
│  • Scales 1–3 instances         │
│  • Workload Identity (no keys)  │
│  • Secrets via Secret Manager   │
└────────────────┬────────────────┘
                 │ HTTP :8080
                 ▼
┌─────────────────────────────────┐
│  Compute Engine: weaviate-vm    │  europe-west3-a  ~$29/mo
│  e2-medium (2 vCPU, 4 GB RAM)   │
│  Docker Compose:                │
│  • Weaviate 1.32.2              │
│  • text2vec-model2vec (embed.)  │
│  Persistent disk → data safe    │
└─────────────────────────────────┘
```

**Estimated monthly cost**: ~$50–80 (Cloud Run scales to zero when idle).  
**Migration path**: change `WEAVIATE_URL` to point at Weaviate Cloud — nothing else required.

---

## Prerequisites

```bash
# Install gcloud CLI
brew install google-cloud-sdk  # macOS

# Authenticate
gcloud auth login
gcloud config set project <PROJECT_ID>
```

Enable required APIs:
```bash
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com
```

---

## One-time Setup

### 1. Artifact Registry repository

```bash
gcloud artifacts repositories create ai-assistant \
  --repository-format=docker \
  --location=europe-west3 \
  --description="AI-Assistant container images"
```

### 2. Service accounts

**CI service account** (builds images, deploys):
```bash
gcloud iam service-accounts create fides-ci \
  --display-name="Fides CI/CD"

# Allow Cloud Run deploys
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-ci@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Allow pushing to Artifact Registry
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-ci@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Allow SSH into Compute Engine VM
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-ci@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/compute.osLogin"

# Allow deploying with runtime SA
gcloud iam service-accounts add-iam-policy-binding \
  fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com \
  --member="serviceAccount:fides-ci@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

**Runtime service account** (used by Cloud Run at runtime):
```bash
gcloud iam service-accounts create fides-runtime \
  --display-name="Fides Runtime"

# GCP APIs: Speech-to-Text, TTS, Firestore, Firebase Admin
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/cloudmicroservices.serviceAgent"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/speech.client"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/texttospeech.client"

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

# Allow reading secrets
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Workload Identity Federation (GitHub Actions → GCP, no keys)

```bash
# Create WIF pool
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Create OIDC provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

POOL_ID=$(gcloud iam workload-identity-pools describe "github-pool" \
  --location="global" --format="value(name)")

# Bind CI SA to the WIF pool (scoped to this repo)
gcloud iam service-accounts add-iam-policy-binding \
  fides-ci@<PROJECT_ID>.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/Fides-Connect/Fides"

# Print the provider resource name (needed for GitHub secret WIF_PROVIDER)
gcloud iam workload-identity-pools providers describe "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
```

### 4. Secrets in Secret Manager

```bash
# Gemini API key
echo -n "<your-gemini-api-key>" | \
  gcloud secrets create gemini-api-key --data-file=-

# Admin secret key (used for admin API endpoints)
echo -n "<your-admin-secret-key>" | \
  gcloud secrets create admin-secret-key --data-file=-
```

### 5. Weaviate VM

```bash
gcloud compute instances create weaviate-vm \
  --zone=europe-west3-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-balanced \
  --tags=weaviate-server \
  --metadata-from-file startup-script=weaviate/startup-script.sh

# Allow AI-Assistant (Cloud Run) to reach Weaviate on port 8080.
# NOTE: For production, restrict source ranges to your Cloud Run egress IPs
# or set up a Serverless VPC Access connector instead.
gcloud compute firewall-rules create allow-weaviate \
  --network=default \
  --action=allow \
  --rules=tcp:8080,tcp:50051 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=weaviate-server \
  --description="Weaviate API access (restrict source IPs for production)"

# Get the VM's internal IP for WEAVIATE_VM_IP secret
gcloud compute instances describe weaviate-vm \
  --zone=europe-west3-a \
  --format="value(networkInterfaces[0].networkIP)"
```

Wait ~3 minutes for the startup script to finish, then verify:
```bash
VM_EXTERNAL_IP=$(gcloud compute instances describe weaviate-vm \
  --zone=europe-west3-a --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
curl http://$VM_EXTERNAL_IP:8080/v1/.well-known/ready
```

### 6. Initialize Weaviate schema

```bash
# Port-forward locally for the init script
gcloud compute ssh weaviate-vm --zone=europe-west3-a -- \
  -L 8090:localhost:8080 -N &
SSH_PID=$!
sleep 3

cd ai-assistant
WEAVIATE_URL=http://localhost:8090 python scripts/init_database.py --load-test-data

kill $SSH_PID
```

---

## GitHub Secrets

Add these in **Settings → Secrets and variables → Actions**:

| Secret | Where to get it |
|---|---|
| `GCP_PROJECT_ID` | `gcloud config get-value project` |
| `WIF_PROVIDER` | Output of WIF provider describe command above |
| `WIF_CI_SERVICE_ACCOUNT` | `fides-ci@<PROJECT_ID>.iam.gserviceaccount.com` |
| `WIF_RT_SERVICE_ACCOUNT` | `fides-runtime@<PROJECT_ID>.iam.gserviceaccount.com` |
| `WEAVIATE_VM_NAME` | `weaviate-vm` |
| `WEAVIATE_VM_ZONE` | `europe-west3-a` |
| `WEAVIATE_VM_IP` | Internal IP from step 5 above |

`GEMINI_API_KEY` and `ADMIN_SECRET_KEY` are stored in **Secret Manager** (not GitHub secrets) and injected by Cloud Run at runtime via `--set-secrets`.

---

## CI/CD Pipeline

```
Push to main branch
        │
        ├── ai-assistant/** changed?
        │       │
        │       ▼
        │  [ai-assistant-test.yml]
        │  unit tests → integration tests
        │       │ (on success)
        │       ▼
        │  [cloud-deploy.yml] deploy-ai-assistant
        │  build image → push to Artifact Registry → gcloud run deploy
        │
        └── weaviate/** changed?
                │
                ▼
           [cloud-deploy.yml] deploy-weaviate
           gcloud compute scp docker-compose.yml
           gcloud compute ssh → docker compose up -d
```

---

## Manual Operations

### Redeploy AI-Assistant without a code change

```bash
# Trigger a new Cloud Run revision with the latest image
gcloud run deploy ai-assistant \
  --image europe-west3-docker.pkg.dev/<PROJECT_ID>/ai-assistant/ai-assistant:latest \
  --region europe-west3
```

### SSH into Weaviate VM

```bash
gcloud compute ssh weaviate-vm --zone=europe-west3-a
# Inside VM:
cd /opt/weaviate
docker compose ps
docker compose logs -f weaviate
```

### Backup Weaviate data

```bash
gcloud compute ssh weaviate-vm --zone=europe-west3-a -- \
  "docker exec weaviate /bin/sh -c 'weaviate-backup create --id backup-\$(date +%Y%m%d)'"
```

---

## Migrating Weaviate to Weaviate Cloud

1. Export data from the VM (or let Weaviate Cloud re-index from source data).
2. Create a cluster on [Weaviate Cloud](https://console.weaviate.cloud).
3. Run `scripts/init_database.py` pointing at the new cluster URL.
4. Update the `WEAVIATE_VM_IP` GitHub secret to the Weaviate Cloud hostname:
   ```
   WEAVIATE_URL = "https://your-cluster.weaviate.network"
   ```
5. Redeploy AI-Assistant (see above).
6. Shut down the VM:
   ```bash
   gcloud compute instances delete weaviate-vm --zone=europe-west3-a
   ```

No code changes are needed — only the `WEAVIATE_URL` environment variable changes.
