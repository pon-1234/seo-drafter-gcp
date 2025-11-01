from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from ..core.config import get_settings
from ..models import (
    BenchmarkRun,
    BenchmarkVariantResult,
    DraftQualitySignals,
    JobCreate,
    LLMConfig,
    Persona,
    WriterPersona,
)
from ..services.firestore import FirestoreRepository

try:  # Import the worker pipeline directly for local execution
    from worker.app.tasks.pipeline import DraftGenerationPipeline
except ImportError as exc:  # pragma: no cover - worker package may not be on PYTHONPATH
    DraftGenerationPipeline = None  # type: ignore
    PIPELINE_IMPORT_ERROR = exc
else:
    PIPELINE_IMPORT_ERROR = None

logger = logging.getLogger(__name__)


class BenchmarkService:
    """Orchestrates multi-LLM benchmark runs by invoking the worker pipeline."""

    def __init__(self, store: FirestoreRepository) -> None:
        self.store = store
        self.settings = get_settings()

    def run(
        self,
        payload: JobCreate,
        *,
        persona: Persona,
        writer_persona: Optional[WriterPersona],
    ) -> BenchmarkRun:
        if not payload.benchmark_plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="benchmark_plan must contain at least one LLM configuration.",
            )

        if not DraftGenerationPipeline or PIPELINE_IMPORT_ERROR:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Draft pipeline is not available in the current environment.",
            )

        run_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        prompt_version = payload.prompt_version or self.settings.default_prompt_version

        variants: List[BenchmarkVariantResult] = []
        aggregate = {
            "total_variants": len(payload.benchmark_plan),
        }

        for index, llm_cfg in enumerate(payload.benchmark_plan):
            variant_id = f"{run_id}-{index + 1}"
            job_id = str(uuid.uuid4())
            draft_id = str(uuid.uuid4())
            pipeline_payload = self._build_pipeline_payload(
                payload,
                persona=persona,
                writer_persona=writer_persona,
                job_id=job_id,
                draft_id=draft_id,
                llm_config=llm_cfg,
                prompt_version=prompt_version,
            )

            pipeline = DraftGenerationPipeline()
            started_at = time.perf_counter()
            try:
                bundle = pipeline.run(pipeline_payload)
            except Exception as exc:  # pragma: no cover - runtime failures depend on external APIs
                logger.exception("Benchmark variant failed (provider=%s model=%s): %s", llm_cfg.provider, llm_cfg.model, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Benchmark generation failed for provider={llm_cfg.provider} model={llm_cfg.model}",
                ) from exc
            elapsed = time.perf_counter() - started_at

            variant_result = self._summarise_variant(
                llm_cfg=llm_cfg,
                bundle=bundle,
                draft_id=draft_id,
                processing_seconds=elapsed,
            )
            variants.append(variant_result)

        run = BenchmarkRun(
            id=run_id,
            primary_keyword=payload.primary_keyword,
            article_type=payload.article_type,
            intent=payload.intent,
            prompt_version=prompt_version,
            created_at=created_at,
            variants=variants,
            aggregate_metrics=aggregate,
        )

        self._persist(run)
        return run

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _build_pipeline_payload(
        self,
        payload: JobCreate,
        *,
        persona: Persona,
        writer_persona: Optional[WriterPersona],
        job_id: str,
        draft_id: str,
        llm_config: LLMConfig,
        prompt_version: str,
    ) -> Dict:
        base_payload = payload.model_dump()
        base_payload.update({
            "job_id": job_id,
            "draft_id": draft_id,
            "project_id": self.settings.project_id,
            "prompt_version": prompt_version,
            "persona": persona.model_dump(),
            "writer_persona": writer_persona.model_dump() if writer_persona else None,
            "llm": llm_config.model_dump(exclude_none=True),
        })
        # Remove benchmark plan itself to avoid recursive execution
        base_payload["benchmark_plan"] = []
        return base_payload

    def _summarise_variant(
        self,
        *,
        llm_cfg: LLMConfig,
        bundle: Dict,
        draft_id: str,
        processing_seconds: float,
    ) -> BenchmarkVariantResult:
        draft_payload = bundle.get("draft") or {}
        quality_payload = bundle.get("quality") or {}
        metadata = bundle.get("metadata") or {}

        word_count, citation_count, excerpt = self._extract_draft_signals(draft_payload)
        quality_signals = DraftQualitySignals.model_validate(quality_payload)
        style_flags = quality_signals.style_violations

        return BenchmarkVariantResult(
            variant_id=str(uuid.uuid4()),
            llm=llm_cfg,
            draft_id=draft_id,
            processing_seconds=processing_seconds,
            word_count=word_count,
            citation_count=citation_count,
            quality=quality_signals,
            style_flags=style_flags,
            metadata=metadata,
            excerpt=excerpt,
        )

    @staticmethod
    def _extract_draft_signals(draft_payload: Dict) -> Tuple[int, int, str]:
        sections = draft_payload.get("sections", []) if isinstance(draft_payload, dict) else []
        words = 0
        citations = set()
        paragraphs_preview: List[str] = []
        for section in sections:
            for paragraph in section.get("paragraphs", []):
                text = paragraph.get("text", "")
                words += len(text.split())
                for citation in paragraph.get("citations", []):
                    if isinstance(citation, str):
                        citations.add(citation)
                    elif isinstance(citation, dict):
                        uri = citation.get("uri") or citation.get("url")
                        if uri:
                            citations.add(uri)
                if len(paragraphs_preview) < 3 and text:
                    paragraphs_preview.append(text.strip())
        excerpt = "\n\n".join(paragraphs_preview)
        return words, len(citations), excerpt

    def _persist(self, run: BenchmarkRun) -> None:
        try:
            payload = json.loads(run.model_dump_json())
            self.store.save_benchmark_run(run.id, payload)
        except Exception as exc:  # pragma: no cover - persistence may fail on GCP
            logger.exception("Failed to persist benchmark run %s: %s", run.id, exc)
