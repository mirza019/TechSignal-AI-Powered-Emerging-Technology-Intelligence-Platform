from datetime import datetime, timezone
from app.config import get_settings
from app.providers.base import get_json
from app.schemas import EvidenceInput


class GDELTProvider:
    def collect(self, technology_id, query, limit):
        if not get_settings().enable_gdelt:
            raise ValueError("GDELT is disabled")
        data = get_json(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            {"query": query, "mode": "artlist", "format": "json", "maxrecords": min(limit, 100), "sort": "datedesc", "timespan": "3months"},
        )
        records = []
        for article in data.get("articles", []):
            date = datetime.strptime(article["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            records.append(
                EvidenceInput(
                    technology_id=technology_id,
                    source_type="news",
                    source_id="gdelt:" + article["url"],
                    title=article["title"],
                    url=article["url"],
                    content="",
                    published_at=date,
                    provider="GDELT",
                    metadata_json={
                        "domain": article.get("domain", ""),
                        "language": article.get("language", ""),
                        "query": query,
                        "date_semantics": "GDELT first-seen timestamp; not independently verified publication date",
                    },
                )
            )
        return records
