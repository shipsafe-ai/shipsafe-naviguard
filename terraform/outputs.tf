output "naviguard_url" {
  description = "NaviGuard Cloud Run service URL"
  value       = google_cloud_run_v2_service.naviguard.uri
}

output "service_account_email" {
  description = "NaviGuard service account email"
  value       = google_service_account.naviguard.email
}
