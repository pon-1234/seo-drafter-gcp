import logging

from fastapi import FastAPI, HTTPException

from .tasks.pipeline import DraftGenerationPipeline

app = FastAPI(title="SEO Drafter Worker", version="0.1.0")
logger = logging.getLogger(__name__)


@app.post("/run-pipeline")
def run_pipeline(payload: dict) -> dict:
    pipeline = DraftGenerationPipeline()
    try:
        result = pipeline.run(payload)
    except Exception as exc:
        job_id = payload.get("job_id", "unknown")
        logger.exception("Pipeline failed for job %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail=f"pipeline_failed:{job_id}") from exc
    return {"status": "completed", "result": result}


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "ok"}
