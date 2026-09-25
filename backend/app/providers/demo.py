from datetime import datetime, timedelta, timezone
from app.schemas import EvidenceInput


class DemoProvider:
    def collect(self, technology_id, query, limit):
        return [
            EvidenceInput(
                technology_id=technology_id,
                source_type="news",
                source_id=f"demo-pipeline:{technology_id}:{i}",
                title=f"[Sample] {query}: pilot validation signal {i + 1}",
                url=f"https://example.com/pipeline/{technology_id}/{i}",
                content="Synthetic demonstration signal. A fictional pilot reports test activity; no real-world claim is made.",
                published_at=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i),
                provider="Demo",
                metadata_json={"domain": "example.com", "query": query},
                is_demo=True,
            )
            for i in range(limit)
        ]
