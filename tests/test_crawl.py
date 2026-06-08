from __future__ import annotations

import json
import httpx
import pytest
from urllib.parse import urlsplit

from s2a.extract.crawl import crawl_site, extract_urls_from_rss_feeds
from s2a.probe import probe_site

HOME_URL = "https://example.com/"
PROJECT_URLS = [
    f"{HOME_URL}projects/alpha",
    f"{HOME_URL}projects/beta",
]
REDIRECT_URL = f"{HOME_URL}projects/abandoned-future"
EXTERNAL_REDIRECT_TARGET = "https://external.example.com/"


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


def test_probe_site_discovers_rss_atom_and_json_links() -> None:
    rss_url = f"{HOME_URL}feed.xml"
    atom_url = f"{HOME_URL}feed.atom"
    home_html = f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"generator\" content=\"Squarespace\" />
    <title>Example Site</title>
    <link rel=\"alternate\" type=\"application/rss+xml\" href=\"{rss_url}\" />
    <link rel=\"alternate\" type=\"application/atom+xml\" href=\"{atom_url}\" />
  </head>
  <body>
    <main><a href=\"/about\">About</a></main>
  </body>
</html>
"""
    json_payload = {
        "collection": {"fullUrl": "/"},
        "items": [{"fullUrl": url} for url in PROJECT_URLS],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == HOME_URL:
            return httpx.Response(
                200,
                content=home_html.encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if url == f"{HOME_URL}?format=json-pretty":
            return httpx.Response(
                200,
                content=json.dumps(json_payload).encode("utf-8"),
                headers={"content-type": "application/json; charset=utf-8"},
            )
        if url.endswith("?format=json-pretty"):
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        if url in {f"{HOME_URL}robots.txt", f"{HOME_URL}sitemap.xml"}:
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        raise AssertionError(f"Unexpected request: {url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        probe = probe_site(client, HOME_URL)

    assert probe.rss_feeds == [rss_url, atom_url]
    assert set(probe.json_links) == {HOME_URL, *PROJECT_URLS}


def test_crawl_site_uses_json_links_as_seeds(tmp_path) -> None:
    home_html = """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"generator\" content=\"Squarespace\" />
    <title>Example Site</title>
  </head>
  <body>
    <main>
      <a href=\"/about\">About</a>
    </main>
  </body>
</html>
"""
    about_html = """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"generator\" content=\"Squarespace\" />
    <title>About</title>
  </head>
  <body>
    <main><article><h1>About</h1></article></main>
  </body>
</html>
"""
    json_payload = {
        "collection": {"fullUrl": "/"},
        "items": [{"fullUrl": url} for url in PROJECT_URLS],
    }
    project_html = {
        PROJECT_URLS[0]: """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"generator\" content=\"Squarespace\" />
    <title>Alpha</title>
    <link rel=\"canonical\" href=\"https://example.com/projects/alpha\" />
  </head>
  <body><main><article><h1>Alpha</h1></article></main></body>
</html>
""",
        PROJECT_URLS[1]: """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"generator\" content=\"Squarespace\" />
    <title>Beta</title>
    <link rel=\"canonical\" href=\"https://example.com/projects/beta\" />
  </head>
  <body><main><article><h1>Beta</h1></article></main></body>
</html>
""",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == HOME_URL:
            return httpx.Response(
                200,
                content=home_html.encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if url == f"{HOME_URL}about":
            return httpx.Response(
                200,
                content=about_html.encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if url == f"{HOME_URL}?format=json-pretty":
            return httpx.Response(
                200,
                content=json.dumps(json_payload).encode("utf-8"),
                headers={"content-type": "application/json; charset=utf-8"},
            )
        if url.endswith("?format=json-pretty"):
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        if url in {f"{HOME_URL}robots.txt", f"{HOME_URL}sitemap.xml"}:
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        if url in project_html:
            return httpx.Response(
                200,
                content=project_html[url].encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        raise AssertionError(f"Unexpected request: {url}")

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        probe = probe_site(client, HOME_URL)
        snapshot = crawl_site(client, probe, tmp_path / "crawl", max_pages=10)

    requested_paths = {urlsplit(page.requested_url).path or "/" for page in snapshot.pages}
    assert requested_paths == {"/", "/about", "/projects/alpha", "/projects/beta"}


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


def test_crawl_site_skips_off_origin_redirect_pages(tmp_path) -> None:
    home_html = f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"generator\" content=\"Squarespace\" />
    <title>Example Site</title>
  </head>
  <body>
    <main>
      <a href=\"{REDIRECT_URL}\">Abandoned Future</a>
    </main>
  </body>
</html>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == HOME_URL:
            return httpx.Response(
                200,
                content=home_html.encode("utf-8"),
                headers={"content-type": "text/html; charset=utf-8"},
            )
        if url == f"{HOME_URL}?format=json-pretty":
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        if url in {f"{HOME_URL}robots.txt", f"{HOME_URL}sitemap.xml"}:
            return httpx.Response(404, content=b"", headers={"content-type": "text/plain"})
        if url == REDIRECT_URL:
            return httpx.Response(
                302,
                headers={"location": EXTERNAL_REDIRECT_TARGET},
                request=request,
            )
        if url == EXTERNAL_REDIRECT_TARGET:
            return httpx.Response(
                200,
                content=b"<!doctype html><html><body><main><article><h1>External</h1></article></main></body></html>",
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )
        raise AssertionError(f"Unexpected request: {url}")

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        probe = probe_site(client, HOME_URL)
        snapshot = crawl_site(client, probe, tmp_path / "crawl", max_pages=10)

    redirected = next(page for page in snapshot.pages if page.requested_url == REDIRECT_URL)
    assert redirected.final_url == EXTERNAL_REDIRECT_TARGET
    assert redirected.external_redirect_url == EXTERNAL_REDIRECT_TARGET
    assert redirected.title is None
    assert redirected.raw_html_path is None
    assert redirected.warnings == [f"Final URL redirected off-origin to {EXTERNAL_REDIRECT_TARGET}."]
    assert all(page.requested_url != EXTERNAL_REDIRECT_TARGET for page in snapshot.pages)
