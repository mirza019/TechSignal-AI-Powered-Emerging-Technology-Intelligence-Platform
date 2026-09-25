from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Evidence, Organization, Technology, User
from app.services.catalog import bootstrap_live_catalog


def test_live_catalog_contains_topics_without_synthetic_records():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as db:
        assert bootstrap_live_catalog(db) is True
        assert db.scalar(select(func.count()).select_from(Technology)) == 15
        assert db.scalar(select(func.count()).select_from(Evidence)) == 0
        assert db.scalar(select(func.count()).select_from(Organization)) == 0
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert all(not item.is_demo for item in db.scalars(select(Technology)))
        assert bootstrap_live_catalog(db) is False
    engine.dispose()
