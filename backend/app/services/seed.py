import csv
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select, func
from app.models import (
    User,
    Role,
    Domain,
    Horizon,
    Technology,
    Keyword,
    Organization,
    Startup,
    Institution,
    Assessment,
    RadarHistory,
    PipelineRun,
    PipelineStep,
    SystemSetting,
    now,
)
from app.services.auth import passwords
from app.schemas import EvidenceInput
from app.repositories.evidence import upsert_evidence
from app.analytics.scoring import calculate_all, DEFAULT_WEIGHTS
from app.utils.records import normalize_name

TECHNOLOGIES = [
    (
        "Grid-forming converters",
        "Grid Stabilization",
        "Converter controls that establish voltage and frequency references in inverter-rich power systems.",
        "grid forming inverter|virtual synchronous machine",
        "H2",
        68,
    ),
    (
        "HVDC converter technologies",
        "HVDC",
        "Converter architectures for efficient, controllable high-voltage direct-current transmission.",
        "HVDC converter|modular multilevel converter",
        "H1",
        88,
    ),
    (
        "SF6-free high-voltage switchgear",
        "High-Voltage Switchgear",
        "Alternative insulation and interruption technologies for high-voltage switching.",
        "SF6 free switchgear|alternative gas insulation",
        "H2",
        70,
    ),
    (
        "Solid-state transformers",
        "Transformers",
        "Power-electronic conversion integrating transformation, control and protection.",
        "solid state transformer|power electronic transformer",
        "H3",
        44,
    ),
    (
        "AI-based transformer condition monitoring",
        "Grid AI",
        "Data-driven detection of transformer degradation using operational and diagnostic signals.",
        "transformer condition monitoring|dissolved gas machine learning",
        "H2",
        65,
    ),
    (
        "Digital substations",
        "Digital Grid",
        "Digitized measurement, protection and control architectures in substations.",
        "digital substation|IEC 61850 process bus",
        "H1",
        90,
    ),
    (
        "Grid-scale energy storage",
        "Energy Storage",
        "Large-scale electrical energy storage for balancing, flexibility and resilience.",
        "grid scale battery storage|stationary energy storage",
        "H1",
        86,
    ),
    (
        "Long-duration energy storage",
        "Energy Storage",
        "Storage approaches targeting sustained delivery over extended durations.",
        "long duration energy storage|flow battery",
        "H2",
        62,
    ),
    (
        "Digital twins for power grids",
        "Digital Grid",
        "Model-based digital representations connecting grid state, simulation and planning.",
        "power grid digital twin|electric network twin",
        "H2",
        59,
    ),
    (
        "Advanced transformer insulation materials",
        "Materials",
        "Dielectric materials and insulation systems for transformer reliability.",
        "transformer insulation nanodielectric|ester insulation",
        "H3",
        46,
    ),
    (
        "Superconducting power transmission",
        "Emerging Research",
        "Cryogenic conductors and system concepts for electrical transmission.",
        "superconducting power cable|HTS transmission",
        "H4",
        22,
    ),
    (
        "AI for grid stability and control",
        "Grid AI",
        "Learning-based methods supporting power-system stability and adaptive control.",
        "machine learning grid stability|reinforcement learning power system",
        "H3",
        42,
    ),
    (
        "Wide-bandgap semiconductors for power electronics",
        "Power Electronics",
        "SiC and GaN switching devices for efficient power conversion.",
        "silicon carbide power electronics|gallium nitride converter",
        "H2",
        73,
    ),
    (
        "Advanced power-electronics cooling",
        "Power Electronics",
        "Thermal management approaches for high-power converter systems.",
        "power electronics cooling|two phase converter cooling",
        "H3",
        48,
    ),
    (
        "Cybersecurity for digital grids",
        "Cybersecurity",
        "Protection, detection and resilience approaches for connected grid infrastructure.",
        "power grid cybersecurity|substation intrusion detection",
        "H1",
        82,
    ),
]
DOMAINS = [
    "HVDC",
    "Transformers",
    "High-Voltage Switchgear",
    "Grid Stabilization",
    "Energy Storage",
    "Power Electronics",
    "Digital Grid",
    "Grid AI",
    "Materials",
    "Cybersecurity",
    "Emerging Research",
]
COLORS = ["#6089e8", "#b38af1", "#deab56", "#28b99a", "#53b6d0", "#ef867c", "#6c9ee9", "#a3bd64", "#b694cb", "#d38fad", "#7b96a3"]
STEPS = [
    "Source Collection",
    "Validation",
    "Cleaning",
    "Deduplication",
    "Classification",
    "Entity Linking",
    "Embedding",
    "Signal Calculation",
    "Grounding Preparation",
    "Database Commit",
]


