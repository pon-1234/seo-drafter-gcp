from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.api import routes as api_routes
from app.core.config import get_settings
from app.main import app as fastapi_app
from app.services.firestore import FirestoreRepository
from app.models import Persona


class DummyLineNotifier:
    calls: List[Dict[str, Any]] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def notify_text(self, recipients, message, *, raise_on_error: bool = False):
        self.__class__.calls.append({"recipients": recipients, "message": message})
        return []


class DummyAIGateway:
    def generate_persona(self, payload):
        return Persona(
            name="テストペルソナ",
            pain_points=["確認用"],
            goals=["検証"],
        )


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr("app.services.firestore.firestore", None)
    monkeypatch.setattr("app.services.workflow.executions_v1", None)
    get_settings.cache_clear()

    shared_repo = FirestoreRepository()
    fastapi_app.dependency_overrides[api_routes.get_firestore] = lambda: shared_repo
    api_routes._test_shared_repo = shared_repo
    monkeypatch.setattr(api_routes, "LineNotifier", DummyLineNotifier)
    fastapi_app.dependency_overrides[api_routes.get_ai_gateway] = lambda: DummyAIGateway()

    DummyLineNotifier.calls.clear()
    yield

    DummyLineNotifier.calls.clear()
    fastapi_app.dependency_overrides.pop(api_routes.get_ai_gateway, None)
    fastapi_app.dependency_overrides.pop(api_routes.get_firestore, None)
    api_routes._test_shared_repo = None  # type: ignore[attr-defined]
    get_settings.cache_clear()
