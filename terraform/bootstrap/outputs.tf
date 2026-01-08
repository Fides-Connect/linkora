output "bucket_name" {
  description = "Name of the Terraform state bucket"
  value       = google_storage_bucket.terraform_state.name
}

output "bucket_url" {
  description = "URL of the Terraform state bucket"
  value       = google_storage_bucket.terraform_state.url
}
