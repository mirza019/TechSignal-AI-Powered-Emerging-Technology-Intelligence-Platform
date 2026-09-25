from collections import Counter
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Response, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.config import get_settings
from app.models import (
    User,
    Domain,
    Horizon,
    Technology,
    Keyword,
    Evidence,
    Organization,
    Startup,
    Assessment,
    RadarHistory,
    AIAnalysis,
    Signal,
    PipelineRun,
    PipelineStep,
    StagedEvidence,
    Report,
    AuditLog,
    SystemSetting,
    WebSource,
    now,
)
from app.schemas import (
    Login,
    TechnologyInput,
    ReviewInput,
    PipelineInput,
    QueryInput,
    AnalysisInput,
    OrganizationInput,
    ReportInput,
    HorizonInput,
)
from app.services.auth import authenticate, token_for, current_user, require, limiter, passwords
from app.services.views import technology_view, technology_detail, organization_view
from app.services.reports import generate_report, render_pdf, METHODOLOGY
from app.utils.records import as_dict, normalize_name
from app.repositories.evidence import evidence_for
from app.pipelines.runner import create_run, execute_run
from app.ai.service import analyze, answer
from app.analytics.scoring import calculate_all, DEFAULT_WEIGHTS
from app.services.data_mode import data_mode

router = APIRouter()


def mode(db):
    return data_mode(db)


def get_or_404(db, model, id):
    value = db.get(model, id)
    if value is None:
        raise HTTPException(404, "Record not found")
    return value


def audit(db, actor, action, entity_id, before=None, after=None):
    db.add(AuditLog(actor_id=actor.id, action=action, entity_id=entity_id, before=before or {}, after=after or {}))


@router.post("/auth/login")
def login(body: Login, request: Request, db: Session = Depends(get_db)):
    limiter.check("login:" + (request.client.host if request.client else "unknown"), 10)
    user = authenticate(db, body.email, body.password)
    return {
        "access_token": token_for(user),
        "token_type": "bearer",
        "user": {k: v for k, v in as_dict(user).items() if k != "password_hash"},
    }


class DemoLoginInput(BaseModel):
    role: Literal["Admin", "Analyst", "Viewer"] = "Viewer"


@router.post("/auth/demo")
def demo_login(body: DemoLoginInput, request: Request, db: Session = Depends(get_db)):
    cfg = get_settings()
    if not (cfg.public_demo and cfg.seed_demo and cfg.environment != "production"):
        raise HTTPException(404, "Public demo sign-in is not enabled")
    limiter.check("demo-login:" + (request.client.host if request.client else "unknown"), 20)
    user = db.scalar(
        select(User).where(User.email == f"{body.role.lower()}@techsignal.local", User.active.is_(True))
    )
    if not user:
        raise HTTPException(503, "Demo workspace is not ready")
    return {
        "access_token": token_for(user),
        "token_type": "bearer",
        "user": {k: v for k, v in as_dict(user).items() if k != "password_hash"},
    }


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {k: v for k, v in as_dict(user).items() if k != "password_hash"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(current_user)):
    technologies = db.scalars(select(Technology).where(Technology.archived.is_(False))).all()
    signals = db.scalars(select(Signal).where(Signal.is_demo == mode(db)).order_by(Signal.created_at.desc())).all()
    evidence = db.scalars(select(Evidence).where(Evidence.is_demo == mode(db))).all()
    orgs = db.scalars(select(Organization).where(Organization.is_demo == mode(db))).all()
    latest_by_technology = {}
    for signal in signals:
        latest_by_technology.setdefault(signal.technology_id, signal)
    return {
        "is_demo": mode(db),
        "kpis": {
            "technologies": len(technologies),
            "signals": len(latest_by_technology),
            "emerging": sum(s.level == "Emerging" for s in latest_by_technology.values()),
            "papers": sum(e.source_type == "paper" for e in evidence),
            "startups": sum(o.kind == "startup" for o in orgs),
            "institutions": sum(o.kind == "institution" for o in orgs),
            "awaiting_review": sum(not t.approved for t in technologies),
        },
        "horizons": dict(Counter(t.horizon for t in technologies)),
        "technologies": [technology_view(db, t, mode(db)) for t in technologies],
        "trend": dict(sorted(Counter(e.published_at.strftime("%Y-%m") for e in evidence).items())),
        "sources": dict(Counter(e.source_type for e in evidence)),
        "recent_activity": [as_dict(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10))],
        "signals": [as_dict(s) for s in list(latest_by_technology.values())[:8]],
    }


