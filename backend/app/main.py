from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
import httpx
from app.config import get_settings
from app.db import SessionLocal, engine
from app.services.seed import seed
from app.services.catalog import bootstrap_live_catalog
from app.api.routes import router
from app.services.sso import router as sso_router
from app.models import PipelineRun, PipelineStep, now

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app):
    cfg = get_settings()
    with SessionLocal() as db:
        if cfg.seed_demo:
            seed(db)
        elif cfg.bootstrap_live_catalog:
            bootstrap_live_catalog(db)
        # Single worker deployment: recover runs interrupted by process restart.
        for run in db.scalars(select(PipelineRun).where(PipelineRun.status.in_(["Pending", "Running"]))):
            run.status = "Failed"
            run.error = "Worker restarted before completion. Retry this run."
            run.ended_at = now()
            for step in db.scalars(
                select(PipelineStep).where(PipelineStep.run_id == run.id, PipelineStep.status.in_(["Pending", "Running"]))
            ):
                step.status = "Failed" if step.status == "Running" else "Skipped"
                step.error = run.error
        db.commit()
    scheduler = None
    if cfg.enable_scheduler:
        from app.tasks.scheduler import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="TechSignal — AI-Powered Emerging Technology Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
    description="Evidence-grounded emerging technology scouting, signals, radar assessments and briefings.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix="/api")
app.include_router(sso_router, prefix="/api")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Duplicate record or invalid relationship; no changes were saved"})


@app.exception_handler(ValueError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)[:500]})


@app.exception_handler(httpx.HTTPError)
async def provider_error(request, exc):
    return JSONResponse(
        status_code=502, content={"detail": "External provider request failed; verify credentials and provider availability"}
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "techsignal"}


@app.get("/health/ready")
def ready():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}
