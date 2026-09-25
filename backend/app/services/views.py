from collections import Counter
from datetime import timedelta
from sqlalchemy import select
from app.models import (
    Technology,
    Keyword,
    Score,
    AIAnalysis,
    Organization,
    Startup,
    PaperInstitution,
    Evidence,
    Author,
    PaperAuthor,
    Assessment,
    RadarHistory,
    now,
)
from app.repositories.evidence import evidence_for
from app.utils.records import as_dict


def technology_view(db, technology, is_demo):
    result = as_dict(technology)
    score = db.scalar(select(Score).where(Score.technology_id == technology.id, Score.is_demo == is_demo).order_by(Score.created_at.desc()))
    result["score"] = as_dict(score) if score else None
    result["keywords"] = list(db.scalars(select(Keyword.keyword).where(Keyword.technology_id == technology.id)))
    result["evidence_count"] = len(db.scalars(evidence_for(db, technology.id, is_demo)).all())
    analysis = db.scalar(
        select(AIAnalysis)
        .where(
            AIAnalysis.technology_id == technology.id,
            AIAnalysis.is_demo == is_demo,
            AIAnalysis.output["suggested_horizon"].as_string().is_not(None),
        )
        .order_by(AIAnalysis.created_at.desc())
    )
    result["latest_analysis"] = as_dict(analysis) if analysis else None
    return result


def organization_view(db, organization, is_demo):
    result = as_dict(organization)
    startup = db.get(Startup, organization.id)
    if startup:
        result.update(as_dict(startup))
    paper_ids = list(db.scalars(select(PaperInstitution.paper_id).where(PaperInstitution.institution_id == organization.id)))
    evidence = db.scalars(
        select(Evidence).where((Evidence.organization_id == organization.id) | Evidence.id.in_(paper_ids), Evidence.is_demo == is_demo)
    ).all()
    recent = sum(e.source_type == "paper" and e.published_at.date() >= (now() - timedelta(days=365)).date() for e in evidence)
    prior = sum(
        e.source_type == "paper" and (now() - timedelta(days=730)).date() <= e.published_at.date() < (now() - timedelta(days=365)).date()
        for e in evidence
    )
    result.update(
        publication_count=sum(e.source_type == "paper" for e in evidence),
        recent_publications=recent,
        prior_publications=prior,
        publication_momentum=(recent - prior) / max(prior, 1),
        baseline_zero=prior == 0,
        evidence=[as_dict(e) for e in evidence],
    )
    authors = db.execute(
        select(Author.name).join(PaperAuthor, PaperAuthor.author_id == Author.id).where(PaperAuthor.paper_id.in_(paper_ids))
    ).all()
    result["top_researchers"] = [
        {"name": name, "publication_count": count} for name, count in Counter(a[0] for a in authors).most_common(5)
    ]
    result["technologies"] = [
        as_dict(t) for t in db.scalars(select(Technology).where(Technology.id.in_({e.technology_id for e in evidence}))).all()
    ]
    return result


def technology_detail(db, technology, is_demo):
    result = technology_view(db, technology, is_demo)
    evidence = db.scalars(evidence_for(db, technology.id, is_demo).order_by(Evidence.published_at.desc())).all()
    result["evidence"] = [as_dict(e) for e in evidence]
    result["history"] = [
        as_dict(a)
        for a in db.scalars(select(Assessment).where(Assessment.technology_id == technology.id).order_by(Assessment.created_at.desc()))
    ]
    result["radar_history"] = [
        as_dict(a)
        for a in db.scalars(
            select(RadarHistory).where(RadarHistory.technology_id == technology.id).order_by(RadarHistory.created_at.desc())
        )
    ]
    linked_ids = set(db.scalars(select(PaperInstitution.institution_id).where(PaperInstitution.paper_id.in_([e.id for e in evidence]))))
    organizations = db.scalars(
        select(Organization).where(
            (Organization.technology_id == technology.id) | Organization.id.in_(linked_ids), Organization.is_demo == is_demo
        )
    ).all()
    result["organizations"] = [organization_view(db, o, is_demo) for o in organizations]
    result["related"] = [
        as_dict(t)
        for t in db.scalars(
            select(Technology).where(Technology.domain == technology.domain, Technology.id != technology.id, Technology.archived.is_(False))
        )
    ]
    return result
