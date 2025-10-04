from __future__ import annotations

import json
import logging
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency
    from google.cloud.workflows import executions_v1
except ImportError:  # pragma: no cover - local fallback
    executions_v1 = None

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class WorkflowLauncher:
    """Triggers Cloud Workflows executions with offline fallback."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = executions_v1.ExecutionsClient() if executions_v1 else None

    def launch(self, job_id: str, payload: Dict) -> Optional[str]:
        if not self._client:
            logger.info("Workflows client unavailable; returning synthetic execution id")
            return f"debug-{job_id}"

        parent = f"projects/{self._settings.project_id}/locations/{self._settings.workflow_region}/workflows/{self._settings.workflow_name}"
        execution = executions_v1.Execution(argument=json.dumps(payload))
        response = self._client.create_execution(parent=parent, execution=execution)
        return response.name
