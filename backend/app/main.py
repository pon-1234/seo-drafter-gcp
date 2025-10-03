from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .core.config import get_settings
from .core.logger import configure_logging  # noqa: F401

settings = get_settings()

app = FastAPI(title="SEO Drafter API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "ok", "project_id": settings.project_id}
