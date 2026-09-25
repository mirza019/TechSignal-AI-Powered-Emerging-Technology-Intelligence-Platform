import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["GEMINI_API_KEY"] = ""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base, get_db
from app.main import app
from app.services.seed import seed
from app.models import User
from sqlalchemy import select
from app.services.auth import token_for, limiter


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    maker = sessionmaker(engine, expire_on_commit=False)
    with maker() as db:
        seed(db)
    yield maker
    engine.dispose()


@pytest.fixture
def db(factory):
    with factory() as session:
        yield session


@pytest.fixture
def client(factory):
    def override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    limiter.events.clear()
    test_client = TestClient(app, raise_server_exceptions=True)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def tokens(db):
    return {u.role: {"Authorization": "Bearer " + token_for(u)} for u in db.scalars(select(User))}
