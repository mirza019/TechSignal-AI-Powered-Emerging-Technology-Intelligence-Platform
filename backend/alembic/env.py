from alembic import context
from sqlalchemy import create_engine
from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401

config = context.config


def include_object(obj, name, type_, reflected, compare_to):
    return name != "evidence_vectors"


if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=Base.metadata, include_object=include_object, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_object=include_object,
            render_as_batch=engine.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
