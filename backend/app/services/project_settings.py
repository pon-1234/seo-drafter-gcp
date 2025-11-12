from __future__ import annotations

from typing import Any, Dict, Optional

from shared.project_defaults import get_project_defaults


def load_project_settings(project_id: str, expertise_level: Optional[str] = None) -> Dict[str, Any]:
    """Load project level defaults for the given project id.

    Args:
        project_id: The project ID to get defaults for
        expertise_level: Optional expertise level to get appropriate sources and media
    """
    return get_project_defaults(project_id, expertise_level)

