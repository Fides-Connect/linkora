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
  iamcredentials.googleapis.com \
  speech.googleapis.com \
  texttospeech.googleapis.com
```

---

## One-time Setup

### 1. Artifact Registry repository

```bash
gcloud artifacts repositories create ai-assistant-dev \
  --repository-format=docker \
  --location=europe-west3 \
  --description="AI-Assistant container images"
```

### 2. Service accounts

**CI service account** — use the existing account `linkora-ci-service-account-dev@linkora-dev.iam.gserviceaccount.com`.

Grant it the required roles:
```bash
CI_SA="linkora-ci-service-account-dev@linkora-dev.iam.gserviceaccount.com"

# Allow Cloud Run deploys
gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${CI_SA}" \
  --role="roles/run.admin"

# Allow pushing to Artifact Registry
gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${CI_SA}" \
  --role="roles/artifactregistry.writer"

# Allow scp/ssh to Compute Engine VM (includes setMetadata, get, osLogin)
gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${CI_SA}" \
  --role="roles/compute.instanceAdmin.v1"

# Allow CI SA to impersonate default Compute Engine service account
# (required for adding SSH keys to VM instance metadata)
PROJECT_NUMBER=$(gcloud projects describe linkora-dev --format="value(projectNumber)")
gcloud iam service-accounts add-iam-policy-binding \
  ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
  --member="serviceAccount:${CI_SA}" \
  --role="roles/iam.serviceAccountUser"

# Allow deploying with runtime SA
gcloud iam service-accounts add-iam-policy-binding \
  linkora-rt-service-account-dev@linkora-dev.iam.gserviceaccount.com \
  --member="serviceAccount:${CI_SA}" \
  --role="roles/iam.serviceAccountUser"
```

**Runtime service account** — use the existing account `linkora-rt-service-account-dev@linkora-dev.iam.gserviceaccount.com`.

Grant it the required roles:
```bash
RT_SA="linkora-rt-service-account-dev@linkora-dev.iam.gserviceaccount.com"

# GCP APIs: Speech-to-Text, TTS, Firestore, Firebase Admin
gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${RT_SA}" \
  --role="roles/speech.client"

gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${RT_SA}" \
  --role="roles/texttospeech.client"

gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${RT_SA}" \
  --role="roles/datastore.user"

# Allow reading secrets
gcloud projects add-iam-policy-binding linkora-dev \
  --member="serviceAccount:${RT_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Workload Identity Federation (GitHub Actions → GCP, no keys)

The WIF pool `linkora-identity-pool-dev`, OIDC provider `linkora-github-provider-dev`, and CI SA binding are all already configured. Retrieve the provider resource name for the GitHub secret:

```bash
# Print the provider resource name (needed for GitHub secret WIF_PROVIDER)
gcloud iam workload-identity-pools providers describe "linkora-github-provider-dev" \
  --location="global" \
  --workload-identity-pool="linkora-identity-pool-dev" \
  --format="value(name)"
```

### 4. Secrets in Secret Manager

No manual setup needed. Add `GEMINI_API_KEY` and `ADMIN_SECRET_KEY` to **GitHub Actions secrets** (see table below) and the deployment workflow will automatically create or update the corresponding Secret Manager secrets on every deploy.

### 5. Weaviate VM

```bash
gcloud compute instances create weaviate-vm-dev \
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
gcloud compute instances describe weaviate-vm-dev \
  --zone=europe-west3-a \
  --format="value(networkInterfaces[0].networkIP)"
```

Wait ~3 minutes for the startup script to finish, then verify:
```bash
VM_EXTERNAL_IP=$(gcloud compute instances describe weaviate-vm-dev \
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
| `WIF_CI_SERVICE_ACCOUNT` | `linkora-ci-service-account-dev@linkora-dev.iam.gserviceaccount.com` |
| `WIF_RT_SERVICE_ACCOUNT` | `linkora-rt-service-account-dev@linkora-dev.iam.gserviceaccount.com` |
| `WEAVIATE_VM_NAME` | `weaviate-vm` |
| `WEAVIATE_VM_ZONE` | `europe-west3-a` |
| `WEAVIATE_VM_IP` | Internal IP from step 5 above |
| `GEMINI_API_KEY` | Your Gemini API key |
| `ADMIN_SECRET_KEY` | Your admin API secret |

The deployment workflow syncs `GEMINI_API_KEY` and `ADMIN_SECRET_KEY` into **Secret Manager** automatically. Cloud Run then injects them at runtime via `--set-secrets` (never in environment variables).

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
