from pathlib import Path

from s2a.files import read_json, write_json, write_text
from s2a.generate.astro import extract_main_html, generate_astro_project
from s2a.normalize.models import (
    AssetManifest,
    CrawlSnapshot,
    DownloadedAsset,
    JsonDataProbe,
    PageSnapshot,
    SiteProbe,
)


def test_generate_astro_project_creates_pages_posts_and_manifest(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        "<html><body><main><h1>Home Title</h1><p>Welcome to the site.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "about.html",
        "<html><body><main><h1>About</h1><p>About page content.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "blog__first-post.html",
        "<html><body><article><h1>First Post</h1><p>Post body content.</p></article></body></html>",
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Site",
        probably_squarespace=True,
        homepage_links=[
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/blog",
        ],
        json_probe=JsonDataProbe(
            source_url="https://example.com/",
            json_url="https://example.com/?format=json-pretty",
            attempted=True,
            available=True,
            status_code=200,
        ),
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
                title="Home Title — Example Site",
                meta_description="Home description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/about",
                final_url="https://example.com/about",
                status_code=200,
                content_type="text/html",
                title="About — Example Site",
                meta_description="About description",
                canonical_url="https://example.com/about",
                raw_html_path="raw-html/about.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/blog/first-post",
                final_url="https://example.com/blog/first-post",
                status_code=200,
                content_type="text/html",
                title="First Post — Example Site",
                meta_description="Post description",
                canonical_url="https://example.com/blog/first-post",
                raw_html_path="raw-html/blog__first-post.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    result = generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")

    assert result.pages_written == 2
    assert result.posts_written == 1
    assert (output_dir / "package.json").exists()
    assert (output_dir / "src/content/pages/home.md").exists()
    assert (output_dir / "src/content/posts/blog--first-post.md").exists()
    assert (output_dir / "migration-manifest.json").exists()


