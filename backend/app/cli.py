import argparse
import getpass
from sqlalchemy import select
from app.db import SessionLocal
from app.config import get_settings
from app.models import Technology, User, Role, Domain, Horizon
from app.services.seed import seed, DOMAINS, COLORS
from app.services.auth import passwords
from app.pipelines.runner import create_run, execute_run
from app.analytics.scoring import calculate_all
from app.ai.retrieval import generate_embeddings
from app.ai.service import analyze
from app.services.data_mode import data_mode


def main():
    parser = argparse.ArgumentParser(description="Grid Radar operations")
    parser.add_argument(
        "command",
        choices=[
            "seed",
            "bootstrap-admin",
            "ingest-openalex",
            "ingest-gdelt",
            "refresh-web-sources",
            "calculate-signals",
            "generate-embeddings",
            "analyze-technologies",
        ],
    )
    parser.add_argument("--technology")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    with SessionLocal() as db:
        if args.command == "seed":
            if get_settings().environment == "production":
                parser.error("Demo seeding is disabled in production")
            seed(db)
            print("Demo seed ready")
            return
        if args.command == "bootstrap-admin":
            email = input("Admin email: ").strip().lower()
            password = getpass.getpass("Password (12+ characters): ")
            if len(password) < 12:
                parser.error("Password must contain at least 12 characters")
            for role in ["Admin", "Analyst", "Viewer"]:
                if not db.get(Role, role):
                    db.add(Role(name=role))
            for domain, color in zip(DOMAINS, COLORS):
                if not db.get(Domain, domain):
                    db.add(Domain(name=domain, color=color))
            for i, threshold in enumerate([80, 55, 30, 0], 1):
                if not db.get(Horizon, f"H{i}"):
                    db.add(
                        Horizon(
                            id=f"H{i}",
                            name=["Near-term", "Emerging", "Longer-term", "Exploratory"][i - 1],
                            description="Configurable portfolio methodology; configure before analyst use.",
                            years=["0–2", "2–5", "5–10", "10+"][i - 1],
                            min_maturity=threshold,
                            display_order=i,
                        )
                    )
            db.flush()
            db.add(User(email=email, name="Administrator", role="Admin", password_hash=passwords.hash(password)))
            db.commit()
            print("Administrator created")
            return
        technology = db.scalar(select(Technology).where(Technology.name.ilike(args.technology))) if args.technology else None
        if args.technology and not technology:
            parser.error("Technology not found")
        providers = {"ingest-openalex": "openalex", "ingest-gdelt": "gdelt", "refresh-web-sources": "web"}
        if args.command in providers:
            run = create_run(db, providers[args.command], technology.id if technology else None, args.limit)
            execute_run(run.id)
            db.expire_all()
            print(f"Run {run.id}: {run.status}")
            if run.status == "Failed":
                raise SystemExit(1)
            return
        if args.command == "calculate-signals":
            calculate_all(db, data_mode(db))
        elif args.command == "generate-embeddings":
            print(f"Embedded {generate_embeddings(db)} records")
        else:
            actor = db.scalar(select(User).where(User.role == "Admin", User.active.is_(True)))
            if not actor:
                parser.error("Bootstrap an administrator first")
            for item in [technology] if technology else db.scalars(select(Technology).where(Technology.archived.is_(False))):
                analyze(db, item, actor, data_mode(db))
        db.commit()


if __name__ == "__main__":
    main()
