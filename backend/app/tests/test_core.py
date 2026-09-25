from datetime import timedelta
from sqlalchemy import select, func
import pytest
from app.models import Technology, Evidence, Organization, User, PipelineRun, PipelineStep, now
from app.schemas import EvidenceInput, AnalysisOutput, AnswerOutput, BriefingOutput, ReportInput
from app.repositories.evidence import upsert_evidence
from app.utils.records import normalize_url, normalize_doi
from app.analytics.scoring import calculate, suggest_horizon
from app.ai.service import analyze, answer, validate_citations, validate_grounded_numbers
from app.ai.retrieval import retrieve
from app.pipelines.runner import create_run, execute_run
from app.services.seed import seed


def test_seed_counts_and_idempotence(db):
    seed(db)
    assert db.scalar(select(func.count()).select_from(Technology)) == 15
    assert db.scalar(select(func.count()).select_from(Evidence).where(Evidence.source_type == "paper")) == 50
    assert db.scalar(select(func.count()).select_from(Evidence).where(Evidence.source_type == "news")) == 50
    assert db.scalar(select(func.count()).select_from(Organization).where(Organization.kind == "startup")) == 20
    assert db.scalar(select(func.count()).select_from(Organization).where(Organization.kind == "institution")) == 10


def test_normalization():
    assert normalize_url("https://Example.COM/paper/?utm_source=test&b=2&a=1#section") == "https://example.com/paper?a=1&b=2"
    assert normalize_doi("https://doi.org/10.123/ABC") == "10.123/abc"
    with pytest.raises(ValueError):
        normalize_url("file:///etc/passwd")


def test_upsert_deduplicates_and_retains_multiple_technology_links(db):
    technologies = db.scalars(select(Technology).limit(2)).all()
    first = EvidenceInput(
        technology_id=technologies[0].id,
        source_type="paper",
        title="An independently retrieved study",
        url="https://public.example.org/a",
        doi="https://doi.org/10.123/ABC",
        content="Original abstract",
        published_at=now() - timedelta(days=1),
        provider="Mock",
    )
    record, created = upsert_evidence(db, first)
    db.flush()
    assert created
    second = first.model_copy(
        update={"technology_id": technologies[1].id, "url": "https://public.example.org/alternate", "content": "Updated abstract"}
    )
    same, created = upsert_evidence(db, second)
    db.flush()
    assert not created and same.id == record.id and same.version == 2
    from app.repositories.evidence import evidence_for

    assert db.scalar(evidence_for(db, technologies[1].id, False)).id == record.id


def test_metrics_and_horizon(db):
    tech = db.scalar(select(Technology))
    score = calculate(db, tech, True)
    assert 0 <= score.dimensions["signal"] <= 100
    assert score.metrics["citation_momentum"] is None
    assert suggest_horizon(db, 90) == "H1"
    assert suggest_horizon(db, 10) == "H4"
    # Live calculations never count synthetic evidence.
    live = calculate(db, tech, False)
    assert live.metrics["evidence_count"] == 0


def test_pipeline_atomic_rollback_and_idempotence(factory):
    with factory() as db:
        tech = db.scalar(select(Technology))
        baseline = db.scalar(select(func.count()).select_from(Evidence))
        run = create_run(db, "demo", tech.id, 4)
        run_id, tech_id = run.id, tech.id
    execute_run(run_id, factory, fail_before_commit=True)
    with factory() as db:
        assert db.get(PipelineRun, run_id).status == "Failed"
        assert db.scalar(select(func.count()).select_from(Evidence)) == baseline
        run = create_run(db, "demo", tech_id, 4)
        run_id = run.id
    execute_run(run_id, factory)
    with factory() as db:
        assert db.get(PipelineRun, run_id).status == "Successful"
        assert db.scalar(select(func.count()).select_from(Evidence)) == baseline + 4
        steps = db.scalars(select(PipelineStep).where(PipelineStep.run_id == run_id)).all()
        assert steps and all(step.status == "Successful" for step in steps)
        assert {step.name for step in steps} >= {"Validation", "Embedding", "Grounding Preparation", "Database Commit"}
        run = create_run(db, "demo", tech_id, 4)
        run_id = run.id
    execute_run(run_id, factory)
    with factory() as db:
        assert db.get(PipelineRun, run_id).status == "Successful"
        assert db.scalar(select(func.count()).select_from(Evidence)) == baseline + 4


def test_bad_staged_record_rejects_entire_batch(factory):
    class InvalidProvider:
        def collect(self, technology_id, query, limit):
            return [{"technology_id": technology_id, "title": "", "url": "file:///secret", "source_type": "invalid"}]

    with factory() as db:
        baseline = db.scalar(select(func.count()).select_from(Evidence))
        run = create_run(db, "demo", db.scalar(select(Technology.id)), 1)
        run_id = run.id
    execute_run(run_id, factory, provider_override=InvalidProvider())
    with factory() as db:
        assert db.get(PipelineRun, run_id).status == "Failed"
        assert db.scalar(select(func.count()).select_from(Evidence)) == baseline


