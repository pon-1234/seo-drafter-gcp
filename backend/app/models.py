from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class IntentType(str, Enum):
    information = "information"
    comparison = "comparison"
    transaction = "transaction"


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


class Persona(BaseModel):
    name: str
    job_to_be_done: Optional[str] = None
    pain_points: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    reading_level: Optional[str] = None
    tone: Optional[str] = None
    search_intent: Optional[IntentType] = None
    success_metrics: List[str] = Field(default_factory=list)


class PersonaDeriveRequest(BaseModel):
    primary_keyword: str
    supporting_keywords: List[str] = Field(default_factory=list)
    region: Optional[str] = None
    device: Optional[str] = None


class PersonaDeriveResponse(BaseModel):
    persona: Persona
    provenance_search_terms: List[str]


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


class Job(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    payload: JobCreate
    workflow_execution_id: Optional[str] = None
    draft_id: Optional[str] = None


class DraftQualitySignals(BaseModel):
    duplication_score: float
    excessive_claims: List[str]
    style_violations: List[str]
    requires_expert_review: bool
    citations_missing: List[str]


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


class APIError(BaseModel):
    message: str
    detail: Optional[str] = None
