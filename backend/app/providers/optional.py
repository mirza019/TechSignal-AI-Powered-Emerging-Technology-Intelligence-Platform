from app.config import get_settings
from app.providers.base import get_json


class SemanticScholarProvider:
    def enrich(self, doi: str):
        settings = get_settings()
        if not settings.enable_semantic_scholar:
            return None
        from urllib.parse import quote

        return get_json(
            "https://api.semanticscholar.org/graph/v1/paper/DOI:" + quote(doi, safe=""),
            {"fields": "title,authors,year,citationCount,abstract,url,paperId"},
            {"x-api-key": settings.semantic_scholar_api_key} if settings.semantic_scholar_api_key else {},
        )


class EPOProvider:
    """Reserved provider boundary. OPS requires credentials and licensing review."""

    def collect(self, technology_id, query, limit):
        raise NotImplementedError("EPO OPS integration is not implemented in v1; patent counts are never fabricated")
