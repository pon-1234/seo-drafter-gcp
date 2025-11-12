from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from ..core.config import get_settings
from ..models import (
    APIError,
    BenchmarkRun,
    DraftApproveRequest,
    DraftBundle,
    DraftListItem,
    DraftListResponse,
    DraftPersistenceRequest,
    Job,
    JobCreate,
    JobFailureReport,
    JobStatus,
    PersonaDeriveRequest,
    PersonaDeriveResponse,
    PersonaTemplate,
    PersonaTemplateCreate,
    PersonaTemplateUpdate,
    PromptVersion,
    PromptVersionCreate,
    RewriteRequest,
    RewriteResponse,
    WriterPersona,
    QualityKpiResponse,
)
from ..services.firestore import FirestoreRepository
from ..services.gcs import DraftStorage
from ..services.quality import QualityEngine
from ..services.workflow import WorkflowLauncher
from ..services.benchmark import BenchmarkService
from ..services.project_settings import load_project_settings
from shared.style import NG_PHRASES, ABSTRACT_PATTERNS

try:
    from ..services.openai_gateway import OpenAIGateway
except ImportError:
    OpenAIGateway = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter()


def get_firestore() -> FirestoreRepository:
    return FirestoreRepository()


def get_ai_gateway():
    """Instantiate the OpenAI gateway or raise if unavailable."""
    if not OpenAIGateway:
        logger.error("OpenAI gateway implementation is not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI support is not available",
        )

    settings = get_settings()
    provider = (settings.llm_provider or "openai").lower()
    if provider not in {"openai", "anthropic"}:
        logger.warning("Unsupported LLM provider '%s', falling back to openai", provider)
        provider = "openai"
    model = settings.openai_model if provider == "openai" else settings.anthropic_model or settings.openai_model

    try:
        return OpenAIGateway(
            api_key=settings.openai_api_key,
            model=model,
            provider=provider,
            anthropic_api_key=settings.anthropic_api_key,
        )
    except Exception as exc:
        logger.error("OpenAI initialization failed: %s (type: %s)", str(exc), type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI initialization failed. Check configuration.",
        )


def get_storage() -> DraftStorage:
    return DraftStorage()


def get_workflow() -> WorkflowLauncher:
    return WorkflowLauncher()


def get_quality_engine() -> QualityEngine:
    return QualityEngine()


@router.post("/api/prompts", response_model=PromptVersion, responses={400: {"model": APIError}})
def create_prompt_version(
    payload: PromptVersionCreate,
    store: FirestoreRepository = Depends(get_firestore),
) -> PromptVersion:
    logger.info("Creating prompt version %s for %s", payload.version, payload.prompt_id)
    return store.create_prompt_version(payload)


@router.get("/api/prompts/{prompt_id}", response_model=PromptVersion, responses={404: {"model": APIError}})
def get_prompt_version(
    prompt_id: str,
    version: Optional[str] = None,
    store: FirestoreRepository = Depends(get_firestore),
):
    prompt = store.get_prompt_version(prompt_id, version)
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt version not found")
    return prompt


@router.post("/api/persona/derive", response_model=PersonaDeriveResponse)
def derive_persona(
    payload: PersonaDeriveRequest,
    ai_gateway=Depends(get_ai_gateway),
) -> PersonaDeriveResponse:
    persona = ai_gateway.generate_persona(payload)
    search_terms = [payload.primary_keyword, *payload.supporting_keywords]
    return PersonaDeriveResponse(persona=persona, provenance_search_terms=search_terms)


@router.get("/api/persona/templates", response_model=List[PersonaTemplate])
def list_persona_templates(store: FirestoreRepository = Depends(get_firestore)) -> List[PersonaTemplate]:
    """Return registered persona templates for the project."""
    return store.list_persona_templates()


@router.post("/api/persona/templates", response_model=PersonaTemplate, responses={400: {"model": APIError}})
def create_persona_template(
    payload: PersonaTemplateCreate,
    store: FirestoreRepository = Depends(get_firestore),
) -> PersonaTemplate:
    try:
        return store.create_persona_template(payload)
    except ValueError as exc:
        if str(exc) == "template_exists":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template with the same id already exists",
            ) from exc
        raise


