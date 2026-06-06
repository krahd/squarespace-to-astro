from __future__ import annotations

import httpx

from s2a.extract.crawl import extract_urls_from_rss_feeds


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
