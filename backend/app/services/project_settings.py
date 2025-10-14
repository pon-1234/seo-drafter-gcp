from __future__ import annotations

from typing import Any, Dict

from shared.project_defaults import get_project_defaults


def load_project_settings(project_id: str) -> Dict[str, Any]:
    """Load project level defaults for the given project id."""
    return get_project_defaults(project_id)

