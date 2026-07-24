from __future__ import annotations

import json
from pathlib import Path

import httpx

from s2a.extract.crawl import crawl_site
from s2a.files import read_json
from s2a.normalize.models import SiteProbe


def test_crawl_extracts_lazy_squarespace_video_json_and_writes_manifest(
    tmp_path: Path,
) -> None:
    page_url = "https://example.com/work"
    html = """<!doctype html>
    <html><head><title>Work</title><link rel="canonical" href="https://example.com/work"></head>
    <body><main><h1>Work</h1><div class="sqs-video-block">Video</div></main></body></html>
    """
    payload = {
        "item": {
            "title": "Work",
            "blocks": [
                {
                    "type": "video",
                    "providerName": "Vimeo",
                    "videoId": "987654321",
                    "embedUrl": "https://player.vimeo.com/video/987654321?h=privatehash",
                }
            ],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == page_url:
            return httpx.Response(
                200,
                content=html.encode(),
                headers={"content-type": "text/html; charset=utf-8"},
                request=request,
            )
        if url == f"{page_url}?format=json-pretty":
            return httpx.Response(
                200,
                content=json.dumps(payload).encode(),
                headers={"content-type": "application/json; charset=utf-8"},
                request=request,
            )
        raise AssertionError(f"Unexpected request: {url}")

    probe = SiteProbe(
        target_url=page_url,
        final_home_url=page_url,
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Work",
        probably_squarespace=True,
    )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = crawl_site(client, probe, tmp_path, max_pages=10)

    assert len(snapshot.pages) == 1
    page = snapshot.pages[0]
    assert len(page.media) == 1
    assert page.media[0].provider == "vimeo"
    assert page.media[0].video_id == "987654321"
    assert page.media[0].privacy_token == "privatehash"
    assert page.media[0].source_kinds == ["json"]

    manifest = read_json(tmp_path / "media_manifest.json")
    assert manifest["counts"]["media_references"] == 1
    assert manifest["counts"]["pages_with_media"] == 1
    assert manifest["items"][0]["owner_route"] == "/work"
    assert manifest["items"][0]["embed_url"] == (
        "https://player.vimeo.com/video/987654321?h=privatehash"
    )
