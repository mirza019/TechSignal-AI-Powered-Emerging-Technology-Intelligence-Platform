from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import get_settings


class Base(DeclarativeBase):
    pass


url = get_settings().database_url
engine = create_engine(url, pool_pre_ping=True, **({"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}))
if url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_pragmas(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")


SessionLocal = sessionmaker(engine, expire_on_commit=False)

if url.startswith("sqlite") and get_settings().sqlite_backup_path:
    from app.services.sqlite_backup import backup_sqlite_database

    @event.listens_for(SessionLocal.class_, "after_commit")
    def snapshot_after_commit(_session):
        backup_sqlite_database()


def get_db():
    with SessionLocal() as session:
        yield session
