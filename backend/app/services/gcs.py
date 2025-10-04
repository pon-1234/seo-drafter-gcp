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
        # Signed URLs require service account key, not available in Cloud Run with default credentials
        # Return public GCS path instead
        return f"gs://{self._settings.drafts_bucket}/{path}"

    def get_local(self, draft_id: str) -> Dict[str, str]:
        return self._local_store.get(draft_id, {})

    def list_artifacts(self, draft_id: str) -> Dict[str, str]:
        """List all artifacts for a draft. Returns dict of {artifact_name: full_path}."""
        prefix = f"projects/{get_settings().project_id}/drafts/{draft_id}/"

        # Try GCS first
        if self._client:
            try:
                bucket = self._bucket()
                blobs = bucket.list_blobs(prefix=prefix)
                artifacts = {}
                for blob in blobs:
                    # Extract just the filename from the full path
                    filename = blob.name.replace(prefix, "")
                    if filename:  # Skip the directory itself
                        artifacts[filename] = blob.name
                return artifacts
            except Exception as e:
                logger.error("Failed to list GCS artifacts for %s: %s", draft_id, e)

        # Fallback to local store
        local = self._local_store.get(draft_id, {})
        artifacts = {}
        for path in local.keys():
            if path.startswith(prefix):
                filename = path.replace(prefix, "")
                artifacts[filename] = path
        return artifacts

    def read_artifact(self, path: str) -> Optional[str]:
        """Read artifact content from GCS or local store."""
        # Try GCS first
        if self._client:
            try:
                blob = self._bucket().blob(path)
                if blob.exists():
                    return blob.download_as_text()
            except Exception as e:
                logger.error("Failed to read GCS artifact %s: %s", path, e)

        # Fallback to local store - search through all drafts
        for draft_data in self._local_store.values():
            if path in draft_data:
                return draft_data[path]

        return None
