from s2a.extract.media import build_media_manifest, extract_media_references
from s2a.normalize.models import CrawlSnapshot, PageSnapshot, SiteProbe


def test_extracts_vimeo_privacy_hash_from_direct_iframe() -> None:
    result = extract_media_references(
        '<iframe src="https://player.vimeo.com/video/123456789?h=deadbeef&title=0"></iframe>',
        None,
    )

    assert result.unresolved == []
    assert len(result.references) == 1
    reference = result.references[0]
    assert reference.provider == "vimeo"
    assert reference.video_id == "123456789"
    assert reference.privacy_token == "deadbeef"
    assert reference.embed_url == "https://player.vimeo.com/video/123456789?h=deadbeef"
    assert reference.source_kinds == ["html"]
    assert reference.confidence == "high"


def test_extracts_encoded_vimeo_configuration_from_squarespace_json() -> None:
    payload = {
        "block": {
            "providerName": "Vimeo",
            "videoId": "987654321",
            "embedUrl": "https%3A%2F%2Fplayer.vimeo.com%2Fvideo%2F987654321%3Fh%3Dabc123",
        }
    }

    result = extract_media_references(None, payload)

    assert result.unresolved == []
    assert len(result.references) == 1
    reference = result.references[0]
    assert reference.provider == "vimeo"
    assert reference.video_id == "987654321"
    assert reference.privacy_token == "abc123"
    assert reference.embed_url == "https://player.vimeo.com/video/987654321?h=abc123"
    assert reference.source_kinds == ["json"]


def test_extracts_youtube_nocookie_from_escaped_json_html() -> None:
    payload = {
        "embedData": {
            "html": '<iframe src="https:\\/\\/www.youtube-nocookie.com\\/embed\\/dQw4w9WgXcQ"></iframe>'
        }
    }

    result = extract_media_references(None, payload)

    assert result.unresolved == []
    assert len(result.references) == 1
    reference = result.references[0]
    assert reference.provider == "youtube"
    assert reference.video_id == "dQw4w9WgXcQ"
    assert reference.embed_url == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


def test_merges_html_and_json_references_without_losing_privacy_hash() -> None:
    html = '<a href="https://vimeo.com/246813579">Watch</a>'
    payload = {
        "providerName": "Vimeo",
        "videoId": "246813579",
        "url": "https://vimeo.com/246813579/privatehash",
    }

    result = extract_media_references(html, payload)

    assert len(result.references) == 1
    reference = result.references[0]
    assert reference.video_id == "246813579"
    assert reference.privacy_token == "privatehash"
    assert reference.source_kinds == ["html", "json"]
    assert reference.occurrences >= 2


def test_reports_provider_mentions_without_stable_ids() -> None:
    result = extract_media_references(
        "This page contains a Vimeo work, but its player data is unavailable.",
        None,
    )

    assert result.references == []
    assert len(result.unresolved) == 1
    assert result.unresolved[0].provider == "vimeo"
    assert result.unresolved[0].source_kinds == ["html"]


def test_build_media_manifest_flattens_page_media() -> None:
    media = extract_media_references(
        '<iframe src="https://player.vimeo.com/video/123456789?h=deadbeef"></iframe>',
        None,
    )
    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example",
        probably_squarespace=True,
    )
    snapshot = CrawlSnapshot(
        generated_at="2026-07-23T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=probe,
        pages=[
            PageSnapshot(
                requested_url="https://example.com/work",
                final_url="https://example.com/work",
                status_code=200,
                content_type="text/html",
                title="Work",
                meta_description=None,
                canonical_url="https://example.com/work",
                media=media.references,
                unresolved_media=media.unresolved,
            )
        ],
    )

    manifest = build_media_manifest(snapshot)

    assert manifest["counts"] == {
        "media_references": 1,
        "pages_with_media": 1,
        "unresolved_provider_mentions": 0,
        "by_provider": {"vimeo": 1},
    }
    assert manifest["items"][0]["owner_route"] == "/work"
    assert manifest["items"][0]["privacy_token"] == "deadbeef"
