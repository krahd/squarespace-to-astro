import hashlib
from pathlib import Path

from s2a.files import read_json, write_json, write_text
from s2a.generate.astro import body_from_html, extract_main_html, generate_astro_project
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


def test_generate_astro_project_uses_homepage_navigation_and_high_fidelity_chrome(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        """
        <html>
                    <body class="tweak-transparent-header header-width-full header-overlay-alignment-center">
                        <header data-current-styles='{"layout": "navRight"}'>
              <div class="header-title-nav-wrapper">
                <div class="header-title-text"><a id="site-title" href="/">Tomas Laurenzo</a></div>
                <div class="header-nav">
                  <div class="header-nav-wrapper">
                    <nav class="header-nav-list">
                      <div class="header-nav-item"><a href="/">Projects</a></div>
                      <div class="header-nav-item"><a href="/texts">Texts</a></div>
                      <div class="header-nav-item"><a href="/about">About</a></div>
                      <div class="header-nav-item"><a href="/contact">Contact</a></div>
                    </nav>
                  </div>
                </div>
              </div>
            </header>
                        <script>
                            window.__tweaks = {"maxPageWidth":"1920px","pagePadding":"4vw","header-vert-padding":"3vw","header-width":"Full"};
                        </script>
            <main><article class="sections"><section class="page-section full-bleed-section"><p>Landing page</p></section></article></main>
          </body>
        </html>
        """,
    )
    write_text(
        raw_html_dir / "texts.html",
        "<html><body><main><h1>Texts</h1><p>Essays and notes.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "about.html",
        "<html><body><main><h1>About</h1><p>Artist bio.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "contact.html",
        "<html><body><main><h1>Contact</h1><p>Reach out.</p></main></body></html>",
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Tomas Laurenzo",
        probably_squarespace=True,
        homepage_links=["https://example.com/"],
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
                title="Projects — Tomas Laurenzo",
                meta_description="Projects",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/texts",
                final_url="https://example.com/texts",
                status_code=200,
                content_type="text/html",
                title="Texts — Tomas Laurenzo",
                meta_description="Texts",
                canonical_url="https://example.com/texts",
                raw_html_path="raw-html/texts.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/about",
                final_url="https://example.com/about",
                status_code=200,
                content_type="text/html",
                title="About — Tomas Laurenzo",
                meta_description="About",
                canonical_url="https://example.com/about",
                raw_html_path="raw-html/about.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/contact",
                final_url="https://example.com/contact",
                status_code=200,
                content_type="text/html",
                title="Contact — Tomas Laurenzo",
                meta_description="Contact",
                canonical_url="https://example.com/contact",
                raw_html_path="raw-html/contact.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    site_data = read_json(output_dir / "src/data/site.json")

    assert site_data["navigationSource"] == "homepage-html"
    assert [item["title"] for item in site_data["navigation"][:4]] == [
        "Projects",
        "Texts",
        "About",
        "Contact",
    ]
    assert site_data["headerStyle"] == "transparent"
    assert site_data["backgroundStyle"] == "plain"
    assert site_data["headerWidth"] == "full"
    assert site_data["headerLayout"] == "nav-right"
    assert site_data["headerAlignment"] == "center"
    assert site_data["pageWidth"] == "1920px"
    assert site_data["pagePadding"] == "4vw"
    assert site_data["headerPadding"] == "3vw"
    assert site_data["fidelityMode"] == "high"
    assert site_data["layoutStrategy"] == "hybrid"


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
    assert (output_dir / "src/content/posts").exists()
    content_config = (output_dir / "src/content.config.ts").read_text(encoding="utf-8")
    assert "export const collections = { pages };" in content_config
    assert "const posts = defineCollection" not in content_config


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


def test_body_from_html_prefers_html_for_portfolio_grid_markup() -> None:
    html = """
                <article class="sections">
                    <section class="page-section collection-type-portfolio-grid-basic">
                        <div class="portfolio-grid-basic grid-wrapper">
                            <a class="grid-item" href="/projects/a"><img src="/assets/images/a.jpg" alt="" /><div class="portfolio-text"><h3 class="portfolio-title">A</h3></div></a>
                            <a class="grid-item" href="/projects/b"><img src="/assets/images/b.jpg" alt="" /><div class="portfolio-text"><h3 class="portfolio-title">B</h3></div></a>
                            <a class="grid-item" href="/projects/c"><img src="/assets/images/c.jpg" alt="" /><div class="portfolio-text"><h3 class="portfolio-title">C</h3></div></a>
                            <a class="grid-item" href="/projects/d"><img src="/assets/images/d.jpg" alt="" /><div class="portfolio-text"><h3 class="portfolio-title">D</h3></div></a>
                            <a class="grid-item" href="/projects/e"><img src="/assets/images/e.jpg" alt="" /><div class="portfolio-text"><h3 class="portfolio-title">E</h3></div></a>
                            <a class="grid-item" href="/projects/f"><img src="/assets/images/f.jpg" alt="" /><div class="portfolio-text"><h3 class="portfolio-title">F</h3></div></a>
                        </div>
                    </section>
                </article>
        """

    body, body_format = body_from_html(html)

    assert body_format == "html"
    assert "portfolio-grid-basic" in body


def test_body_from_html_markdown_flag_keeps_simple_image_lists_as_markdown() -> None:
    html = """
        <section>
          <p>Sketchbook selections.</p>
          <a href="/works/a"><img src="/assets/images/a.jpg" alt="A" /></a>
          <a href="/works/b"><img src="/assets/images/b.jpg" alt="B" /></a>
          <a href="/works/c"><img src="/assets/images/c.jpg" alt="C" /></a>
          <a href="/works/d"><img src="/assets/images/d.jpg" alt="D" /></a>
          <a href="/works/e"><img src="/assets/images/e.jpg" alt="E" /></a>
          <a href="/works/f"><img src="/assets/images/f.jpg" alt="F" /></a>
        </section>
        """

    _default_body, default_format = body_from_html(html)
    markdown_body, markdown_format = body_from_html(html, markdown_first=True)

    assert default_format == "html"
    assert markdown_format == "markdown"
    assert "![A](/assets/images/a.jpg)" in markdown_body


def test_body_from_html_prefers_html_for_fluid_engine_markup() -> None:
    html = """
    <article class="sections">
        <section class="page-section" data-fluid-engine-section>
            <div data-fluid-engine="true">
                <style>
                    .fe-block-sample {
                        grid-area: 1/1/2/7;
                        z-index: 2;
                    }
                </style>
                <div class="fluid-engine">
                    <div class="fe-block fe-block-sample"><div class="embed-block-wrapper"><iframe src="https://player.vimeo.com/video/123"></iframe></div></div>
                </div>
            </div>
        </section>
    </article>
    """

    body, body_format = body_from_html(html)

    assert body_format == "html"
    assert "data-fluid-engine" in body


def test_extract_main_html_preserves_fluid_engine_styles_in_high_fidelity() -> None:
    html = """
    <html>
        <body>
            <main>
                <section class="page-section" data-fluid-engine-section>
                    <div data-fluid-engine="true">
                        <style>
                            .fe-block-sample {
                                grid-area: 2/2/7/18;
                                z-index: 4;
                            }
                        </style>
                        <div class="fluid-engine">
                            <div class="fe-block fe-block-sample">
                                <div class="sqs-block-content"><iframe src="https://player.vimeo.com/video/456"></iframe></div>
                            </div>
                        </div>
                    </div>
                </section>
            </main>
        </body>
    </html>
    """

    fragment = extract_main_html(html)

    assert "grid-area: 2/2/7/18" in fragment
    assert ".fe-block-sample" in fragment


def test_generate_astro_project_preserves_html_for_portfolio_grid_homepage(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        """
        <html><body>
          <main>
            <article class="sections">
              <section class="page-section collection-type-portfolio-grid-basic">
                <div class="portfolio-grid-basic grid-wrapper">
                  <a class="grid-item" href="/projects/a"><div class="grid-image"><img src="https://images.squarespace-cdn.com/content/a.jpg" alt="" /></div><div class="portfolio-text"><h3 class="portfolio-title">A</h3></div></a>
                  <a class="grid-item" href="/projects/b"><div class="grid-image"><img src="https://images.squarespace-cdn.com/content/b.jpg" alt="" /></div><div class="portfolio-text"><h3 class="portfolio-title">B</h3></div></a>
                  <a class="grid-item" href="/projects/c"><div class="grid-image"><img src="https://images.squarespace-cdn.com/content/c.jpg" alt="" /></div><div class="portfolio-text"><h3 class="portfolio-title">C</h3></div></a>
                  <a class="grid-item" href="/projects/d"><div class="grid-image"><img src="https://images.squarespace-cdn.com/content/d.jpg" alt="" /></div><div class="portfolio-text"><h3 class="portfolio-title">D</h3></div></a>
                  <a class="grid-item" href="/projects/e"><div class="grid-image"><img src="https://images.squarespace-cdn.com/content/e.jpg" alt="" /></div><div class="portfolio-text"><h3 class="portfolio-title">E</h3></div></a>
                  <a class="grid-item" href="/projects/f"><div class="grid-image"><img src="https://images.squarespace-cdn.com/content/f.jpg" alt="" /></div><div class="portfolio-text"><h3 class="portfolio-title">F</h3></div></a>
                </div>
              </section>
            </article>
          </main>
        </body></html>
        """,
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Portfolio",
        probably_squarespace=True,
        homepage_links=["https://example.com/"],
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
                title="Example Portfolio",
                meta_description="Portfolio description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    content = (output_dir / "src/content/pages/home.md").read_text(encoding="utf-8")

    assert "bodyFormat: html" in content
    assert "portfolio-grid-basic" in content


def test_generate_astro_project_components_strategy_rebuilds_portfolio_grid(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        """
        <html><body>
          <main>
            <article class="sections">
              <section class="page-section collection-type-portfolio-grid-basic">
                <div class="portfolio-grid-basic grid-wrapper">
                  <a class="grid-item" href="/projects/a"><div class="grid-image"><img src="/assets/images/a.jpg" alt="A" /></div><div class="portfolio-text"><h3 class="portfolio-title">A</h3></div></a>
                  <a class="grid-item" href="/projects/b"><div class="grid-image"><img src="/assets/images/b.jpg" alt="B" /></div><div class="portfolio-text"><h3 class="portfolio-title">B</h3></div></a>
                  <a class="grid-item" href="/projects/c"><div class="grid-image"><img src="/assets/images/c.jpg" alt="C" /></div><div class="portfolio-text"><h3 class="portfolio-title">C</h3></div></a>
                </div>
              </section>
            </article>
          </main>
        </body></html>
        """,
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Portfolio",
        probably_squarespace=True,
        homepage_links=["https://example.com/"],
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
                title="Example Portfolio",
                meta_description="Portfolio description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    generate_astro_project(
        snapshot_path,
        output_dir,
        site_url="https://example.com",
        layout_strategy="components",
    )
    content = (output_dir / "src/content/pages/home.md").read_text(encoding="utf-8")

    assert "bodyFormat: html" in content
    assert "presentation: immersive" in content
    assert "s2a-gallery-grid" in content
    assert "portfolio-grid-basic" not in content


def test_generate_astro_project_high_hybrid_preserves_fluid_engine_layout_styles(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        "<html><body><main><h1>Home</h1><p>Welcome.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "montevideo.html",
        """
        <html><body><main><article class="sections"><section class="page-section" data-fluid-engine-section>
            <div data-fluid-engine="true">
                <style>
                    .fe-block-title {
                        grid-area: 1/2/3/12;
                        z-index: 1;
                    }
                    @media (min-width: 768px) {
                        .fe-block-title {
                            grid-area: 2/3/5/20;
                            z-index: 3;
                        }
                    }
                    .fe-block-video {
                        grid-area: 3/1/8/13;
                        z-index: 2;
                    }
                    @media (min-width: 768px) {
                        .fe-block-video {
                            grid-area: 6/4/18/24;
                            z-index: 4;
                        }
                    }
                </style>
                <div class="fluid-engine">
                    <div class="fe-block fe-block-title"><div class="sqs-block website-component-block"><div class="sqs-block-content"><div class="sqs-html-content"><h1>Montevideo, 1983</h1></div></div></div></div>
                    <div class="fe-block fe-block-video"><div class="sqs-block embed-block" data-sqsp-block="embed"><div class="sqs-block-content"><div class="intrinsic"><div class="embed-block-wrapper"><iframe src="https://player.vimeo.com/video/1096721320"></iframe></div></div></div></div></div>
                </div>
            </div>
        </section></article></main></body></html>
        """,
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Site",
        probably_squarespace=True,
        homepage_links=["https://example.com/", "https://example.com/montevideo"],
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
                title="Home — Example Site",
                meta_description="Home description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/montevideo",
                final_url="https://example.com/montevideo",
                status_code=200,
                content_type="text/html",
                title="Montevideo — Example Site",
                meta_description="Project description",
                canonical_url="https://example.com/montevideo",
                raw_html_path="raw-html/montevideo.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    content = (output_dir / "src/content/pages/montevideo.md").read_text(encoding="utf-8")

    assert "bodyFormat: html" in content
    assert "presentation: immersive" in content
    assert "grid-area: 2/3/5/20" in content
    assert "data-fluid-engine" in content


def test_generate_astro_project_components_strategy_rebuilds_fluid_engine_page(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    write_text(
        raw_html_dir / "index.html",
        "<html><body><main><h1>Home</h1><p>Welcome.</p></main></body></html>",
    )
    write_text(
        raw_html_dir / "fluid.html",
        """
        <html><body><main><article class="sections"><section class="page-section" data-fluid-engine-section>
            <div data-fluid-engine="true">
                <style>
                    .fe-block-copy {
                        grid-area: 1/2/3/8;
                        z-index: 2;
                    }
                    @media (min-width: 768px) {
                        .fe-block-copy {
                            grid-area: 2/4/7/14;
                            z-index: 5;
                        }
                    }
                    .fe-block-embed {
                        grid-area: 3/1/7/13;
                        z-index: 4;
                    }
                    @media (min-width: 768px) {
                        .fe-block-embed {
                            grid-area: 8/2/20/22;
                            z-index: 6;
                        }
                    }
                </style>
                <div class="fluid-engine">
                    <div class="fe-block fe-block-copy"><div class="sqs-block website-component-block"><div class="sqs-block-content"><div class="sqs-html-content"><p>Fluid copy block.</p></div></div></div></div>
                    <div class="fe-block fe-block-embed"><div class="sqs-block embed-block" data-sqsp-block="embed"><div class="sqs-block-content"><div class="intrinsic"><div class="embed-block-wrapper"><iframe src="https://player.vimeo.com/video/789"></iframe></div></div></div></div></div>
                </div>
            </div>
        </section></article></main></body></html>
        """,
    )

    probe = SiteProbe(
        target_url="https://example.com/",
        final_home_url="https://example.com/",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example Site",
        probably_squarespace=True,
        homepage_links=["https://example.com/", "https://example.com/fluid"],
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
                title="Home — Example Site",
                meta_description="Home description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/fluid",
                final_url="https://example.com/fluid",
                status_code=200,
                content_type="text/html",
                title="Fluid — Example Site",
                meta_description="Fluid description",
                canonical_url="https://example.com/fluid",
                raw_html_path="raw-html/fluid.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    generate_astro_project(
        snapshot_path,
        output_dir,
        site_url="https://example.com",
        layout_strategy="components",
    )
    content = (output_dir / "src/content/pages/fluid.md").read_text(encoding="utf-8")

    assert "bodyFormat: html" in content
    assert "presentation: immersive" in content
    assert "s2a-fluid--components" in content
    assert "s2a-fluid-block--embed" in content
    assert "--s2a-grid-area-desktop: 8 / 2 / 20 / 22;" in content
    assert "data-fluid-engine-section" not in content


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

    hero_suffix = hashlib.sha256(b"hero-bytes").hexdigest()[:12]
    brochure_suffix = hashlib.sha256(b"brochure-bytes").hexdigest()[:12]
    poster_suffix = hashlib.sha256(b"poster-bytes").hexdigest()[:12]
    video_suffix = hashlib.sha256(b"video-bytes").hexdigest()[:12]
    downloaded_files = {
        f"downloaded-assets/images/hero-{hero_suffix}.jpg": b"hero-bytes",
        f"downloaded-assets/files/brochure-{brochure_suffix}.pdf": b"brochure-bytes",
        f"downloaded-assets/images/poster-{poster_suffix}.jpg": b"poster-bytes",
        f"downloaded-assets/videos/clip-{video_suffix}.mp4": b"video-bytes",
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
                    filename=f"hero-{hero_suffix}.jpg",
                    local_path=f"downloaded-assets/images/hero-{hero_suffix}.jpg",
                    public_path=f"/assets/images/hero-{hero_suffix}.jpg",
                    canonical_id=hashlib.sha256(b"hero-bytes").hexdigest(),
                ),
                DownloadedAsset(
                    source_url="https://static1.squarespace.com/files/brochure.pdf",
                    final_url="https://static1.squarespace.com/files/brochure.pdf",
                    asset_type="file",
                    owner_route="/media",
                    group_key="a-2",
                    filename=f"brochure-{brochure_suffix}.pdf",
                    local_path=f"downloaded-assets/files/brochure-{brochure_suffix}.pdf",
                    public_path=f"/assets/files/brochure-{brochure_suffix}.pdf",
                    canonical_id=hashlib.sha256(b"brochure-bytes").hexdigest(),
                ),
                DownloadedAsset(
                    source_url="https://images.squarespace-cdn.com/content/poster.jpg",
                    final_url="https://images.squarespace-cdn.com/content/poster.jpg",
                    asset_type="image",
                    owner_route="/media",
                    group_key="video-3",
                    filename=f"poster-{poster_suffix}.jpg",
                    local_path=f"downloaded-assets/images/poster-{poster_suffix}.jpg",
                    public_path=f"/assets/images/poster-{poster_suffix}.jpg",
                    canonical_id=hashlib.sha256(b"poster-bytes").hexdigest(),
                ),
                DownloadedAsset(
                    source_url="https://static1.squarespace.com/media/clip.mp4",
                    final_url="https://static1.squarespace.com/media/clip.mp4",
                    asset_type="video",
                    owner_route="/media",
                    group_key="video-3",
                    filename=f"clip-{video_suffix}.mp4",
                    local_path=f"downloaded-assets/videos/clip-{video_suffix}.mp4",
                    public_path=f"/assets/videos/clip-{video_suffix}.mp4",
                    canonical_id=hashlib.sha256(b"video-bytes").hexdigest(),
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
    assert f"/assets/images/hero-{hero_suffix}.jpg" in content
    assert f"/assets/files/brochure-{brochure_suffix}.pdf" in content
    assert f"/assets/images/poster-{poster_suffix}.jpg" in content
    assert f"/assets/videos/clip-{video_suffix}.mp4" in content
    assert "data:image/gif" not in content
    assert "images.squarespace-cdn.com" not in content
    assert "static1.squarespace.com" not in content
    assert (output_dir /
            f"public/assets/images/hero-{hero_suffix}.jpg").read_bytes() == b"hero-bytes"
    assert (output_dir /
            f"public/assets/files/brochure-{brochure_suffix}.pdf").read_bytes() == b"brochure-bytes"
    assert (output_dir /
            f"public/assets/images/poster-{poster_suffix}.jpg").read_bytes() == b"poster-bytes"
    assert (output_dir /
            f"public/assets/videos/clip-{video_suffix}.mp4").read_bytes() == b"video-bytes"


def test_generate_astro_project_rewrites_alias_urls_to_one_canonical_asset(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshot"
    raw_html_dir = snapshot_dir / "raw-html"
    raw_html_dir.mkdir(parents=True)

    alias_url = "https://images.squarespace-cdn.com/content/hero-b.jpg"
    source_url = "https://images.squarespace-cdn.com/content/hero-a.jpg"
    shared_bytes = b"shared-hero-bytes"
    shared_hash = hashlib.sha256(shared_bytes).hexdigest()
    shared_suffix = shared_hash[:12]
    localized_relative_path = f"downloaded-assets/images/hero-a-{shared_suffix}.jpg"

    write_text(
        raw_html_dir / "index.html",
        f"<html><body><main><img src=\"{source_url}\" alt=\"Hero A\" /></main></body></html>",
    )
    write_text(
        raw_html_dir / "gallery.html",
        f"<html><body><main><img src=\"{alias_url}\" alt=\"Hero B\" /></main></body></html>",
    )
    localized_file = snapshot_dir / localized_relative_path
    localized_file.parent.mkdir(parents=True, exist_ok=True)
    localized_file.write_bytes(shared_bytes)

    write_json(
        snapshot_dir / "asset_manifest.json",
        AssetManifest(
            generated_at="2026-04-05T00:00:00+00:00",
            items=[
                DownloadedAsset(
                    source_url=source_url,
                    final_url=source_url,
                    asset_type="image",
                    owner_route="/",
                    group_key="img-1",
                    filename=f"hero-a-{shared_suffix}.jpg",
                    local_path=localized_relative_path,
                    public_path=f"/assets/images/hero-a-{shared_suffix}.jpg",
                    canonical_id=shared_hash,
                    alias_source_urls=[alias_url],
                    deduplicated_from_count=2,
                )
            ],
            source_asset_count=2,
            deduplicated_asset_count=1,
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
            "https://example.com/gallery",
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
                title="Home — Example Site",
                meta_description="Home description",
                canonical_url="https://example.com/",
                raw_html_path="raw-html/index.html",
            ),
            PageSnapshot(
                requested_url="https://example.com/gallery",
                final_url="https://example.com/gallery",
                status_code=200,
                content_type="text/html",
                title="Gallery — Example Site",
                meta_description="Gallery description",
                canonical_url="https://example.com/gallery",
                raw_html_path="raw-html/gallery.html",
            ),
        ],
    )

    snapshot_path = snapshot_dir / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro-site"
    result = generate_astro_project(snapshot_path, output_dir, site_url="https://example.com")
    home_content = (output_dir / "src/content/pages/home.md").read_text(encoding="utf-8")
    gallery_content = (output_dir / "src/content/pages/gallery.md").read_text(encoding="utf-8")

    assert result.pages_written == 2
    assert f"/assets/images/hero-a-{shared_suffix}.jpg" in home_content
    assert f"/assets/images/hero-a-{shared_suffix}.jpg" in gallery_content
    assert (output_dir /
            f"public/assets/images/hero-a-{shared_suffix}.jpg").read_bytes() == shared_bytes
    assert len(list((output_dir / "public/assets/images").iterdir())) == 1
