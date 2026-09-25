from datetime import timedelta
import math
from sqlalchemy import select
from app.models import Technology, Paper, PaperInstitution, Score, Signal, SystemSetting, Horizon, now
from app.repositories.evidence import evidence_for
from app.utils.records import digest

DEFAULT_WEIGHTS = {"research": 0.30, "commercial": 0.25, "maturity": 0.20, "relevance": 0.15, "evidence": 0.10}
FORMULA = "Research=min(100,20*log2(1+papers_365d)+20*max(0,paper_growth)); Commercial=min(100,15*news_365d+20*max(0,news_growth)); Evidence=min(100,10*records+10*independent_domains); Signal=weighted mean(Research,Commercial,analyst Maturity,analyst Relevance,Evidence). Growth=(recent-prior)/max(prior,1), with prior=0 explicitly flagged. Citation momentum is not inferred from a single snapshot."


def weights_for(db):
    setting = db.get(SystemSetting, "score_weights")
    return setting.value if setting else DEFAULT_WEIGHTS


def suggest_horizon(db, maturity):
    horizons = db.scalars(select(Horizon).order_by(Horizon.min_maturity.desc())).all()
    return next((h.id for h in horizons if maturity >= h.min_maturity), "H4")


def calculate(db, technology, is_demo, at=None):
    at = at or now()
    evidence = db.scalars(evidence_for(db, technology.id, is_demo)).all()
    recent = [e for e in evidence if e.published_at.date() >= (at - timedelta(days=365)).date()]
    prior = [e for e in evidence if (at - timedelta(days=730)).date() <= e.published_at.date() < (at - timedelta(days=365)).date()]
    papers = sum(e.source_type == "paper" for e in recent)
    old_papers = sum(e.source_type == "paper" for e in prior)
    news = sum(e.source_type == "news" for e in recent)
    old_news = sum(e.source_type == "news" for e in prior)
    growth = (papers - old_papers) / max(old_papers, 1)
    news_growth = (news - old_news) / max(old_news, 1)
    from urllib.parse import urlsplit

    domains = {urlsplit(e.url).hostname for e in recent}
    citations = sum((db.get(Paper, e.id).citation_count if db.get(Paper, e.id) else 0) for e in evidence if e.source_type == "paper")
    recent_institutions = set(
        db.scalars(
            select(PaperInstitution.institution_id).where(PaperInstitution.paper_id.in_([e.id for e in recent if e.source_type == "paper"]))
        )
    )
    prior_institutions = set(
        db.scalars(
            select(PaperInstitution.institution_id).where(PaperInstitution.paper_id.in_([e.id for e in prior if e.source_type == "paper"]))
        )
    )
    metrics = {
        "active_institutions": len(recent_institutions),
        "new_institutions_vs_prior_window": len(recent_institutions - prior_institutions),
        "startups_recent": sum(e.source_type == "startup" for e in recent),
        "patents_recent": sum(e.source_type == "patent" for e in recent),
        "papers_recent": papers,
        "papers_prior": old_papers,
        "paper_growth": growth,
        "paper_growth_baseline_zero": old_papers == 0,
        "news_recent": news,
        "news_prior": old_news,
        "news_growth": news_growth,
        "independent_domains": len(domains),
        "evidence_count": len(evidence),
        "citation_total": citations,
        "citation_momentum": None,
        "days_since_latest": (at.date() - max(e.published_at.date() for e in evidence)).days if evidence else None,
    }
    dimensions = {
        "research": round(min(100, 20 * math.log2(1 + papers) + 20 * max(0, growth)), 1),
        "commercial": round(min(100, 15 * news + 20 * max(0, news_growth)), 1),
        "maturity": technology.maturity,
        "relevance": technology.strategic_relevance,
        "evidence": min(100, len(evidence) * 10 + len(domains) * 10),
        "uncertainty": round(100 * (1 - technology.confidence), 1),
    }
    weights = weights_for(db)
    dimensions["signal"] = round(sum(dimensions[k] * v for k, v in weights.items()) / sum(weights.values()), 1) if evidence else 0
    score = Score(technology_id=technology.id, metrics=metrics, dimensions=dimensions, weights=weights, formula=FORMULA, is_demo=is_demo)
    db.add(score)
    rules_setting = db.get(SystemSetting, "signal_rules")
    rules = (
        rules_setting.value
        if rules_setting
        else {"strong_score": 70, "emerging_score": 40, "growth_threshold": 0.25, "min_publications": 2}
    )
    level = (
        "Strong"
        if dimensions["signal"] >= rules["strong_score"]
        else "Emerging"
        if dimensions["signal"] >= rules["emerging_score"]
        else "Weak"
    )
    if evidence:
        ids = sorted(e.id for e in recent)
        rule = f"Weighted score {dimensions['signal']}; {papers} recent papers; growth {growth:.0%}" + (
            " (zero prior baseline)" if not old_papers else ""
        )
        triggers = []
        if papers >= rules["min_publications"] and growth > rules["growth_threshold"]:
            triggers.append("publication activity increase")
        if news >= 2 and news_growth > rules["growth_threshold"]:
            triggers.append("news activity increase")
        if metrics["new_institutions_vs_prior_window"]:
            triggers.append("institution activity absent in prior window")
        if metrics["startups_recent"]:
            triggers.append("recent startup evidence")
        if metrics["patents_recent"]:
            triggers.append("recent patent evidence")
        if len(domains) >= 3:
            triggers.append("multiple source domains")
        metrics["triggered_rules"] = triggers
        rule += "; " + ", ".join(triggers) if triggers else ""
        fingerprint = digest(technology.id + str(is_demo) + level + str(ids) + str(rules) + str(triggers))
        if not db.scalar(select(Signal).where(Signal.fingerprint == fingerprint)):
            db.add(
                Signal(
                    technology_id=technology.id,
                    level=level,
                    rule=rule,
                    evidence_ids=ids,
                    fingerprint=fingerprint,
                    metrics=metrics,
                    is_demo=is_demo,
                )
            )
    return score


def calculate_all(db, is_demo):
    for technology in db.scalars(select(Technology).where(Technology.archived.is_(False))):
        calculate(db, technology, is_demo)
    db.flush()
