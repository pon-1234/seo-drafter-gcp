from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class IntentType(str, Enum):
    information = "information"
    comparison = "comparison"
    transaction = "transaction"


class ArticleType(str, Enum):
    information = "information"
    comparison = "comparison"
    ranking = "ranking"
    closing = "closing"


class HeadingMode(str, Enum):
    auto = "auto"
    manual = "manual"


class OutputFormat(str, Enum):
    docs = "docs"
    html = "html"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PromptLayer(str, Enum):
    system = "system"
    developer = "developer"
    user = "user"


class PromptTemplate(BaseModel):
    layer: PromptLayer
    content: str


class PromptVersion(BaseModel):
    version: str = Field(..., description="Prompt version identifier")
    templates: List[PromptTemplate]
    variables: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PromptVersionCreate(BaseModel):
    prompt_id: str
    version: str
    templates: List[PromptTemplate]
    variables: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None


class ReaderPersonaTemplate(BaseModel):
    job_role: Optional[str] = None
    experience_years: Optional[str] = None
    needs: List[str] = Field(default_factory=list)
    prohibited_expressions: List[str] = Field(default_factory=list)


class WriterPersonaTemplate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    expertise: Optional[str] = None
    voice: Optional[str] = None
    mission: Optional[str] = None
    qualities: List[str] = Field(default_factory=list)


class PersonaTemplateExtras(BaseModel):
    intended_cta: Optional[str] = None
    notation_guidelines: Optional[str] = None
    quality_rubric: Optional[str] = None
    preferred_sources: List[str] = Field(default_factory=list)
    reference_media: List[str] = Field(default_factory=list)
    supporting_keywords: List[str] = Field(default_factory=list)
    reference_urls: List[str] = Field(default_factory=list)


class PersonaTemplateHeading(BaseModel):
    mode: HeadingMode = HeadingMode.auto
    overrides: List[str] = Field(default_factory=list)


class PersonaTemplateBase(BaseModel):
    label: str
    description: Optional[str] = None
    reader: Optional[ReaderPersonaTemplate] = None
    writer: Optional[WriterPersonaTemplate] = None
    extras: Optional[PersonaTemplateExtras] = None
    heading: Optional[PersonaTemplateHeading] = None


class PersonaTemplateCreate(PersonaTemplateBase):
    id: str = Field(description="Unique identifier for the template")


class PersonaTemplate(PersonaTemplateBase):
    id: str


class PersonaTemplateUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    reader: Optional[ReaderPersonaTemplate] = None
    writer: Optional[WriterPersonaTemplate] = None
    extras: Optional[PersonaTemplateExtras] = None
    heading: Optional[PersonaTemplateHeading] = None


class Persona(BaseModel):
    name: str
    job_to_be_done: Optional[str] = None
    pain_points: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    reading_level: Optional[str] = None
    tone: Optional[str] = None
    search_intent: Optional[IntentType] = None
    success_metrics: List[str] = Field(default_factory=list)


class WriterPersona(BaseModel):
    name: str
    role: Optional[str] = None
    expertise: Optional[str] = None
    voice: Optional[str] = None
    qualities: List[str] = Field(default_factory=list)
    mission: Optional[str] = None


class PersonaBrief(BaseModel):
    job_role: str = Field(..., description="読者の職種")
    experience_years: Optional[str] = Field(None, description="経験年数やシニアリティ")
    needs: List[str] = Field(default_factory=list, description="読者の主要なニーズ")
    prohibited_expressions: List[str] = Field(default_factory=list, description="避けるべき禁則表現")


class PersonaDeriveRequest(BaseModel):
    primary_keyword: str
    supporting_keywords: List[str] = Field(default_factory=list)
    region: Optional[str] = None
    device: Optional[str] = None
    article_type: Optional[ArticleType] = None
    intended_cta: Optional[str] = None
    persona_brief: Optional[PersonaBrief] = None


class PersonaDeriveResponse(BaseModel):
    persona: Persona
    provenance_search_terms: List[str]


class HeadingDirective(BaseModel):
    mode: HeadingMode = HeadingMode.auto
    headings: List[str] = Field(default_factory=list, description="指定する見出しのリスト (mode=manual の場合)")


