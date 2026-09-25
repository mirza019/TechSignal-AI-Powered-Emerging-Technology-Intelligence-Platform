import logging
import httpx
from sqlalchemy import select
from app.db import SessionLocal
from app.config import get_settings
from app.providers.optional import SemanticScholarProvider
from app.models import PipelineRun, PipelineStep, StagedEvidence, Technology, Keyword, WebSource, now
from app.schemas import EvidenceInput
from app.services.seed import STEPS
from app.providers.demo import DemoProvider
from app.providers.openalex import OpenAlexProvider
from app.providers.gdelt import GDELTProvider
from app.scrapers.public import PublicScraper
from app.repositories.evidence import upsert_evidence
from app.ai.retrieval import generate_embeddings
from app.analytics.scoring import calculate_all

logger = logging.getLogger(__name__)


def create_run(db, provider, technology_id, limit, parent=None):
    run = PipelineRun(
        provider=provider,
        technology_id=technology_id,
        limit=limit,
        parent_run_id=parent.id if parent else None,
        retry_count=parent.retry_count + 1 if parent else 0,
    )
    db.add(run)
    db.flush()
    for i, name in enumerate(STEPS):
        db.add(PipelineStep(run_id=run.id, name=name, position=i, retry_count=run.retry_count))
    db.commit()
    return run