def test_generate_astro_project_keeps_portfolio_routes_as_pages(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_json_dir = snapshot_dir / "raw-json"
    raw_html_dir.mkdir(parents=True)
    raw_json_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        "<html><body><main><h1>Projects</h1><p>Portfolio landing page.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "projects__alpha.html",
        "<html><body><article><h1>Alpha</h1><p>Project alpha body.</p></article></body></html>",
    )
    write_text(
        raw_html_dir / "projects__beta.html",
        "<html><body><article><h1>Beta</h1><p>Project beta body.</p></article></body></html>",
    )
    write_json(
        raw_json_dir / "index.json",
        {
            "collection": {
                "title": "Projects",
                "typeLabel": "portfolio",
                "typeName": "portfolio-grid-basic",
                "fullUrl": "/",
            },
            "items": [
                {"fullUrl": "/projects/alpha", "recordTypeLabel": "portfolio-item"},
                {"fullUrl": "/projects/beta", "recordTypeLabel": "portfolio-item"},
            ],
        },
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Portfolio",
        probably_squarespace=True,
        homepage_links=[
            "https://example.com/",
            "https://example.com/projects/alpha",
            "https://example.com/projects/beta",
        ],
        json_probe=JsonDataProbe(
            source_url="https://example.com/",
            json_url="https://example.com/?format=json-pretty",
            attempted=True,
            available=True,
            status_code=200,
        ),
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
                title="Projects — Example Portfolio",
                meta_description="Portfolio description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
                raw_json_path="raw-json/index.json",
            ),
            PageSnapshot(
                requested_url="https://example.com/projects/alpha",
                final_url="https://example.com/projects/alpha",
                status_code=200,
                content_type="text/html",
                title="Alpha — Example Portfolio",
                meta_description="Alpha description",
                canonical_url="https://example.com/projects/alpha",
                raw_html_path="raw-html/projects__alpha.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/projects/beta",
                final_url="https://example.com/projects/beta",
                status_code=200,
                content_type="text/html",
                title="Beta — Example Portfolio",
                meta_description="Beta description",
                canonical_url="https://example.com/projects/beta",
                raw_html_path="raw-html/projects__beta.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    result = generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    manifest = read_json(output_dir / "migration-manifest.json")

    assert result.pages_written == 3
    assert result.posts_written == 0
    assert manifest["blog_base_path"] == "/blog"
    assert len(manifest["posts"]) == 0
    assert (output_dir / "src/content/pages/projects--alpha.md").exists()
    assert (output_dir / "src/content/pages/projects--beta.md").exists()


def test_extract_main_html_handles_nested_noise_elements() -> None:
    html = """
        <html>
            <body>
                <main>
                    <div class="sidebar">
                        <nav><a href="/">Home</a></nav>
                    </div>
                    <section>
                        <h1>Article Title</h1>
                        <p>This body is intentionally long enough to survive the extractor threshold after noisy elements are removed.</p>
                    </section>
                </main>
            </body>
        </html>
        """

    fragment = extract_main_html(html)

    assert "Article Title" in fragment
    assert "sidebar" not in fragment


def test_generate_astro_project_skips_utility_routes(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        "<html><body><main><h1>Home Title</h1><p>Welcome to the site.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "cart.html",
        "<html><body><main><h1>Your Cart</h1><p>Cart contents.</p></main></body></html>",
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Site",
        probably_squarespace=True,
        homepage_links=[
            "https://example.com/",
            "https://example.com/cart",
        ],
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
                title="Home Title — Example Site",
                meta_description="Home description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/cart",
                final_url="https://example.com/cart",
                status_code=200,
                content_type="text/html",
                title="Cart — Example Site",
                meta_description="Cart description",
                canonical_url="https://example.com/cart",
                raw_html_path="raw-html/cart.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    result = generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    manifest = read_json(output_dir / "migration-manifest.json")

    assert result.pages_written == 1
    assert all(page["route_path"] != "/cart" for page in manifest["pages"])
    assert all(item["url"] != "/cart" for item in manifest["navigation"])
    assert not (output_dir / "src/content/pages/cart.md").exists()
    assert any("/cart" in warning for warning in result.warnings)


def test_generate_astro_project_localizes_asset_urls_and_copies_downloads(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "media.html",
        """
        <html>
          <body>
            <main>
              <h1>Media</h1>
                            <p>
                                <img
                                    src="data:image/gif;base64,abc123"
                                    data-src="https://images.squarespace-cdn.com/content/hero.jpg"
                                    alt="Hero image"
                                />
                            </p>
              <p><a href="https://static1.squarespace.com/files/brochure.pdf">Brochure</a></p>
              <video poster="https://images.squarespace-cdn.com/content/poster.jpg">
                <source src="https://static1.squarespace.com/media/clip.mp4" />
              </video>
            </main>
          </body>
        </html>
        """,
    )

    downloaded_files = {
        "downloaded-assets/images/media-1-original.jpg": b"hero-bytes",
        "downloaded-assets/files/media-file-2-brochure.pdf": b"brochure-bytes",
        "downloaded-assets/images/media-3-poster.jpg": b"poster-bytes",
        "downloaded-assets/videos/media-4-original.mp4": b"video-bytes",
    }
    for relative_path, content in downloaded_files.items():
        file_path = snapshot_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

    write_json(
        snapshot_dir / "asset_manifest.json",
        AssetManifest(
            generated_at="2026-04-05T00:00:00+00:00",
            items=[
                DownloadedAsset(
                    source_url="https://images.squarespace-cdn.com/content/hero.jpg",
                    final_url="https://images.squarespace-cdn.com/content/hero.jpg",
                    asset_type="image",
                    owner_route="/media",
                    group_key="img-1",
                    filename="media-1-original.jpg",
                    local_path="downloaded-assets/images/media-1-original.jpg",
                    public_path="/assets/images/media-1-original.jpg",
                ),
                DownloadedAsset(
                    source_url="https://static1.squarespace.com/files/brochure.pdf",
                    final_url="https://static1.squarespace.com/files/brochure.pdf",
                    asset_type="file",
                    owner_route="/media",
                    group_key="a-2",
                    filename="media-file-2-brochure.pdf",
                    local_path="downloaded-assets/files/media-file-2-brochure.pdf",
                    public_path="/assets/files/media-file-2-brochure.pdf",
                ),
                DownloadedAsset(
                    source_url="https://images.squarespace-cdn.com/content/poster.jpg",
                    final_url="https://images.squarespace-cdn.com/content/poster.jpg",
                    asset_type="image",
                    owner_route="/media",
                    group_key="video-3",
                    filename="media-3-poster.jpg",
                    local_path="downloaded-assets/images/media-3-poster.jpg",
                    public_path="/assets/images/media-3-poster.jpg",
                ),
                DownloadedAsset(
                    source_url="https://static1.squarespace.com/media/clip.mp4",
                    final_url="https://static1.squarespace.com/media/clip.mp4",
                    asset_type="video",
                    owner_route="/media",
                    group_key="video-3",
                    filename="media-4-original.mp4",
                    local_path="downloaded-assets/videos/media-4-original.mp4",
                    public_path="/assets/videos/media-4-original.mp4",
                ),
            ],
        ),
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Site",
        probably_squarespace=True,
        homepage_links=[
            "https://example.com/",
            "https://example.com/media",
        ],
    )
    snapshot = CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com/",
        base_url="https://example.com/",
        probe=probe,
        pages=[
            PageSnapshot(
                requested_url="https://example.com/media",
                final_url="https://example.com/media",
                status_code=200,
                content_type="text/html",
                title="Media — Example Site",
                meta_description="Media description",
                canonical_url="https://example.com/media",
                raw_html_path="raw-html/media.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    result = generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    content = (output_dir / "src/content/pages/media.md").read_text(encoding="utf-8")

    assert result.pages_written == 2
    assert "/assets/images/media-1-original.jpg" in content
    assert "/assets/files/media-file-2-brochure.pdf" in content
    assert "/assets/images/media-3-poster.jpg" in content
    assert "/assets/videos/media-4-original.mp4" in content
    assert "data:image/gif" not in content
    assert "images.squarespace-cdn.com" not in content
    assert "static1.squarespace.com" not in content
    assert (output_dir / "public/assets/images/media-1-original.jpg").read_bytes() == b"hero-bytes"
    assert (output_dir / "public/assets/files/media-file-2-brochure.pdf").read_bytes() == b"brochure-bytes"
    assert (output_dir / "public/assets/images/media-3-poster.jpg").read_bytes() == b"poster-bytes"
    assert (output_dir / "public/assets/videos/media-4-original.mp4").read_bytes() == b"video-bytes"
