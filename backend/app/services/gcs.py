from __future__ import annotations

import json
import logging
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency
    from google.cloud import storage  # type: ignore
except ImportError:  # pragma: no cover - local fallback
    storage = None

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class DraftStorage:
    """Handles Cloud Storage persistence for draft artifacts."""

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket_name = settings.drafts_bucket
        self._client = storage.Client(project=settings.project_id) if storage else None
        self._local_store: Dict[str, Dict[str, str]] = {}

    def _bucket(self):  # pragma: no cover - requires GCP
        if not self._client:
            raise RuntimeError("Cloud Storage client unavailable")
        return self._client.bucket(self._bucket_name)

    def save_artifact(self, draft_id: str, filename: str, payload: Dict) -> str:
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        return self.save_raw(draft_id, filename, data)

    def save_raw(self, draft_id: str, filename: str, data: str) -> str:
        path = f"projects/{get_settings().project_id}/drafts/{draft_id}/{filename}"
        if self._client:
            blob = self._bucket().blob(path)
            blob.upload_from_string(data, content_type="application/json")
        else:
            draft_entry = self._local_store.setdefault(draft_id, {})
            draft_entry[path] = data
        return path

    def get_signed_url(self, path: str, expires: int = 3600) -> Optional[str]:
        if not self._client:
            return None
        blob = self._bucket().blob(path)
        return blob.generate_signed_url(expiration=expires)

    def get_local(self, draft_id: str) -> Dict[str, str]:
        return self._local_store.get(draft_id, {})
