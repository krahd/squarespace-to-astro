from pathlib import Path

from s2a.files import read_json, write_json, write_text
from s2a.generate.astro import extract_main_html, generate_astro_project
from s2a.normalize.models import CrawlSnapshot, JsonDataProbe, PageSnapshot, SiteProbe


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
