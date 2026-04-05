from s2a.normalize.models import CrawlSnapshot, JsonDataProbe, PageSnapshot, SiteProbe
from s2a.normalize.transform import build_report


def test_build_report_counts_json_and_password_pages() -> None:
    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example",
        probably_squarespace=True,
        version_hint="7.x",
        password_gate_detected=False,
        json_probe=JsonDataProbe(
            source_url="https://example.com/",
            json_url="https://example.com/?format=json-pretty",
            attempted=True,
            available=True,
            status_code=200,
        ),
        sitemap_status_code=200,
        sitemap_entries=["https://example.com/"],
    )
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=probe,
        pages=[
            PageSnapshot(
                requested_url="https://example.com/",
                final_url="https://example.com/",
                status_code=200,
                content_type="text/html",
                title="Home",
                meta_description=None,
                canonical_url="https://example.com/",
                json_probe=JsonDataProbe(
                    source_url="https://example.com/",
                    json_url="https://example.com/?format=json-pretty",
                    attempted=True,
                    available=True,
                    status_code=200,
                ),
                asset_urls=["https://example.com/logo.png"],
                internal_links=["https://example.com/about"],
            ),
            PageSnapshot(
                requested_url="https://example.com/private",
                final_url="https://example.com/private",
                status_code=200,
                content_type="text/html",
                title="Private",
                meta_description=None,
                canonical_url="https://example.com/private",
                password_gate_detected=True,
            ),
        ],
    )

    report = build_report(snapshot)

    assert report.pages_crawled == 2
    assert report.ok_pages == 2
    assert report.pages_with_json == 1
    assert report.password_gated_pages == 1
    assert report.unique_assets == 1
    assert report.unique_internal_links == 1
    assert report.manual_follow_up == [
        "Password-gated pages were detected. Use auth-browser or crawl/migrate with --site-password or --storage-state to capture authenticated content before generating the final site."
    ]
