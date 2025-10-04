variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "seo-drafter-gcp"
}

variable "project_number" {
  description = "GCP Project Number"
  type        = string
  default     = "468719745959"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-northeast1"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}
