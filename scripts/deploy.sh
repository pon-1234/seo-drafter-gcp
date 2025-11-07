#!/bin/bash
set -e

# GCP Configuration
PROJECT_ID="seo-drafter-gcp"
REGION="asia-northeast1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/seo-drafter"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$ROOT_DIR"

echo "=== SEO Drafter Deployment Script ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Root: $ROOT_DIR"
echo ""

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
  echo "Error: Not authenticated with gcloud. Run: gcloud auth login"
  exit 1
fi

# Set project
gcloud config set project $PROJECT_ID

# Function to build and push Docker image
build_and_push() {
  local service=$1
  local tag="${REGISTRY}/${service}:latest"

  echo "Building $service..."
  docker buildx build \
    --platform linux/amd64 \
    --tag "$tag" \
    --file "$service/Dockerfile" \
    --push \
    "$ROOT_DIR"
  
  echo "✓ $service image pushed: $tag"
}

# Function to deploy Cloud Run service
deploy_cloud_run() {
  local service=$1
  local image=$2
  local service_account=$3
  local env_vars=$4
  local allow_unauthenticated=${5:-"--no-allow-unauthenticated"}
  local timeout=${6:-300}

  echo "Deploying $service to Cloud Run..."

  gcloud run deploy $service \
    --image=$image \
    --region=$REGION \
    --platform=managed \
    --service-account=$service_account \
    --set-env-vars="$env_vars" \
    --memory=1Gi \
    --cpu=1 \
    --timeout=$timeout \
    --max-instances=10 \
    $allow_unauthenticated

  echo "✓ $service deployed successfully"
}

ensure_openai_credentials() {
  if [[ -n "$OPENAI_API_KEY" ]]; then
    return
  fi

  if [[ "$SERVICES" != *"backend"* && "$SERVICES" != *"worker"* ]]; then
    return
  fi

  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: OPENAI_API_KEY is not set and jq is not installed to reuse it from existing services." >&2
    exit 1
  fi

  local existing_key=""
  local services_to_check=("seo-drafter-api" "seo-drafter-worker")
  for svc in "${services_to_check[@]}"; do
    local describe_output
    if describe_output=$(gcloud run services describe "$svc" --region="$REGION" --format=json 2>/dev/null); then
      existing_key=$(echo "$describe_output" | jq -r '.spec.template.spec.containers[0].env[] | select(.name=="OPENAI_API_KEY").value' | head -n1)
      if [[ -n "$existing_key" && "$existing_key" != "null" ]]; then
        OPENAI_API_KEY="$existing_key"
        echo "Reusing OpenAI API key from existing $svc deployment."
        return
      fi
    fi
  done

  echo "Error: OPENAI_API_KEY is not set. Export OPENAI_API_KEY before running deploy.sh." >&2
  exit 1
}

# Parse command line arguments
SKIP_BUILD=false
SERVICES=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --services)
      SERVICES="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--skip-build] [--services backend,worker,ui]"
      exit 1
      ;;
  esac
done

# Default to all services if none specified
if [ -z "$SERVICES" ]; then
  SERVICES="backend,worker,ui"
fi

# Build and push Docker images
if [ "$SKIP_BUILD" = false ]; then
  echo "=== Building and pushing Docker images ==="

  IFS=',' read -ra SERVICE_ARRAY <<< "$SERVICES"
  for service in "${SERVICE_ARRAY[@]}"; do
    build_and_push $service
  done

  echo ""
fi

# Deploy services
echo "=== Deploying Cloud Run services ==="

if [[ "$SERVICES" == *"backend"* || "$SERVICES" == *"worker"* ]]; then
  ensure_openai_credentials
fi

