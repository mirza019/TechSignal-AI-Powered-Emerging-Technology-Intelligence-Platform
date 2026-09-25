"""Public-page scraper. Exact domain allowlist, robots and pinned public IPs.

Redirects are deliberately rejected to avoid crossing an access boundary.
Only text fragments are retained. JavaScript-only sources require manual review.
"""

import ipaddress
import socket
import time
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from app.config import get_settings
from app.schemas import EvidenceInput
from app.utils.records import normalize_url


def validate_public_url(url: str, allowed_domains: list[str]):
    url = normalize_url(url)
    p = urlsplit(url)
    if p.hostname not in allowed_domains or p.port not in (None, 80, 443):
        raise ValueError("URL is outside the exact domain allowlist or uses a disallowed port")
    addresses = {
        item[4][0] for item in socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    }
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Private, loopback and reserved addresses are forbidden")
    return url, sorted(addresses)[0]


class PinnedAdapter(HTTPAdapter):
    def __init__(self, hostname, **kwargs):
        self.hostname = hostname
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs.update(assert_hostname=self.hostname, server_hostname=self.hostname)
        return super().init_poolmanager(*args, **kwargs)


class PublicScraper:
    _lock = threading.Lock()
    _last: dict[str, float] = {}

    def __init__(self):
        self.settings = get_settings()

    def fetch(self, url):
        canonical, ip = validate_public_url(url, self.settings.scraper_allowed_domains)
        p = urlsplit(canonical)
        with self._lock:
            delay = self.settings.scraper_interval - (time.monotonic() - self._last.get(p.hostname, 0))
            if delay > 0:
                time.sleep(delay)
            self._last[p.hostname] = time.monotonic()
        address = f"[{ip}]" if ":" in ip else ip
        target = p._replace(netloc=address + (f":{p.port}" if p.port else "")).geturl()
        for attempt in range(3):
            try:
                with requests.Session() as session:
                    session.trust_env = False
                    if p.scheme == "https":
                        session.mount("https://", PinnedAdapter(p.hostname))
                    with session.get(
                        target,
                        headers={"Host": p.netloc, "User-Agent": self.settings.scraper_user_agent},
                        timeout=(5, 15),
                        allow_redirects=False,
                        stream=True,
                    ) as response:
                        if 300 <= response.status_code < 400:
                            raise ValueError("Redirect refused; approve the destination explicitly")
                        response.raise_for_status()
                        if "text/" not in response.headers.get("Content-Type", ""):
                            raise ValueError("Only public text content can be scraped")
                        content = bytearray()
                        for chunk in response.iter_content(16384):
                            content.extend(chunk)
                            if len(content) > 1_000_000:
                                raise ValueError("Page exceeds 1 MB limit")
                        return content.decode(response.encoding or "utf-8", errors="replace")
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(0.5 * 2**attempt)

    def collect_page(self, url, technology_id, organization_id=None):
        if not self.settings.enable_web_scraping:
            raise ValueError("Web scraping is disabled")
        canonical, _ = validate_public_url(url, self.settings.scraper_allowed_domains)
        parsed = urlsplit(canonical)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots = RobotFileParser()
        # Fail closed if robots cannot be fetched, including missing robots.
        robots.parse(self.fetch(robots_url).splitlines())
        if not robots.can_fetch(self.settings.scraper_user_agent, canonical):
            raise ValueError("robots.txt disallows this page")
        delay = robots.crawl_delay(self.settings.scraper_user_agent) or 0
        if delay > 60:
            raise ValueError("Crawl delay exceeds interactive budget; schedule source separately")
        if delay:
            time.sleep(delay)
        soup = BeautifulSoup(self.fetch(canonical), "html.parser")
        if soup.select("input[type=password], .paywall, [data-paywall]"):
            raise ValueError("Authentication or paywall marker detected")
        for node in soup.select("script, style, nav, footer, header, form"):
            node.decompose()
        fragments = [p.get_text(" ", strip=True) for p in soup.select("main p, article p")]
        if not fragments:
            fragments = [p.get_text(" ", strip=True) for p in soup.select("p")]
        title = soup.title.get_text(" ", strip=True) if soup.title else canonical
        content = "\n".join(p[:500] for p in fragments if len(p) > 40)[:3000]
        if not content:
            raise ValueError("No factual text fragments; JS rendering is not enabled")
        return EvidenceInput(
            technology_id=technology_id,
            organization_id=organization_id,
            source_type="web",
            title=title[:2000],
            url=canonical,
            content=content,
            published_at=datetime.now(timezone.utc),
            provider="Approved public web",
            metadata_json={
                "date_semantics": "last checked; publication date unavailable",
                "last_checked": datetime.now(timezone.utc).isoformat(),
            },
        )

    def crawl(self, urls, technology_id, max_depth=0, max_pages=10):
        """Depth zero by default; follow at most one level of approved links."""
        if max_depth not in (0, 1) or not 1 <= max_pages <= 20:
            raise ValueError("Crawl depth must be 0–1 and page budget 1–20")
        queue = [(url, 0) for url in urls]
        seen, records = set(), []
        while queue and len(seen) < max_pages:
            url, depth = queue.pop(0)
            url = normalize_url(url)
            if url in seen:
                continue
            seen.add(url)
            records.append(self.collect_page(url, technology_id))
            if depth < max_depth:
                soup = BeautifulSoup(self.fetch(url), "html.parser")
                for a in soup.select("a[href]"):
                    target = urljoin(url, a["href"])
                    if urlsplit(target).hostname in self.settings.scraper_allowed_domains:
                        queue.append((target, depth + 1))
        return records
