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


class LLMProvider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"


class ExpertiseLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    expert = "expert"


class ToneStyle(str, Enum):
    casual = "casual"
    formal = "formal"


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




class LLMConfig(BaseModel):
    provider: LLMProvider = LLMProvider.openai
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_output_tokens: Optional[int] = Field(default=None, ge=128, le=8192)
    label: Optional[str] = Field(default=None, description="UI 表示用の任意ラベル")



class SerpResult(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)


class RewriteRequest(BaseModel):
    text: str
    instruction: str
    llm: Optional[LLMConfig] = None


class RewriteResponse(BaseModel):
    rewritten_text: str
    detected_ng_phrases: List[str] = Field(default_factory=list)
    detected_abstract_phrases: List[str] = Field(default_factory=list)


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
    llm: Optional[LLMConfig] = None
    benchmark_plan: List[LLMConfig] = Field(default_factory=list, description="比較用のLLM候補一覧")
    serp_snapshot: List[SerpResult] = Field(default_factory=list)
    expertise_level: ExpertiseLevel = Field(default=ExpertiseLevel.intermediate, description="読者の専門性レベル")
    tone: ToneStyle = Field(default=ToneStyle.formal, description="文章のトーン")


class Job(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    payload: JobCreate
    workflow_execution_id: Optional[str] = None
    draft_id: Optional[str] = None
    error_message: Optional[str] = None
    error_detail: Optional[Dict[str, Any]] = None


class DraftQualitySignals(BaseModel):
    duplication_score: float
    excessive_claims: List[str]
    style_violations: List[str]
    requires_expert_review: bool
    citations_missing: List[str]
    rubric_scores: Dict[str, str] = Field(default_factory=dict)
    rubric_summary: Optional[str] = None
    citation_count: int = 0
    numeric_facts: int = 0
    banned_phrase_hits: List[str] = Field(default_factory=list)
    abstract_phrase_hits: List[str] = Field(default_factory=list)


class DraftPersistenceRequest(BaseModel):
    job_id: str
    draft_id: Optional[str] = None
    payload: Dict[str, Any]


class JobFailureReport(BaseModel):
    reason: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None



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
    meta: Optional[Dict[str, Any]] = None
    internal_links: Optional[List[InternalLink]] = None
    draft_content: Optional[str] = None
    style_rewrite_metrics: Optional[Dict[str, Any]] = None
    style_rewritten: Optional[bool] = None
    validation_warnings: List[str] = Field(default_factory=list)


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


class BenchmarkVariantResult(BaseModel):
    variant_id: str
    llm: LLMConfig
    draft_id: str
    processing_seconds: float
    word_count: int
    citation_count: int
    quality: DraftQualitySignals
    style_flags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    excerpt: str


class BenchmarkRun(BaseModel):
    id: str
    primary_keyword: str
    article_type: ArticleType
    intent: Optional[IntentType] = None
    prompt_version: Optional[str] = None
    created_at: datetime
    variants: List[BenchmarkVariantResult]
    aggregate_metrics: Dict[str, Any] = Field(default_factory=dict)


class QualityKpiResponse(BaseModel):
    sample_size: int
    avg_duplication: float
    avg_citation_count: float
    avg_numeric_facts: float
    ng_phrase_rate: float
    abstract_phrase_rate: float


class APIError(BaseModel):
    message: str
    detail: Optional[str] = None
