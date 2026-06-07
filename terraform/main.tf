terraform {
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

resource "google_cloud_run_v2_service" "naviguard" {
  name     = "naviguard"
  location = var.region

  template {
    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "1"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "PHOENIX_PROJECT_NAME"
        value = "naviguard"
      }
      env {
        name  = "PHOENIX_BASE_URL"
        value = "https://app.phoenix.arize.com/s/prateek-srivastava23"
      }
      env {
        name = "PHOENIX_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "PHOENIX_API_KEY"
            version = "latest"
          }
        }
      }
      env {
        name = "PHOENIX_COLLECTOR_ENDPOINT"
        value_source {
          secret_key_ref {
            secret  = "PHOENIX_COLLECTOR_ENDPOINT"
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }

    service_account = google_service_account.naviguard.email
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

resource "google_service_account" "naviguard" {
  account_id   = "naviguard-sa"
  display_name = "NaviGuard Service Account"
}

resource "google_project_iam_member" "naviguard_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.naviguard.email}"
}

resource "google_project_iam_member" "naviguard_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.naviguard.email}"
}

resource "google_cloud_run_v2_service_iam_member" "naviguard_public" {
  location = google_cloud_run_v2_service.naviguard.location
  name     = google_cloud_run_v2_service.naviguard.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
