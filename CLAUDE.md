# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SEO Drafter GCP is a monorepo implementing an MVP for automated SEO article research, outline generation, and draft creation using Google Cloud Platform services. The system orchestrates UI (Next.js), API/Backend (FastAPI), Worker (FastAPI), Cloud Workflows, Firestore, Cloud Storage, BigQuery, and Vertex AI.

## Architecture

This is a microservices architecture with the following components:

- **UI (Next.js)**: Cloud Run service providing brief input forms, prompt management, persona studio, preview, and quality check pages
- **Backend (FastAPI)**: Cloud Run API service handling job creation, prompt versioning, persona generation, and draft management. Integrates with Firestore, GCS, Workflows, and Vertex AI
- **Worker (FastAPI)**: Cloud Run service executing the draft generation pipeline (intent estimation → outline → draft → FAQ/Meta/Links → quality evaluation)
- **Cloud Workflows**: Orchestrates the pipeline by calling Worker then Backend's internal endpoint in sequence

### Data Flow

1. UI → `POST /api/jobs` → Backend creates job in Firestore
2. Backend → Triggers Cloud Workflows execution
3. Workflows → `POST /run-pipeline` → Worker (generates draft)
4. Workflows → `POST /internal/drafts` → Backend (persists to GCS, updates Firestore)
5. UI → `GET /api/drafts/{id}` → Backend (preview/approval)

### Key Services

- **FirestoreRepository** (`backend/app/services/firestore.py`): Manages jobs, prompts, and drafts with in-memory fallback for local development
- **DraftStorage** (`backend/app/services/gcs.py`): Handles GCS artifact storage (outline.json, draft.md, meta.json, quality.json)
- **QualityEngine** (`backend/app/services/quality.py`): Performs YMYL detection, citation validation, style checks
- **VertexGateway** (`backend/app/services/vertex.py`): Interfaces with Vertex AI for persona generation and content grounding
- **DraftGenerationPipeline** (`worker/app/tasks/pipeline.py`): Executes the sequential draft generation steps

## Development Commands

### Backend (FastAPI API)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Run tests
pytest tests/
```

### Worker (FastAPI Pipeline)
```bash
cd worker
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8090

# Run tests
pytest tests/
```

### UI (Next.js)
```bash
cd ui
npm install
npm run dev        # Development server
npm run build      # Production build
npm start          # Production server
```

## Testing

```bash
# Backend tests (includes API integration, Vertex AI, BigQuery)
cd backend && pytest tests/

# Worker tests (includes pipeline end-to-end tests)
cd worker && pytest tests/
```

## Environment Variables

### Backend
- `GCP_PROJECT`: GCP project ID (optional for local dev, falls back to in-memory)
- `DRAFTS_BUCKET`: GCS bucket name for artifacts
- `FIRESTORE_NAMESPACE`: Optional Firestore namespace prefix
- `DEFAULT_PROMPT_VERSION`: Default prompt version to use
- `WORKFLOW_NAME`: Name of the Cloud Workflows workflow
- `WORKFLOW_LOCATION`: GCP region for Workflows

### UI
- `NEXT_PUBLIC_API_BASE_URL`: Backend API URL (e.g., `http://localhost:8080`)

## Firestore Schema

Collections follow this pattern:
- `jobs/{jobId}`: Contains `status`, `prompt_version`, `workflow_execution_id`, `seed`, `draft_id`
- `prompts/{promptId}`: Contains `versions.{version}` with System/Developer/User templates
- `drafts/{draftId}`: Contains GCS paths, quality metrics, approval audit logs

## Local Development Notes

- All services use **in-memory fallbacks** when GCP SDKs are unavailable, allowing development without GCP credentials
- FirestoreRepository automatically switches to dict-based storage if `google-cloud-firestore` is not installed
- DraftStorage uses local filesystem when GCS client is unavailable
- The workflow launcher skips execution in local mode

## Deployment

### Quick Start
```bash
# 1. Initialize GCP resources
./scripts/setup-gcp.sh

# 2. Deploy infrastructure with Terraform
cd terraform
terraform init
terraform apply

# 3. Deploy all services
cd ..
./scripts/deploy.sh
```

### Individual Service Deployment
```bash
# Deploy specific services
./scripts/deploy.sh --services backend
./scripts/deploy.sh --services worker
./scripts/deploy.sh --services ui

# Skip building Docker images (use existing)
./scripts/deploy.sh --skip-build
```

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Implemented Features

### Vertex AI Google Search Grounding
- **Location**: `backend/app/services/vertex.py` - `generate_with_grounding()` method
- Generates content with automatic citation from Google Search results
- Used in Worker pipeline for section and FAQ generation
- Returns text with grounding metadata and citation URIs

### BigQuery Vector Search
- **Location**: `backend/app/services/bigquery.py` - `InternalLinkRepository` class
- Performs semantic similarity search using ML.GENERATE_EMBEDDING and ML.DISTANCE
- Vector search query combines keyword and persona goals for better relevance
- Fallback to text-based search when vector search is unavailable
- `store_article_embedding()` method for indexing new articles

### Internal Link Recommendations
- **Pipeline Integration**: `worker/app/tasks/pipeline.py` - `propose_links()` method
- Calls BigQuery Vector Search to find related articles
- Results include URL, title, recommended anchor text, similarity score, and snippet
- **API Response**: `backend/app/api/routes.py` - includes `internal_links` in DraftBundle
- **UI Display**: `ui/app/preview/page.tsx` - dedicated section showing internal link candidates

### Infrastructure as Code
- **Terraform**: `terraform/main.tf` provisions all GCP resources
  - BigQuery dataset and tables (article_embeddings, articles)
  - GCS bucket with versioning and lifecycle rules
  - Pub/Sub topics (draft-generation-events, quality-check-events)
  - Cloud Tasks queue (draft-retry-queue) with retry configuration
  - Service accounts with least-privilege IAM bindings
  - Cloud Workflows deployment
- **Setup Script**: `scripts/setup-gcp.sh` for initial API enablement and resource creation
- **Deploy Script**: `scripts/deploy.sh` for automated Cloud Run deployment

### Testing
- **Backend Tests**:
  - `backend/tests/test_api_integration.py` - Full API endpoint coverage
  - `backend/tests/test_vertex.py` - Vertex AI service unit tests
  - `backend/tests/test_bigquery.py` - BigQuery repository tests
- **Worker Tests**:
  - `worker/tests/test_pipeline.py` - End-to-end pipeline tests
  - Intent estimation, outline generation, quality evaluation

## Future Extensions

- Cloud Tasks/PubSub step-by-step retry implementation
- Secret Manager integration for API keys and style guides
- Cloud Monitoring dashboards and alerting policies
- CI/CD pipeline with Cloud Build triggers
- Custom domain and Cloud CDN configuration
- VPC Service Controls for enhanced security