# Get service URLs for environment variables
if [[ "$SERVICES" == *"backend"* ]]; then
  BACKEND_ENV="GCP_PROJECT=${PROJECT_ID},GCP_REGION=${REGION},DRAFTS_BUCKET=${PROJECT_ID}-drafts,BIGQUERY_DATASET=seo_drafter,WORKFLOW_NAME=draft-generation,WORKFLOW_LOCATION=${REGION},VERTEX_MODEL_PRO=gemini-1.5-pro-002,VERTEX_MODEL_FLASH=gemini-1.5-flash-002"
  if [[ -n "$OPENAI_API_KEY" ]]; then
    BACKEND_ENV+=",OPENAI_API_KEY=${OPENAI_API_KEY}"
  fi
  if [[ -n "$OPENAI_MODEL" ]]; then
    BACKEND_ENV+=",OPENAI_MODEL=${OPENAI_MODEL}"
  fi

  deploy_cloud_run \
    "seo-drafter-api" \
    "${REGISTRY}/backend:latest" \
    "seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
    "$BACKEND_ENV" \
    "--allow-unauthenticated" \
    300

  # Get backend URL
  BACKEND_URL=$(gcloud run services describe seo-drafter-api --region=$REGION --format='value(status.url)')
  echo "Backend URL: $BACKEND_URL"
fi

if [[ "$SERVICES" == *"worker"* ]]; then
  WORKER_ENV="GCP_PROJECT=${PROJECT_ID},GCP_REGION=${REGION},BIGQUERY_DATASET=seo_drafter,VERTEX_MODEL_PRO=gemini-1.5-pro-002,VERTEX_MODEL_FLASH=gemini-1.5-flash-002"
  if [[ -n "$OPENAI_API_KEY" ]]; then
    WORKER_ENV+=",OPENAI_API_KEY=${OPENAI_API_KEY}"
  fi
  if [[ -n "$OPENAI_MODEL" ]]; then
    WORKER_ENV+=",OPENAI_MODEL=${OPENAI_MODEL}"
  fi

  deploy_cloud_run \
    "seo-drafter-worker" \
    "${REGISTRY}/worker:latest" \
    "seo-drafter-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
    "$WORKER_ENV" \
    "--no-allow-unauthenticated" \
    600

  # Get worker URL
  WORKER_URL=$(gcloud run services describe seo-drafter-worker --region=$REGION --format='value(status.url)')
  echo "Worker URL: $WORKER_URL"
fi

if [[ "$SERVICES" == *"ui"* ]]; then
  # Use backend URL if available, otherwise use placeholder
  if [ -z "$BACKEND_URL" ]; then
    BACKEND_URL=$(gcloud run services describe seo-drafter-api --region=$REGION --format='value(status.url)' 2>/dev/null || echo "https://seo-drafter-api-REPLACE.run.app")
  fi

  UI_ENV="NEXT_PUBLIC_API_BASE_URL=${BACKEND_URL}"

  deploy_cloud_run \
    "seo-drafter-ui" \
    "${REGISTRY}/ui:latest" \
    "seo-drafter-api@${PROJECT_ID}.iam.gserviceaccount.com" \
    "$UI_ENV" \
    "--allow-unauthenticated" \
    300

  UI_URL=$(gcloud run services describe seo-drafter-ui --region=$REGION --format='value(status.url)')
  echo "UI URL: $UI_URL"
fi

echo ""
echo "=== Deployment Summary ==="
echo "✓ All services deployed successfully!"
echo ""
echo "Service URLs:"
if [[ "$SERVICES" == *"backend"* ]]; then
  echo "  Backend API: $BACKEND_URL"
fi
if [[ "$SERVICES" == *"worker"* ]]; then
  echo "  Worker: $WORKER_URL (internal)"
fi
if [[ "$SERVICES" == *"ui"* ]]; then
  echo "  UI: $UI_URL"
fi
echo ""
echo "Next steps:"
echo "1. Update Cloud Workflows environment variables if needed"
echo "2. Test the deployment with: curl $BACKEND_URL/healthz"
echo "3. Access the UI at: $UI_URL"
