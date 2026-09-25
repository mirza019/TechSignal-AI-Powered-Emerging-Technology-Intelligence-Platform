from io import BytesIO
from datetime import timedelta
from xml.sax.saxutils import escape
import httpx
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from sqlalchemy import select
from app.config import get_settings
from app.models import Report, Briefing, Technology, Organization, RadarHistory, AIAnalysis, Score, now
from app.ai.service import (
    GeminiProvider,
    validate_citations,
    validate_grounded_numbers,
    deterministic_confidence,
    context,
    PROMPT_VERSION,
)
from app.ai.retrieval import retrieve
from app.schemas import BriefingOutput

METHODOLOGY = "Configurable H1–H4 technology horizon model."


def generate_report(db, request, actor, is_demo, provider=None):
    technology = db.get(Technology, request.technology_id) if request.technology_id else None
    organization = db.get(Organization, request.organization_id) if request.organization_id else None
    subject = organization.name if organization else technology.name if technology else "Technology portfolio"
    query = f"{request.kind} for {subject}. Technology focus, opportunities, risks and analyst questions."
    evidence = retrieve(db, query, technology.id if technology else None, is_demo, organization.id if organization else None)
    model, usage, output = "deterministic-evidence-summary", {}, None
    score = (
        db.scalar(select(Score).where(Score.technology_id == technology.id, Score.is_demo == is_demo).order_by(Score.created_at.desc()))
        if technology
        else None
    )
    prompt = {
        "task": query,
        "subject": subject,
        "evidence": context(evidence),
        "verified_metrics": score.metrics if score else {},
        "instructions": "All factual claims must refer to evidence IDs. If a section lacks evidence, explicitly say so. Questions and opportunities must be presented as proposals, not facts. This is a bounded bundle, not an exhaustive report.",
    }
    if (provider or get_settings().gemini_api_key) and evidence:
        try:
            output, usage = (provider or GeminiProvider()).generate(BriefingOutput, prompt)
            validate_citations(output, evidence)
            validate_grounded_numbers(output, prompt)
            output.confidence_score = deterministic_confidence(evidence)
            model = get_settings().gemini_model
        except (httpx.HTTPError, ValueError, KeyError, RuntimeError) as exc:
            # An unavailable model, malformed JSON, unsupported citation or
            # invented number must not break briefing preparation.
            usage = {"fallback_reason": type(exc).__name__}
            output = None
    if output is None:
        output = BriefingOutput(
            executive_summary=f"{len(evidence)} selected {'synthetic' if is_demo else 'public'} evidence records for analyst review. "
            + ("No LLM synthesis was performed." if evidence else "Insufficient evidence for a grounded briefing."),
            organization_overview=organization.description if organization else "Not an organization briefing.",
            technology_focus=technology.description if technology else "See the source records for the specific technical scope.",
            why_it_matters="Decision support: investigate suitability, maturity and deployment constraints against the evidence.",
            research_momentum="A small retrieved bundle cannot establish a portfolio-wide research trend; consult the computed profile metrics.",
            commercial_momentum="News or startup mentions do not independently establish commercial readiness.",
            recent_signals=[f"{e.title} [{e.id}]" for e in evidence],
            relevant_research=[f"{e.title} [{e.id}]" for e in evidence if e.source_type == "paper"],
            relevant_patents=[f"{e.title} [{e.id}]" for e in evidence if e.source_type == "patent"],
            relevant_startups=[f"{e.title} [{e.id}]" for e in evidence if e.source_type == "startup"],
            relevant_institutions=[],
            opportunities=["Investigate independently validated deployment evidence; no verified opportunity is asserted."],
            risks=["Coverage gaps and unverified source claims may affect assessment reliability."],
            uncertainties=[
                "Synthetic demonstration data." if is_demo else "Retrieved evidence is bounded and may be incomplete.",
                "Citation membership does not establish claim entailment.",
            ],
            questions_to_ask=[
                "Which claims have independent experimental validation?",
                "What operating limits, integration requirements and failure modes remain?",
                "Which pilot results, customers or partnerships can be verified?",
            ],
            monitoring_recommendation="Review original sources and reassess when independent evidence changes.",
            confidence_score=deterministic_confidence(evidence),
            evidence_ids=[e.id for e in evidence],
        )
    validate_citations(output, evidence)
    analysis = AIAnalysis(
        technology_id=technology.id if technology else None,
        model=model,
        prompt_version=PROMPT_VERSION,
        output=output.model_dump(),
        evidence_ids=output.evidence_ids,
        confidence=output.confidence_score,
        token_usage=usage,
        actor_id=actor.id,
        is_demo=is_demo,
    )
    db.add(analysis)
    db.flush()
    lines = [
        f"# {request.kind}",
        f"## {subject}",
        f"Generated {now().date()} | {'SYNTHETIC DEMO DATA' if is_demo else 'PUBLIC EVIDENCE'}",
        METHODOLOGY,
        "## Executive Summary",
        output.executive_summary,
        "## Organization Overview",
        output.organization_overview,
        "## Technology Description / Focus",
        output.technology_focus,
        "## Why It Matters",
        output.why_it_matters,
        "## Current Maturity",
        f"Analyst maturity: {technology.maturity}/100. Current horizon: {technology.horizon}. "
        + ("This is still a synthetic baseline assessment." if technology.is_demo else "Analyst-reviewed placement.")
        if technology
        else "See the individual technology assessments.",
        "## Research Momentum",
        output.research_momentum,
        "## Commercial Momentum",
        output.commercial_momentum,
    ]
    sections = [
        ("Key Signals", output.recent_signals),
        ("Relevant Research", output.relevant_research),
        ("Relevant Startups", output.relevant_startups),
        ("Relevant Universities / Institutions", output.relevant_institutions),
        ("Relevant Patents", output.relevant_patents),
        ("Potential Opportunities", output.opportunities),
        ("Potential Threats / Risks", output.risks),
        ("Key Uncertainties", output.uncertainties),
        ("Questions to Ask", output.questions_to_ask),
    ]
    for heading, items in sections:
        lines += [f"## {heading}"] + ([f"- {item}" for item in items] or ["No supporting evidence in this retrieved bundle."])
    lines += [
        "## Suggested Horizon",
        f"Current analyst placement: {technology.horizon}. A changed horizon requires explicit analyst review."
        if technology
        else "No organization horizon is inferred.",
        "## Confidence",
        f"{output.confidence_score:.0%}; evidence-limited interpretation.",
        "## Monitoring Recommendation",
        output.monitoring_recommendation,
        "## Important Changes / Horizon Movements",
    ]
    period = 7 if request.kind.startswith("Weekly") else 30
    history = db.scalars(
        select(RadarHistory)
        .where(
            RadarHistory.created_at >= now() - timedelta(days=period),
            *([RadarHistory.technology_id == technology.id] if technology else []),
        )
        .order_by(RadarHistory.created_at.desc())
        .limit(20)
    ).all()
    lines += [f"{db.get(Technology, h.technology_id).name}: {h.old_horizon} → {h.new_horizon}; {h.reason}" for h in history] or [
        f"No recorded horizon changes in the last {period} days."
    ]
    lines += [
        "## Analyst Notes",
        organization.analyst_notes if organization else technology.analyst_notes if technology else "See individual profiles.",
        "## Evidence Sources",
    ]
    lines += [f"- [{e.id}] {e.title} — {e.url}" for e in evidence]
    lines += [
        "## Provenance",
        f"Model: {analysis.model}; prompt: {analysis.prompt_version}; analysis ID: {analysis.id}; status: pending analyst review.",
        "Citation validation verifies record membership, not the truth or entailment of every generated claim. Source coverage is bounded to the displayed evidence bundle.",
    ]
    report = Report(
        title=f"{request.kind} · {subject}",
        kind=request.kind,
        markdown="\n\n".join(lines),
        evidence_ids=[e.id for e in evidence],
        actor_id=actor.id,
        is_demo=is_demo,
    )
    db.add(report)
    db.flush()
    if "Briefing" in request.kind or technology:
        db.add(
            Briefing(
                report_id=report.id,
                organization_id=organization.id if organization else None,
                technology_id=technology.id if technology else None,
            )
        )
    return report


def render_pdf(report):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#153e3c")
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    styles["Heading2"].fontSize = 13
    styles["Heading2"].leading = 17
    styles["Heading2"].spaceBefore = 10
    styles["Heading2"].spaceAfter = 6
    styles["Heading2"].keepWithNext = True
    story = []
    for line in report.markdown.split("\n\n"):
        style = styles["Heading2"] if line.startswith("## ") else styles["Title"] if line.startswith("# ") else styles["BodyText"]
        clean = line.lstrip("# ").replace("→", " to ").replace("—", "-").replace("·", "|").replace("–", "-").replace("‑", "-")
        story.append(Paragraph(escape(clean).replace("\n", "<br/>"), style))
        if not line.startswith("#"):
            story.append(Spacer(1, 4))

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            36,
            24,
            "TechSignal | AI-Powered Emerging Technology Intelligence | " + ("Synthetic demo" if report.is_demo else "Public evidence"),
        )
        canvas.drawRightString(A4[0] - 36, 24, str(doc.page))

    SimpleDocTemplate(
        buffer,
        title=report.title,
        author="TechSignal",
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=48,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