def seed(db):
    if db.scalar(select(func.count()).select_from(Technology)):
        return
    for role in ["Admin", "Analyst", "Viewer"]:
        if not db.get(Role, role):
            db.add(Role(name=role))
    db.flush()
    users = []
    for role in ["Admin", "Analyst", "Viewer"]:
        user = User(email=f"{role.lower()}@radar.local", name=f"Demo {role}", role=role, password_hash=passwords.hash("RadarDemo2026!"))
        db.add(user)
        users.append(user)
    for domain, color in zip(DOMAINS, COLORS):
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
    db.add(SystemSetting(key="score_weights", value=DEFAULT_WEIGHTS))
    db.add(
        SystemSetting(key="signal_rules", value={"strong_score": 70, "emerging_score": 40, "growth_threshold": 0.25, "min_publications": 2})
    )
    db.flush()
    technologies = []
    for i, (name, domain, description, keywords, horizon, maturity) in enumerate(TECHNOLOGIES):
        technology = Technology(
            name=name,
            domain=domain,
            description=description,
            horizon=horizon,
            maturity=maturity,
            confidence=round(0.48 + (i % 6) * 0.07, 2),
            strategic_relevance=65 + (i % 4) * 8,
            approved=i % 3 != 0,
            last_reviewed=now() - timedelta(days=i + 1),
            is_demo=True,
            analyst_notes="Synthetic portfolio assessment. Validate all assumptions before real use.",
        )
        db.add(technology)
        db.flush()
        for keyword in [name] + keywords.split("|"):
            db.add(Keyword(technology_id=technology.id, keyword=keyword))
        technologies.append(technology)
    institutions = []
    for i in range(10):
        institution = Organization(
            name=f"Sample {['Northshore', 'Helios', 'Rivermark', 'Westhaven', 'Cedar', 'Boreal', 'Aurora', 'Meridian', 'Alpine', 'Seabrook'][i]} Energy Institute",
            normalized_name=f"sample institute {i}",
            kind="institution",
            country=["Germany", "Denmark", "Netherlands", "Sweden", "France"][i % 5],
            description="Fictional research institution for portfolio demonstration.",
            domains=[technologies[i].domain],
            technology_id=technologies[i].id,
            is_demo=True,
        )
        db.add(institution)
        db.flush()
        db.add(Institution(organization_id=institution.id, openalex_id=f"demo:institution:{i}"))
        institutions.append(institution)
    path = Path(__file__).resolve().parents[3] / "data" / "startups.csv"
    if not path.exists():
        path = Path("/data/startups.csv")
    with path.open() as handle:
        for i, row in enumerate(csv.DictReader(handle)):
            technology = technologies[i % 15]
            organization = Organization(
                name=row["company_name"],
                normalized_name=normalize_name(row["company_name"]),
                website=row["website"],
                country=row["country"],
                city=row["city"],
                kind="startup",
                description=row["description"],
                domains=[technology.domain],
                technology_id=technology.id,
                confidence=0.4,
                is_demo=True,
            )
            db.add(organization)
            db.flush()
            db.add(
                Startup(
                    organization_id=organization.id,
                    founded_year=int(row["founded_year"]),
                    development_stage=row["development_stage"],
                    source_urls=[row["website"]],
                    public_funding_signal="Synthetic record; no actual funding claim",
                    latest_signal_date=now() - timedelta(days=i),
                )
            )
            upsert_evidence(
                db,
                EvidenceInput(
                    technology_id=technology.id,
                    organization_id=organization.id,
                    source_type="startup",
                    source_id=f"demo:startup:{i}",
                    title=row["company_name"] + " — sample organization profile",
                    url=row["website"],
                    content=row["description"],
                    published_at=now() - timedelta(days=i),
                    provider="Demo",
                    is_demo=True,
                ),
            )
    for i in range(50):
        technology = technologies[i % 15]
        institution = institutions[i % 10]
        # Distribute dated evidence across comparison windows.
        days = [12, 35, 82, 145, 230, 420, 500, 630][i % 8]
        record, _ = upsert_evidence(
            db,
            EvidenceInput(
                technology_id=technology.id,
                source_type="paper",
                source_id=f"demo:paper:{i}",
                title=f"[Sample] {technology.name}: {['experimental validation', 'system integration study', 'performance evaluation', 'control architecture'][i % 4]} {i + 1}",
                url=f"https://example.com/research/{i + 1}",
                content=f"Synthetic research abstract about {technology.name.lower()}. A fictional study evaluates system performance, engineering constraints and validation requirements. This record is not a real publication.",
                published_at=now() - timedelta(days=days + i),
                provider="Demo",
                is_demo=True,
                metadata_json={
                    "citation_count": 8 + i * 3,
                    "journal": "Synthetic Grid Research",
                    "topics": [technology.domain],
                    "institutions": [{"id": f"demo:institution:{i % 10}", "name": institution.name, "country": institution.country}],
                    "authors": [{"id": f"demo:author:{i % 12}", "name": f"Sample Researcher {i % 12 + 1}"}],
                },
            ),
        )
        upsert_evidence(
            db,
            EvidenceInput(
                technology_id=technology.id,
                source_type="news",
                source_id=f"demo:news:{i}",
                title=f"[Sample] {technology.name}: {['pilot announced', 'test milestone reported', 'research collaboration', 'demonstration program'][i % 4]} {i + 1}",
                url=f"https://example.com/news/{i + 1}",
                content="Synthetic market-signal metadata. This does not describe a real announcement.",
                published_at=now() - timedelta(days=(i * 7) + (400 if i % 7 == 0 else 0)),
                provider="Demo",
                is_demo=True,
                metadata_json={"domain": "example.com", "language": "English", "query": technology.name},
            ),
        )
    db.flush()
    from app.models import Evidence

    for t in technologies:
        ids = list(db.scalars(select(Evidence.id).where(Evidence.technology_id == t.id).limit(3)))
        db.add(
            Assessment(
                technology_id=t.id,
                actor_id=users[1].id,
                horizon=t.horizon,
                maturity=t.maturity,
                confidence=t.confidence,
                notes="Synthetic baseline assessment for portfolio demonstration.",
                evidence_ids=ids,
            )
        )
        db.add(
            RadarHistory(
                technology_id=t.id, old_horizon="H4", new_horizon=t.horizon, actor_id=users[1].id, reason="Synthetic initial placement"
            )
        )
    calculate_all(db, True)
    from app.ai.retrieval import generate_embeddings

    generate_embeddings(db)
    run = PipelineRun(provider="demo", status="Successful", ended_at=now(), limit=100)
    db.add(run)
    db.flush()
    for i, name in enumerate(STEPS):
        db.add(
            PipelineStep(
                run_id=run.id,
                name=name,
                position=i,
                status="Skipped" if name == "AI Enrichment" else "Successful",
                processed=120,
                inserted=120 if name == "Database Commit" else 0,
                started_at=now() - timedelta(seconds=10 - i),
                ended_at=now() - timedelta(seconds=9 - i),
            )
        )
    db.commit()
