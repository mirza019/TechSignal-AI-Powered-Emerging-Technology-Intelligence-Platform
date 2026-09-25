import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from app.db import SessionLocal
from app.config import get_settings
from app.models import User, Technology
from app.pipelines.runner import create_run, execute_run
from app.analytics.scoring import calculate_all
from app.ai.retrieval import generate_embeddings
from app.ai.service import analyze
from app.services.reports import generate_report
from app.schemas import ReportInput
from app.services.data_mode import data_mode

logger = logging.getLogger(__name__)


def ingest(provider):
    with SessionLocal() as db:
        if provider != "demo" and data_mode(db):
            return
        if provider == "demo" and not data_mode(db):
            provider = "openalex"
        run = create_run(db, provider, None, 10)
        run_id = run.id
    execute_run(run_id)


def maintenance():
    with SessionLocal.begin() as db:
        generate_embeddings(db)
        calculate_all(db, data_mode(db))


def reassess():
    with SessionLocal.begin() as db:
        actor = db.scalar(select(User).where(User.role == "Admin", User.active.is_(True)))
        if actor:
            for technology in db.scalars(select(Technology).where(Technology.archived.is_(False)).limit(15)):
                analyze(db, technology, actor, data_mode(db))


def weekly_report():
    with SessionLocal.begin() as db:
        actor = db.scalar(select(User).where(User.role == "Admin", User.active.is_(True)))
        if actor:
            generate_report(db, ReportInput(), actor, data_mode(db))


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})
    cfg = get_settings()
    scheduler.add_job(ingest, "cron", hour=2, args=["demo" if cfg.demo_mode else "openalex"], id="academic-ingestion")
    if not cfg.demo_mode and cfg.enable_gdelt:
        scheduler.add_job(ingest, "cron", hour=3, args=["gdelt"], id="news-ingestion")
    if not cfg.demo_mode and cfg.enable_web_scraping:
        scheduler.add_job(ingest, "cron", hour=4, args=["web"], id="web-refresh")
    scheduler.add_job(maintenance, "cron", hour=5, id="embeddings-and-signals")
    scheduler.add_job(reassess, "cron", day_of_week="sun", hour=6, id="ai-reassessment")
    scheduler.add_job(weekly_report, "cron", day_of_week="mon", hour=7, id="weekly-report")
    scheduler.start()
    return scheduler
