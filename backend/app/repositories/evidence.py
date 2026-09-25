from difflib import SequenceMatcher
from sqlalchemy import select, or_
from app.models import (
    Evidence,
    EvidenceTechnology,
    Paper,
    News,
    Author,
    PaperAuthor,
    Institution,
    Organization,
    PaperInstitution,
    Technology,
)
from app.schemas import EvidenceInput
from app.utils.records import digest, normalize_name


def evidence_for(db, technology_id=None, is_demo=None):
    query = select(Evidence)
    if technology_id:
        ids = select(EvidenceTechnology.evidence_id).where(EvidenceTechnology.technology_id == technology_id)
        query = query.where(or_(Evidence.technology_id == technology_id, Evidence.id.in_(ids)))
    if is_demo is not None:
        query = query.where(Evidence.is_demo == is_demo)
    return query


def upsert_evidence(db, record: EvidenceInput, run_id=None):
    if not db.get(Technology, record.technology_id):
        raise ValueError("Missing technology mapping")
    conditions = [Evidence.url == record.url]
    if record.source_id:
        conditions.append(Evidence.source_id == record.source_id)
    if record.doi:
        conditions.append(Evidence.doi == record.doi)
    existing = db.scalar(select(Evidence).where(or_(*conditions)))
    content_hash = digest(record.title + "\n" + record.content)
    if not existing:
        existing = db.scalar(select(Evidence).where(Evidence.content_hash == content_hash, Evidence.is_demo == record.is_demo))
    if not existing:
        candidates = db.scalars(
            evidence_for(db, record.technology_id, record.is_demo).where(Evidence.source_type == record.source_type)
        ).all()
        title = normalize_name(record.title)
        existing = next(
            (
                e
                for e in candidates
                if not (e.provider == record.provider and e.source_id and record.source_id and e.source_id != record.source_id)
                and abs((e.published_at.date() - record.published_at.date()).days) <= 7
                and SequenceMatcher(None, normalize_name(e.title), title).ratio() > 0.97
            ),
            None,
        )
    inserted = existing is None
    if existing and existing.is_demo != record.is_demo:
        raise ValueError("Demo/live identity collision")
    if not existing:
        existing = Evidence(**record.model_dump(), content_hash=content_hash, run_id=run_id)
        db.add(existing)
        db.flush()
    else:
        # Source identifiers/URLs remain stable; merge changed content and metadata.
        if existing.content_hash != content_hash or existing.metadata_json != record.metadata_json:
            existing.title = record.title
            existing.content = record.content
            existing.metadata_json = record.metadata_json
            existing.content_hash = content_hash
            existing.version += 1
            existing.embedding = None
            existing.run_id = run_id
    if not db.get(EvidenceTechnology, (existing.id, record.technology_id)):
        db.add(EvidenceTechnology(evidence_id=existing.id, technology_id=record.technology_id))
    meta = record.metadata_json
    if record.source_type == "paper":
        paper = db.get(Paper, existing.id)
        if not paper:
            paper = Paper(evidence_id=existing.id)
            db.add(paper)
        paper.citation_count = int(meta.get("citation_count", 0))
        paper.journal = meta.get("journal", "")
        paper.topics = meta.get("topics", [])
        paper.semantic_scholar_id = meta.get("semantic_scholar", {}).get("paperId") or paper.semantic_scholar_id
        db.flush()
        for a in meta.get("authors", []):
            author = db.scalar(select(Author).where(Author.source_id == a["id"]))
            if not author:
                author = Author(name=a["name"], source_id=a["id"])
                db.add(author)
                db.flush()
            if not db.get(PaperAuthor, (existing.id, author.id)):
                db.add(PaperAuthor(paper_id=existing.id, author_id=author.id))
        for i in meta.get("institutions", []):
            institution = db.scalar(select(Institution).where(Institution.openalex_id == i["id"]))
            if not institution:
                org = db.scalar(select(Organization).where(Organization.normalized_name == normalize_name(i["name"])))
                if not org:
                    org = Organization(
                        name=i["name"],
                        normalized_name=normalize_name(i["name"]),
                        kind="institution",
                        country=i.get("country", "Unknown"),
                        is_demo=record.is_demo,
                        domains=[],
                    )
                    db.add(org)
                    db.flush()
                institution = db.get(Institution, org.id)
                if not institution:
                    institution = Institution(organization_id=org.id, openalex_id=i["id"])
                    db.add(institution)
                    db.flush()
            linked_org = db.get(Organization, institution.organization_id)
            technology = db.get(Technology, record.technology_id)
            if technology.domain not in linked_org.domains:
                linked_org.domains = linked_org.domains + [technology.domain]
            if not linked_org.description:
                linked_org.description = f"Institution listed in {record.provider} research affiliations; country code {linked_org.country}. See linked publications for the verified research scope."
                linked_org.embedding = None
            if not linked_org.website and i["id"].startswith("https://"):
                linked_org.website = i["id"]
            if not db.get(PaperInstitution, (existing.id, institution.organization_id)):
                db.add(PaperInstitution(paper_id=existing.id, institution_id=institution.organization_id))
    if record.source_type == "news":
        news = db.get(News, existing.id)
        if not news:
            news = News(
                evidence_id=existing.id,
                domain=meta.get("domain", ""),
                language=meta.get("language", "Unknown"),
                query=meta.get("query", ""),
            )
            db.add(news)
    return existing, inserted
