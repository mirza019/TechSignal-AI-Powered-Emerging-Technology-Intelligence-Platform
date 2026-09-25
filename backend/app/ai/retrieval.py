"""Bounded retrieval with deterministic local subword embeddings.

The offline encoder is deliberately lightweight (hashed word/bigram features),
not a pretrained language model. FAISS handles cosine retrieval; PostgreSQL may
use pgvector. Encoder version/dimension must change together on migration.
"""

from functools import lru_cache
import hashlib
import re
import numpy as np
from sqlalchemy import select, text
from app.models import Evidence, SystemSetting, Organization
from app.config import get_settings
from app.repositories.evidence import evidence_for

DIM = 384
ENCODER = "local-hash-word-bigram-v1"


@lru_cache(maxsize=1)
def semantic_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def encoder_name():
    cfg = get_settings()
    return cfg.embedding_model if cfg.embedding_backend == "sentence-transformers" else ENCODER


def embed(value):
    if get_settings().embedding_backend == "sentence-transformers":
        result = semantic_model().encode(value, normalize_embeddings=True)
        if len(result) != DIM:
            raise ValueError("Semantic encoder must produce 384 dimensions")
        return result.tolist()
    words = re.findall(r"[a-z0-9]+", value.lower())
    features = words + [" ".join(pair) for pair in zip(words, words[1:])]
    vec = np.zeros(DIM, dtype=np.float32)
    for word in features:
        h = hashlib.sha256(word.encode()).digest()
        vec[int.from_bytes(h[:4], "little") % DIM] += 1 if h[4] % 2 else -1
    norm = np.linalg.norm(vec)
    return (vec / norm if norm else vec).tolist()


def generate_embeddings(db):
    setting = db.get(SystemSetting, "embedding_encoder")
    changed = not setting or setting.value.get("name") != encoder_name() or setting.value.get("dimensions") != DIM
    records = db.scalars(select(Evidence) if changed else select(Evidence).where(Evidence.embedding.is_(None))).all()
    if not setting:
        setting = SystemSetting(key="embedding_encoder", value={})
        db.add(setting)
    setting.value = {"name": encoder_name(), "dimensions": DIM}
    for record in records:
        record.embedding = embed(record.title + " " + record.content)
    organizations = db.scalars(select(Organization) if changed else select(Organization).where(Organization.embedding.is_(None))).all()
    for organization in organizations:
        organization.embedding = embed(organization.name + " " + organization.description)
    db.flush()
    if db.bind.dialect.name == "postgresql":
        # The optional extension/table is provisioned by migration 0002.
        available = db.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')"))
        if available:
            for record in records:
                db.execute(
                    text(
                        "INSERT INTO evidence_vectors (evidence_id, embedding) VALUES (:id, CAST(:v AS vector)) ON CONFLICT (evidence_id) DO UPDATE SET embedding=EXCLUDED.embedding"
                    ),
                    {"id": record.id, "v": str(record.embedding)},
                )
    return len(records)


def retrieve(db, query, technology_id=None, is_demo=True, organization_id=None, limit=8):
    stmt = evidence_for(db, technology_id, is_demo)
    if organization_id:
        from app.models import PaperInstitution

        linked = select(PaperInstitution.paper_id).where(PaperInstitution.institution_id == organization_id)
        stmt = stmt.where((Evidence.organization_id == organization_id) | Evidence.id.in_(linked))
    # Bounded candidate set; full corpus never enters the LLM context.
    records = db.scalars(stmt.order_by(Evidence.published_at.desc()).limit(2000)).all()
    if not records:
        return []
    vector = np.array([embed(query)], dtype="float32")
    setting = db.get(SystemSetting, "embedding_encoder")
    compatible = bool(setting and setting.value.get("name") == encoder_name() and setting.value.get("dimensions") == DIM)
    if compatible and db.bind.dialect.name == "postgresql" and db.scalar(text("SELECT to_regclass('evidence_vectors') IS NOT NULL")):
        from sqlalchemy import bindparam

        ids = [r.id for r in records]
        statement = text(
            "SELECT evidence_id FROM evidence_vectors WHERE evidence_id IN :ids ORDER BY embedding <=> CAST(:vector AS vector) LIMIT :limit"
        ).bindparams(bindparam("ids", expanding=True))
        order = list(db.scalars(statement, {"ids": ids, "vector": str(vector[0].tolist()), "limit": limit}))
        if len(order) == min(limit, len(records)):
            indexed = {r.id: r for r in records}
            return [indexed[id] for id in order]
    matrix = np.array(
        [r.embedding if compatible and r.embedding and len(r.embedding) == DIM else embed(r.title + " " + r.content) for r in records],
        dtype="float32",
    )
    try:
        import faiss

        index = faiss.IndexFlatIP(DIM)
        index.add(matrix)
        _, order = index.search(vector, min(limit, len(records)))
        return [records[int(i)] for i in order[0]]
    except ImportError:
        order = np.argsort(-(matrix @ vector[0]))[:limit]
        return [records[int(i)] for i in order]