@router.put("/api/persona/templates/{template_id}", response_model=PersonaTemplate, responses={404: {"model": APIError}})
def update_persona_template(
    template_id: str,
    payload: PersonaTemplateUpdate,
    store: FirestoreRepository = Depends(get_firestore),
) -> PersonaTemplate:
    template = store.update_persona_template(template_id, payload)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.delete("/api/persona/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona_template(
    template_id: str,
    store: FirestoreRepository = Depends(get_firestore),
) -> None:
    deleted = store.delete_persona_template(template_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


@router.post("/api/jobs", response_model=Job, responses={400: {"model": APIError}})
def create_job(
    payload: JobCreate,
    store: FirestoreRepository = Depends(get_firestore),
    workflow: WorkflowLauncher = Depends(get_workflow),
    ai_gateway=Depends(get_ai_gateway),
) -> Job:
    job_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    logger.info("Creating job %s", job_id)

    settings = get_settings()
    project_defaults = load_project_settings(settings.project_id)

    default_writer_payload = project_defaults.get("writer_persona", {})
    writer_persona = payload.writer_persona or (
        WriterPersona(**default_writer_payload) if default_writer_payload else None
    )
    preferred_sources = payload.preferred_sources or project_defaults.get("preferred_sources", [])
    reference_media = payload.reference_media or project_defaults.get("reference_media", [])

    resolved_payload_dict = payload.model_dump()
    if writer_persona:
        resolved_payload_dict["writer_persona"] = writer_persona.model_dump()
    else:
        resolved_payload_dict["writer_persona"] = None
    resolved_payload_dict["preferred_sources"] = preferred_sources
    resolved_payload_dict["reference_media"] = reference_media

    resolved_payload = JobCreate(**resolved_payload_dict)

    job = store.create_job(job_id, resolved_payload, draft_id=draft_id)

    persona = payload.persona_override or ai_gateway.generate_persona(
        PersonaDeriveRequest(
            primary_keyword=payload.primary_keyword,
            supporting_keywords=payload.supporting_keywords,
            article_type=payload.article_type,
            intended_cta=payload.intended_cta,
            persona_brief=payload.persona_brief,
        )
    )

    launch_payload = {
        "job_id": job_id,
        "project_id": settings.project_id,
        "prompt_version": payload.prompt_version or get_settings().default_prompt_version,
        "primary_keyword": payload.primary_keyword,
        "supporting_keywords": payload.supporting_keywords,
        "intent": payload.intent,
        "word_count_range": payload.word_count_range,
        "prohibited_claims": payload.prohibited_claims,
        "style_guide_id": payload.style_guide_id,
        "existing_article_ids": payload.existing_article_ids,
        "article_type": payload.article_type,
        "intended_cta": payload.intended_cta,
        "persona_brief": payload.persona_brief.model_dump() if payload.persona_brief else None,
        "notation_guidelines": payload.notation_guidelines,
        "heading_directive": payload.heading_directive.model_dump(),
        "reference_urls": payload.reference_urls,
        "output_format": payload.output_format,
        "quality_rubric": payload.quality_rubric,
        "persona": persona.model_dump(),
        "writer_persona": resolved_payload_dict.get("writer_persona"),
        "preferred_sources": preferred_sources,
        "reference_media": reference_media,
        "project_template_id": resolved_payload_dict.get("project_template_id"),
        "expertise_level": payload.expertise_level.value,
        "tone": payload.tone.value,
    }
    if payload.llm:
        launch_payload["llm"] = payload.llm.model_dump(exclude_none=True)
    if payload.benchmark_plan:
        launch_payload["benchmark_plan"] = [cfg.model_dump(exclude_none=True) for cfg in payload.benchmark_plan]
    execution_id = workflow.launch(job_id, launch_payload)
    if execution_id:
        job = store.update_job(job_id, workflow_execution_id=execution_id, status=JobStatus.running) or job
    return job


@router.post("/api/benchmarks/run", response_model=BenchmarkRun, responses={400: {"model": APIError}})
def run_benchmark(
    payload: JobCreate,
    store: FirestoreRepository = Depends(get_firestore),
    ai_gateway=Depends(get_ai_gateway),
) -> BenchmarkRun:
    if not payload.benchmark_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="benchmark_plan must contain at least one LLM configuration",
        )

    settings = get_settings()
    project_defaults = load_project_settings(settings.project_id)

    default_writer_payload = project_defaults.get("writer_persona", {})
    writer_persona = payload.writer_persona or (
        WriterPersona(**default_writer_payload) if default_writer_payload else None
    )
    preferred_sources = payload.preferred_sources or project_defaults.get("preferred_sources", [])
    reference_media = payload.reference_media or project_defaults.get("reference_media", [])

    persona = payload.persona_override or ai_gateway.generate_persona(
        PersonaDeriveRequest(
            primary_keyword=payload.primary_keyword,
            supporting_keywords=payload.supporting_keywords,
            article_type=payload.article_type,
            intended_cta=payload.intended_cta,
            persona_brief=payload.persona_brief,
        )
    )

    resolved_payload_dict = payload.model_dump()
    resolved_payload_dict["writer_persona"] = writer_persona.model_dump() if writer_persona else None
    resolved_payload_dict["preferred_sources"] = preferred_sources
    resolved_payload_dict["reference_media"] = reference_media

    resolved_payload = JobCreate(**resolved_payload_dict)

    benchmark_service = BenchmarkService(store)
    result = benchmark_service.run(
        resolved_payload,
        persona=persona,
        writer_persona=writer_persona,
    )
    return result


