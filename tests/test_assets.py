from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from s2a.extract.assets import (
    download_snapshot_assets,
    estimate_snapshot_asset_download,
    extract_asset_references,
    is_squarespace_asset_url,
    upgrade_legacy_asset_manifest,
)
from s2a.files import read_json, write_json
from s2a.normalize.models import (
    AssetManifest,
    AssetReference,
    CrawlSnapshot,
    DownloadedAsset,
    PageSnapshot,
    SiteProbe,
)


def test_extract_asset_references_discovers_media_files_and_backgrounds() -> None:
    soup = BeautifulSoup(
        """
        <main>
          <figure>
            <img
              src="/images/hero.jpg?w=300"
              srcset="/images/hero.jpg?w=300 300w, /images/hero.jpg?w=1200 1200w"
              alt="Hero image"
            />
            <figcaption>Hero caption</figcaption>
          </figure>
          <video poster="https://images.squarespace-cdn.com/content/poster.jpg">
            <source src="https://static1.squarespace.com/media/clip.mp4" />
          </video>
          <a href="/s/guide.pdf">Guide PDF</a>
          <div style="background-image: url('/images/background.jpg?width=1200')">Backdrop</div>
        </main>
        """,
        "html.parser",
    )

    references = extract_asset_references(
        soup,
        "https://example.com/media",
        "/media",
    )

    by_url_and_attribute = {
        (reference.source_url, reference.attribute): reference
        for reference in references
    }

    hero_reference = by_url_and_attribute[
        ("https://example.com/images/hero.jpg?w=300", "src")
    ]
    hero_small_reference = by_url_and_attribute[
        ("https://example.com/images/hero.jpg?w=300", "srcset")
    ]
    hero_large_reference = by_url_and_attribute[
        ("https://example.com/images/hero.jpg?w=1200", "srcset")
    ]
    poster_reference = by_url_and_attribute[
        ("https://images.squarespace-cdn.com/content/poster.jpg", "poster")
    ]
    video_reference = by_url_and_attribute[
        ("https://static1.squarespace.com/media/clip.mp4", "src")
    ]
    file_reference = by_url_and_attribute[("https://example.com/s/guide.pdf", "href")]
    background_reference = by_url_and_attribute[
        ("https://example.com/images/background.jpg?width=1200", "style")
    ]

    assert hero_reference.asset_type == "image"
    assert hero_reference.caption == "Hero caption"
    assert hero_reference.alt_text == "Hero image"
    assert hero_small_reference.variant_hint == "small"
    assert hero_large_reference.variant_hint == "large"
    assert poster_reference.variant_hint == "poster"
    assert video_reference.asset_type == "video"
    assert file_reference.asset_type == "file"
    assert file_reference.link_text == "Guide PDF"
    assert background_reference.variant_hint == "large"


def test_is_squarespace_asset_url_matches_exact_hosts_and_subdomains() -> None:
    assert is_squarespace_asset_url(
        "https://static1.squarespace.com/media/clip.mp4"
    )
    assert is_squarespace_asset_url(
        "https://images.squarespace-cdn.com/content/hero.jpg"
    )
    assert is_squarespace_asset_url(
        "https://foo.images.squarespace-cdn.com/content/hero.jpg"
    )
    assert not is_squarespace_asset_url("https://not-squarespace.com/image.jpg")
    assert not is_squarespace_asset_url("https://squarespace.com.evil.test/image.jpg")


def test_extract_asset_references_prefers_lazy_loaded_media_attributes() -> None:
    soup = BeautifulSoup(
        """
        <main>
          <img
            src="data:image/gif;base64,abc123"
            data-src="https://images.squarespace-cdn.com/content/lazy-hero.jpg"
            data-srcset="https://images.squarespace-cdn.com/content/lazy-hero.jpg?w=400 400w, https://images.squarespace-cdn.com/content/lazy-hero.jpg?w=1400 1400w"
            alt="Lazy hero"
          />
        </main>
        """,
        "html.parser",
    )

    references = extract_asset_references(
        soup,
        "https://example.com/media",
        "/media",
    )

    by_url_and_attribute = {
        (reference.source_url, reference.attribute): reference
        for reference in references
    }

    lazy_src_reference = by_url_and_attribute[
        (
            "https://images.squarespace-cdn.com/content/lazy-hero.jpg",
            "data-src",
        )
    ]
    lazy_small_reference = by_url_and_attribute[
        (
            "https://images.squarespace-cdn.com/content/lazy-hero.jpg?w=400",
            "data-srcset",
        )
    ]
    lazy_large_reference = by_url_and_attribute[
        (
            "https://images.squarespace-cdn.com/content/lazy-hero.jpg?w=1400",
            "data-srcset",
        )
    ]

    assert lazy_src_reference.alt_text == "Lazy hero"
    assert lazy_small_reference.variant_hint == "small"
    assert lazy_large_reference.variant_hint == "large"


