from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.utils.records import normalize_url, normalize_doi


class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=256)


class TechnologyInput(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    domain: str
    description: str = Field(default="", max_length=10000)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    analyst_notes: str = Field(default="", max_length=20000)
    archived: bool = False


class ReviewInput(BaseModel):
    horizon: Literal["H1", "H2", "H3", "H4"]
    maturity: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    notes: str = Field(min_length=10, max_length=10000)
    evidence_ids: list[str] = Field(min_length=1, max_length=100)
    analysis_id: str | None = None


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    technology_id: str
    source_type: Literal["paper", "news", "web", "startup", "patent"]
    source_id: str | None = None
    title: str = Field(min_length=3, max_length=2000)
    url: str
    doi: str | None = None
    content: str = Field(default="", max_length=12000)
    published_at: datetime
    provider: str
    metadata_json: dict = Field(default_factory=dict)
    organization_id: str | None = None
    is_demo: bool = False

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return normalize_url(value)

    @field_validator("doi")
    @classmethod
    def valid_doi(cls, value):
        return normalize_doi(value)

    @field_validator("published_at")
    @classmethod
    def valid_date(cls, value):
        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        if value.year < 1900 or value > datetime.now(timezone.utc):
            raise ValueError("Publication date must be between 1900 and today")
        return value


class PipelineInput(BaseModel):
    provider: Literal["demo", "openalex", "gdelt", "web"] = "demo"
    technology_id: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class QueryInput(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    technology_id: str | None = None


class AnalysisInput(BaseModel):
    technology_id: str


class AnalysisOutput(BaseModel):
    technology_id: str
    technology_name: str
    executive_summary: str
    signal_strength: str
    research_momentum: str
    commercial_momentum: str
    maturity_assessment: str
    suggested_horizon: Literal["H1", "H2", "H3", "H4"]
    opportunities: list[str]
    risks: list[str]
    uncertainties: list[str]
    key_organizations: list[str]
    key_research_institutions: list[str]
    monitoring_recommendation: str
    confidence_score: float = Field(ge=0, le=1)
    evidence_ids: list[str]


class AnswerOutput(BaseModel):
    facts: list[str]
    interpretation: str
    uncertainties: list[str]
    evidence_ids: list[str]


class OrganizationInput(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    website: str = ""
    country: str = "Unknown"
    city: str = ""
    description: str = Field(default="", max_length=10000)
    domains: list[str] = Field(default_factory=list)
    technology_id: str | None = None
    analyst_notes: str = Field(default="", max_length=10000)
    confidence: float = Field(default=0.3, ge=0, le=1)
    founded_year: int | None = Field(default=None, ge=1800, le=2100)
    development_stage: str = "Unknown"
    public_funding_signal: str = "Not verified"
    research_partners: list[str] = Field(default_factory=list)
    patents_found: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    @field_validator("website")
    @classmethod
    def website_url(cls, value):
        return normalize_url(value) if value else ""

    @field_validator("source_urls")
    @classmethod
    def source_url_list(cls, values):
        return [normalize_url(v) for v in values]


class ReportInput(BaseModel):
    kind: Literal[
        "Weekly Technology Intelligence Report",
        "Monthly Technology Radar Update",
        "Technology Opportunity Report",
        "Startup Briefing",
        "Research Institution Briefing",
    ] = "Weekly Technology Intelligence Report"
    technology_id: str | None = None
    organization_id: str | None = None


class HorizonInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=2000)
    years: str = Field(min_length=1, max_length=30)
    min_maturity: float = Field(ge=0, le=100)
    display_order: int = Field(ge=1, le=4)
    score_rules: dict = Field(default_factory=dict)


class BriefingOutput(BaseModel):
    executive_summary: str
    organization_overview: str
    technology_focus: str
    why_it_matters: str
    research_momentum: str
    commercial_momentum: str
    recent_signals: list[str]
    relevant_research: list[str]
    relevant_patents: list[str]
    relevant_startups: list[str]
    relevant_institutions: list[str]
    opportunities: list[str]
    risks: list[str]
    uncertainties: list[str]
    questions_to_ask: list[str]
    monitoring_recommendation: str
    confidence_score: float = Field(ge=0, le=1)
    evidence_ids: list[str]
