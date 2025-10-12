terraform {
  required_version = ">= 1.5"
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

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "workflows.googleapis.com",
    "cloudtasks.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# GCS Bucket for Drafts
resource "google_storage_bucket" "drafts" {
  name                        = "${var.project_id}-drafts"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# BigQuery Dataset
resource "google_bigquery_dataset" "seo_drafter" {
  dataset_id  = "seo_drafter"
  location    = var.region
  description = "SEO Drafter vector embeddings and internal links"

  labels = {
    environment = var.environment
  }
}

# BigQuery Tables
resource "google_bigquery_table" "article_embeddings" {
  dataset_id = google_bigquery_dataset.seo_drafter.dataset_id
  table_id   = "article_embeddings"

  schema = jsonencode([
    {
      name = "article_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "url"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "title"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "snippet"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "content"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "metadata"
      type = "JSON"
      mode = "NULLABLE"
    },
    {
      name        = "embedding"
      type        = "FLOAT64"
      mode        = "REPEATED"
      description = "Vector embedding for similarity search"
    },
    {
      name = "published"
      type = "BOOL"
      mode = "REQUIRED"
    },
    {
      name = "created_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "updated_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    }
  ])

  deletion_protection = true
}

resource "google_bigquery_table" "articles" {
  dataset_id = google_bigquery_dataset.seo_drafter.dataset_id
  table_id   = "articles"

  schema = jsonencode([
    {
      name = "article_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "url"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "title"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "snippet"
      type = "STRING"
      mode = "NULLABLE"
    },
    {
      name = "published"
      type = "BOOL"
      mode = "REQUIRED"
    },
    {
      name = "updated_at"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    }
  ])

  deletion_protection = true
}

# Pub/Sub Topics
resource "google_pubsub_topic" "draft_generation_events" {
  name = "draft-generation-events"

  labels = {
    environment = var.environment
  }
}

resource "google_pubsub_topic" "quality_check_events" {
  name = "quality-check-events"

  labels = {
    environment = var.environment
  }
}

# Cloud Tasks Queue
resource "google_cloud_tasks_queue" "draft_retry_queue" {
  name     = "draft-retry-queue"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 5
  }

  retry_config {
    max_attempts       = 5
    max_retry_duration = "3600s"
    max_backoff        = "300s"
    min_backoff        = "10s"
  }
}

# Service Accounts
resource "google_service_account" "api" {
  account_id   = "seo-drafter-api"
  display_name = "SEO Drafter API Service Account"
  description  = "Service account for SEO Drafter Backend API"
}

resource "google_service_account" "worker" {
  account_id   = "seo-drafter-worker"
  display_name = "SEO Drafter Worker Service Account"
  description  = "Service account for SEO Drafter Worker"
}

resource "google_service_account" "workflow" {
  account_id   = "seo-drafter-workflow"
  display_name = "SEO Drafter Workflow Service Account"
  description  = "Service account for Cloud Workflows"
}

# IAM Bindings for API Service Account
resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_workflows" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_bigquery_data" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_bigquery_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# IAM Bindings for Worker Service Account
resource "google_project_iam_member" "worker_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_bigquery_data" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_bigquery_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

# IAM Bindings for Workflow Service Account
resource "google_project_iam_member" "workflow_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

resource "google_project_iam_member" "workflow_tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

# Cloud Workflows
resource "google_workflows_workflow" "draft_generation" {
  name            = "draft-generation"
  region          = var.region
  description     = "Orchestrates draft generation pipeline"
  service_account = google_service_account.workflow.email
  source_contents = file("${path.module}/../workflows/draft_generation.yaml")

  depends_on = [
    google_project_service.required_apis
  ]
}