def test_pipeline_keeps_successful_results_when_one_query_is_rate_limited(factory):
    import httpx

    class PartialProvider:
        calls = 0

        def collect(self, technology_id, query, limit):
            self.calls += 1
            if self.calls > 1:
                request = httpx.Request("GET", "https://provider.example/api")
                response = httpx.Response(429, request=request)
                raise httpx.HTTPStatusError("rate limited", request=request, response=response)
            return [
                EvidenceInput(
                    technology_id=technology_id,
                    source_type="paper",
                    source_id="partial:1",
                    title="A retrieved provider record",
                    url="https://provider.example/record/1",
                    content="Evidence collected before another query was throttled.",
                    published_at=now(),
                    provider="Mock",
                )
            ]

    with factory() as db:
        run = create_run(db, "openalex", None, 1)
        run_id = run.id
    execute_run(run_id, factory, provider_override=PartialProvider())
    with factory() as db:
        run = db.get(PipelineRun, run_id)
        source = db.scalar(
            select(PipelineStep).where(PipelineStep.run_id == run_id, PipelineStep.name == "Source Collection")
        )
        assert run.status == "Successful"
        assert source.processed == 1
        assert "skipped queries" in source.error


def test_pipeline_explains_provider_rate_limit(factory):
    import httpx

    class ThrottledProvider:
        def collect(self, technology_id, query, limit):
            request = httpx.Request("GET", "https://provider.example/api")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    with factory() as db:
        run = create_run(db, "gdelt", db.scalar(select(Technology.id)), 1)
        run_id = run.id
    execute_run(run_id, factory, provider_override=ThrottledProvider())
    with factory() as db:
        run = db.get(PipelineRun, run_id)
        assert run.status == "Deferred"
        assert "HTTP 429" in run.error
        assert "No data changed" in run.error
        steps = db.scalars(select(PipelineStep).where(PipelineStep.run_id == run_id).order_by(PipelineStep.position)).all()
        assert steps[0].status == "Deferred"
        assert all(step.status == "Skipped" for step in steps[1:])


def test_ai_citations_and_no_automatic_horizon_overwrite(db):
    technology = db.scalar(select(Technology))
    user = db.scalar(select(User).where(User.role == "Analyst"))
    original = technology.horizon
    result = analyze(db, technology, user, True)
    assert result.evidence_ids
    assert technology.horizon == original
    assert result.approval_status == "Pending"
    output = AnalysisOutput.model_validate(result.output)
    output.evidence_ids = ["invented-id"]
    with pytest.raises(ValueError, match="unsupported"):
        validate_citations(output, retrieve(db, technology.name, technology.id, True))
    with pytest.raises(ValueError):
        AnalysisOutput.model_validate_json('{"not": "an assessment"}')


def test_ai_rejects_unsupported_numbers_and_falls_back(db):
    class NumericProvider:
        def generate(self, schema, prompt):
            evidence_id = prompt["evidence"][0]["id"]
            return (
                AnswerOutput(
                    facts=[f"Adoption increased by 98765 percent [{evidence_id}]"],
                    interpretation="A fabricated 54321 deployments were reported.",
                    uncertainties=[],
                    evidence_ids=[evidence_id],
                ),
                {},
            )

    user = db.scalar(select(User).where(User.role == "Analyst"))
    technology = db.scalar(select(Technology))
    output, _, record = answer(db, technology.name, user, technology.id, True, provider=NumericProvider())
    assert "98765" not in str(output.model_dump()) and "54321" not in str(output.model_dump())
    assert record.model == "deterministic-evidence-summary"
    assert record.token_usage["fallback_reason"] == "ValueError"


def test_numeric_grounding_accepts_only_supplied_values():
    output = AnswerOutput(facts=["The evidence contains 12 studies."], interpretation="", uncertainties=[], evidence_ids=[])
    assert validate_grounded_numbers(output, {"verified_count": 12}) is output
    output.facts = ["The evidence contains 13 studies."]
    with pytest.raises(ValueError, match="numeric"):
        validate_grounded_numbers(output, {"verified_count": 12})


def test_report_generation_falls_back_when_model_output_is_ungrounded(db):
    from app.services.reports import generate_report

    class InvalidReportProvider:
        def generate(self, schema, prompt):
            evidence_id = prompt["evidence"][0]["id"]
            fields = {
                name: ([f"Unsupported 99999 claim [{evidence_id}]"] if field.annotation == list[str] else "Unsupported 99999 claim")
                for name, field in BriefingOutput.model_fields.items()
                if name not in ("confidence_score", "evidence_ids")
            }
            return schema(**fields, confidence_score=0.99, evidence_ids=[evidence_id]), {}

    user = db.scalar(select(User).where(User.role == "Analyst"))
    technology = db.scalar(select(Technology))
    report = generate_report(
        db,
        ReportInput(kind="Technology Opportunity Report", technology_id=technology.id),
        user,
        True,
        provider=InvalidReportProvider(),
    )
    assert "99999" not in report.markdown
    assert "deterministic-evidence-summary" in report.markdown


def test_retrieval_is_bounded_and_mode_isolated(db):
    assert len(retrieve(db, "grid converter", is_demo=True, limit=5)) == 5
    assert retrieve(db, "grid converter", is_demo=False) == []


def test_comparative_query_uses_actual_metrics(db):
    from app.ai.portfolio_queries import portfolio_facts

    facts, evidence = portfolio_facts(db, "What technologies show the fastest research growth?", True)
    assert evidence
    assert all("zero baseline" not in f for f in facts)
    facts, evidence = portfolio_facts(db, "Show H3 technologies with increasing research momentum", True)
    assert all("(H3)" in f for f in facts)


def test_encoder_dimension_change_falls_back_safely(db):
    evidence = db.scalar(select(Evidence))
    evidence.embedding = [1.0] * 256
    db.flush()
    results = retrieve(db, "grid", evidence.technology_id, True)
    assert results
