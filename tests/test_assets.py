import hashlib
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from s2a.extract.assets import download_snapshot_assets, estimate_snapshot_asset_download, extract_asset_references
from s2a.normalize.models import AssetReference, CrawlSnapshot, PageSnapshot, SiteProbe


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
        (reference.source_url, reference.attribute): reference for reference in references
    }

    hero_reference = by_url_and_attribute[("https://example.com/images/hero.jpg?w=300", "src")]
    hero_small_reference = by_url_and_attribute[(
        "https://example.com/images/hero.jpg?w=300", "srcset")]
    hero_large_reference = by_url_and_attribute[(
        "https://example.com/images/hero.jpg?w=1200", "srcset")]
    poster_reference = by_url_and_attribute[(
        "https://images.squarespace-cdn.com/content/poster.jpg", "poster")]
    video_reference = by_url_and_attribute[(
        "https://static1.squarespace.com/media/clip.mp4", "src")]
    file_reference = by_url_and_attribute[("https://example.com/s/guide.pdf", "href")]
    background_reference = by_url_and_attribute[(
        "https://example.com/images/background.jpg?width=1200", "style")]

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
        (reference.source_url, reference.attribute): reference for reference in references
    }

    lazy_src_reference = by_url_and_attribute[(
        "https://images.squarespace-cdn.com/content/lazy-hero.jpg",
        "data-src",
    )]
    lazy_small_reference = by_url_and_attribute[(
        "https://images.squarespace-cdn.com/content/lazy-hero.jpg?w=400",
        "data-srcset",
    )]
    lazy_large_reference = by_url_and_attribute[(
        "https://images.squarespace-cdn.com/content/lazy-hero.jpg?w=1400",
        "data-srcset",
    )]

    assert lazy_src_reference.alt_text == "Lazy hero"
    assert lazy_small_reference.variant_hint == "small"
    assert lazy_large_reference.variant_hint == "large"


def test_download_snapshot_assets_downloads_squarespace_assets_with_friendly_names(tmp_path: Path) -> None:
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
                (completed, total, detail)),
        )

    hero_suffix = hashlib.sha256(b"image-bytes").hexdigest()[:12]
    guide_suffix = hashlib.sha256(b"%PDF-1.7").hexdigest()[:12]
    assert [item.public_path for item in manifest.items] == [
        f"/assets/files/pricing-guide-{guide_suffix}.pdf",
        f"/assets/images/hero-small-{hero_suffix}.jpg",
    ]
    assert manifest.warnings == []
    assert manifest.source_asset_count == 2
    assert manifest.deduplicated_asset_count == 0
    assert progress_updates == [(0, 2, None), (1, 2, None), (2, 2, None)]
    assert (
        tmp_path / f"downloaded-assets/images/hero-small-{hero_suffix}.jpg").read_bytes() == b"image-bytes"
    assert (
        tmp_path / f"downloaded-assets/files/pricing-guide-{guide_suffix}.pdf").read_bytes() == b"%PDF-1.7"


def test_download_snapshot_assets_merges_same_content_from_different_urls(tmp_path: Path) -> None:
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

    suffix = hashlib.sha256(shared_bytes).hexdigest()[:12]

    assert len(manifest.items) == 1
    assert manifest.source_asset_count == 2
    assert manifest.deduplicated_asset_count == 1
    assert manifest.items[0].public_path == f"/assets/images/hero-a-{suffix}.jpg"
    assert manifest.items[0].alias_source_urls == [
        "https://images.squarespace-cdn.com/content/hero-b.jpg"
    ]
    assert manifest.items[0].deduplicated_from_count == 2
    assert (tmp_path / f"downloaded-assets/images/hero-a-{suffix}.jpg").read_bytes() == shared_bytes


def test_estimate_snapshot_asset_download_uses_unique_squarespace_assets_and_tracks_unknown_sizes() -> None:
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
        if request.method == "HEAD" and str(request.url) == "https://images.squarespace-cdn.com/content/hero.jpg?w=300":
            return httpx.Response(200, headers={"content-length": str(3 * 1024 * 1024)})
        if request.method == "HEAD" and str(request.url) == "https://static1.squarespace.com/files/pricing-guide.pdf":
            return httpx.Response(200, headers={})
        if request.method == "GET" and str(request.url) == "https://static1.squarespace.com/files/pricing-guide.pdf":
            return httpx.Response(200, headers={})
        raise AssertionError(f"Unexpected {request.method} request for {request.url}")

    progress_updates: list[tuple[int, int, str | None]] = []

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        estimate = estimate_snapshot_asset_download(
            client,
            snapshot,
            progress_callback=lambda completed, total, detail: progress_updates.append(
                (completed, total, detail)),
        )

    assert estimate.asset_count == 2
    assert estimate.estimated_size_bytes == 3 * 1024 * 1024
    assert estimate.unknown_size_count == 1
    assert progress_updates == [(0, 2, None), (1, 2, None), (2, 2, None)]
