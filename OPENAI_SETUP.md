# OpenAI API Integration Setup

This guide explains how to configure the SEO Drafter to use the OpenAI API.

## Overview

The system now standardizes on OpenAI for all AI-powered features.

## Configuration

### Environment Variables

Set these environment variables in your Cloud Run services or local `.env` file:

```bash
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5  # use gpt-5-mini for drafts / o4-mini for ultra-fast runs
# Optional Anthropics
ANTHROPIC_API_KEY=your-claude-api-key
ANTHROPIC_MODEL=claude-sonnet-4-5  # claude-sonnet-4-5-20250929 for pinned prod
```

### Recommended Models (2025)

**OpenAI**
- `gpt-5` — highest quality reasoning + long-form generation; use as the default for briefs, drafts, and QA checks.
- `gpt-5-mini` — cost-optimized sibling that excels at bulk outlining, ideation, and first-pass drafts.
- `o4-mini` — lightweight reasoning-forward model for rapid QC loops, structural rewrites, or assistant-style prompts.
- _Deprecation note_: `gpt-4o` / `gpt-4o-mini` are now treated as legacy. Plan migrations to the models above per the official Models & Deprecations page.

**Anthropic**
- `claude-sonnet-4-5` — balanced default. For production stability, pin to the latest snapshot (e.g., `claude-sonnet-4-5-20250929`).
- `claude-haiku-4-5` — fastest and lowest cost; ideal for high-volume outline/draft passes.
- `claude-opus-4-1` — strict reasoning + fact-checking when accuracy matters most.
- _Deprecation note_: `Claude 3.5 Sonnet (2024-06-20)` retired on 2025-10-28 and `Claude 3 Opus` is legacy.

Always confirm active SKUs via the official OpenAI Models/Deprecations and Anthropic Claude docs before rolling out workflow changes.

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
  --set-env-vars="OPENAI_API_KEY=sk-proj-..."

# Backend service
gcloud run services update seo-drafter-api \
  --region=asia-northeast1 \
  --set-env-vars="OPENAI_API_KEY=sk-proj-..."
```

## Features

### Content Generation
- Uses the shared `LLMGateway` abstraction (OpenAI GPT-5 family by default, Anthropic Claude when `LLM_PROVIDER=anthropic`)
- Supports temperature control for creative vs factual content
- Extracts citations from generated content

### Persona Generation
- Creates target persona descriptions with the same model set to keep tone consistent
- Used in both backend and worker services

## SEO Draft Workflow Tips

- **Two-stage generation:** create outline/structure with `gpt-5-mini` or `claude-haiku-4-5`, then promote winning drafts with `gpt-5` or `claude-sonnet-4-5` for factual polishing and tonality adjustments.
- **Style guardrails:** pin the editorial style guide in System/Developer messages and request headings, summaries, and FAQ blocks as JSON so the UI can parse outputs consistently.
- **Cost levers:** deduplicate long shared prompts so they can be cached. Anthropic Prompt Caching is supported out of the box and dramatically reduces spend on large system messages.

## API Usage

The provider-agnostic gateway (`shared/llm/gateway.py`) is instantiated by `backend/app/services/ai_gateway.py` and `worker/app/services/openai_gateway.py`. It surfaces:

- `generate_with_grounding()`: Generate content with citation extraction
- `generate_persona()`: Generate persona descriptions

### OpenAI Responses API (Python)

```python
from openai import OpenAI

client = OpenAI()
response = client.responses.create(
    model="gpt-5",  # swap to gpt-5-mini for drafts / o4-mini for fast checks
    input=[
        {"role": "system", "content": "You are an SEO lead writer. Output JSON with heading+FAQ."},
        {"role": "user", "content": "Primary keyword: サイトコントローラー おすすめ"},
    ],
    temperature=0.6,
    max_output_tokens=2000,
)
```

### Anthropic Messages API (Python)

```python
from anthropic import Anthropic

client = Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-5",  # pin claude-sonnet-4-5-20250929 for deterministic prod runs
    system="Follow the style guide from the developer message and cite sources as [Source: URL].",
    messages=[{"role": "user", "content": "ドラフト骨子とFAQをJSONで出してください。"}],
    max_tokens=2000,
    temperature=0.6,
)
```

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

## Cost Considerations

- **OpenAI:** `gpt-5` delivers the highest quality but also the highest unit price. `gpt-5-mini` reduces cost ~40-60% for outline/first drafts, and `o4-mini` is the cheapest when you only need structural rewrites or quick QC loops.
- **Anthropic:** `claude-opus-4-1` focuses on reasoning-heavy passes, `claude-sonnet-4-5` balances cost and quality for production drafts, and `claude-haiku-4-5` is the budget option for large batch briefs.
- **Prompt sizing:** expect 500–2,000 tokens per section. A five-section draft typically consumes 2,500–10,000 tokens before revisions. Multiply by the per-million-token price listed on each provider's Models/Pricing page to budget per article.
- **Caching:** cache shared system prompts (Anthropic Prompt Caching or OpenAI Reusable Prompts when available) so that only per-job deltas are billed.

## Security

**IMPORTANT**: Never commit API keys to git!

The `.env` files are gitignored. For production, consider:
- Google Cloud Secret Manager
- Environment-specific configurations
- Key rotation policies
