from typing import Protocol
import threading
import time
from urllib.parse import urlsplit
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import httpx
from app.schemas import EvidenceInput


class Provider(Protocol):
    def collect(self, technology_id: str, query: str, limit: int) -> list[EvidenceInput]: ...


_lock = threading.Lock()
_last_request: dict[str, float] = {}


def get_json(url: str, params=None, headers=None):
    """Paced requests, Retry-After support and bounded transient retries.

    Provider URLs are constants in adapters. Authentication failures are not retried.
    GDELT requests are conservatively spaced to respect its public service budget.
    """
    host = urlsplit(url).hostname
    interval = 5.5 if host == "api.gdeltproject.org" else 1.1
    for attempt in range(4):
        with _lock:
            delay = interval - (time.monotonic() - _last_request.get(host, 0))
            if delay > 0:
                time.sleep(delay)
            _last_request[host] = time.monotonic()
        try:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.get(url, params=params, headers={"User-Agent": "GridRadarPortfolio/1.0", **(headers or {})})
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    retry = response.headers.get("Retry-After", "")
                    try:
                        wait = float(retry)
                    except ValueError:
                        try:
                            wait = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                        except (ValueError, TypeError):
                            wait = 4 * 2**attempt
                    time.sleep(min(30, max(interval, wait)))
                    continue
                response.raise_for_status()
                return response.json()
        except (httpx.TransportError, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 * 2**attempt)
    raise RuntimeError("Provider retry budget exhausted")