def execute_run(run_id, session_factory=SessionLocal, provider_override=None, fail_before_commit=False):
    """Collection is staged durably; all production mutations share one transaction.

    Separate diagnostic transactions preserve failed-run logs on rollback. A retry
    creates a linked new run and replays the bounded idempotent operation.
    """
    with session_factory() as db:
        run = db.get(PipelineRun, run_id)
        run.status = "Running"
        steps = db.scalars(select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.position)).all()
        run_provider, limit, technology_id = run.provider, run.limit, run.technology_id
        steps[0].status = "Running"
        steps[0].started_at = now()
        db.commit()
        technologies = db.scalars(
            select(Technology).where(Technology.archived.is_(False), *([Technology.id == technology_id] if technology_id else []))
        ).all()
        if run_provider != "web" and not technologies:
            raise ValueError("No active technologies matched this pipeline run")
        raw_records = []
        collection_warnings = []
        rate_limited_queries = 0
        try:
            if run_provider == "web":
                scraper = PublicScraper()
                sources = db.scalars(
                    select(WebSource)
                    .where(WebSource.enabled.is_(True), *([WebSource.technology_id == technology_id] if technology_id else []))
                    .limit(limit)
                ).all()
                for source in sources:
                    raw_records.append(scraper.collect_page(source.url, source.technology_id, source.organization_id))
            else:
                provider = provider_override or {"demo": DemoProvider, "openalex": OpenAlexProvider, "gdelt": GDELTProvider}[run_provider]()
                for technology in technologies:
                    keywords = list(db.scalars(select(Keyword.keyword).where(Keyword.technology_id == technology.id)))
                    query = (
                        "(" + " OR ".join('"' + k.replace('"', "") + '"' for k in keywords[:4]) + ")"
                        if run_provider == "gdelt"
                        else " OR ".join(keywords[:4]) or technology.name
                    )
                    try:
                        raw_records.extend(provider.collect(technology.id, query, limit))
                    except (httpx.HTTPError, RuntimeError) as exc:
                        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                        rate_limited_queries += int(status == 429)
                        detail = f"HTTP {status}" if status else type(exc).__name__
                        collection_warnings.append(f"{technology.name}: {detail}")
                        logger.warning(
                            "Provider query skipped after bounded retries",
                            extra={"run_id": run_id, "provider": run_provider, "technology_id": technology.id},
                        )
                if collection_warnings and not raw_records:
                    if rate_limited_queries == len(collection_warnings):
                        message = (
                            f"{run_provider.upper() if run_provider == 'gdelt' else run_provider.title()} temporarily deferred "
                            "all requests because the provider returned HTTP 429. No data changed. "
                            "Retry later or wait for the next scheduled collection window."
                        )
                        run.status = "Deferred"
                        run.error = message
                        run.ended_at = now()
                        steps[0].status = "Deferred"
                        steps[0].error = message
                        steps[0].ended_at = now()
                        for step in steps[1:]:
                            step.status = "Skipped"
                            step.error = "Collection was deferred before validation; no data changed"
                        db.commit()
                        return
                    raise RuntimeError(
                        f"{run_provider.title()} did not return data after bounded retries. "
                        "The public service may be rate-limited; retry one technology later."
                    )
            if get_settings().enable_semantic_scholar and run_provider == "openalex":
                enrichment = SemanticScholarProvider()
                for record in raw_records:
                    if isinstance(record, EvidenceInput) and record.doi:
                        result = enrichment.enrich(record.doi)
                        if result:
                            record.metadata_json["semantic_scholar"] = result
            for record in raw_records:
                payload = record.model_dump(mode="json") if isinstance(record, EvidenceInput) else record
                db.add(StagedEvidence(run_id=run_id, payload=payload))
            steps[0].status = "Successful"
            steps[0].processed = len(raw_records)
            if collection_warnings:
                noun = "query" if len(collection_warnings) == 1 else "queries"
                steps[0].error = f"Completed with {len(collection_warnings)} skipped {noun} after provider retries."
            steps[0].ended_at = now()
            db.commit()
            staged = db.scalars(select(StagedEvidence).where(StagedEvidence.run_id == run_id)).all()
            validated = []
            for item in staged:
                try:
                    record = EvidenceInput.model_validate(item.payload)
                    if not db.get(Technology, record.technology_id):
                        raise ValueError("Missing technology mapping")
                    if run_provider != "demo" and record.is_demo:
                        raise ValueError("Live provider returned synthetic evidence")
                    validated.append(record)
                except ValueError as exc:
                    item.valid = False
                    item.error = str(exc)[:1000]
            rejected = len(staged) - len(validated)
            for step in steps[1:3]:
                step.status = "Successful"
                step.started_at = now()
                step.ended_at = now()
                step.processed = len(staged)
                step.rejected = rejected
            db.commit()
            if rejected:
                raise ValueError(f"Quality gate rejected {rejected} records; no production merge performed")
            # Commit any read-only session transaction before the atomic merge.
            db.rollback()
            inserted = updated = 0
            with db.begin():
                # Serialize concurrent production merges on PostgreSQL.
                if db.bind.dialect.name == "postgresql":
                    from sqlalchemy import text

                    db.execute(text("SELECT pg_advisory_xact_lock(8216701)"))
                for record in validated:
                    _, is_new = upsert_evidence(db, record, run_id)
                    inserted += int(is_new)
                    updated += int(not is_new)
                db.flush()
                generate_embeddings(db)
                calculate_all(db, run_provider == "demo")
                if run_provider == "web":
                    for source in sources:
                        source.last_checked = now()
                if fail_before_commit:
                    raise RuntimeError("Injected failure before commit")
                for i, step in enumerate(steps[3:], 3):
                    step.status = "Successful"
                    step.started_at = now()
                    step.ended_at = now()
                    step.processed = len(validated)
                    if step.name == "Database Commit":
                        step.inserted, step.updated = inserted, updated
                run.status = "Successful"
                run.ended_at = now()
        except Exception as exc:
            db.rollback()
            logger.exception("Pipeline failed", extra={"run_id": run_id})
            run = db.get(PipelineRun, run_id)
            run.status = "Failed"
            # Do not persist exception URLs that might contain credentials.
            run.error = f"{type(exc).__name__}: " + (
                str(exc)[:500]
                if isinstance(exc, (ValueError, RuntimeError))
                else "Provider or database operation failed; see local server diagnostics"
            )
            run.ended_at = now()
            steps = db.scalars(select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.position)).all()
            failed_set = False
            for step in steps:
                if step.status in ("Pending", "Running"):
                    step.status = "Failed" if not failed_set else "Skipped"
                    step.error = run.error if not failed_set else "Not committed because run failed"
                    step.ended_at = now()
                    failed_set = True
            db.commit()
