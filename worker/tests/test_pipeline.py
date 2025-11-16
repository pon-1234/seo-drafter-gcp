import json

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
            primary_keyword="SEO対策",
            persona={"name": "テストユーザー"},
            intent="information",
            article_type="information",
            cta="資料DL",
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric="standard",
            reference_urls=[],
            output_format="html",
            notation_guidelines=None,
            word_count_range="2000-2400",
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-5",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )
        payload = {"primary_keyword": "SEO対策"}

        outline = pipeline.generate_outline(context, payload)

        assert "title" in outline
        assert "h2" in outline
        assert len(outline["h2"]) > 0
        assert "SEO対策" in outline["title"]
        assert outline.get("reader_note")
        assert outline["provisional_title"] == outline["title"]

    def test_generate_meta(self):
        """Test meta tag generation."""
        pipeline = DraftGenerationPipeline()
        payload = {"primary_keyword": "Python プログラミング"}
        context = PipelineContext(
            job_id="test-123",
            draft_id="draft-123",
            project_id="test-project",
            prompt_version="v1.0",
            primary_keyword="Python プログラミング",
            persona={},
            intent="information",
            article_type="information",
            cta="資料DL",
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric="standard",
            reference_urls=[],
            output_format="docs",
            notation_guidelines=None,
            word_count_range=None,
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-5",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )

        meta = pipeline.generate_meta(payload, context)

        assert "title_options" in meta
        assert "description_options" in meta
        assert "og" in meta
        assert len(meta["title_options"]) > 0

    def test_generate_meta_prefers_final_title(self):
        pipeline = DraftGenerationPipeline()
        payload = {"primary_keyword": "Python プログラミング"}
        context = PipelineContext(
            job_id="test-123",
            draft_id="draft-123",
            project_id="test-project",
            prompt_version="v1.0",
            primary_keyword="Python プログラミング",
            persona={},
            intent="information",
            article_type="information",
            cta="資料DL",
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric="standard",
            reference_urls=[],
            output_format="docs",
            notation_guidelines=None,
            word_count_range=None,
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-5",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )

        meta = pipeline.generate_meta(payload, context, final_title="完成タイトル")

        assert meta["final_title"] == "完成タイトル"
        assert meta["title_options"][0] == "完成タイトル"
        assert "完成タイトル" in meta["description_options"][0]
        assert meta["og"]["title"] == "完成タイトル"

    def test_finalize_title_uses_llm_output(self):
        pipeline = DraftGenerationPipeline()
        context = PipelineContext(
            job_id="job-1",
            draft_id="draft-1",
            project_id="proj",
            prompt_version="v1",
            primary_keyword="GA4",
            persona={},
            intent="information",
            article_type="information",
            cta=None,
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric=None,
            reference_urls=[],
            output_format="html",
            notation_guidelines=None,
            word_count_range=None,
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )
        outline = {"title": "仮タイトル", "provisional_title": "仮タイトル"}
        draft = {
            "sections": [
                {
                    "h2": "結論",
                    "paragraphs": [{"text": "GA4とGTMの連携手順を詳しく解説。"}],
                }
            ]
        }
        conclusion = {"main_conclusion": "GA4とGTMの組み合わせが最適", "supporting_points": ["理由1", "理由2"]}

        def fake_generate(prompt, **kwargs):
            return {"text": "Title: GA4とGTM連携で成果を出す実践ガイド"}

        pipeline._generate_grounded_content = fake_generate  # type: ignore[assignment]

        result = pipeline.finalize_title(context, outline, draft, conclusion=conclusion)

        assert result["final_title"] == "GA4とGTM連携で成果を出す実践ガイド"
        assert result["provisional_title"] == "仮タイトル"
        assert result["title_variants"] == []
        assert "title_rationale" in result

    def test_finalize_title_falls_back_to_provisional(self):
        pipeline = DraftGenerationPipeline()
        context = PipelineContext(
            job_id="job-1",
            draft_id="draft-1",
            project_id="proj",
            prompt_version="v1",
            primary_keyword="GA4",
            persona={},
            intent="information",
            article_type="information",
            cta=None,
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric=None,
            reference_urls=[],
            output_format="html",
            notation_guidelines=None,
            word_count_range=None,
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )
        outline = {"title": "仮タイトル", "provisional_title": "仮タイトル"}
        draft = {"sections": []}

        def fake_generate(prompt, **kwargs):
            return {"text": ""}

        pipeline._generate_grounded_content = fake_generate  # type: ignore[assignment]

        result = pipeline.finalize_title(context, outline, draft)

        assert result["final_title"] == "仮タイトル"
        assert result["provisional_title"] == "仮タイトル"

    def test_refine_draft_applies_refinement_payload(self):
        pipeline = DraftGenerationPipeline()
        context = PipelineContext(
            job_id="job-1",
            draft_id="draft-1",
            project_id="proj",
            prompt_version="v1",
            primary_keyword="GA4",
            persona={},
            intent="information",
            article_type="information",
            cta=None,
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric=None,
            reference_urls=[],
            output_format="html",
            notation_guidelines=None,
            word_count_range=None,
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )
        outline = {
            "title": "仮タイトル",
            "provisional_title": "仮タイトル",
            "h2": [{"text": "結論"}],
        }
        draft = {
            "sections": [
                {
                    "h2": "結論",
                    "paragraphs": [
                        {
                            "heading": "要点",
                            "text": "元の文章",
                            "citations": ["https://example.com"],
                        }
                    ],
                }
            ],
            "faq": [{"question": "Q", "answer": "A"}],
            "claims": [{"id": "claim-1", "text": "古い主張", "citations": []}],
        }
        refinement_payload = {
            "sections": [
                {
                    "h2": "結論",
                    "paragraphs": [
                        {"text": "推敲後の文章", "citations": ["https://example.com/new"]},
                    ],
                }
            ],
            "faq": [{"question": "更新後のQ", "answer": "更新後のA"}],
            "claims": [{"id": "claim-1", "text": "新しい主張", "citations": ["https://example.com/new"]}],
            "refinement_notes": ["冗長な表現を整理"],
        }

        def fake_generate(prompt, **kwargs):
            return {"text": json.dumps(refinement_payload, ensure_ascii=False)}

        pipeline._generate_grounded_content = fake_generate  # type: ignore[assignment]

        refined = pipeline.refine_draft(context, outline, draft)

        assert refined["sections"][0]["paragraphs"][0]["text"] == "推敲後の文章"
        assert refined["faq"][0]["answer"] == "更新後のA"
        assert refined["claims"][0]["text"] == "新しい主張"
        assert refined["refinement_notes"][0] == "冗長な表現を整理"

    def test_evaluate_quality(self):
        """Test quality evaluation."""
        pipeline = DraftGenerationPipeline()
        draft = {
            "draft": {
                "sections": [
                    {"paragraphs": [{"citations": []}]},
                    {"paragraphs": [{"citations": ["https://example.com"]}]},
                ]
            },
            "claims": [
                {"id": "claim-1", "text": "テキスト", "citations": []},
                {"id": "claim-2", "text": "テキスト2", "citations": ["https://example.com"]}
            ]
        }
        context = PipelineContext(
            job_id="test-123",
            draft_id="draft-123",
            project_id="test-project",
            prompt_version="v1.0",
            primary_keyword="テストキーワード",
            persona={},
            intent="information",
            article_type="information",
            cta=None,
            heading_mode="auto",
            heading_overrides=[],
            quality_rubric="standard",
            reference_urls=[],
            output_format="html",
            notation_guidelines=None,
            word_count_range=None,
            writer_persona={},
            preferred_sources=[],
            reference_media=[],
            project_template_id=None,
            prompt_layers={},
            llm_provider="openai",
            llm_model="gpt-5",
            llm_temperature=0.7,
            serp_snapshot=[],
            serp_gap_topics=[],
            expertise_level="intermediate",
            tone="formal",
        )

        quality = pipeline.evaluate_quality(draft, context)

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
            },
            "article_type": "comparison",
            "intended_cta": "資料請求",
            "quality_rubric": "standard",
            "heading_directive": {
                "mode": "manual",
                "headings": ["リード", "要点", "CTA"]
            },
            "reference_urls": ["https://example.com"],
            "output_format": "docs",
            "notation_guidelines": "英数字は半角",
            "word_count_range": "2000-2400"
        }

        def stub_generate(*args, **kwargs):
            return {
                "text": "セクション本文のダミーです。\n顧客便益: 行動につながります。",
                "citations": [{"url": "https://example.com"}],
            }

        pipeline._generate_grounded_content = stub_generate  # type: ignore[assignment]

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
        assert result["outline"].get("reader_note")

        # Verify draft structure
        assert "sections" in result["draft"]
        assert "faq" in result["draft"]

        # Verify metadata
        assert result["metadata"]["job_id"] == "test-job-123"
        assert result["metadata"]["draft_id"] == "test-draft-123"
        assert result["metadata"]["article_type"] == "comparison"
        assert result["metadata"]["provisional_title"] == result["outline"]["title"]
        assert result["metadata"]["final_title"]
        assert result["meta"].get("final_title") == result["metadata"]["final_title"]
