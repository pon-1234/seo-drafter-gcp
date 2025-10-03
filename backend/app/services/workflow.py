from __future__ import annotations

import json
import logging
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency
    from google.cloud import workflows_v1
except ImportError:  # pragma: no cover - local fallback
    workflows_v1 = None

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class WorkflowLauncher:
    """Triggers Cloud Workflows executions with offline fallback."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = workflows_v1.ExecutionsClient() if workflows_v1 else None

    def launch(self, job_id: str, payload: Dict) -> Optional[str]:
        if not self._client:
            logger.info("Workflows client unavailable; returning synthetic execution id")
            return f"debug-{job_id}"

        parent = self._client.workflow_path(
            self._settings.project_id,
            self._settings.workflow_region,
            self._settings.workflow_name,
        )
        response = self._client.create_execution(parent=parent, execution={"argument": json.dumps(payload)})
        return response.name
