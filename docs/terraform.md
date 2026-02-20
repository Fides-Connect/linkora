# Terraform Infrastructure Documentation

This document covers infrastructure provisioning using Terraform for the Linkora AI Voice Assistant platform on Google Cloud Platform (GKE).

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Infrastructure Components](#infrastructure-components)
- [Directory Structure](#directory-structure)
- [Bootstrap Setup](#bootstrap-setup)
- [Main Infrastructure](#main-infrastructure)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [State Management](#state-management)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

The Linkora platform uses Terraform to provision and manage Google Cloud Platform (GKE) infrastructure, providing:
- **Infrastructure as Code**: Version-controlled, reproducible infrastructure
- **GKE Autopilot Cluster**: Managed Kubernetes with auto-scaling
- **Network Configuration**: Custom VPC with optimized pod/service ranges
- **State Management**: Remote backend in Google Cloud Storage
- **Firewall Rules**: Secure network access configuration

### Managed Resources

- GKE Autopilot Cluster: `fides-production`
- VPC Network: Custom network with pod/service IP ranges
- Firewall Rules: Health checks and load balancing
- GCS State Backend: `<PROJECT_ID>-tfstate`

## 📋 Prerequisites

### Required Tools

- **Terraform**: Version 1.0 or higher
- **gcloud CLI**: Google Cloud SDK
- **kubectl**: Kubernetes command-line tool

### Install Tools

```bash
# Install Terraform
brew install terraform  # macOS
# Or: https://www.terraform.io/downloads

# Install gcloud CLI
brew install google-cloud-sdk  # macOS
# Or: https://cloud.google.com/sdk/docs/install

# Install kubectl
brew install kubectl  # macOS
# Or: https://kubernetes.io/docs/tasks/tools/
```

### Google Cloud Setup

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set project
gcloud config set project <PROJECT_ID>

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable storage-api.googleapis.com
```

## 🏗️ Infrastructure Components

### GKE Autopilot Cluster

**Configuration:**
- **Name**: `fides-production`
- **Region**: `europe-west3` (Frankfurt)
- **Mode**: Autopilot (fully managed)
- **Network**: Custom VPC
- **Release Channel**: REGULAR (stable updates)

**Benefits of Autopilot:**
- ✅ Fully managed nodes (no node management)
- ✅ Auto-scaling based on workload
- ✅ Built-in security best practices
- ✅ Pay per pod (cost-optimized)
- ✅ Automatic updates and patches

### Network Configuration

**VPC Network:**
```hcl
resource "google_compute_network" "vpc" {
  name                    = "fides-vpc"
  auto_create_subnetworks = false
}
```

**Subnet:**
- **Region**: `europe-west3`
- **Primary CIDR**: `10.0.0.0/24` (node IPs)
- **Pod CIDR**: `10.1.0.0/16` (pod IPs)
- **Service CIDR**: `10.2.0.0/16` (service IPs)

**IP Allocation:**
- Nodes: 256 IPs (10.0.0.0/24)
- Pods: 65,536 IPs (10.1.0.0/16)
- Services: 65,536 IPs (10.2.0.0/16)

### Firewall Rules

**Health Check Rule:**
```hcl
# Allows Google Cloud health checkers
source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
target_tags   = ["gke-node"]
allow {
  protocol = "tcp"
  ports    = ["8080", "80", "443"]
}
```

## 📁 Directory Structure

```
terraform/
├── main.tf              # Main infrastructure definition
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── bootstrap/           # State backend setup
│   ├── main.tf         # GCS bucket creation
│   ├── variables.tf    # Bootstrap variables
│   └── outputs.tf      # Backend configuration
```

## 🚀 Bootstrap Setup

The bootstrap process creates the GCS bucket for Terraform state storage.

### Step 1: Navigate to Bootstrap Directory

```bash
cd terraform/bootstrap
```

### Step 2: Initialize Terraform

```bash
terraform init
```

### Step 3: Review Plan

```bash
terraform plan
```

**Resources to be created:**
- GCS bucket: `<PROJECT_ID>-tfstate`
- Bucket versioning: Enabled
- Bucket encryption: Google-managed

### Step 4: Apply Configuration

```bash
terraform apply

# Type 'yes' to confirm
```

### Step 5: Note Backend Configuration

The output will provide backend configuration:

```hcl
backend "gcs" {
  bucket = "<PROJECT_ID>-tfstate"
  prefix = "terraform/state"
}
```

## 🏗️ Main Infrastructure

### Step 1: Configure Backend

Add to `terraform/main.tf` (if not present):

```hcl
terraform {
  backend "gcs" {
    bucket = "<PROJECT_ID>-tfstate"
    prefix = "terraform/state"
  }
}
```

### Step 2: Initialize Terraform

```bash
cd terraform
terraform init
```

**This will:**
- Download required providers
- Configure remote state backend
- Prepare workspace for deployment

### Step 3: Review Configuration

Create `terraform.tfvars`:

```hcl
project_id   = "<PROJECT_ID>"
region       = "europe-west3"
cluster_name = "fides-production"
```

### Step 4: Plan Infrastructure

```bash
terraform plan
```

**Review the plan:**
- GKE Autopilot cluster
- VPC network and subnet
- Firewall rules
- IAM bindings

### Step 5: Apply Configuration

```bash
terraform apply

# Review changes
# Type 'yes' to confirm
```

**Deployment time**: 10-15 minutes

### Step 6: Verify Deployment

```bash
# Get cluster credentials
gcloud container clusters get-credentials fides-production \
  --region europe-west3

# Verify cluster
kubectl cluster-info
kubectl get nodes
```

## ⚙️ Configuration

### Variables

**File**: `terraform/variables.tf`

```hcl
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "<PROJECT_ID>"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west3"
}

variable "cluster_name" {
  description = "GKE Cluster Name"
  type        = string
  default     = "fides-production"
}

variable "environment" {
  description = "Environment (dev, staging, production)"
  type        = string
  default     = "production"
}
```

### Outputs

**File**: `terraform/outputs.tf`

```hcl
output "cluster_name" {
  description = "GKE Cluster Name"
  value       = google_container_cluster.primary.name
}

output "cluster_endpoint" {
  description = "GKE Cluster Endpoint"
  value       = google_container_cluster.primary.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Cluster CA Certificate"
  value       = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "region" {
  description = "GCP Region"
  value       = var.region
}
```

### Custom Configuration

**Override variables:**
```bash
terraform apply \
  -var="cluster_name=fides-staging" \
  -var="region=us-central1"
```

**Use custom tfvars file:**
```bash
terraform apply -var-file="staging.tfvars"
```

## 🔄 Deployment

### Initial Deployment

```bash
# Navigate to terraform directory
cd terraform

# Initialize (first time only)
terraform init

# Plan changes
terraform plan -out=tfplan

# Apply changes
terraform apply tfplan
```

### Update Infrastructure

```bash
# Make changes to .tf files

# Review changes
terraform plan

# Apply updates
terraform apply
```

### Destroy Infrastructure

```bash
# ⚠️ WARNING: This will delete all resources

terraform destroy

# Review resources to be destroyed
# Type 'yes' to confirm
```

### Targeted Updates

```bash
# Update only specific resource
terraform apply -target=google_container_cluster.primary

# Destroy specific resource
terraform destroy -target=google_compute_firewall.health_check
```

## 📊 State Management

### Remote State Backend

**Configuration:**
- **Backend**: Google Cloud Storage (GCS)
- **Bucket**: `<PROJECT_ID>-tfstate`
- **Prefix**: `terraform/state`
- **Encryption**: Google-managed keys
- **Versioning**: Enabled

### View State

```bash
# List resources in state
terraform state list

# Show specific resource
terraform state show google_container_cluster.primary

# Pull current state
terraform state pull > terraform.tfstate.backup
```

### State Operations

**Move resource:**
```bash
terraform state mv \
  google_compute_network.vpc \
  google_compute_network.new_vpc
```

**Remove resource from state:**
```bash
# Resource remains in GCP but removed from Terraform management
terraform state rm google_compute_firewall.old_rule
```

**Import existing resource:**
```bash
terraform import google_container_cluster.primary \
  projects/<PROJECT_ID>/locations/europe-west3/clusters/fides-production
```

### State Locking

GCS backend automatically provides state locking:
- Prevents concurrent modifications
- Uses GCS object metadata for locking
- Automatic lock release on completion

If lock is stuck:
```bash
# Force unlock (use with caution)
terraform force-unlock <lock-id>
```

## 🔐 Security Best Practices

### Service Account Permissions

**Minimum required roles:**
- `roles/compute.admin`: Network and firewall management
- `roles/container.admin`: GKE cluster management
- `roles/storage.admin`: State bucket access
- `roles/iam.serviceAccountUser`: Service account operations

### Secrets Management

**Never commit:**
- `terraform.tfvars` (add to `.gitignore`)
- `*.tfstate` files
- Service account keys (use Workload Identity Federation instead)

**Use environment variables:**
```bash
export TF_VAR_project_id="<PROJECT_ID>"
# Authenticate via WIF or user ADC rather than a key file:
gcloud auth application-default login
```

### Network Security

**Firewall rules:**
- Allow only necessary ports
- Restrict source IP ranges
- Use target tags for specificity

**Private GKE:**
For enhanced security, consider private GKE cluster:
```hcl
private_cluster_config {
  enable_private_nodes    = true
  enable_private_endpoint = false
  master_ipv4_cidr_block = "172.16.0.0/28"
}
```

## 🐛 Troubleshooting

### Terraform Init Fails

**Symptoms**: Backend initialization errors

**Solutions:**

1. **GCS bucket doesn't exist:**
   ```bash
   # Run bootstrap first
   cd bootstrap
   terraform init && terraform apply
   ```

2. **Insufficient permissions:**
   ```bash
   # Check current auth
   gcloud auth list
   
   # Re-authenticate
   gcloud auth application-default login
   ```

3. **Wrong project:**
   ```bash
   gcloud config set project <PROJECT_ID>
   ```

### Apply Fails

**Symptoms**: Resource creation errors

**Common Issues:**

1. **API not enabled:**
   ```bash
   gcloud services enable container.googleapis.com
   gcloud services enable compute.googleapis.com
   ```

2. **Quota exceeded:**
   ```bash
   # Check quotas
   gcloud compute project-info describe --project=<PROJECT_ID>
   
   # Request quota increase in GCP Console
   ```

3. **Resource already exists:**
   ```bash
   # Import existing resource
   terraform import google_container_cluster.primary \
     projects/PROJECT_ID/locations/REGION/clusters/CLUSTER_NAME
   ```

### State Lock Issues

**Symptoms**: "Error acquiring the state lock"

**Solutions:**

```bash
# Check lock status
gsutil ls -L gs://<PROJECT_ID>-tfstate/terraform/state/default.tflock

# Force unlock (if safe)
terraform force-unlock <lock-id>

# Remove stale lock manually
gsutil rm gs://<PROJECT_ID>-tfstate/terraform/state/default.tflock
```

### Cluster Access Issues

**Symptoms**: Can't connect to cluster after creation

**Solutions:**

```bash
# Get credentials
gcloud container clusters get-credentials fides-production \
  --region europe-west3 \
  --project <PROJECT_ID>

# Verify kubectl config
kubectl config current-context

# Test connection
kubectl cluster-info
```

## 📊 Cost Optimization

### GKE Autopilot Pricing

**Billing model**: Pay per pod CPU/memory usage

**Estimated costs:**
- Small workload (2 pods): ~$50/month
- Medium workload (5 pods): ~$120/month
- Large workload (10 pods): ~$240/month

**Cost-saving tips:**
1. **Right-size resources**: Don't over-provision pod requests
2. **Use HPA**: Auto-scale based on actual load
3. **Spot instances**: Use preemptible pods for non-critical workloads
4. **Monitoring**: Set up billing alerts

### Monitor Costs

```bash
# GCP billing report
gcloud billing accounts list

# Current month costs
gcloud billing accounts describe <account-id>

# Set up budget alert in GCP Console
```

## 🔄 CI/CD Integration

The Terraform infrastructure is managed separately from application deployment:

**Manual Changes:**
- Infrastructure changes via Terraform
- Requires manual `terraform apply`

**Workflow:**
1. Update Terraform configuration
2. Run `terraform plan` to review
3. Apply changes: `terraform apply`
4. Deploy applications via CI/CD

## 🔗 Related Documentation

- [Helm Documentation](helm.md) - Kubernetes deployment
- [Architecture Overview](architecture.md) - System design
- [Getting Started](getting-started.md) - Initial setup
