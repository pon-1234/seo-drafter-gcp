from fastapi import FastAPI

from .tasks.pipeline import DraftGenerationPipeline

app = FastAPI(title="SEO Drafter Worker", version="0.1.0")


@app.post("/run-pipeline")
def run_pipeline(payload: dict) -> dict:
    pipeline = DraftGenerationPipeline()
    result = pipeline.run(payload)
    return {"status": "completed", "result": result}


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "ok"}
