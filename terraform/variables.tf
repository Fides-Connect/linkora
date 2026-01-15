variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "gen-lang-client-0859968110"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west3"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "fides-production"
}
