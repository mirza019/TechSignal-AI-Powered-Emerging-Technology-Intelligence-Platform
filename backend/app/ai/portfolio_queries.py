"""Conservative deterministic routing for portfolio comparisons.

These rules compute rankings from stored metrics, never from a language model.
Unrecognized queries fall through to ordinary evidence retrieval.
"""

import re
from sqlalchemy import select
from app.models import Technology, Score
from app.repositories.evidence import evidence_for


def portfolio_facts(db, query, is_demo):
    lower = query.lower()
    horizon_match = re.search(r"\bh[1-4]\b", lower)
    comparative = any(
        term in lower for term in ["fastest", "growth", "weak commercial", "compare research", "increasing research"]
    ) or bool(horizon_match)
    if not comparative:
        return [], []
    technologies = db.scalars(select(Technology).where(Technology.archived.is_(False))).all()
    rows = []
    for technology in technologies:
        if horizon_match and technology.horizon.lower() != horizon_match.group():
            continue
        score = db.scalar(
            select(Score).where(Score.technology_id == technology.id, Score.is_demo == is_demo).order_by(Score.created_at.desc())
        )
        if not score or not score.metrics.get("evidence_count"):
            continue
        if "increasing" in lower and score.metrics["paper_growth"] <= 0:
            continue
        if "weak commercial" in lower and score.dimensions["commercial"] >= 40:
            continue
        rows.append((technology, score))
    # Unknown zero baselines are excluded from a claimed fastest-growth ranking.
    if "fastest" in lower:
        rows = [(t, s) for t, s in rows if not s.metrics["paper_growth_baseline_zero"]]
    rows.sort(key=lambda item: item[1].metrics["paper_growth"], reverse=True)
    facts, records = [], []
    for technology, score in rows[:5]:
        evidence = db.scalars(evidence_for(db, technology.id, is_demo)).all()[:2]
        records.extend(evidence)
        references = " ".join(f"[{e.id}]" for e in evidence)
        facts.append(
            f"{technology.name} ({technology.horizon}): {score.metrics['papers_recent']} recent / {score.metrics['papers_prior']} prior papers; growth {score.metrics['paper_growth']:.0%}"
            + (" (zero baseline)" if score.metrics["paper_growth_baseline_zero"] else "")
            + f"; research score {score.dimensions['research']}; commercial score {score.dimensions['commercial']}. Computed {score.created_at.date()}. {references}"
        )
    if not facts:
        facts = ["No technologies with sufficient collected evidence match these quantitative conditions."]
    return facts, list({e.id: e for e in records}.values())
