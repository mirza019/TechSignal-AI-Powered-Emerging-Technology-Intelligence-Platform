"""Optional pgvector acceleration; FAISS remains available without extension privileges."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0c84da38558c"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return
    # Use a savepoint so a managed database without extension permissions is usable.
    try:
        with connection.begin_nested():
            connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    except sa.exc.DBAPIError:
        return
    connection.execute(
        sa.text(
            "CREATE TABLE evidence_vectors (evidence_id VARCHAR(36) PRIMARY KEY REFERENCES technology_evidence(id) ON DELETE CASCADE, embedding vector(384) NOT NULL)"
        )
    )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS evidence_vectors")
