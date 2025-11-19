import pytest

from app.tasks.pipeline import DraftGenerationPipeline, PipelineContext


class DummyRewriter:
    def __init__(self) -> None:
        self.calls = 0

    def rewrite_sections(self, sections, **kwargs):
        self.calls += 1
        return sections


def _build_context() -> PipelineContext:
    return PipelineContext(
        job_id="test-job",
        draft_id="draft-xyz",
        project_id="test-project",
        prompt_version="v1",
        primary_keyword="CMP 導入",
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
        llm_model="gpt-5",
        llm_temperature=0.5,
        serp_snapshot=[],
        serp_gap_topics=[],
        expertise_level="intermediate",
        tone="formal",
    )


def test_style_rewrite_metrics_collected(monkeypatch):
    pipeline = DraftGenerationPipeline()
    pipeline.ai_gateway = object()
    dummy_rewriter = DummyRewriter()
    pipeline.style_rewriter = dummy_rewriter
    context = _build_context()
    draft = {
        "sections": [
            {
                "h2": "背景と課題",
                "paragraphs": [{"text": "アトリビューション/リフト/MMMを整理する。", "citations": []}],
            }
        ]
    }
    monkeypatch.setenv("ENABLE_STYLE_REWRITE", "true")
    monkeypatch.setenv("STYLE_REWRITE_SAMPLE_ONLY", "false")

    diagnostics = pipeline._maybe_apply_style_rewrite(draft, context)

    assert diagnostics["style_rewritten"] is True
    metrics = diagnostics["style_rewrite_metrics"]
    assert metrics["paragraph_count"] == 1
    assert metrics["elapsed_seconds"] >= 0
    assert dummy_rewriter.calls == 1

    monkeypatch.delenv("ENABLE_STYLE_REWRITE", raising=False)
    monkeypatch.delenv("STYLE_REWRITE_SAMPLE_ONLY", raising=False)
