"""Create the non-synthetic workspace catalog used by live deployments."""

from sqlalchemy import select, func

from app.analytics.scoring import DEFAULT_WEIGHTS
from app.models import Domain, Horizon, Keyword, Role, SystemSetting, Technology
from app.services.seed import COLORS, DOMAINS, TECHNOLOGIES


def bootstrap_live_catalog(db):
    """Create taxonomy and tracked topics without inserting claimed evidence."""
    if db.scalar(select(func.count()).select_from(Technology)):
        return False
    for role in ("Admin", "Analyst", "Viewer"):
        if not db.get(Role, role):
            db.add(Role(name=role))
    for domain, color in zip(DOMAINS, COLORS):
        if not db.get(Domain, domain):
            db.add(Domain(name=domain, color=color))
    for i, (name, description, years, threshold) in enumerate(
        [
            ("Near-term", "Relatively mature; evaluate practical deployment fit.", "0–2 years", 80),
            ("Emerging", "Increasing practical activity; validate adoption pathways.", "2–5 years", 55),
            ("Longer-term", "Technically promising with unresolved technical or market uncertainty.", "5–10 years", 30),
            ("Exploratory", "Early research and weak signals; monitor evidence development.", "10+ years", 0),
        ],
        1,
    ):
        if not db.get(Horizon, f"H{i}"):
            db.add(
                Horizon(
                    id=f"H{i}",
                    name=name,
                    description=description,
                    years=years,
                    min_maturity=threshold,
                    display_order=i,
                    score_rules={"basis": "analyst maturity threshold; suggestion only"},
                )
            )
    if not db.get(SystemSetting, "score_weights"):
        db.add(SystemSetting(key="score_weights", value=DEFAULT_WEIGHTS))
    if not db.get(SystemSetting, "signal_rules"):
        db.add(
            SystemSetting(
                key="signal_rules",
                value={"strong_score": 70, "emerging_score": 40, "growth_threshold": 0.25, "min_publications": 2},
            )
        )
    db.flush()
    for name, domain, description, keywords, _horizon, _maturity in TECHNOLOGIES:
        technology = Technology(
            name=name,
            domain=domain,
            description=description,
            horizon="H4",
            maturity=0,
            confidence=0,
            strategic_relevance=50,
            approved=False,
            is_demo=False,
            analyst_notes="",
        )
        db.add(technology)
        db.flush()
        for keyword in [name, *keywords.split("|")]:
            db.add(Keyword(technology_id=technology.id, keyword=keyword))
    db.commit()
    return True
