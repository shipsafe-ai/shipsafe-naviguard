variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run"
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "Container image URL (gcr.io/PROJECT/naviguard:TAG)"
  type        = string
}
