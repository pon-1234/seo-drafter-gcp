output "drafts_bucket_name" {
  description = "Name of the GCS bucket for drafts"
  value       = google_storage_bucket.drafts.name
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.seo_drafter.dataset_id
}

output "workflow_name" {
  description = "Cloud Workflows workflow name"
  value       = google_workflows_workflow.draft_generation.name
}

output "api_service_account" {
  description = "API service account email"
  value       = google_service_account.api.email
}

output "worker_service_account" {
  description = "Worker service account email"
  value       = google_service_account.worker.email
}

output "workflow_service_account" {
  description = "Workflow service account email"
  value       = google_service_account.workflow.email
}

output "pubsub_topics" {
  description = "Pub/Sub topic names"
  value = {
    draft_generation = google_pubsub_topic.draft_generation_events.name
    quality_check    = google_pubsub_topic.quality_check_events.name
  }
}

output "tasks_queue_name" {
  description = "Cloud Tasks queue name"
  value       = google_cloud_tasks_queue.draft_retry_queue.name
}