@router.get("/technologies")
def technologies(q: str = "", domain: str = "", archived: bool = False, db: Session = Depends(get_db), user=Depends(current_user)):
    stmt = select(Technology).where(Technology.archived == archived)
    if q:
        stmt = stmt.where(Technology.name.ilike("%" + q + "%"))
    if domain:
        stmt = stmt.where(Technology.domain == domain)
    return [technology_view(db, t, mode(db)) for t in db.scalars(stmt.order_by(Technology.name))]


@router.get("/technologies/{id}")
def technology(id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    return technology_detail(db, get_or_404(db, Technology, id), mode(db))


def save_technology(db, body, actor, existing=None):
    if not db.get(Domain, body.domain):
        raise HTTPException(422, "Unknown domain")
    before = as_dict(existing) if existing else {}
    if existing:
        before["keywords"] = list(db.scalars(select(Keyword.keyword).where(Keyword.technology_id == existing.id)))
    data = body.model_dump(exclude={"keywords"})
    technology = existing or Technology(is_demo=mode(db))
    for key, value in data.items():
        setattr(technology, key, value)
    db.add(technology)
    db.flush()
    for keyword in db.scalars(select(Keyword).where(Keyword.technology_id == technology.id)):
        db.delete(keyword)
    db.flush()
    for keyword in set([body.name] + body.keywords):
        if not keyword.strip() or len(keyword) > 200:
            raise HTTPException(422, "Keywords must contain 1–200 characters")
        db.add(Keyword(technology_id=technology.id, keyword=keyword.strip()))
    audit(
        db,
        actor,
        "technology.updated" if existing else "technology.created",
        technology.id,
        before,
        {**as_dict(technology), "keywords": body.keywords},
    )
    db.commit()
    return technology_view(db, technology, mode(db))


@router.post("/technologies", status_code=201)
def create_technology(body: TechnologyInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    return save_technology(db, body, user)


@router.put("/technologies/{id}")
def update_technology(id: str, body: TechnologyInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    return save_technology(db, body, user, get_or_404(db, Technology, id))


@router.post("/technologies/{id}/review")
def review(id: str, body: ReviewInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    technology = get_or_404(db, Technology, id)
    valid_ids = set(db.scalars(evidence_for(db, id, mode(db)).with_only_columns(Evidence.id)))
    if not set(body.evidence_ids) <= valid_ids:
        raise HTTPException(422, "Every assessment citation must belong to this technology and data mode")
    analysis = get_or_404(db, AIAnalysis, body.analysis_id) if body.analysis_id else None
    if analysis and (analysis.technology_id != id or analysis.is_demo != mode(db)):
        raise HTTPException(422, "Analysis does not belong to this technology/data mode")
    before = as_dict(technology)
    db.add(Assessment(technology_id=id, actor_id=user.id, **body.model_dump()))
    db.add(RadarHistory(technology_id=id, actor_id=user.id, old_horizon=technology.horizon, new_horizon=body.horizon, reason=body.notes))
    technology.horizon, technology.maturity, technology.confidence = body.horizon, body.maturity, body.confidence
    technology.analyst_notes = body.notes
    technology.approved, technology.last_reviewed = True, now()
    technology.is_demo = mode(db)
    if analysis:
        analysis.approval_status = "Approved"
    audit(db, user, "assessment.approved", id, before, as_dict(technology))
    from app.analytics.scoring import calculate

    calculate(db, technology, mode(db))
    db.commit()
    return technology_detail(db, technology, mode(db))


@router.get("/radar")
def radar(db: Session = Depends(get_db), user=Depends(current_user)):
    return {
        "methodology": METHODOLOGY,
        "horizons": [as_dict(h) for h in db.scalars(select(Horizon).order_by(Horizon.display_order))],
        "technologies": [technology_view(db, t, mode(db)) for t in db.scalars(select(Technology).where(Technology.archived.is_(False)))],
        "history": [as_dict(h) for h in db.scalars(select(RadarHistory).order_by(RadarHistory.created_at.desc()).limit(250))],
    }


@router.get("/signals")
def signals(db: Session = Depends(get_db), user=Depends(current_user)):
    return [as_dict(s) for s in db.scalars(select(Signal).where(Signal.is_demo == mode(db)).order_by(Signal.created_at.desc()).limit(500))]


@router.get("/papers")
@router.get("/evidence")
def evidence(
    request: Request,
    technology_id: str | None = None,
    q: str = "",
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    stmt = evidence_for(db, technology_id, mode(db))
    if request.url.path.endswith("/papers"):
        stmt = stmt.where(Evidence.source_type == "paper")
    if q:
        stmt = stmt.where(Evidence.title.ilike("%" + q + "%"))
    return [as_dict(e) for e in db.scalars(stmt.order_by(Evidence.published_at.desc()).limit(limit))]


@router.get("/startups")
@router.get("/institutions")
def organizations(request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    kind = "startup" if request.url.path.endswith("/startups") else "institution"
    result = [
        organization_view(db, o, mode(db))
        for o in db.scalars(select(Organization).where(Organization.kind == kind, Organization.is_demo == mode(db)))
    ]
    return sorted(result, key=lambda o: (-o["publication_count"], o["name"]))


@router.get("/organizations/{id}")
def organization(id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    return organization_view(db, get_or_404(db, Organization, id), mode(db))


def save_startup(db, body, user, existing=None):
    if body.technology_id and not db.get(Technology, body.technology_id):
        raise HTTPException(422, "Unknown technology")
    if any(not db.get(Domain, d) for d in body.domains):
        raise HTTPException(422, "Unknown domain")
    before = as_dict(existing) if existing else {}
    if existing and db.get(Startup, existing.id):
        before.update(as_dict(db.get(Startup, existing.id)))
    org_fields = {"name", "website", "country", "city", "description", "domains", "technology_id", "analyst_notes", "confidence"}
    org = existing or Organization(kind="startup", is_demo=mode(db))
    for key, value in body.model_dump(include=org_fields).items():
        setattr(org, key, value)
    org.normalized_name = normalize_name(org.name)
    org.embedding = None
    db.add(org)
    db.flush()
    startup = db.get(Startup, org.id) or Startup(organization_id=org.id)
    for key, value in body.model_dump(exclude=org_fields).items():
        setattr(startup, key, value)
    db.add(startup)
    audit(db, user, "startup.updated" if existing else "startup.created", org.id, before, {**as_dict(org), **as_dict(startup)})
    db.commit()
    return organization_view(db, org, mode(db))


@router.post("/startups", status_code=201)
def create_startup(body: OrganizationInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    return save_startup(db, body, user)


@router.put("/startups/{id}")
def update_startup(id: str, body: OrganizationInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    org = get_or_404(db, Organization, id)
    if org.kind != "startup":
        raise HTTPException(422, "Record is not a startup")
    return save_startup(db, body, user, org)


@router.post("/pipeline/run", status_code=202)
def pipeline_run(body: PipelineInput, tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    limiter.check("pipeline:" + user.id, 5)
    if body.technology_id:
        get_or_404(db, Technology, body.technology_id)
    if body.provider == "demo" and not mode(db):
        raise HTTPException(422, "Demo ingestion is disabled in live mode")
    if body.provider != "demo" and mode(db):
        raise HTTPException(422, "Set DEMO_MODE=false before live ingestion; demo records stay isolated")
    run = create_run(db, body.provider, body.technology_id, body.limit)
    audit(db, user, "pipeline.requested", run.id, after=body.model_dump())
    db.commit()
    tasks.add_task(execute_run, run.id)
    return as_dict(run)


@router.get("/pipeline/runs")
def pipeline_runs(db: Session = Depends(get_db), user=Depends(current_user)):
    return [as_dict(r) for r in db.scalars(select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(50))]


@router.get("/pipeline/runs/{id}")
def pipeline_detail(id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    run = get_or_404(db, PipelineRun, id)
    return {
        **as_dict(run),
        "steps": [as_dict(s) for s in db.scalars(select(PipelineStep).where(PipelineStep.run_id == id).order_by(PipelineStep.position))],
    }


@router.post("/pipeline/runs/{id}/retry", status_code=202)
def retry_pipeline(id: str, tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    parent = get_or_404(db, PipelineRun, id)
    if parent.status not in ("Failed", "Deferred"):
        raise HTTPException(409, "Only failed or deferred runs may be retried")
    limiter.check("pipeline:" + user.id, 5)
    run = create_run(db, parent.provider, parent.technology_id, parent.limit, parent)
    audit(db, user, "pipeline.retried", run.id, after={"parent_run_id": parent.id})
    db.commit()
    tasks.add_task(execute_run, run.id)
    return as_dict(run)


@router.post("/ai/technology-analysis")
def analysis(body: AnalysisInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    limiter.check("ai:" + user.id)
    result = analyze(db, get_or_404(db, Technology, body.technology_id), user, mode(db))
    audit(db, user, "analysis.generated", result.id)
    db.commit()
    return as_dict(result)


@router.post("/ai/query")
def query(body: QueryInput, db: Session = Depends(get_db), user=Depends(current_user)):
    limiter.check("ai:" + user.id)
    if body.technology_id:
        get_or_404(db, Technology, body.technology_id)
    output, evidence, record = answer(db, body.query, user, body.technology_id, mode(db))
    db.commit()
    return {**output.model_dump(), "sources": [as_dict(e) for e in evidence], "analysis_id": record.id, "model": record.model}


@router.get("/reports")
def reports(db: Session = Depends(get_db), user=Depends(current_user)):
    return [as_dict(r) for r in db.scalars(select(Report).where(Report.is_demo == mode(db)).order_by(Report.created_at.desc()))]


@router.post("/reports/generate", status_code=201)
@router.post("/briefings/startup", status_code=201)
@router.post("/briefings/institution", status_code=201)
@router.post("/briefings/technology", status_code=201)
def report_generate(body: ReportInput, db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    limiter.check("reports:" + user.id, 6)
    if body.technology_id:
        get_or_404(db, Technology, body.technology_id)
    if body.organization_id:
        org = get_or_404(db, Organization, body.organization_id)
        if org.is_demo != mode(db):
            raise HTTPException(422, "Organization belongs to a different data mode")
    if body.kind in ("Startup Briefing", "Research Institution Briefing") and not body.organization_id:
        raise HTTPException(422, "Select an organization for the briefing")
    if body.kind == "Technology Opportunity Report" and not body.technology_id:
        raise HTTPException(422, "Select a technology")
    report = generate_report(db, body, user, mode(db))
    audit(db, user, "report.generated", report.id)
    db.commit()
    return as_dict(report)


@router.get("/reports/{id}/export")
def export_report(id: str, format: Literal["pdf", "md"] = "pdf", db: Session = Depends(get_db), user=Depends(current_user)):
    report = get_or_404(db, Report, id)
    content = render_pdf(report) if format == "pdf" else report.markdown.encode()
    return Response(
        content,
        media_type="application/pdf" if format == "pdf" else "text/markdown",
        headers={"Content-Disposition": f'attachment; filename="techsignal-{report.id}.{format}"'},
    )


@router.get("/settings")
def settings(db: Session = Depends(get_db), user=Depends(current_user)):
    cfg = get_settings()
    return {
        "methodology": METHODOLOGY,
        "is_demo": mode(db),
        "horizons": [as_dict(h) for h in db.scalars(select(Horizon).order_by(Horizon.display_order))],
        "domains": [as_dict(d) for d in db.scalars(select(Domain))],
        "score_weights": db.get(SystemSetting, "score_weights").value if db.get(SystemSetting, "score_weights") else DEFAULT_WEIGHTS,
        "signal_rules": db.get(SystemSetting, "signal_rules").value if db.get(SystemSetting, "signal_rules") else {},
        "providers": {
            "gemini": bool(cfg.gemini_api_key),
            "openalex": True,
            "gdelt": cfg.enable_gdelt,
            "semantic_scholar": cfg.enable_semantic_scholar,
            "epo": False,
            "web": cfg.enable_web_scraping,
        },
        "scheduler_enabled": cfg.enable_scheduler,
        "embedding_model": cfg.embedding_model
        if cfg.embedding_backend == "sentence-transformers"
        else "local-hash-word-bigram-v1 (offline lexical encoder; FAISS / optional pgvector)",
    }


@router.put("/settings/horizons/{id}")
def update_horizon(id: str, body: HorizonInput, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    horizon = get_or_404(db, Horizon, id)
    before = as_dict(horizon)
    for key, value in body.model_dump().items():
        setattr(horizon, key, value)
    audit(db, user, "methodology.updated", id, before, as_dict(horizon))
    db.commit()
    return as_dict(horizon)


@router.put("/settings/weights")
def update_weights(body: dict[str, float], db: Session = Depends(get_db), user=Depends(require("Admin"))):
    if set(body) != set(DEFAULT_WEIGHTS) or any(not 0 <= v <= 1 for v in body.values()) or abs(sum(body.values()) - 1) > 0.001:
        raise HTTPException(422, "Provide research, commercial, maturity, relevance and evidence weights between 0 and 1 totaling 1")
    value = db.get(SystemSetting, "score_weights") or SystemSetting(key="score_weights", value=DEFAULT_WEIGHTS)
    before = value.value
    value.value = body
    db.add(value)
    audit(db, user, "weights.updated", "score_weights", before, body)
    calculate_all(db, mode(db))
    db.commit()
    return body


class SignalRules(BaseModel):
    strong_score: float = Field(ge=0, le=100)
    emerging_score: float = Field(ge=0, le=100)
    growth_threshold: float = Field(ge=0, le=10)
    min_publications: int = Field(ge=1, le=10000)


@router.put("/settings/signal-rules")
def signal_rules(body: SignalRules, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    if body.emerging_score >= body.strong_score:
        raise HTTPException(422, "Emerging threshold must be below strong threshold")
    value = db.get(SystemSetting, "signal_rules") or SystemSetting(key="signal_rules", value={})
    before = value.value
    value.value = body.model_dump()
    db.add(value)
    audit(db, user, "signal_rules.updated", value.key, before, value.value)
    db.commit()
    return value.value


class DomainInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    color: str = Field(pattern=r"^#[a-fA-F0-9]{6}$")


@router.post("/settings/domains", status_code=201)
def add_domain(body: DomainInput, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    domain = Domain(**body.model_dump())
    db.add(domain)
    audit(db, user, "domain.created", domain.name, after=body.model_dump())
    db.commit()
    return as_dict(domain)


class UserInput(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["Admin", "Analyst", "Viewer"]


@router.get("/users")
def users(db: Session = Depends(get_db), user=Depends(require("Admin"))):
    return [{k: v for k, v in as_dict(u).items() if k != "password_hash"} for u in db.scalars(select(User))]


@router.post("/users", status_code=201)
def add_user(body: UserInput, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    created = User(email=body.email.lower(), name=body.name, role=body.role, password_hash=passwords.hash(body.password))
    db.add(created)
    db.flush()
    audit(db, user, "user.created", created.id, after={"email": created.email, "role": created.role})
    db.commit()
    return {"id": created.id, "email": created.email, "role": created.role}


@router.get("/quality")
def quality(db: Session = Depends(get_db), user=Depends(current_user)):
    records = db.scalars(select(Evidence).where(Evidence.is_demo == mode(db))).all()
    rejected = db.scalars(
        select(StagedEvidence).where(StagedEvidence.valid.is_(False)).order_by(StagedEvidence.created_at.desc()).limit(50)
    ).all()
    return {
        "total": len(records),
        "missing_titles": sum(not e.title.strip() for e in records),
        "missing_technology": sum(not e.technology_id for e in records),
        "missing_content": sum(not e.content for e in records),
        "embedded": sum(e.embedding is not None for e in records),
        "rejected": [{"id": e.id, "run_id": e.run_id, "error": e.error} for e in rejected],
        "url_policy": "URLs are syntax-validated on ingest. External link availability is not probed automatically; link rot remains unverified.",
        "duplicate_policy": "Unique source ID, DOI and normalized URL; content hash and title similarity checked before merge.",
    }


@router.get("/audit")
def audit_logs(db: Session = Depends(get_db), user=Depends(require("Admin", "Analyst"))):
    return [as_dict(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))]


class SourceInput(BaseModel):
    url: str
    technology_id: str
    organization_id: str | None = None


@router.get("/sources")
def sources(db: Session = Depends(get_db), user=Depends(require("Admin"))):
    return [as_dict(s) for s in db.scalars(select(WebSource))]


@router.post("/sources", status_code=201)
def add_source(body: SourceInput, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    from app.scrapers.public import validate_public_url

    url, _ = validate_public_url(body.url, get_settings().scraper_allowed_domains)
    get_or_404(db, Technology, body.technology_id)
    if body.organization_id:
        get_or_404(db, Organization, body.organization_id)
    source = WebSource(**{**body.model_dump(), "url": url})
    db.add(source)
    db.flush()
    audit(db, user, "source.created", source.id, after={"url": url})
    db.commit()
    return as_dict(source)


class DataModeInput(BaseModel):
    is_demo: bool


@router.put("/settings/data-mode")
def change_data_mode(body: DataModeInput, db: Session = Depends(get_db), user=Depends(require("Admin"))):
    if body.is_demo and get_settings().environment == "production":
        raise HTTPException(422, "Synthetic mode is prohibited in production")
    setting = db.get(SystemSetting, "data_mode") or SystemSetting(key="data_mode", value={})
    before = setting.value
    setting.value = body.model_dump()
    db.add(setting)
    audit(db, user, "data_mode.updated", "data_mode", before, setting.value)
    db.commit()
    return setting.value