def test_download_snapshot_assets_downloads_squarespace_assets_with_friendly_names(
    tmp_path: Path,
) -> None:
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=SiteProbe(
            target_url="https://example.com/",
            final_home_url="https://example.com/",
            site_origin="https://example.com",
            homepage_status_code=200,
            homepage_title="Example Site",
            probably_squarespace=True,
        ),
        pages=[
            PageSnapshot(
                requested_url="https://example.com/media",
                final_url="https://example.com/media",
                status_code=200,
                content_type="text/html",
                title="Media",
                meta_description=None,
                canonical_url="https://example.com/media",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/hero.jpg?w=300",
                        asset_type="image",
                        attribute="src",
                        owner_route="/media",
                        group_key="img-1",
                        alt_text="Hero image",
                        variant_hint="small",
                    ),
                    AssetReference(
                        source_url="https://static1.squarespace.com/files/pricing-guide.pdf",
                        asset_type="file",
                        attribute="href",
                        owner_route="/media",
                        group_key="a-2",
                        link_text="Pricing Guide",
                        variant_hint="file",
                    ),
                    AssetReference(
                        source_url="https://www.youtube.com/watch?v=abc123",
                        asset_type="video",
                        attribute="src",
                        owner_route="/media",
                        group_key="video-3",
                        variant_hint="original",
                    ),
                ],
            )
        ],
    )

    responses = {
        "https://images.squarespace-cdn.com/content/hero.jpg?w=300": httpx.Response(
            200,
            content=b"image-bytes",
            headers={"content-type": "image/jpeg"},
        ),
        "https://static1.squarespace.com/files/pricing-guide.pdf": httpx.Response(
            200,
            content=b"%PDF-1.7",
            headers={"content-type": "application/pdf"},
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            raise AssertionError(f"Unexpected request for {request.url}")
        return response

    progress_updates: list[tuple[int, int, str | None]] = []

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        manifest = download_snapshot_assets(
            client,
            snapshot,
            tmp_path,
            progress_callback=lambda completed, total, detail: progress_updates.append(
                (completed, total, detail)
            ),
        )

    assert [item.public_path for item in manifest.items] == [
        "/assets/files/pricing-guide.pdf",
        "/assets/images/media-1-small.jpg",
    ]
    assert manifest.warnings == []
    assert manifest.source_asset_count == 2
    assert manifest.deduplicated_asset_count == 0
    assert progress_updates == [(0, 2, None), (1, 2, None), (2, 2, None)]
    assert (
        tmp_path / "downloaded-assets/images/media-1-small.jpg"
    ).read_bytes() == b"image-bytes"
    assert (
        tmp_path / "downloaded-assets/files/pricing-guide.pdf"
    ).read_bytes() == b"%PDF-1.7"


def test_download_snapshot_assets_merges_same_content_from_different_urls(
    tmp_path: Path,
) -> None:
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=SiteProbe(
            target_url="https://example.com/",
            final_home_url="https://example.com/",
            site_origin="https://example.com",
            homepage_status_code=200,
            homepage_title="Example Site",
            probably_squarespace=True,
        ),
        pages=[
            PageSnapshot(
                requested_url="https://example.com/media",
                final_url="https://example.com/media",
                status_code=200,
                content_type="text/html",
                title="Media",
                meta_description=None,
                canonical_url="https://example.com/media",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/hero-a.jpg",
                        asset_type="image",
                        attribute="src",
                        owner_route="/media",
                        group_key="img-1",
                    )
                ],
            ),
            PageSnapshot(
                requested_url="https://example.com/gallery",
                final_url="https://example.com/gallery",
                status_code=200,
                content_type="text/html",
                title="Gallery",
                meta_description=None,
                canonical_url="https://example.com/gallery",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/hero-b.jpg",
                        asset_type="image",
                        attribute="src",
                        owner_route="/gallery",
                        group_key="img-2",
                    )
                ],
            ),
        ],
    )

    shared_bytes = b"same-image-bytes"
    responses = {
        "https://images.squarespace-cdn.com/content/hero-a.jpg": httpx.Response(
            200,
            content=shared_bytes,
            headers={"content-type": "image/jpeg"},
        ),
        "https://images.squarespace-cdn.com/content/hero-b.jpg": httpx.Response(
            200,
            content=shared_bytes,
            headers={"content-type": "image/jpeg"},
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            raise AssertionError(f"Unexpected request for {request.url}")
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        manifest = download_snapshot_assets(client, snapshot, tmp_path)

    assert len(manifest.items) == 1
    assert manifest.source_asset_count == 2
    assert manifest.deduplicated_asset_count == 1
    assert manifest.items[0].public_path == "/assets/images/media-1.jpg"
    assert manifest.items[0].alias_source_urls == [
        "https://images.squarespace-cdn.com/content/hero-b.jpg"
    ]
    assert manifest.items[0].deduplicated_from_count == 2
    assert (
        tmp_path / "downloaded-assets/images/media-1.jpg"
    ).read_bytes() == shared_bytes


def test_download_snapshot_assets_uses_route_labels_for_generic_cdn_image_names(
    tmp_path: Path,
) -> None:
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=SiteProbe(
            target_url="https://example.com/",
            final_home_url="https://example.com/",
            site_origin="https://example.com",
            homepage_status_code=200,
            homepage_title="Example Site",
            probably_squarespace=True,
        ),
        pages=[
            PageSnapshot(
                requested_url="https://example.com/projects/barcelona",
                final_url="https://example.com/projects/barcelona",
                status_code=200,
                content_type="text/html",
                title="Barcelona",
                meta_description=None,
                canonical_url="https://example.com/projects/barcelona",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/image-asset.png",
                        asset_type="image",
                        attribute="src",
                        owner_route="/projects/barcelona",
                        group_key="img-1",
                    ),
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/image-asset-2.png",
                        asset_type="image",
                        attribute="src",
                        owner_route="/projects/barcelona",
                        group_key="img-2",
                    ),
                ],
            )
        ],
    )

    responses = {
        "https://images.squarespace-cdn.com/content/image-asset.png": httpx.Response(
            200,
            content=b"barcelona-image-1",
            headers={"content-type": "image/webp"},
        ),
        "https://images.squarespace-cdn.com/content/image-asset-2.png": httpx.Response(
            200,
            content=b"barcelona-image-2",
            headers={"content-type": "image/webp"},
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            raise AssertionError(f"Unexpected request for {request.url}")
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        manifest = download_snapshot_assets(client, snapshot, tmp_path)

    assert [item.public_path for item in manifest.items] == [
        "/assets/images/barcelona-1.webp",
        "/assets/images/barcelona-2.webp",
    ]


def test_download_snapshot_assets_uses_width_tokens_before_numeric_collision_suffixes(
    tmp_path: Path,
) -> None:
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=SiteProbe(
            target_url="https://example.com/",
            final_home_url="https://example.com/",
            site_origin="https://example.com",
            homepage_status_code=200,
            homepage_title="Example Site",
            probably_squarespace=True,
        ),
        pages=[
            PageSnapshot(
                requested_url="https://example.com/projects/barcelona",
                final_url="https://example.com/projects/barcelona",
                status_code=200,
                content_type="text/html",
                title="Barcelona",
                meta_description=None,
                canonical_url="https://example.com/projects/barcelona",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/image-asset.png?format=1000w",
                        asset_type="image",
                        attribute="srcset",
                        owner_route="/projects/barcelona",
                        group_key="img-213",
                        variant_hint="large",
                    ),
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/image-asset.png?format=1500w",
                        asset_type="image",
                        attribute="srcset",
                        owner_route="/projects/barcelona",
                        group_key="img-213",
                        variant_hint="large",
                    ),
                ],
            )
        ],
    )

    responses = {
        "https://images.squarespace-cdn.com/content/image-asset.png?format=1000w": httpx.Response(
            200,
            content=b"barcelona-image-1000",
            headers={"content-type": "image/webp"},
        ),
        "https://images.squarespace-cdn.com/content/image-asset.png?format=1500w": httpx.Response(
            200,
            content=b"barcelona-image-1500",
            headers={"content-type": "image/webp"},
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            raise AssertionError(f"Unexpected request for {request.url}")
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        manifest = download_snapshot_assets(client, snapshot, tmp_path)

    assert sorted(item.public_path for item in manifest.items) == [
        "/assets/images/barcelona-1-large-1500w.webp",
        "/assets/images/barcelona-1-large.webp",
    ]


def test_download_snapshot_assets_expands_route_labels_when_page_suffixes_collide(
    tmp_path: Path,
) -> None:
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=SiteProbe(
            target_url="https://example.com/",
            final_home_url="https://example.com/",
            site_origin="https://example.com",
            homepage_status_code=200,
            homepage_title="Example Site",
            probably_squarespace=True,
        ),
        pages=[
            PageSnapshot(
                requested_url="https://example.com/projects/barcelona",
                final_url="https://example.com/projects/barcelona",
                status_code=200,
                content_type="text/html",
                title="Barcelona Project",
                meta_description=None,
                canonical_url="https://example.com/projects/barcelona",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/project-image-asset.png",
                        asset_type="image",
                        attribute="src",
                        owner_route="/projects/barcelona",
                        group_key="img-1",
                    ),
                ],
            ),
            PageSnapshot(
                requested_url="https://example.com/exhibitions/barcelona",
                final_url="https://example.com/exhibitions/barcelona",
                status_code=200,
                content_type="text/html",
                title="Barcelona Exhibition",
                meta_description=None,
                canonical_url="https://example.com/exhibitions/barcelona",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/exhibition-image-asset.png",
                        asset_type="image",
                        attribute="src",
                        owner_route="/exhibitions/barcelona",
                        group_key="img-1",
                    ),
                ],
            ),
        ],
    )

    responses = {
        "https://images.squarespace-cdn.com/content/project-image-asset.png": httpx.Response(
            200,
            content=b"project-image",
            headers={"content-type": "image/png"},
        ),
        "https://images.squarespace-cdn.com/content/exhibition-image-asset.png": httpx.Response(
            200,
            content=b"exhibition-image",
            headers={"content-type": "image/png"},
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            raise AssertionError(f"Unexpected request for {request.url}")
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        manifest = download_snapshot_assets(client, snapshot, tmp_path)

    assert [item.public_path for item in manifest.items] == [
        "/assets/images/exhibitions-barcelona-1.png",
        "/assets/images/projects-barcelona-1.png",
    ]


def test_upgrade_legacy_asset_manifest_renames_hashed_assets_and_merges_duplicates(
    tmp_path: Path,
) -> None:
    first_relative_path = (
        "downloaded-assets/images/still-tom-cc-large-db0f0226d1de.webp"
    )
    duplicate_relative_path = (
        "downloaded-assets/images/be-water-large-db0f0226d1de.webp"
    )
    first_file = tmp_path / first_relative_path
    duplicate_file = tmp_path / duplicate_relative_path
    first_file.parent.mkdir(parents=True, exist_ok=True)
    first_file.write_bytes(b"shared-image")
    duplicate_file.write_bytes(b"shared-image")

    legacy_manifest = AssetManifest(
        generated_at="2026-04-05T00:00:00+00:00",
        items=[
            DownloadedAsset(
                source_url="https://images.squarespace-cdn.com/content/still-tom-cc.png?format=1000w",
                final_url="https://images.squarespace-cdn.com/content/still-tom-cc.png?format=1000w",
                asset_type="image",
                owner_route="/projects/be-water",
                group_key="img-7",
                filename="still-tom-cc-large-db0f0226d1de.webp",
                local_path=first_relative_path,
                public_path="/assets/images/still-tom-cc-large-db0f0226d1de.webp",
                canonical_id="db0f0226d1de1111111111111111111111111111111111111111111111111111",
                sha256="db0f0226d1de1111111111111111111111111111111111111111111111111111",
                variant_hint="large",
                deduplicated_from_count=1,
            ),
            DownloadedAsset(
                source_url="https://images.squarespace-cdn.com/content/be-water-duplicate.png?format=1000w",
                final_url="https://images.squarespace-cdn.com/content/be-water-duplicate.png?format=1000w",
                asset_type="image",
                owner_route="/projects/be-water",
                group_key="img-8",
                filename="be-water-large-db0f0226d1de.webp",
                local_path=duplicate_relative_path,
                public_path="/assets/images/be-water-large-db0f0226d1de.webp",
                canonical_id="db0f0226d1de1111111111111111111111111111111111111111111111111111",
                sha256="db0f0226d1de1111111111111111111111111111111111111111111111111111",
                variant_hint="large",
                deduplicated_from_count=1,
            ),
        ],
    )
    write_json(tmp_path / "asset_manifest.json", legacy_manifest)

    upgraded_manifest, warnings, upgraded = upgrade_legacy_asset_manifest(
        tmp_path,
        read_json(tmp_path / "asset_manifest.json"),
    )

    assert upgraded is True
    assert warnings == [
        "Upgraded legacy asset_manifest.json filenames from hash-suffixed paths to the current route-based naming scheme."
    ]
    assert upgraded_manifest["warnings"] == []
    assert [item["public_path"] for item in upgraded_manifest["items"]] == [
        "/assets/images/be-water-1-large.webp",
    ]
    assert upgraded_manifest["items"][0]["deduplicated_from_count"] == 2
    assert {
        upgraded_manifest["items"][0]["source_url"],
        *upgraded_manifest["items"][0]["alias_source_urls"],
    } == {
        "https://images.squarespace-cdn.com/content/still-tom-cc.png?format=1000w",
        "https://images.squarespace-cdn.com/content/be-water-duplicate.png?format=1000w",
    }
    assert (
        tmp_path / "downloaded-assets/images/be-water-1-large.webp"
    ).read_bytes() == b"shared-image"
    assert not first_file.exists()
    assert not duplicate_file.exists()


def test_estimate_snapshot_asset_download_uses_unique_squarespace_assets_and_tracks_unknown_sizes() -> (
    None
):
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=SiteProbe(
            target_url="https://example.com/",
            final_home_url="https://example.com/",
            site_origin="https://example.com",
            homepage_status_code=200,
            homepage_title="Example Site",
            probably_squarespace=True,
        ),
        pages=[
            PageSnapshot(
                requested_url="https://example.com/media",
                final_url="https://example.com/media",
                status_code=200,
                content_type="text/html",
                title="Media",
                meta_description=None,
                canonical_url="https://example.com/media",
                assets=[
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/hero.jpg?w=300",
                        asset_type="image",
                        attribute="src",
                        owner_route="/media",
                        group_key="img-1",
                        variant_hint="small",
                    ),
                    AssetReference(
                        source_url="https://images.squarespace-cdn.com/content/hero.jpg?w=300",
                        asset_type="image",
                        attribute="srcset",
                        owner_route="/media",
                        group_key="img-1",
                        variant_hint="large",
                    ),
                    AssetReference(
                        source_url="https://static1.squarespace.com/files/pricing-guide.pdf",
                        asset_type="file",
                        attribute="href",
                        owner_route="/media",
                        group_key="a-2",
                        link_text="Pricing Guide",
                        variant_hint="file",
                    ),
                ],
            )
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method == "HEAD"
            and str(request.url)
            == "https://images.squarespace-cdn.com/content/hero.jpg?w=300"
        ):
            return httpx.Response(200, headers={"content-length": str(3 * 1024 * 1024)})
        if (
            request.method == "HEAD"
            and str(request.url)
            == "https://static1.squarespace.com/files/pricing-guide.pdf"
        ):
            return httpx.Response(200, headers={})
        if (
            request.method == "GET"
            and str(request.url)
            == "https://static1.squarespace.com/files/pricing-guide.pdf"
        ):
            return httpx.Response(200, headers={})
        raise AssertionError(f"Unexpected {request.method} request for {request.url}")

    progress_updates: list[tuple[int, int, str | None]] = []

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        estimate = estimate_snapshot_asset_download(
            client,
            snapshot,
            progress_callback=lambda completed, total, detail: progress_updates.append(
                (completed, total, detail)
            ),
        )

    assert estimate.asset_count == 2
    assert estimate.estimated_size_bytes == 3 * 1024 * 1024
    assert estimate.unknown_size_count == 1
    assert progress_updates == [(0, 2, None), (1, 2, None), (2, 2, None)]
