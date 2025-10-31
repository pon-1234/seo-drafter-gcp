import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import routes as api_routes
from app.models import (
    Cast,
    LineRecipient,
    LineRecipientType,
    Store,
)
from app.services.firestore import FirestoreRepository
from app.services.line_notifications import dedupe_recipients, parse_recipient


client = TestClient(app)


@pytest.fixture
def repo():
    repository = FirestoreRepository()
    api_routes.LineNotifier.calls.clear()

    store = Store(
        id="ikebukuro",
        name="池袋店",
        line_recipient=LineRecipient(type=LineRecipientType.group, identifier="G123456789"),
        timezone="Asia/Tokyo",
    )
    repository.upsert_store(store)
    cast = Cast(
        id="cast-001",
        name="ゆり",
        store_id=store.id,
        line_recipient=LineRecipient(type=LineRecipientType.user, identifier="U987654321"),
    )
    repository.upsert_cast(cast)

    original_provider = app.dependency_overrides.get(api_routes.get_firestore)
    app.dependency_overrides[api_routes.get_firestore] = lambda: repository
    yield repository
    if original_provider is not None:
        app.dependency_overrides[api_routes.get_firestore] = original_provider
    else:
        app.dependency_overrides.pop(api_routes.get_firestore, None)


def test_parse_recipient_round_trip():
    recipient = parse_recipient("user:U1234|テスト")
    assert recipient.type is LineRecipientType.user
    assert recipient.identifier == "U1234"
    assert recipient.label == "テスト"


def test_parse_recipient_invalid():
    with pytest.raises(ValueError):
        parse_recipient("invalid")


def test_dedupe_recipients():
    r1 = LineRecipient(type=LineRecipientType.user, identifier="U1")
    r2 = LineRecipient(type=LineRecipientType.user, identifier="U2")
    r3 = LineRecipient(type=LineRecipientType.user, identifier="U1")
    result = dedupe_recipients([r1, r2, r3])
    assert result == [r1, r2]


def test_chat_notification_dispatch(repo):
    payload = {
        "event_id": "chat-001",
        "cast_id": "cast-001",
        "store_id": "ikebukuro",
        "customer_name": "田中様",
        "sender_name": "田中様",
        "message": "ご予約について相談したいです。",
        "channel": "webチャット",
        "unread_count": 1,
        "sent_at": "2024-06-01T03:00:00Z",
    }
    response = client.post("/internal/notifications/chat", json=payload)
    assert response.status_code == 202
    body = response.json()
    assert body["event"]["id"] == "chat-001"
    assert len(body["recipients"]) == 2
    assert body["errors"] == []

    assert api_routes.LineNotifier.calls, "LINE notifier should be invoked"
    call = api_routes.LineNotifier.calls[-1]
    assert len(call["recipients"]) == 2
    assert "📩 新着チャット" in call["message"]
    assert "田中様" in call["message"]

    events = repo.list_chat_events("cast-001")
    assert events and events[0].id == "chat-001"


def test_reservation_notification_dispatch(repo):
    payload = {
        "event_id": "reserve-001",
        "reservation_id": "res-001",
        "cast_id": "cast-001",
        "store_id": "ikebukuro",
        "customer_name": "高橋様",
        "customer_contact": "sample@example.com",
        "menu_name": "アロマ60分",
        "channel": "予約フォーム",
        "note": "初回来店",
        "status": "confirmed",
        "start_at": "2024-06-10T12:00:00+09:00",
        "end_at": "2024-06-10T13:00:00+09:00",
    }
    response = client.post("/internal/notifications/reservation", json=payload)
    assert response.status_code == 202
    body = response.json()
    assert body["event"]["id"] == "reserve-001"
    assert len(body["recipients"]) == 2
    assert body["errors"] == []

    call = api_routes.LineNotifier.calls[-1]
    assert "🗓️ 新着予約" in call["message"]
    assert "アロマ60分" in call["message"]

    events = repo.list_reservation_events("cast-001")
    assert events and events[0].id == "reserve-001"
