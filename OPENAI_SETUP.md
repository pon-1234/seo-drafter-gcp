# OpenAI API Integration Setup

This guide explains how to configure the SEO Drafter to use OpenAI API instead of Vertex AI.

## Overview

The system now supports two AI providers:
- **OpenAI** (default): Uses GPT-4o for content generation
- **Vertex AI**: Uses Gemini models for content generation

## Configuration

### Environment Variables

Set these environment variables in your Cloud Run services or local `.env` file:

```bash
AI_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o  # or gpt-4-turbo, gpt-3.5-turbo
```

### Local Development

1. Copy the example environment file:
```bash
cp worker/.env.example worker/.env
cp backend/.env.example backend/.env
```

2. Edit the `.env` files and add your OpenAI API key:
```bash
OPENAI_API_KEY=sk-proj-...
```

3. Start the services:
```bash
cd backend && uvicorn app.main:app --reload --port 8080
cd worker && uvicorn app.main:app --reload --port 8090
```

### Cloud Run Deployment

Set environment variables for deployed services:

```bash
# Worker service
gcloud run services update seo-drafter-worker \
  --region=asia-northeast1 \
  --set-env-vars="OPENAI_API_KEY=sk-proj-...,AI_PROVIDER=openai"

# Backend service
gcloud run services update seo-drafter-api \
  --region=asia-northeast1 \
  --set-env-vars="OPENAI_API_KEY=sk-proj-...,AI_PROVIDER=openai"
```

## Features

### Content Generation
- Uses OpenAI's Chat Completions API
- Supports temperature control for creative vs factual content
- Extracts citations from generated content

### Persona Generation
- Creates target persona descriptions
- Used in both backend and worker services

### Fallback Behavior
- If OpenAI initialization fails, automatically falls back to Vertex AI
- Graceful error handling with detailed logging

## API Usage

The OpenAI gateway (`backend/app/services/openai_gateway.py`) provides:

- `generate_with_grounding()`: Generate content with citation extraction
- `generate_persona()`: Generate persona descriptions

## Switching Between Providers

To switch back to Vertex AI:
```bash
AI_PROVIDER=vertex
```

Or remove the `AI_PROVIDER` environment variable to use OpenAI (default).

## Troubleshooting

### OpenAI API Key Not Found
Error: `ValueError: OpenAI API key is required`

Solution: Set `OPENAI_API_KEY` environment variable

### Module Import Error
Error: `ImportError: openai package is required`

Solution: Install dependencies
```bash
pip install -r requirements.txt
```

### Rate Limiting
OpenAI has rate limits. If you hit limits:
- Upgrade your OpenAI plan
- Add retry logic (future enhancement)
- Switch to Vertex AI temporarily

## Cost Considerations

- GPT-4o: ~$5-15 per 1M tokens (input/output)
- GPT-4-turbo: ~$10-30 per 1M tokens
- GPT-3.5-turbo: ~$0.5-1.5 per 1M tokens

Estimate: ~500-2000 tokens per article section
- Full article (5 sections): ~2500-10000 tokens
- Cost per article: $0.01-0.30 (GPT-4o)

## Security

**IMPORTANT**: Never commit API keys to git!

The `.env` files are gitignored. For production, consider:
- Google Cloud Secret Manager
- Environment-specific configurations
- Key rotation policies
