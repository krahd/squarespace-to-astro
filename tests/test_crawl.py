from __future__ import annotations

import httpx
import pytest

from s2a.extract.crawl import extract_urls_from_rss_feeds
from s2a.probe import probe_site


def test_extract_urls_from_rss_feeds_prefers_atom_alternate_links() -> None:
    feed_url = "https://example.com/feed.atom"
    atom_feed = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Feed</title>
  <entry>
    <title>First Post</title>
    <link rel="self" href="https://example.com/feeds/posts/1" />
    <link rel="alternate" href="https://example.com/blog/first-post" />
  </entry>
</feed>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == feed_url
        return httpx.Response(
            200,
            content=atom_feed.encode("utf-8"),
            headers={"content-type": "application/atom+xml"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        urls = extract_urls_from_rss_feeds(client, [feed_url], "https://example.com")

    assert urls == ["https://example.com/blog/first-post"]


@pytest.mark.parametrize(
    ("feed_url", "feed_xml", "content_type"),
    [
        (
            "https://example.com/feed.xml",
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE rss [
  <!ENTITY xxe SYSTEM "https://example.com/evil-rss">
]>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Bad Post</title>
      <link>&xxe;</link>
    </item>
  </channel>
</rss>
""",
            "application/rss+xml",
        ),
        (
            "https://example.com/feed.atom",
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE feed [
  <!ENTITY xxe SYSTEM "https://example.com/evil-atom">
]>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Feed</title>
  <entry>
    <title>Bad Entry</title>
    <link rel="alternate" href="&xxe;" />
  </entry>
</feed>
""",
            "application/atom+xml",
        ),
    ],
)
def test_extract_urls_from_rss_feeds_rejects_entity_expansion(
    feed_url: str, feed_xml: str, content_type: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == feed_url
        return httpx.Response(
            200,
            content=feed_xml.encode("utf-8"),
            headers={"content-type": content_type},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        urls = extract_urls_from_rss_feeds(client, [feed_url], "https://example.com")

    assert urls == []


def test_probe_site_rejects_entity_expansion_in_sitemap() -> None:
    target_url = "https://example.com/"
    robots_url = "https://example.com/robots.txt"
    sitemap_url = "https://example.com/sitemap.xml"
    home_html = """<html><head><meta name="generator" content="Squarespace"></head><body>Home</body></html>"""
    robots_txt = f"User-agent: *\nSitemap: {sitemap_url}\n"
    malicious_sitemap = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE urlset [
  <!ENTITY xxe SYSTEM "https://example.com/evil-sitemap">
]>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>&xxe;</loc>
  </url>
</urlset>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == target_url:
            return httpx.Response(
                200,
                content=home_html.encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if url == f"{target_url}?format=json-pretty":
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        if url == robots_url:
            return httpx.Response(
                200,
                content=robots_txt.encode("utf-8"),
                headers={"content-type": "text/plain; charset=utf-8"},
            )
        if url == sitemap_url:
            return httpx.Response(
                200,
                content=malicious_sitemap.encode("utf-8"),
                headers={"content-type": "application/xml; charset=utf-8"},
            )
        raise AssertionError(f"Unexpected request: {url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        probe = probe_site(client, target_url)

    assert probe.sitemap_url == sitemap_url
    assert probe.sitemap_entries == []
    assert any("Could not parse sitemap XML" in warning for warning in probe.warnings)
