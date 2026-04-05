from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class JsonDataProbe:
    source_url: str
    json_url: str
    attempted: bool
    available: bool
    status_code: int | None
    top_level_keys: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class SiteProbe:
    target_url: str
    final_home_url: str | None
    site_origin: str
    homepage_status_code: int | None
    homepage_title: str | None
    probably_squarespace: bool
    squarespace_indicators: list[str] = field(default_factory=list)
    version_hint: str | None = None
    password_gate_detected: bool = False
    json_probe: JsonDataProbe | None = None
    robots_url: str | None = None
    robots_status_code: int | None = None
    robots_disallow_all: bool = False
    robots_sitemaps: list[str] = field(default_factory=list)
    sitemap_url: str | None = None
    sitemap_status_code: int | None = None
    sitemap_entries: list[str] = field(default_factory=list)
    homepage_links: list[str] = field(default_factory=list)
    rss_feeds: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageSnapshot:
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    headings: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    asset_urls: list[str] = field(default_factory=list)
    squarespace_indicators: list[str] = field(default_factory=list)
    password_gate_detected: bool = False
    json_probe: JsonDataProbe | None = None
    raw_html_path: str | None = None
    raw_json_path: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CrawlSnapshot:
    generated_at: str
    target_url: str
    base_url: str
    probe: SiteProbe
    pages: list[PageSnapshot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageReportEntry:
    url: str
    status_code: int | None
    title: str | None
    json_available: bool
    password_gate_detected: bool


@dataclass(slots=True)
class CrawlReport:
    generated_at: str
    target_url: str
    probably_squarespace: bool
    version_hint: str | None
    pages_crawled: int
    ok_pages: int
    pages_with_json: int
    password_gated_pages: int
    unique_assets: int
    unique_internal_links: int
    sitemap_entries: int
    rss_feeds: list[str] = field(default_factory=list)
    manual_follow_up: list[str] = field(default_factory=list)
    pages: list[PageReportEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AuthCaptureReport:
    generated_at: str
    target_url: str
    login_url: str
    storage_state_path: str
    mode: str
    cookies_saved: int
    headless: bool
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WordPressItem:
    title: str | None
    link: str | None
    post_type: str | None
    status: str | None
    slug: str | None
    guid: str | None
    published_at: str | None
    excerpt_html: str | None
    content_html: str | None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WordPressExport:
    source_path: str
    site_title: str | None
    site_link: str | None
    site_description: str | None
    items: list[WordPressItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedNavigationItem:
    title: str
    url: str
    external: bool = False


@dataclass(slots=True)
class GeneratedContentEntry:
    entry_id: str
    title: str
    slug: str
    route_path: str
    description: str | None
    source_url: str | None
    canonical_url: str | None
    body: str
    body_format: str
    home: bool = False
    published_at: str | None = None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AstroManifest:
    generated_at: str
    site_title: str
    site_description: str | None
    base_url: str | None
    blog_base_path: str
    blog_title: str
    navigation: list[GeneratedNavigationItem] = field(default_factory=list)
    pages: list[GeneratedContentEntry] = field(default_factory=list)
    posts: list[GeneratedContentEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AstroGenerationResult:
    generated_at: str
    output_dir: str
    manifest_path: str
    pages_written: int
    posts_written: int
    warnings: list[str] = field(default_factory=list)
