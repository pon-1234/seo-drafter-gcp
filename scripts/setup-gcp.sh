#!/bin/bash
set -e

# GCP Project Configuration
PROJECT_ID="seo-drafter-gcp"
PROJECT_NUMBER="468719745959"
REGION="asia-northeast1"
ZONE="asia-northeast1-a"

echo "Setting up GCP project: $PROJECT_ID"

# Set default project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "Enabling required GCP APIs..."
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  workflows.googleapis.com \
  cloudtasks.googleapis.com \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com

# Create service accounts
echo "Creating service accounts..."

# Backend API service account
gcloud iam service-accounts create seo-drafter-api \
  --display-name="SEO Drafter API Service Account" \
  --description="Service account for SEO Drafter Backend API" || true

# Worker service account
gcloud iam service-accounts create seo-drafter-worker \
  --display-name="SEO Drafter Worker Service Account" \
  --description="Service account for SEO Drafter Worker" || true

# Workflow service account
gcloud iam service-accounts create seo-drafter-workflow \
  --display-name="SEO Drafter Workflow Service Account" \
  --description="Service account for Cloud Workflows" || true

# Grant permissions to Backend API service account
echo "Granting permissions to Backend API service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/workflows.invoker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant permissions to Worker service account
echo "Granting permissions to Worker service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant permissions to Workflow service account
echo "Granting permissions to Workflow service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-workflow@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:seo-drafter-workflow@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"

# Create GCS bucket for drafts
echo "Creating GCS bucket for drafts..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://${PROJECT_ID}-drafts || true
gsutil uniformbucketlevelaccess set on gs://${PROJECT_ID}-drafts

# Create Firestore database (if not exists)
echo "Setting up Firestore..."
gcloud firestore databases create --location=$REGION --type=firestore-native || true

# Create BigQuery dataset for vector search
echo "Creating BigQuery dataset..."
bq --location=$REGION mk -d \
  --description "SEO Drafter vector embeddings and internal links" \
  seo_drafter || true

# Create Artifact Registry repository
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create seo-drafter \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker repository for SEO Drafter services" || true

# Create Pub/Sub topics
echo "Creating Pub/Sub topics..."
gcloud pubsub topics create draft-generation-events || true
gcloud pubsub topics create quality-check-events || true

# Create Cloud Tasks queue
echo "Creating Cloud Tasks queue..."
gcloud tasks queues create draft-retry-queue \
  --location=$REGION \
  --max-attempts=5 \
  --max-concurrent-dispatches=10 \
  --max-retry-duration=3600s || true

echo "GCP setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Run terraform init && terraform apply in terraform/ directory"
echo "2. Build and deploy services using scripts/deploy.sh"
echo "3. Configure environment variables in .env files"