class JobCreate(BaseModel):
    primary_keyword: str
    supporting_keywords: List[str] = Field(default_factory=list)
    intent: Optional[IntentType] = None
    word_count_range: Optional[str] = None
    prohibited_claims: List[str] = Field(default_factory=list)
    style_guide_id: Optional[str] = None
    prompt_version: Optional[str] = None
    existing_article_ids: List[str] = Field(default_factory=list)
    persona_override: Optional[Persona] = None
    article_type: ArticleType = ArticleType.information
    persona_brief: Optional[PersonaBrief] = None
    intended_cta: Optional[str] = None
    notation_guidelines: Optional[str] = None
    heading_directive: HeadingDirective = Field(default_factory=HeadingDirective)
    reference_urls: List[str] = Field(default_factory=list)
    output_format: OutputFormat = OutputFormat.html
    quality_rubric: Optional[str] = None
    writer_persona: Optional[WriterPersona] = None
    preferred_sources: List[str] = Field(default_factory=list)
    reference_media: List[str] = Field(default_factory=list)
    project_template_id: Optional[str] = None


class Job(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    payload: JobCreate


class LineRecipientType(str, Enum):
    user = "user"
    group = "group"
    room = "room"


class LineRecipient(BaseModel):
    type: LineRecipientType
    identifier: str
    label: Optional[str] = None


class Store(BaseModel):
    id: str
    name: str
    line_recipient: Optional[LineRecipient] = None
    timezone: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Cast(BaseModel):
    id: str
    name: str
    store_id: Optional[str] = None
    line_recipient: Optional[LineRecipient] = None
    additional_recipients: List[LineRecipient] = Field(default_factory=list)
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatEventBase(BaseModel):
    cast_id: str
    store_id: Optional[str] = None
    sender_name: Optional[str] = None
    customer_name: Optional[str] = None
    message: str
    channel: Optional[str] = None
    unread_count: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatEventCreate(ChatEventBase):
    event_id: Optional[str] = None
    sent_at: datetime


class ChatEvent(ChatEventBase):
    id: str
    sent_at: datetime
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class ReservationStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class ReservationEventBase(BaseModel):
    cast_id: str
    store_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    menu_name: Optional[str] = None
    channel: Optional[str] = None
    note: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReservationEventCreate(ReservationEventBase):
    reservation_id: str
    event_id: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    status: ReservationStatus = ReservationStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReservationEvent(ReservationEventBase):
    id: str
    reservation_id: str
    start_at: datetime
    end_at: Optional[datetime] = None
    status: ReservationStatus
    created_at: datetime
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class ChatNotificationResponse(BaseModel):
    event: ChatEvent
    recipients: List[LineRecipient] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ReservationNotificationResponse(BaseModel):
    event: ReservationEvent
    recipients: List[LineRecipient] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    workflow_execution_id: Optional[str] = None
    draft_id: Optional[str] = None


class DraftQualitySignals(BaseModel):
    duplication_score: float
    excessive_claims: List[str]
    style_violations: List[str]
    requires_expert_review: bool
    citations_missing: List[str]
    rubric_scores: Dict[str, str] = Field(default_factory=dict)
    rubric_summary: Optional[str] = None


class DraftPersistenceRequest(BaseModel):
    job_id: str
    draft_id: Optional[str] = None
    payload: Dict[str, Any]



class InternalLink(BaseModel):
    url: str
    title: str
    anchor: str
    score: float
    snippet: Optional[str] = None


class DraftBundle(BaseModel):
    draft_id: str
    gcs_paths: Dict[str, str]
    signed_urls: Optional[Dict[str, HttpUrl]] = None
    quality: DraftQualitySignals
    metadata: Dict[str, str]
    internal_links: Optional[List[InternalLink]] = None
    draft_content: Optional[str] = None


class DraftApproveRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None


class DraftListItem(BaseModel):
    """Summary of a draft for list view."""
    draft_id: str
    job_id: str
    status: str
    created_at: Optional[str] = None
    title: Optional[str] = None
    article_type: Optional[str] = None
    primary_keyword: Optional[str] = None


class DraftListResponse(BaseModel):
    """Response containing list of drafts."""
    drafts: List[DraftListItem]
    total: int


class APIError(BaseModel):
    message: str
    detail: Optional[str] = None
