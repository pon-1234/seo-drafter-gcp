from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.config import get_settings
from ..models import (
    APIError,
    ChatEvent,
    ChatEventCreate,
    ChatNotificationResponse,
    DraftApproveRequest,
    DraftBundle,
    DraftListItem,
    DraftListResponse,
    DraftPersistenceRequest,
    Job,
    JobCreate,
    JobStatus,
    PersonaDeriveRequest,
    PersonaDeriveResponse,
    PersonaTemplate,
    PersonaTemplateCreate,
    PersonaTemplateUpdate,
    PromptVersion,
    PromptVersionCreate,
    ReservationEvent,
    ReservationEventCreate,
    ReservationNotificationResponse,
    ReservationStatus,
    WriterPersona,
    Cast,
    Store,
    LineRecipient,
)
from ..services.firestore import FirestoreRepository
from ..services.gcs import DraftStorage
from ..services.quality import QualityEngine
from ..services.workflow import WorkflowLauncher
from ..services.project_settings import load_project_settings
from ..services.line_notifications import (
    LineNotificationError,
    LineNotifier,
    default_recipients,
    dedupe_recipients,
)

try:
    from ..services.openai_gateway import OpenAIGateway
except ImportError:
    OpenAIGateway = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_TIMEZONE = "Asia/Tokyo"


def _coerce_timezone(tz_name: Optional[str]) -> ZoneInfo:
    candidate = (tz_name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(candidate)
    except Exception:  # pragma: no cover - defensive fallback
        return ZoneInfo(DEFAULT_TIMEZONE)


def _format_timestamp(dt: datetime, tz_name: Optional[str]) -> str:
    tz = _coerce_timezone(tz_name)
    if dt.tzinfo:
        localized = dt.astimezone(tz)
    else:
        localized = dt.replace(tzinfo=timezone.utc).astimezone(tz)
    return localized.strftime("%Y-%m-%d %H:%M")


def _resolve_recipients(
    repo: FirestoreRepository, cast_id: Optional[str], store_id: Optional[str]
) -> Tuple[List[LineRecipient], Optional[Cast], Optional[Store]]:
    cast = repo.get_cast(cast_id) if cast_id else None
    resolved_store_id = store_id or (cast.store_id if cast else None)
    store = repo.get_store(resolved_store_id) if resolved_store_id else None

    candidates: List[Optional[LineRecipient]] = []
    if cast and cast.line_recipient:
        candidates.append(cast.line_recipient)
    if cast:
        candidates.extend(cast.additional_recipients)
    if store and store.line_recipient:
        candidates.append(store.line_recipient)
    candidates.extend(default_recipients())

    recipients = dedupe_recipients(candidates)
    return recipients, cast, store


def _build_chat_message(event: ChatEvent, cast: Optional[Cast], store: Optional[Store]) -> str:
    store_label = store.name if store else (event.store_id or "店舗未登録")
    cast_label = cast.name if cast else event.cast_id
    timestamp = _format_timestamp(event.sent_at, store.timezone if store else None)
    lines = [
        "📩 新着チャット",
        f"店舗: {store_label}",
        f"キャスト: {cast_label}",
        f"受信: {timestamp}",
    ]
    if event.customer_name:
        lines.append(f"お客様: {event.customer_name}")
    if event.sender_name and event.sender_name != event.customer_name:
        lines.append(f"送信者: {event.sender_name}")
    if event.channel:
        lines.append(f"経路: {event.channel}")
    if event.unread_count is not None:
        lines.append(f"未読件数: {event.unread_count}")
    if event.metadata:
        for key, value in event.metadata.items():
            lines.append(f"{key}: {value}")
    lines.append("----")
    lines.append(event.message)
    return "\n".join(lines)


STATUS_LABEL = {
    ReservationStatus.pending: "仮予約",
    ReservationStatus.confirmed: "確定",
    ReservationStatus.cancelled: "キャンセル",
    ReservationStatus.completed: "完了",
}


def _build_reservation_message(
    event: ReservationEvent, cast: Optional[Cast], store: Optional[Store]
) -> str:
    store_label = store.name if store else (event.store_id or "店舗未登録")
    cast_label = cast.name if cast else event.cast_id
    start = _format_timestamp(event.start_at, store.timezone if store else None)
    end = None
    if event.end_at:
        end = _format_timestamp(event.end_at, store.timezone if store else None)
    timeframe = f"{start} - {end}" if end else start
    status_label = STATUS_LABEL.get(event.status, event.status.value)
    lines = [
        "🗓️ 新着予約",
        f"店舗: {store_label}",
        f"キャスト: {cast_label}",
        f"日時: {timeframe}",
        f"ステータス: {status_label}",
    ]
    if event.menu_name:
        lines.append(f"メニュー: {event.menu_name}")
    if event.customer_name:
        lines.append(f"お客様: {event.customer_name}")
    if event.customer_contact:
        lines.append(f"連絡先: {event.customer_contact}")
    if event.channel:
        lines.append(f"経路: {event.channel}")
    if event.note:
        lines.append(f"備考: {event.note}")
    if event.metadata:
        for key, value in event.metadata.items():
            lines.append(f"{key}: {value}")
    return "\n".join(lines)

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

    try:
        return OpenAIGateway(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
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


@router.post(
    "/internal/notifications/chat",
    response_model=ChatNotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_chat_notification(
    payload: ChatEventCreate,
    repo: FirestoreRepository = Depends(get_firestore),
) -> ChatNotificationResponse:
    event = repo.create_chat_event(payload)
    recipients, cast, store_entry = _resolve_recipients(repo, event.cast_id, event.store_id)
    errors: List[str] = []

    if not recipients:
        logger.warning("No LINE recipients resolved for chat event %s", event.id)
        return ChatNotificationResponse(event=event, recipients=[], errors=["no_recipients"])

    try:
        notifier = LineNotifier()
    except LineNotificationError as exc:
        logger.warning("LINE notifier unavailable: %s", exc)
        errors.append(str(exc))
        return ChatNotificationResponse(event=event, recipients=recipients, errors=errors)

    message = _build_chat_message(event, cast, store_entry)
    dispatch_errors = await notifier.notify_text(recipients, message)
    errors.extend(dispatch_errors)

    return ChatNotificationResponse(event=event, recipients=recipients, errors=errors)


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

    # If not found, try to find the job and use job_id as fallback
    # (older drafts may be stored by job_id instead of draft_id)
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
@router.post(
    "/internal/notifications/reservation",
    response_model=ReservationNotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_reservation_notification(
    payload: ReservationEventCreate,
    repo: FirestoreRepository = Depends(get_firestore),
) -> ReservationNotificationResponse:
    event = repo.create_reservation_event(payload)
    recipients, cast, store_entry = _resolve_recipients(repo, event.cast_id, event.store_id)
    errors: List[str] = []

    if not recipients:
        logger.warning("No LINE recipients resolved for reservation event %s", event.id)
        return ReservationNotificationResponse(event=event, recipients=[], errors=["no_recipients"])

    try:
        notifier = LineNotifier()
    except LineNotificationError as exc:
        logger.warning("LINE notifier unavailable: %s", exc)
        errors.append(str(exc))
        return ReservationNotificationResponse(event=event, recipients=recipients, errors=errors)

    message = _build_reservation_message(event, cast, store_entry)
    dispatch_errors = await notifier.notify_text(recipients, message)
    errors.extend(dispatch_errors)

    return ReservationNotificationResponse(event=event, recipients=recipients, errors=errors)
