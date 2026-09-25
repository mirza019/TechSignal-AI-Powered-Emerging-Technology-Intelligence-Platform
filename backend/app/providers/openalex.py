from datetime import date

from app.config import get_settings
from app.providers.base import get_json
from app.schemas import EvidenceInput


def reconstruct_abstract(index):
    if not index:
        return ""
    words = {position: word for word, positions in index.items() for position in positions if 0 <= position < 5000}
    return " ".join(words[i] for i in sorted(words))[:12000]


class OpenAlexProvider:
    def collect(self, technology_id, query, limit):
        key = get_settings().openalex_api_key
        response = get_json(
            "https://api.openalex.org/works",
            {"search": query, "per-page": min(limit, 100), "sort": "publication_date:desc"},
            {"Authorization": f"Bearer {key}"} if key else {},
        )
        records = []
        for work in response.get("results", []):
            if not work.get("publication_date") or not work.get("display_name"):
                continue
            try:
                publication_date = date.fromisoformat(work["publication_date"])
            except (TypeError, ValueError):
                continue
            if publication_date > date.today():
                continue
            authors = []
            institutions = {}
            for authorship in work.get("authorships", []):
                author = authorship.get("author") or {}
                if author.get("id"):
                    authors.append({"id": author["id"], "name": author.get("display_name", "Unknown")})
                for inst in authorship.get("institutions", []):
                    if inst.get("id"):
                        institutions[inst["id"]] = {
                            "id": inst["id"],
                            "name": inst.get("display_name", "Unknown"),
                            "country": inst.get("country_code") or "Unknown",
                        }
            source = (work.get("primary_location") or {}).get("source") or {}
            records.append(
                EvidenceInput(
                    technology_id=technology_id,
                    source_type="paper",
                    source_id=work["id"],
                    title=work["display_name"],
                    url=work.get("doi") or work["id"],
                    doi=work.get("doi"),
                    content=reconstruct_abstract(work.get("abstract_inverted_index")),
                    published_at=publication_date.isoformat() + "T00:00:00Z",
                    provider="OpenAlex",
                    metadata_json={
                        "citation_count": work.get("cited_by_count", 0),
                        "authors": authors,
                        "institutions": list(institutions.values()),
                        "journal": source.get("display_name", ""),
                        "topics": [t.get("display_name") for t in work.get("topics", [])],
                        "query": query,
                    },
                )
            )
        return records
