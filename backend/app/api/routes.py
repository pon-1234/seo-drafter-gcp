from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.config import get_settings
from ..models import (
    APIError,
    DraftApproveRequest,
    DraftBundle,
    DraftPersistenceRequest,
    Job,
    JobCreate,
    JobStatus,
    PersonaDeriveRequest,
    PersonaDeriveResponse,
    PromptVersion,
    PromptVersionCreate,
)
from ..services.firestore import FirestoreRepository
from ..services.gcs import DraftStorage
from ..services.quality import QualityEngine
from ..services.vertex import VertexGateway
from ..services.workflow import WorkflowLauncher

logger = logging.getLogger(__name__)

router = APIRouter()


def get_firestore() -> FirestoreRepository:
    return FirestoreRepository()


def get_vertex() -> VertexGateway:
    return VertexGateway()


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
    vertex: VertexGateway = Depends(get_vertex),
) -> PersonaDeriveResponse:
    persona = vertex.generate_persona(payload)
    search_terms = [payload.primary_keyword, *payload.supporting_keywords]
    return PersonaDeriveResponse(persona=persona, provenance_search_terms=search_terms)


@router.post("/api/jobs", response_model=Job, responses={400: {"model": APIError}})
def create_job(
    payload: JobCreate,
    store: FirestoreRepository = Depends(get_firestore),
    workflow: WorkflowLauncher = Depends(get_workflow),
    vertex: VertexGateway = Depends(get_vertex),
) -> Job:
    job_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    logger.info("Creating job %s", job_id)
    job = store.create_job(job_id, payload, draft_id=draft_id)

    persona = payload.persona_override or vertex.generate_persona(
        PersonaDeriveRequest(
            primary_keyword=payload.primary_keyword,
            supporting_keywords=payload.supporting_keywords,
        )
    )

    launch_payload = {
        "job_id": job_id,
        "project_id": get_settings().project_id,
        "prompt_version": payload.prompt_version or get_settings().default_prompt_version,
        "primary_keyword": payload.primary_keyword,
        "supporting_keywords": payload.supporting_keywords,
        "intent": payload.intent,
        "word_count_range": payload.word_count_range,
        "prohibited_claims": payload.prohibited_claims,
        "style_guide_id": payload.style_guide_id,
        "existing_article_ids": payload.existing_article_ids,
        "persona": persona.dict(),
    }
    execution_id = workflow.launch(job_id, launch_payload)
    if execution_id:
        job = store.update_job(job_id, workflow_execution_id=execution_id, status=JobStatus.running) or job
    return job


@router.get("/api/jobs/{job_id}", response_model=Job, responses={404: {"model": APIError}})
def get_job(job_id: str, store: FirestoreRepository = Depends(get_firestore)) -> Job:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/api/drafts/{draft_id}", response_model=DraftBundle, responses={404: {"model": APIError}})
def get_draft(
    draft_id: str,
    store: DraftStorage = Depends(get_storage),
    quality: QualityEngine = Depends(get_quality_engine),
) -> DraftBundle:
    import json

    # List artifacts from GCS or local store
    artifacts = store.list_artifacts(draft_id)
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

    return quality.bundle(
        draft_id=draft_id,
        paths=paths,
        metadata={"status": "preview"},
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

    firestore_repo.update_job(payload.job_id, status=JobStatus.completed)

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


def _render_markdown(draft: dict) -> str:
    sections = draft.get("sections", [])
    faq_items = draft.get("faq", [])
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
