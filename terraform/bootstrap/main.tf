# Bootstrap Terraform State Bucket
# Run this first to create the GCS bucket for Terraform state
# Usage: cd terraform/bootstrap && terraform init && terraform apply

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# GCS bucket for Terraform state
resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id}-tfstate"
  location      = var.region
  force_destroy = false
  
  uniform_bucket_level_access = true
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    condition {
      num_newer_versions = 3
    }
    action {
      type = "Delete"
    }
  }
}
