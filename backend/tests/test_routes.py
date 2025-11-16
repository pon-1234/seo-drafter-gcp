from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import _render_markdown, get_firestore, get_quality_engine, get_storage
from app.services import firestore as firestore_module, gcs as gcs_module
from app.services.firestore import FirestoreRepository
from app.services.gcs import DraftStorage
from app.services.quality import QualityEngine

firestore_module.firestore = None  # Force in-memory fallback during tests
gcs_module.storage = None  # Disable real GCS client for tests

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


def test_render_markdown_uses_outline_title_and_merges_faq():
    draft = {
        "sections": [
            {
                "h2": "30秒で要点",
                "paragraphs": [
                    {"heading": "まとめ", "text": "本文です。"}
                ],
            },
            {
                "h2": "よくある質問（FAQ）",
                "paragraphs": [],
            },
        ],
        "faq": [
            {"question": "費用は？", "answer": "状況により異なります。"}
        ],
    }
    outline = {"title": "デジタルマーケティングとは？"}
    markdown = _render_markdown(draft, outline)

    assert markdown.splitlines()[0] == "# デジタルマーケティングとは？"
    # FAQ見出しは1回のみ
    assert markdown.count("## よくある質問（FAQ）") <= 1
    assert markdown.count("よくある質問（FAQ）") >= 1


def test_render_markdown_aggregates_references():
    draft = {
        "sections": [
            {
                "h2": "セクション",
                "paragraphs": [
                    {
                        "heading": "詳細",
                        "text": "数値を整理します。",
                        "citations": [
                            "https://example.com/data/2024",
                            "https://example.com/data/2024",  # duplicate should be deduped
                        ],
                    }
                ],
            }
        ],
        "faq": [
            {
                "question": "効果は？",
                "answer": "3カ月で改善が見えます。",
                "citations": ["https://support.google.com/analytics/answer"],
            }
        ],
    }
    markdown = _render_markdown(draft, {"title": "テストタイトル"})

    assert "## 参考情報" in markdown
    assert "[example.com/data/2024]" in markdown
    assert "[support.google.com/analytics/answer]" in markdown
    assert "根拠:" not in markdown


def test_render_markdown_strips_duplicate_h3():
    draft = {
        "sections": [
            {
                "h2": "セクション",
                "paragraphs": [
                    {
                        "heading": "重複見出し",
                        "text": "### 重複見出し 詳細をまとめます。",
                    }
                ],
            }
        ]
    }
    markdown = _render_markdown(draft, {"title": "テスト"})

    assert markdown.count("### 重複見出し") == 1
    assert "詳細をまとめます。" in markdown


def test_render_markdown_splits_multi_url_citation():
    draft = {
        "sections": [
            {
                "h2": "セクション",
                "paragraphs": [
                    {
                        "heading": "参考リンク",
                        "text": "資料を掲載します。",
                        "citations": ["https://example.com/a, https://example.com/b https://example.org/c)"],
                    }
                ],
            }
        ]
    }
    markdown = _render_markdown(draft, {"title": "テスト"})
    assert markdown.count("## 参考情報") == 1
    assert "[example.com/a]" in markdown
    assert "[example.com/b]" in markdown
    assert "[example.org/c]" in markdown


def test_draft_metadata_propagation_roundtrip():
    store = DraftStorage()
    firestore = FirestoreRepository()
    quality = QualityEngine()
    app.dependency_overrides[get_storage] = lambda: store
    app.dependency_overrides[get_firestore] = lambda: firestore
    app.dependency_overrides[get_quality_engine] = lambda: quality
    try:
        payload = {
            "job_id": "job-123",
            "draft_id": "draft-abc",
            "payload": {
                "outline": {
                    "title": "仮タイトル",
                    "provisional_title": "仮タイトル",
                    "h2": [],
                },
                "draft": {
                    "sections": [
                        {
                            "h2": "イントロダクション",
                            "paragraphs": [{"heading": "概要", "text": "概要文です。"}],
                        }
                    ],
                    "faq": [],
                },
                "meta": {"final_title": "完成タイトル"},
                "links": [],
                "quality": {
                    "similarity": 0.12,
                    "claims": [],
                    "style_violations": [],
                    "is_ymyl": False,
                    "ng_phrases": [],
                    "abstract_phrases": [],
                },
            },
        }

        response = client.post("/internal/drafts", json=payload)
        assert response.status_code == 200
        bundle = response.json()
        assert bundle["metadata"]["provisional_title"] == "仮タイトル"
        assert bundle["metadata"]["final_title"] == "完成タイトル"
        assert bundle["meta"]["final_title"] == "完成タイトル"

        response = client.get(f"/api/drafts/{bundle['draft_id']}")
        assert response.status_code == 200
        round_trip = response.json()
        assert round_trip["metadata"]["provisional_title"] == "仮タイトル"
        assert round_trip["metadata"]["final_title"] == "完成タイトル"
        assert round_trip["meta"]["final_title"] == "完成タイトル"
    finally:
        app.dependency_overrides.clear()
