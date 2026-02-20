variable "project_id" {
  description = "GCP Project ID"
  type        = string
  # Set via terraform.tfvars or -var="project_id=<your-project-id>"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west3"
}
