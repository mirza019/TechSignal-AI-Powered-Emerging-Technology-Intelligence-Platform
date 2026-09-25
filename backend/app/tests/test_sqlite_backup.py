import sqlite3

from app.config import get_settings
from app.services.sqlite_backup import backup_sqlite_database, sqlite_path


def test_sqlite_snapshot_is_consistent(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    target = tmp_path / "backup" / "snapshot.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE records (value TEXT NOT NULL)")
        db.execute("INSERT INTO records VALUES ('real provider record')")
    cfg = get_settings()
    monkeypatch.setattr(cfg, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(cfg, "sqlite_backup_path", str(target))
    assert backup_sqlite_database() is True
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT value FROM records").fetchone() == ("real provider record",)
    assert sqlite_path("postgresql://example/radar") is None
