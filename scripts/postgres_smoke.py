"""PostgreSQL/pgvector acceptance smoke for CI or a running local database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import select, func, text
from app.db import SessionLocal
from app.models import Evidence, Technology, PipelineRun
from app.pipelines.runner import create_run, execute_run
from app.ai.retrieval import retrieve

with SessionLocal() as db:
    assert db.bind.dialect.name == 'postgresql'
    assert db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')"))
    assert db.scalar(select(func.count()).select_from(Technology)) == 15
    before = db.scalar(select(func.count()).select_from(Evidence))
    technology_id = db.scalar(select(Technology.id))
    run = create_run(db, 'demo', technology_id, 2)
    run_id = run.id
execute_run(run_id, fail_before_commit=True)
with SessionLocal() as db:
    assert db.get(PipelineRun, run_id).status == 'Failed'
    assert db.scalar(select(func.count()).select_from(Evidence)) == before
    run = create_run(db, 'demo', technology_id, 2)
    run_id = run.id
execute_run(run_id)
with SessionLocal() as db:
    assert db.get(PipelineRun, run_id).status == 'Successful'
    assert db.scalar(select(func.count()).select_from(Evidence)) == before + 2
    assert retrieve(db, 'grid forming converter', technology_id, True)
print('PostgreSQL migration, seed, atomic rollback, merge and retrieval passed.')