@router.get("/api/benchmarks", response_model=List[BenchmarkRun])
def list_benchmarks(limit: int = 20, store: FirestoreRepository = Depends(get_firestore)) -> List[BenchmarkRun]:
    runs = []
    for item in store.list_benchmark_runs(limit=limit):
        try:
            runs.append(BenchmarkRun(**item))
        except ValidationError:
            logger.warning("Skipping malformed benchmark entry: %s", item.get("id"))
    return runs


@router.post("/api/tools/rewrite", response_model=RewriteResponse, responses={400: {"model": APIError}})
def rewrite_text(
    payload: RewriteRequest,
    ai_gateway=Depends(get_ai_gateway),
) -> RewriteResponse:
    settings = get_settings()
    gateway = ai_gateway

    if payload.llm:
        llm_cfg = payload.llm
        provider_value = getattr(llm_cfg.provider, "value", llm_cfg.provider)
        provider = str(provider_value).lower()
        if provider not in {"openai", "anthropic"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported LLM provider")
        model = llm_cfg.model or (settings.openai_model if provider == "openai" else settings.anthropic_model)
        gateway = OpenAIGateway(
            api_key=settings.openai_api_key,
            model=model,
            provider=provider,
            anthropic_api_key=settings.anthropic_api_key,
        )

    system_message = (
        "あなたは編集者です。以下の文章を指示に従ってリライトしてください。"
        "誇張・あいまいな表現を排除し、根拠が不明瞭な部分は条件付きの表現に変更します。"
        "事実関係は維持しつつ読みやすく整形し、必要であれば文を分割または補足してください。"
    )
    user_message = f"指示: {payload.instruction}\n---\n原文:\n{payload.text}"

    try:
        result = gateway.generate_with_grounding(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=800,
        )
    except Exception as exc:  # pragma: no cover - depends on external API
        logger.exception("Rewrite generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rewrite generation failed") from exc

    rewritten = (result.get("text") or "").strip()
    detected_ng = [phrase for phrase in NG_PHRASES if phrase and phrase in rewritten]
    detected_abstract = [phrase for phrase in ABSTRACT_PATTERNS if phrase and phrase in rewritten]

    return RewriteResponse(
        rewritten_text=rewritten,
        detected_ng_phrases=detected_ng,
        detected_abstract_phrases=detected_abstract,
    )


@router.get("/api/jobs/{job_id}", response_model=Job, responses={404: {"model": APIError}})
def get_job(job_id: str, store: FirestoreRepository = Depends(get_firestore)) -> Job:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/api/drafts", response_model=DraftListResponse)
def list_drafts(
    limit: int = 50,
    store: FirestoreRepository = Depends(get_firestore),
) -> DraftListResponse:
    """List all drafts ordered by creation time."""
    jobs = store.list_jobs(limit=limit)
    draft_items = []

    for job in jobs:
        if not job.draft_id:
            continue

        draft_item = DraftListItem(
            draft_id=job.draft_id,
            job_id=job.id,
            status=job.status.value if hasattr(job.status, 'value') else str(job.status),
            created_at=job.created_at.isoformat() if job.created_at else None,
            article_type=job.payload.article_type if job.payload else None,
            primary_keyword=job.payload.primary_keyword if job.payload else None,
            title=f"{job.payload.primary_keyword} {job.payload.article_type}ガイド" if job.payload else None,
        )
        draft_items.append(draft_item)

    return DraftListResponse(drafts=draft_items, total=len(draft_items))


@router.get("/api/drafts/{draft_id}", response_model=DraftBundle, responses={404: {"model": APIError}})
def get_draft(
    draft_id: str,
    store: DraftStorage = Depends(get_storage),
    quality: QualityEngine = Depends(get_quality_engine),
    firestore_repo: FirestoreRepository = Depends(get_firestore),
) -> DraftBundle:
    import json

    # List artifacts from GCS or local store
    artifacts = store.list_artifacts(draft_id)

    # Find the job to retrieve generation parameters
    matching_job = None
    if not artifacts:
        try:
            # Try to find job where draft_id matches
            jobs = firestore_repo.list_jobs(limit=100)
            matching_job = next((j for j in jobs if j.draft_id == draft_id), None)
            if matching_job:
                # Try with job_id
                artifacts = store.list_artifacts(matching_job.id)
                if artifacts:
                    logger.info("Found draft using job_id %s for draft_id %s", matching_job.id, draft_id)
        except Exception as e:
            logger.warning("Failed to lookup job for draft_id %s: %s", draft_id, e)
    else:
        # Artifacts found, now try to find the job for metadata
        try:
            jobs = firestore_repo.list_jobs(limit=100)
            matching_job = next((j for j in jobs if j.draft_id == draft_id), None)
        except Exception as e:
            logger.warning("Failed to lookup job metadata for draft_id %s: %s", draft_id, e)

    if not artifacts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    # Read quality, links, and draft content
    quality_payload = {}
    links_payload = []
    draft_content = None

    for filename, full_path in artifacts.items():
        if filename == "quality.json":
            data = store.read_artifact(full_path)
            if data:
                try:
                    quality_payload = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Quality payload for %s is not valid JSON", draft_id)
        elif filename == "links.json":
            data = store.read_artifact(full_path)
            if data:
                try:
                    links_data = json.loads(data)
                    links_payload = links_data.get("suggestions", [])
                except json.JSONDecodeError:
                    logger.warning("Links payload for %s is not valid JSON", draft_id)
        elif filename == "draft.md":
            draft_content = store.read_artifact(full_path)

    # Build paths dict and signed URLs
    paths = artifacts
    signed_urls = {}
    for key, path_value in paths.items():
        url = store.get_signed_url(path_value)
        # Only include HTTP/HTTPS URLs, not gs:// paths
        if url and (url.startswith('http://') or url.startswith('https://')):
            signed_urls[key] = url

    # Build metadata with generation parameters
    metadata = {"status": "preview"}
    if matching_job and matching_job.payload:
        payload = matching_job.payload
        # Build metadata dict, excluding None values
        metadata_updates = {
            "job_id": matching_job.id,
            "primary_keyword": payload.primary_keyword,
            "expertise_level": payload.expertise_level.value if hasattr(payload.expertise_level, 'value') else str(payload.expertise_level),
            "tone": payload.tone.value if hasattr(payload.tone, 'value') else str(payload.tone),
            "article_type": payload.article_type.value if hasattr(payload.article_type, 'value') else str(payload.article_type),
            "output_format": payload.output_format.value if hasattr(payload.output_format, 'value') else str(payload.output_format),
        }

        # Add optional fields only if they are not None
        if matching_job.created_at:
            metadata_updates["created_at"] = matching_job.created_at.isoformat()
        if payload.word_count_range:
            metadata_updates["word_count_range"] = payload.word_count_range
        if payload.prompt_version:
            metadata_updates["prompt_version"] = payload.prompt_version
        if payload.intended_cta:
            metadata_updates["intended_cta"] = payload.intended_cta
        if payload.quality_rubric:
            metadata_updates["quality_rubric"] = payload.quality_rubric
        if payload.llm:
            if hasattr(payload.llm.provider, 'value'):
                metadata_updates["llm_provider"] = payload.llm.provider.value
            if payload.llm.model:
                metadata_updates["llm_model"] = payload.llm.model

        metadata.update(metadata_updates)

    return quality.bundle(
        draft_id=draft_id,
        paths=paths,
        metadata=metadata,
        draft_content=quality_payload,
        signed_urls=signed_urls or None,
        internal_links=links_payload,
        draft_text=draft_content,
    )


@router.post("/internal/drafts", response_model=DraftBundle)
def persist_draft(
    payload: DraftPersistenceRequest,
    store: DraftStorage = Depends(get_storage),
    firestore_repo: FirestoreRepository = Depends(get_firestore),
    quality: QualityEngine = Depends(get_quality_engine),
) -> DraftBundle:
    if not payload.payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing draft payload")

    outputs = payload.payload
    draft_id = payload.draft_id or str(uuid.uuid4())
    outline = outputs.get("outline", {})
    draft = outputs.get("draft", {})
    meta = outputs.get("meta", {})
    links = outputs.get("links", [])
    quality_snapshot = outputs.get("quality", {})

    outline_path = store.save_artifact(draft_id, "outline.json", outline)
    draft_md = _render_markdown(draft)
    draft_path = store.save_raw(draft_id, "draft.md", draft_md)
    meta_path = store.save_artifact(draft_id, "meta.json", meta)
    links_path = store.save_artifact(draft_id, "links.json", {"suggestions": links})
    quality_path = store.save_artifact(draft_id, "quality.json", quality_snapshot)

    firestore_repo.update_job(
        payload.job_id,
        status=JobStatus.completed,
        error_message=None,
        error_detail=None,
    )
    firestore_repo.record_quality_snapshot(
        {
            "draft_id": draft_id,
            "job_id": payload.job_id,
            "created_at": datetime.utcnow().isoformat(),
            "duplication_score": quality_snapshot.get("similarity"),
            "citation_count": quality_snapshot.get("citation_count"),
            "numeric_facts": quality_snapshot.get("numeric_facts"),
            "ng_hits": quality_snapshot.get("ng_phrases", []),
            "abstract_hits": quality_snapshot.get("abstract_phrases", []),
            "style_violations": quality_snapshot.get("style_violations", []),
        }
    )

    paths = {
        "outline": outline_path,
        "draft": draft_path,
        "meta": meta_path,
        "links": links_path,
        "quality": quality_path,
    }
    signed_urls = {}
    for key, path_value in paths.items():
        url = store.get_signed_url(path_value)
        # Only include HTTP/HTTPS URLs, not gs:// paths
        if url and (url.startswith('http://') or url.startswith('https://')):
            signed_urls[key] = url
    bundle = quality.bundle(
        draft_id=draft_id,
        paths=paths,
        metadata={"job_id": payload.job_id, "draft_id": draft_id, "status": "generated"},
        draft_content=quality_snapshot,
        signed_urls=signed_urls or None,
        internal_links=links,
    )
    return bundle


@router.post("/internal/jobs/{job_id}/fail", response_model=Job, responses={404: {"model": APIError}})
def mark_job_failed(
    job_id: str,
    payload: Optional[JobFailureReport] = None,
    store: FirestoreRepository = Depends(get_firestore),
) -> Job:
    """Mark a job as failed when downstream processing aborts."""
    body = payload or JobFailureReport()
    job = store.update_job(
        job_id,
        status=JobStatus.failed,
        error_message=body.reason,
        error_detail=body.detail,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _render_markdown(draft: dict) -> str:
    payload: dict = {}
    if isinstance(draft, dict):
        if "sections" in draft or "faq" in draft:
            payload = draft
        elif isinstance(draft.get("draft"), dict):
            payload = draft.get("draft", {})
    sections = payload.get("sections", []) if isinstance(payload, dict) else []
    faq_items = payload.get("faq", []) if isinstance(payload, dict) else []
    lines = ["# 生成ドラフト"]
    for section in sections:
        lines.append(f"## {section.get('h2', '')}")
        for paragraph in section.get("paragraphs", []):
            heading = paragraph.get("heading")
            if heading:
                lines.append(f"### {heading}")
            lines.append(paragraph.get("text", ""))
            citations = paragraph.get("citations", [])
            if citations:
                lines.append("根拠: " + ", ".join(citations))
            lines.append("")
    if faq_items:
        lines.append("## FAQ")
        for item in faq_items:
            lines.append(f"### {item.get('question', '')}")
            lines.append(item.get("answer", ""))
            lines.append("")
    return "\n".join(lines)


@router.post("/api/drafts/{draft_id}/approve", response_model=DraftBundle)
def approve_draft(
    draft_id: str,
    payload: DraftApproveRequest,
    store: DraftStorage = Depends(get_storage),
    quality: QualityEngine = Depends(get_quality_engine),
) -> DraftBundle:
    logger.info("Draft %s approved by %s", draft_id, payload.approved_by)
    local = store.get_local(draft_id)
    if not local:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    import json

    quality_payload = {}
    for path_key, data in local.items():
        if path_key.endswith("quality.json"):
            try:
                quality_payload = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("Quality payload for %s is not valid JSON", draft_id)
            break
    metadata = {"status": "approved", "approved_by": payload.approved_by}
    if payload.notes:
        metadata["notes"] = payload.notes
    paths = {k: k for k in local.keys()}
    signed_urls = {}
    for key, path_value in paths.items():
        url = store.get_signed_url(path_value)
        # Only include HTTP/HTTPS URLs, not gs:// paths
        if url and (url.startswith('http://') or url.startswith('https://')):
            signed_urls[key] = url
    return quality.bundle(draft_id, paths, metadata, quality_payload, signed_urls=signed_urls or None)


@router.post("/internal/jobs/cleanup-stale")
def cleanup_stale_jobs(
    timeout_minutes: int = 30,
    store: FirestoreRepository = Depends(get_firestore),
) -> dict:
    """Mark jobs that have been running for too long as failed.

    Args:
        timeout_minutes: Jobs running longer than this will be marked as failed (default: 30 minutes)
    """
    from datetime import datetime, timedelta

    cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    jobs = store.list_jobs(limit=100)

    stale_jobs = []
    for job in jobs:
        if job.status == JobStatus.running and job.updated_at and job.updated_at < cutoff_time:
            stale_jobs.append({
                "job_id": job.id,
                "updated_at": job.updated_at.isoformat(),
                "age_minutes": (datetime.utcnow() - job.updated_at).total_seconds() / 60
            })
            logger.warning("Marking stale job %s as failed (age: %.1f minutes)",
                         job.id, (datetime.utcnow() - job.updated_at).total_seconds() / 60)
            store.update_job(
                job.id,
                status=JobStatus.failed,
                error_message="job_timeout",
                error_detail={
                    "note": f"Job exceeded timeout of {timeout_minutes} minutes",
                    "cleanup_timestamp": datetime.utcnow().isoformat()
                }
            )

    return {
        "cleaned_up": len(stale_jobs),
        "timeout_minutes": timeout_minutes,
        "stale_jobs": stale_jobs
    }


@router.get("/api/analytics/quality-kpis", response_model=QualityKpiResponse)
def get_quality_kpis(limit: int = 100, store: FirestoreRepository = Depends(get_firestore)) -> QualityKpiResponse:
    snapshots = store.list_quality_snapshots(limit=limit)
    if not snapshots:
        return QualityKpiResponse(
            sample_size=0,
            avg_duplication=0.0,
            avg_citation_count=0.0,
            avg_numeric_facts=0.0,
            ng_phrase_rate=0.0,
            abstract_phrase_rate=0.0,
        )

    sample = len(snapshots)
    avg_duplication = sum(float(snapshot.get("duplication_score") or 0.0) for snapshot in snapshots) / sample
    avg_citation_count = sum(int(snapshot.get("citation_count") or 0) for snapshot in snapshots) / sample
    avg_numeric_facts = sum(int(snapshot.get("numeric_facts") or 0) for snapshot in snapshots) / sample
    ng_phrase_rate = sum(1 for snapshot in snapshots if snapshot.get("ng_hits")) / sample
    abstract_phrase_rate = sum(1 for snapshot in snapshots if snapshot.get("abstract_hits")) / sample

    return QualityKpiResponse(
        sample_size=sample,
        avg_duplication=avg_duplication,
        avg_citation_count=avg_citation_count,
        avg_numeric_facts=avg_numeric_facts,
        ng_phrase_rate=ng_phrase_rate,
        abstract_phrase_rate=abstract_phrase_rate,
    )
