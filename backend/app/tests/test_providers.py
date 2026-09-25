from unittest.mock import patch
import pytest
from app.providers.openalex import OpenAlexProvider, reconstruct_abstract
from app.providers.gdelt import GDELTProvider
from app.scrapers.public import validate_public_url


def test_openalex_adapter():
    fixture = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "display_name": "Grid forming converter evaluation",
                "publication_date": "2025-01-01",
                "doi": "https://doi.org/10.123/ABC",
                "cited_by_count": 12,
                "abstract_inverted_index": {"Grid": [0], "converters": [1]},
                "authorships": [
                    {
                        "author": {"id": "A1", "display_name": "Test Author"},
                        "institutions": [{"id": "I1", "display_name": "Test Institute", "country_code": "DE"}],
                    }
                ],
            }
        ]
    }
    with patch("app.providers.openalex.get_json", return_value=fixture):
        record = OpenAlexProvider().collect("tech", "grid converter", 1)[0]
    assert record.content == "Grid converters" and record.doi == "10.123/abc"
    assert record.metadata_json["institutions"][0]["name"] == "Test Institute"
    assert reconstruct_abstract(None) == ""


def test_gdelt_adapter():
    fixture = {
        "articles": [
            {
                "url": "https://news.example.org/a?utm_campaign=x",
                "title": "Converter pilot announced",
                "seendate": "20250101T120000Z",
                "domain": "news.example.org",
                "language": "English",
            }
        ]
    }
    with patch("app.providers.gdelt.get_json", return_value=fixture):
        record = GDELTProvider().collect("tech", "converter", 1)[0]
    assert record.content == "" and record.url == "https://news.example.org/a"
    assert "first-seen" in record.metadata_json["date_semantics"]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/a",
        "http://127.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://example.org:444/a",
    ],
)
def test_ssrf_rejected(url):
    with pytest.raises(ValueError):
        validate_public_url(url, ["example.org"])


def test_dns_private_address_rejected():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 443))]):
        with pytest.raises(ValueError, match="Private"):
            validate_public_url("https://approved.org/a", ["approved.org"])


def test_robots_denial_prevents_page_request(monkeypatch):
    from app.scrapers.public import PublicScraper

    scraper = PublicScraper()
    monkeypatch.setattr(scraper.settings, "enable_web_scraping", True)
    monkeypatch.setattr(scraper.settings, "scraper_allowed_domains", ["approved.org"])
    monkeypatch.setattr("app.scrapers.public.validate_public_url", lambda url, domains: (url, "93.184.216.34"))
    called = []

    def fetch(url):
        called.append(url)
        return "User-agent: *\nDisallow: /"

    monkeypatch.setattr(scraper, "fetch", fetch)
    with pytest.raises(ValueError, match="robots.txt"):
        scraper.collect_page("https://approved.org/page", "technology")
    assert called == ["https://approved.org/robots.txt"]


def test_scraper_retains_only_fragments(monkeypatch):
    from app.scrapers.public import PublicScraper

    scraper = PublicScraper()
    monkeypatch.setattr(scraper.settings, "enable_web_scraping", True)
    monkeypatch.setattr(scraper.settings, "scraper_allowed_domains", ["approved.org"])
    monkeypatch.setattr("app.scrapers.public.validate_public_url", lambda url, domains: (url, "93.184.216.34"))

    def fetch(url):
        if url.endswith("robots.txt"):
            return "User-agent: *\nAllow: /"
        return "<html><title>Public test research</title><nav>Discard navigation</nav><main><p>A factual public research fragment long enough for the approved page parser to retain.</p></main><script>secret irrelevant script</script></html>"

    monkeypatch.setattr(scraper, "fetch", fetch)
    result = scraper.collect_page("https://approved.org/page", "technology")
    assert "factual public research" in result.content
    assert "script" not in result.content and "navigation" not in result.content
