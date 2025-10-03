from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    from google.api_core import exceptions as gcloud_exceptions  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    class _NotFound(Exception):
        ...

    class gcloud_exceptions:  # type: ignore
        NotFound = _NotFound

try:  # pragma: no cover - optional dependency
    from google.cloud import firestore  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    firestore = None

from ..core.config import get_settings
from ..models import Job, JobCreate, JobStatus, PromptVersion, PromptVersionCreate

logger = logging.getLogger(__name__)


class FirestoreRepository:
    """Firestore backed persistence with in-memory fallback for local dev."""

    def __init__(self) -> None:
        settings = get_settings()
        self._namespace = settings.firestore_namespace
        self._client = firestore.Client(project=settings.project_id) if firestore else None
        self._jobs: Dict[str, Job] = {}
        self._prompts: Dict[str, Dict[str, PromptVersion]] = {}

    def _doc_path(self, collection: str, doc_id: str) -> str:
        if self._namespace:
            return f"{self._namespace}/{collection}/{doc_id}"
        return f"{collection}/{doc_id}"

    # Jobs
    def create_job(self, job_id: str, payload: JobCreate, draft_id: Optional[str] = None) -> Job:
        now = datetime.utcnow()
        job = Job(
            id=job_id,
            status=JobStatus.pending,
            created_at=now,
            updated_at=now,
            payload=payload,
            draft_id=draft_id,
        )
        if self._client:
            doc_ref = self._client.document(self._doc_path("jobs", job_id))
            doc_ref.set(job.dict())
        else:
            self._jobs[job_id] = job
        return job

    def update_job(self, job_id: str, **updates: Any) -> Optional[Job]:
        current = self.get_job(job_id)
        if not current:
            return None
        data = current.dict()
        data.update(updates)
        data["updated_at"] = datetime.utcnow()
        job = Job(**data)
        if self._client:
            doc_ref = self._client.document(self._doc_path("jobs", job_id))
            doc_ref.set(job.dict())
        else:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("jobs", job_id))
            try:
                snapshot = doc_ref.get()
            except gcloud_exceptions.NotFound:  # pragma: no cover
                return None
            if not snapshot.exists:
                return None
            return Job(**snapshot.to_dict())
        return self._jobs.get(job_id)

    # Prompt versions
    def create_prompt_version(self, data: PromptVersionCreate) -> PromptVersion:
        entry = PromptVersion(
            version=data.version,
            templates=data.templates,
            variables=data.variables,
            description=data.description,
        )
        prompt_versions = self._prompts.setdefault(data.prompt_id, {})
        prompt_versions[data.version] = entry

        if self._client:
            doc_ref = self._client.document(self._doc_path("prompts", data.prompt_id))
            doc_ref.set({"versions": {data.version: entry.dict()}}, merge=True)
        return entry

    def get_prompt_version(self, prompt_id: str, version: Optional[str]) -> Optional[PromptVersion]:
        if self._client:
            doc_ref = self._client.document(self._doc_path("prompts", prompt_id))
            snapshot = doc_ref.get()
            if snapshot.exists:
                data = snapshot.to_dict()
                versions: Dict[str, Dict[str, Any]] = data.get("versions", {})
                if not version and versions:
                    version = sorted(versions.keys())[-1]
                if version and version in versions:
                    return PromptVersion(**versions[version])
            return None

        prompt_versions = self._prompts.get(prompt_id, {})
        if not version and prompt_versions:
            version = sorted(prompt_versions.keys())[-1]
        return prompt_versions.get(version) if version else None
