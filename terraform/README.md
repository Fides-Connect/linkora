# Terraform README

This directory contains Terraform configuration for deploying the Fides infrastructure to Google Cloud Platform.

## Structure

- `bootstrap/` - Creates the GCS bucket for Terraform state (run this first)
- `main.tf` - Main infrastructure configuration (VPC, GKE cluster)
- `variables.tf` - Input variables
- `outputs.tf` - Output values

## Quick Start

1. **Create Terraform state bucket:**
   ```bash
   cd bootstrap
   terraform init
   terraform apply
   cd ..
   ```

2. **Deploy infrastructure:**
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

3. **Get outputs:**
   ```bash
   terraform output
   ```

## Resources Created

- Google Compute Network (VPC)
- Google Compute Subnetwork with secondary IP ranges
- GKE Autopilot Cluster
- Firewall rules

## Variables

- `project_id`: GCP project ID (default: gen-lang-client-0859968110)
- `region`: GCP region (default: europe-west3)
- `cluster_name`: GKE cluster name (default: fides-production)

## Notes

- GKE Autopilot is used for automated cluster management
- Cluster is in `europe-west3` (Frankfurt) for low latency to Germany
- State is stored in GCS bucket for team collaboration
