from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(default=now)
    updated_at: Mapped[datetime] = mapped_column(default=now, onupdate=now)


class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(20), primary_key=True)


class User(Record, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(ForeignKey("roles.name"))
    external_subject: Mapped[str | None] = mapped_column(String(300), unique=True)
    active: Mapped[bool] = mapped_column(default=True)


class Domain(Base):
    __tablename__ = "technology_domains"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    color: Mapped[str] = mapped_column(String(20), default="#18a585")


class Horizon(Base):
    __tablename__ = "radar_horizons"
    id: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    years: Mapped[str] = mapped_column(String(30))
    min_maturity: Mapped[float] = mapped_column(default=0)
    display_order: Mapped[int]
    score_rules: Mapped[dict] = mapped_column(JSON, default=dict)


class Technology(Record, Base):
    __tablename__ = "technologies"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    domain: Mapped[str] = mapped_column(ForeignKey("technology_domains.name"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    horizon: Mapped[str] = mapped_column(ForeignKey("radar_horizons.id"), default="H4")
    maturity: Mapped[float] = mapped_column(default=30)
    strategic_relevance: Mapped[float] = mapped_column(default=50)
    confidence: Mapped[float] = mapped_column(default=0.3)
    approved: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)
    analyst_notes: Mapped[str] = mapped_column(Text, default="")
    last_reviewed: Mapped[datetime | None]
    is_demo: Mapped[bool] = mapped_column(default=False)


class Keyword(Record, Base):
    __tablename__ = "technology_keywords"
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("technology_id", "keyword"),)


class Organization(Record, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    website: Mapped[str] = mapped_column(Text, default="")
    country: Mapped[str] = mapped_column(String(100), default="Unknown")
    city: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    domains: Mapped[list] = mapped_column(JSON, default=list)
    technology_id: Mapped[str | None] = mapped_column(ForeignKey("technologies.id"), index=True)
    embedding: Mapped[list | None] = mapped_column(JSON)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    analyst_notes: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(default=0.3)
    is_demo: Mapped[bool] = mapped_column(default=False)


class Startup(Base):
    __tablename__ = "startups"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    founded_year: Mapped[int | None]
    development_stage: Mapped[str] = mapped_column(String(80), default="Unknown")
    public_funding_signal: Mapped[str] = mapped_column(Text, default="Not verified")
    research_partners: Mapped[list] = mapped_column(JSON, default=list)
    patents_found: Mapped[list] = mapped_column(JSON, default=list)
    source_urls: Mapped[list] = mapped_column(JSON, default=list)
    latest_signal_date: Mapped[datetime | None]


class Institution(Base):
    __tablename__ = "institutions"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    openalex_id: Mapped[str | None] = mapped_column(String(200), unique=True)


class Evidence(Record, Base):
    __tablename__ = "technology_evidence"
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    source_id: Mapped[str | None] = mapped_column(String(300), unique=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, unique=True)
    doi: Mapped[str | None] = mapped_column(String(250), unique=True)
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[datetime] = mapped_column(index=True)
    provider: Mapped[str] = mapped_column(String(50))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    is_demo: Mapped[bool] = mapped_column(default=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(default=1)
    embedding: Mapped[list | None] = mapped_column(JSON)


class EvidenceTechnology(Base):
    __tablename__ = "evidence_technologies"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("technology_evidence.id"), primary_key=True)
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), primary_key=True)


class Paper(Base):
    __tablename__ = "papers"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("technology_evidence.id"), primary_key=True)
    citation_count: Mapped[int] = mapped_column(default=0)
    journal: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list] = mapped_column(JSON, default=list)
    semantic_scholar_id: Mapped[str | None] = mapped_column(String(100), unique=True)


class Author(Record, Base):
    __tablename__ = "authors"
    name: Mapped[str] = mapped_column(String(200))
    source_id: Mapped[str] = mapped_column(String(250), unique=True)


class PaperAuthor(Base):
    __tablename__ = "paper_authors"
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.evidence_id"), primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("authors.id"), primary_key=True)


class PaperInstitution(Base):
    __tablename__ = "paper_institutions"
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.evidence_id"), primary_key=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.organization_id"), primary_key=True)


