import pytest
from app.tasks.pipeline import DraftGenerationPipeline, PipelineContext


class TestDraftGenerationPipeline:
    def test_estimate_intent_explicit(self):
        """Test intent estimation with explicit intent."""
        pipeline = DraftGenerationPipeline()
        payload = {
            "job_id": "test-123",
            "intent": "comparison",
            "persona": {}
        }

        intent = pipeline.estimate_intent(payload)
        assert intent == "comparison"

    def test_estimate_intent_from_persona(self):
        """Test intent estimation from persona goals."""
        pipeline = DraftGenerationPipeline()
        payload = {
            "job_id": "test-123",
            "persona": {
                "goals": ["比較して最適な選択をしたい"]
            }
        }

        intent = pipeline.estimate_intent(payload)
        assert intent == "comparison"

    def test_generate_outline(self):
        """Test outline generation."""
        pipeline = DraftGenerationPipeline()
        context = PipelineContext(
            job_id="test-123",
            draft_id="draft-123",
            project_id="test-project",
            prompt_version="v1.0",
            persona={"name": "テストユーザー"},
            intent="information"
        )
        payload = {"primary_keyword": "SEO対策"}

        outline = pipeline.generate_outline(context, payload)

        assert "title" in outline
        assert "h2" in outline
        assert len(outline["h2"]) > 0
        assert "SEO対策" in outline["title"]

    def test_generate_meta(self):
        """Test meta tag generation."""
        pipeline = DraftGenerationPipeline()
        payload = {"primary_keyword": "Python プログラミング"}

        meta = pipeline.generate_meta(payload)

        assert "title_options" in meta
        assert "description_options" in meta
        assert "og" in meta
        assert len(meta["title_options"]) > 0

    def test_evaluate_quality(self):
        """Test quality evaluation."""
        pipeline = DraftGenerationPipeline()
        draft = {
            "claims": [
                {"id": "claim-1", "text": "テキスト", "citations": []},
                {"id": "claim-2", "text": "テキスト2", "citations": ["https://example.com"]}
            ]
        }

        quality = pipeline.evaluate_quality(draft)

        assert "similarity" in quality
        assert "claims" in quality
        assert "style_violations" in quality
        assert "is_ymyl" in quality
        assert len(quality["claims"]) == 1  # Only one claim without citations

    def test_run_pipeline_end_to_end(self):
        """Test complete pipeline execution."""
        pipeline = DraftGenerationPipeline()
        payload = {
            "job_id": "test-job-123",
            "draft_id": "test-draft-123",
            "project_id": "test-project",
            "primary_keyword": "テストキーワード",
            "supporting_keywords": ["サブキーワード1", "サブキーワード2"],
            "persona": {
                "name": "テストユーザー",
                "goals": ["情報収集"],
                "pain_points": ["時間がない"],
                "tone": "実務的"
            }
        }

        result = pipeline.run(payload)

        assert "outline" in result
        assert "draft" in result
        assert "meta" in result
        assert "links" in result
        assert "quality" in result
        assert "metadata" in result

        # Verify outline structure
        assert "title" in result["outline"]
        assert "h2" in result["outline"]

        # Verify draft structure
        assert "sections" in result["draft"]
        assert "faq" in result["draft"]

        # Verify metadata
        assert result["metadata"]["job_id"] == "test-job-123"
        assert result["metadata"]["draft_id"] == "test-draft-123"
