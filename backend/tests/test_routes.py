from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body


def test_list_benchmarks_empty():
    response = client.get("/api/benchmarks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_quality_kpis_empty():
    response = client.get("/api/analytics/quality-kpis")
    assert response.status_code == 200
    data = response.json()
    assert data["sample_size"] == 0