class News(Base):
    __tablename__ = "news_signals"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("technology_evidence.id"), primary_key=True)
    domain: Mapped[str] = mapped_column(String(250))
    language: Mapped[str] = mapped_column(String(50), default="English")
    query: Mapped[str] = mapped_column(Text, default="")


class Patent(Record, Base):
    __tablename__ = "patents"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("technology_evidence.id"), unique=True)
    applicant: Mapped[str] = mapped_column(Text)
    inventor: Mapped[str] = mapped_column(Text)
    classifications: Mapped[list] = mapped_column(JSON, default=list)
    family: Mapped[str] = mapped_column(Text, default="")
    legal_status: Mapped[str] = mapped_column(Text, default="Unknown")


class WebSource(Record, Base):
    __tablename__ = "web_sources"
    url: Mapped[str] = mapped_column(Text, unique=True)
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    enabled: Mapped[bool] = mapped_column(default=True)
    last_checked: Mapped[datetime | None]
    content_hash: Mapped[str] = mapped_column(String(64), default="")


class Assessment(Record, Base):
    __tablename__ = "technology_assessments"
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    horizon: Mapped[str] = mapped_column(ForeignKey("radar_horizons.id"))
    maturity: Mapped[float]
    confidence: Mapped[float]
    notes: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey("ai_analyses.id"))


class RadarHistory(Record, Base):
    __tablename__ = "radar_history"
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), index=True)
    old_horizon: Mapped[str] = mapped_column(String(2))
    new_horizon: Mapped[str] = mapped_column(String(2))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)


class Score(Record, Base):
    __tablename__ = "technology_scores"
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), index=True)
    metrics: Mapped[dict] = mapped_column(JSON)
    dimensions: Mapped[dict] = mapped_column(JSON)
    weights: Mapped[dict] = mapped_column(JSON)
    formula: Mapped[str] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False)


class Signal(Record, Base):
    __tablename__ = "detected_signals"
    technology_id: Mapped[str] = mapped_column(ForeignKey("technologies.id"), index=True)
    level: Mapped[str] = mapped_column(String(20))
    rule: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    metrics: Mapped[dict] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(default=False)


class AIAnalysis(Record, Base):
    __tablename__ = "ai_analyses"
    technology_id: Mapped[str | None] = mapped_column(ForeignKey("technologies.id"), index=True)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(30))
    output: Mapped[dict] = mapped_column(JSON)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float]
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_status: Mapped[str] = mapped_column(String(20), default="Pending")
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_demo: Mapped[bool] = mapped_column(default=False)


class Report(Record, Base):
    __tablename__ = "reports"
    title: Mapped[str] = mapped_column(String(250))
    kind: Mapped[str] = mapped_column(String(80))
    markdown: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_demo: Mapped[bool] = mapped_column(default=False)


class Briefing(Record, Base):
    __tablename__ = "briefings"
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    technology_id: Mapped[str | None] = mapped_column(ForeignKey("technologies.id"))


class PipelineRun(Record, Base):
    __tablename__ = "pipeline_runs"
    provider: Mapped[str] = mapped_column(String(40))
    technology_id: Mapped[str | None] = mapped_column(ForeignKey("technologies.id"))
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    limit: Mapped[int] = mapped_column(default=20)
    error: Mapped[str] = mapped_column(Text, default="")
    ended_at: Mapped[datetime | None]
    retry_count: Mapped[int] = mapped_column(default=0)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("pipeline_runs.id"))


class PipelineStep(Record, Base):
    __tablename__ = "pipeline_steps"
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    processed: Mapped[int] = mapped_column(default=0)
    inserted: Mapped[int] = mapped_column(default=0)
    updated: Mapped[int] = mapped_column(default=0)
    rejected: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(default=0)


class StagedEvidence(Record, Base):
    __tablename__ = "staged_evidence"
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    valid: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str] = mapped_column(Text, default="")


class IngestionJob(Record, Base):
    __tablename__ = "ingestion_jobs"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    cron: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(default=False)


class AuditLog(Record, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


Index("ix_evidence_technology_date", Evidence.technology_id, Evidence.published_at)


class SSOExchange(Base):
    __tablename__ = "sso_exchanges"
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(index=True)
