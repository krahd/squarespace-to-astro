from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from html import unescape
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
import yaml

from s2a.files import read_json, write_json, write_text
from s2a.normalize.models import (
    AstroGenerationResult,
    AstroManifest,
    GeneratedContentEntry,
    GeneratedNavigationItem,
)


NOISE_PATTERN = re.compile(
    r"nav|menu|header|footer|breadcrumb|share|social|cookie|newsletter|pagination|search|sidebar",
    re.IGNORECASE,
)
KNOWN_BLOG_SEGMENTS = {"blog", "news", "journal", "stories", "posts", "writing"}
UTILITY_ROUTE_SEGMENTS = {"cart", "checkout", "account"}
HEADER_NAV_SELECTORS = (
    ".header-display-desktop .header-nav-list",
    ".header-title-nav-wrapper .header-nav-list",
    ".header-nav-list",
    ".header-nav nav",
    ".Header-nav nav",
    "header nav",
    "[data-test='header-inner'] nav",
)
NAV_TEXT_IGNORE = {
    "",
    "skip to content",
    "menu",
    "open menu",
    "close menu",
    "search",
}
TRANSPARENT_HEADER_MARKERS = (
    '"tweak-transparent-header":"true"',
    "tweak-transparent-header",
    "transparent-header",
    "header-overlay-alignment",
)
STRUCTURED_CONTENT_SELECTOR = (
    ".s2a-gallery-grid, .s2a-fluid, .portfolio-grid-basic, .grid-wrapper, .sqs-gallery, .gallery-block, "
    "[data-fluid-engine-section], [data-fluid-engine], .fluid-engine, .fe-block, .embed-block, iframe"
)
FORCED_HTML_SELECTOR = (
    ".s2a-gallery-grid, .s2a-fluid, [data-fluid-engine-section], [data-fluid-engine], .fluid-engine, "
    ".fe-block, .embed-block, iframe"
)
LAYOUT_STYLE_MARKERS = (
    "grid-area:",
    ".fe-block",
    ".fluid-engine",
    ".portfolio-grid",
    ".sqs-gallery-design-grid",
    "embed-block-wrapper",
)
FLUID_BLOCK_STYLE_PATTERN = re.compile(
    r"\.(?P<block>fe-block-[A-Za-z0-9_]+)\s*\{\s*[^{}]*?grid-area:\s*(?P<area>[^;]+);\s*z-index:\s*(?P<z>[^;]+);",
    re.S,
)
FLUID_BLOCK_DESKTOP_STYLE_PATTERN = re.compile(
    r"@media\s*\(min-width:\s*768px\)\s*\{\s*\.(?P<block>fe-block-[A-Za-z0-9_]+)\s*\{\s*[^{}]*?grid-area:\s*(?P<area>[^;]+);\s*z-index:\s*(?P<z>[^;]+);",
    re.S,
)


def generate_astro_project(
    snapshot_path: Path,
    output_dir: Path,
    xml_import_path: Path | None = None,
    site_url: str | None = None,
    base_path: str | None = None,
    project_name: str | None = None,
    fidelity_mode: str = "high",
    layout_strategy: str = "hybrid",
    markdown_first: bool = False,
) -> AstroGenerationResult:
    snapshot = read_json(snapshot_path)
    xml_import = read_json(xml_import_path) if xml_import_path else None
    asset_manifest_path = snapshot_path.parent / "asset_manifest.json"
    asset_manifest = read_json(asset_manifest_path) if asset_manifest_path.exists() else None

    manifest = build_astro_manifest(
        snapshot,
        snapshot_path.parent,
        xml_import,
        asset_manifest,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    if site_url:
        manifest.base_url = site_url.rstrip("/")

    write_project(
        output_dir,
        manifest,
        base_path=base_path,
        project_name=project_name,
        snapshot_root=snapshot_path.parent,
        asset_manifest=asset_manifest,
    )
    write_json(output_dir / "migration-manifest.json", manifest)

    return AstroGenerationResult(
        generated_at=datetime.now(UTC).isoformat(),
        output_dir=str(output_dir),
        manifest_path="migration-manifest.json",
        pages_written=len(manifest.pages),
        posts_written=len(manifest.posts),
        warnings=manifest.warnings,
    )


def build_astro_manifest(
    snapshot: dict,
    snapshot_root: Path,
    xml_import: dict | None,
    asset_manifest: dict | None,
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> AstroManifest:
    probe = snapshot.get("probe", {})
    page_snapshots = snapshot.get("pages", [])
    xml_items = xml_import.get("items", []) if xml_import else []
    xml_site_title = xml_import.get("site_title") if xml_import else None
    xml_site_description = xml_import.get("site_description") if xml_import else None

    site_title = (
        xml_site_title
        or probe.get("homepage_title")
        or find_page_title(page_snapshots, "/")
        or "Squarespace Migration"
    )
    site_description = (
        xml_site_description
        or find_page_description(page_snapshots, "/")
    )
    base_url = probe.get("final_home_url") or snapshot.get("base_url")
    blog_base_path = infer_blog_base_path(page_snapshots, snapshot_root, xml_items)
    blog_title = determine_blog_title(page_snapshots, blog_base_path, site_title)
    skipped_utility_routes = sorted(
        {
            route_path_for_page(page)
            for page in page_snapshots
            if is_utility_route(route_path_for_page(page))
        }
    )
    asset_lookup = build_asset_lookup(asset_manifest)
    raw_homepage_html = raw_html_from_page(find_home_page_snapshot(page_snapshots), snapshot_root)
    header_style = infer_header_style(raw_homepage_html, fidelity_mode)
    background_style = infer_background_style(raw_homepage_html, fidelity_mode)
    header_width = infer_header_width(raw_homepage_html, fidelity_mode)
    header_layout = infer_header_layout(raw_homepage_html, fidelity_mode)
    header_alignment = infer_header_alignment(raw_homepage_html, fidelity_mode)
    page_width = extract_tweak_value(raw_homepage_html, "maxPageWidth")
    page_padding = extract_tweak_value(raw_homepage_html, "pagePadding")
    header_padding = extract_tweak_value(raw_homepage_html, "header-vert-padding")

    pages = build_page_entries(
        page_snapshots,
        snapshot_root,
        xml_items,
        blog_base_path,
        site_title,
        asset_lookup,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    posts = build_post_entries(
        page_snapshots,
        snapshot_root,
        xml_items,
        blog_base_path,
        site_title,
        asset_lookup,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    navigation, navigation_source = build_navigation(
        snapshot,
        snapshot_root,
        page_snapshots,
        pages,
        posts,
        blog_base_path,
        blog_title,
        site_title,
        base_url,
    )
    warnings: list[str] = []

    if not any(page.home for page in pages):
        pages.insert(
            0,
            GeneratedContentEntry(
                entry_id="home",
                title=site_title,
                slug="",
                route_path="/",
                description=site_description,
                source_url=base_url,
                canonical_url=base_url,
                body=f"# {site_title}\n\nThis homepage was created as a placeholder because the crawler could not extract one automatically.",
                body_format="markdown",
                home=True,
            ),
        )
        warnings.append(
            "A placeholder homepage was created because no extracted home page was available.")

    if not posts:
        warnings.append(
            "No blog posts were generated. The Astro site will contain page content only.")

    if skipped_utility_routes:
        warnings.append(
            "Skipped utility routes that do not map cleanly to static content: "
            + ", ".join(skipped_utility_routes)
        )

    if asset_manifest and asset_manifest.get("warnings"):
        warnings.extend(asset_manifest.get("warnings", []))

    return AstroManifest(
        generated_at=datetime.now(UTC).isoformat(),
        site_title=site_title,
        site_description=site_description,
        base_url=base_url,
        blog_base_path=blog_base_path,
        blog_title=blog_title,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
        navigation_source=navigation_source,
        header_style=header_style,
        background_style=background_style,
        header_width=header_width,
        header_layout=header_layout,
        header_alignment=header_alignment,
        page_width=page_width,
        page_padding=page_padding,
        header_padding=header_padding,
        navigation=navigation,
        pages=pages,
        posts=posts,
        warnings=warnings,
    )


def build_page_entries(
    page_snapshots: list[dict],
    snapshot_root: Path,
    xml_items: list[dict],
    blog_base_path: str,
    site_title: str,
    asset_lookup: dict[str, str],
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> list[GeneratedContentEntry]:
    entries: dict[str, GeneratedContentEntry] = {}
    xml_pages = {
        normalize_path(urlsplit(item.get("link") or f"/{item.get('slug') or ''}").path): item
        for item in xml_items
        if item.get("post_type") == "page" and item.get("status") == "publish"
    }
    posts_exist = any(
        item.get("post_type") == "post" and item.get("status") == "publish" for item in xml_items
    ) or any(is_post_path(route_path_for_page(page), blog_base_path) for page in page_snapshots)

    for page in page_snapshots:
        route_path = route_path_for_page(page)
        if is_utility_route(route_path):
            continue
        if route_path == blog_base_path and posts_exist:
            continue
        if is_post_path(route_path, blog_base_path):
            continue

        entry = generated_entry_from_snapshot(
            page,
            snapshot_root,
            route_path,
            site_title,
            asset_lookup,
            fidelity_mode=fidelity_mode,
            layout_strategy=layout_strategy,
            markdown_first=markdown_first,
        )
        xml_page = xml_pages.pop(route_path, None)
        if xml_page and xml_page.get("content_html"):
            body, body_format, presentation = body_and_presentation_from_html(
                localize_content_html(xml_page.get("content_html"), asset_lookup),
                fidelity_mode=fidelity_mode,
                layout_strategy=layout_strategy,
                markdown_first=markdown_first,
            )
            entry = replace(
                entry,
                title=clean_title(xml_page.get("title") or entry.title, site_title),
                description=excerpt_text(xml_page.get("excerpt_html")) or entry.description,
                source_url=xml_page.get("link") or entry.source_url,
                canonical_url=xml_page.get("link") or entry.canonical_url,
                body=body,
                body_format=body_format,
                presentation=presentation,
            )
        entries[route_path] = entry

    for route_path, xml_page in xml_pages.items():
        if is_utility_route(route_path):
            continue
        if route_path == blog_base_path and posts_exist:
            continue
        if is_post_path(route_path, blog_base_path):
            continue
        entries[route_path] = generated_entry_from_xml_item(
            xml_page,
            route_path,
            site_title,
            asset_lookup,
            fidelity_mode=fidelity_mode,
            layout_strategy=layout_strategy,
            markdown_first=markdown_first,
        )

    ordered = sorted(entries.values(), key=lambda entry: (not entry.home, entry.route_path))
    return ordered


def build_post_entries(
    page_snapshots: list[dict],
    snapshot_root: Path,
    xml_items: list[dict],
    blog_base_path: str,
    site_title: str,
    asset_lookup: dict[str, str],
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> list[GeneratedContentEntry]:
    entries: dict[str, GeneratedContentEntry] = {}

    for xml_item in xml_items:
        if xml_item.get("post_type") != "post" or xml_item.get("status") != "publish":
            continue

        route_path = normalize_path(urlsplit(xml_item.get(
            "link") or f"{blog_base_path}/{xml_item.get('slug') or ''}").path)
        if not is_post_path(route_path, blog_base_path):
            route_path = normalize_path(
                f"{blog_base_path}/{xml_item.get('slug') or route_path.strip('/')}")
        entries[route_path] = generated_post_from_xml_item(
            xml_item,
            route_path,
            blog_base_path,
            site_title,
            asset_lookup,
            fidelity_mode=fidelity_mode,
            layout_strategy=layout_strategy,
            markdown_first=markdown_first,
        )

    for page in page_snapshots:
        route_path = route_path_for_page(page)
        if is_utility_route(route_path):
            continue
        if not is_post_path(route_path, blog_base_path):
            continue
        if route_path in entries:
            continue
        entries[route_path] = generated_post_from_snapshot(
            page,
            snapshot_root,
            route_path,
            blog_base_path,
            site_title,
            asset_lookup,
            fidelity_mode=fidelity_mode,
            layout_strategy=layout_strategy,
            markdown_first=markdown_first,
        )

    return sorted(
        entries.values(),
        key=lambda entry: entry.published_at or entry.route_path,
        reverse=True,
    )


def generated_entry_from_snapshot(
    page: dict,
    snapshot_root: Path,
    route_path: str,
    site_title: str,
    asset_lookup: dict[str, str],
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> GeneratedContentEntry:
    html_fragment = localize_content_html(
        html_from_snapshot(
            page,
            snapshot_root,
            fidelity_mode=fidelity_mode,
            layout_strategy=layout_strategy,
        ),
        asset_lookup,
    )
    body, body_format, presentation = body_and_presentation_from_html(
        html_fragment,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    title = clean_title(page.get("title") or label_from_path(route_path), site_title)
    source_url = page.get("final_url") or page.get("requested_url")
    description = page.get("meta_description")

    if not body:
        body = f"# {title}\n\nThis page was discovered during migration, but the crawler could not extract a clean body automatically."
        body_format = "markdown"
        presentation = "standard"

    return GeneratedContentEntry(
        entry_id=entry_id_for_path(route_path, "page"),
        title=title,
        slug=slug_for_page(route_path),
        route_path=route_path,
        description=description,
        source_url=source_url,
        canonical_url=page.get("canonical_url") or source_url,
        body=body,
        body_format=body_format,
        presentation=presentation,
        home=route_path == "/",
    )


def generated_entry_from_xml_item(
    xml_item: dict,
    route_path: str,
    site_title: str,
    asset_lookup: dict[str, str],
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> GeneratedContentEntry:
    body, body_format, presentation = body_and_presentation_from_html(
        localize_content_html(
            xml_item.get("content_html") or xml_item.get("excerpt_html") or "",
            asset_lookup,
        ),
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    title = clean_title(xml_item.get("title") or label_from_path(route_path), site_title)

    if not body:
        body = f"# {title}\n"
        body_format = "markdown"
        presentation = "standard"

    return GeneratedContentEntry(
        entry_id=entry_id_for_path(route_path, "page"),
        title=title,
        slug=slug_for_page(route_path),
        route_path=route_path,
        description=excerpt_text(xml_item.get("excerpt_html")),
        source_url=xml_item.get("link"),
        canonical_url=xml_item.get("link"),
        body=body,
        body_format=body_format,
        presentation=presentation,
        home=route_path == "/",
    )


def generated_post_from_snapshot(
    page: dict,
    snapshot_root: Path,
    route_path: str,
    blog_base_path: str,
    site_title: str,
    asset_lookup: dict[str, str],
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> GeneratedContentEntry:
    html_fragment = localize_content_html(
        html_from_snapshot(
            page,
            snapshot_root,
            fidelity_mode=fidelity_mode,
            layout_strategy=layout_strategy,
        ),
        asset_lookup,
    )
    body, body_format, presentation = body_and_presentation_from_html(
        html_fragment,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    title = clean_title(page.get("title") or label_from_path(route_path), site_title)
    source_url = page.get("final_url") or page.get("requested_url")
    published_at = infer_date_from_route(route_path)

    if not body:
        body = f"# {title}\n\nThis post was discovered during migration, but its body could not be converted cleanly."
        body_format = "markdown"
        presentation = "standard"

    return GeneratedContentEntry(
        entry_id=entry_id_for_path(route_path, "post"),
        title=title,
        slug=relative_post_slug(route_path, blog_base_path),
        route_path=route_path,
        description=page.get("meta_description"),
        source_url=source_url,
        canonical_url=page.get("canonical_url") or source_url,
        body=body,
        body_format=body_format,
        presentation=presentation,
        published_at=published_at,
    )


def generated_post_from_xml_item(
    xml_item: dict,
    route_path: str,
    blog_base_path: str,
    site_title: str,
    asset_lookup: dict[str, str],
    *,
    fidelity_mode: str,
    layout_strategy: str,
    markdown_first: bool,
) -> GeneratedContentEntry:
    body, body_format, presentation = body_and_presentation_from_html(
        localize_content_html(
            xml_item.get("content_html") or xml_item.get("excerpt_html") or "",
            asset_lookup,
        ),
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    title = clean_title(xml_item.get("title") or label_from_path(route_path), site_title)

    if not body:
        body = f"# {title}\n"
        body_format = "markdown"
        presentation = "standard"

    return GeneratedContentEntry(
        entry_id=entry_id_for_path(route_path, "post"),
        title=title,
        slug=relative_post_slug(route_path, blog_base_path),
        route_path=route_path,
        description=excerpt_text(xml_item.get("excerpt_html")),
        source_url=xml_item.get("link"),
        canonical_url=xml_item.get("link"),
        body=body,
        body_format=body_format,
        presentation=presentation,
        published_at=normalize_datetime_string(xml_item.get("published_at")),
        categories=list(dict.fromkeys(xml_item.get("categories", []))),
        tags=list(dict.fromkeys(xml_item.get("tags", []))),
    )


def build_navigation(
    snapshot: dict,
    snapshot_root: Path,
    page_snapshots: list[dict],
    pages: list[GeneratedContentEntry],
    posts: list[GeneratedContentEntry],
    blog_base_path: str,
    blog_title: str,
    site_title: str,
    base_url: str | None,
) -> tuple[list[GeneratedNavigationItem], str]:
    page_titles = {
        page.route_path: page.title for page in pages
    }
    snapshot_titles = {
        route_path_for_page(page): clean_title(page.get("title") or label_from_path(route_path_for_page(page)), site_title)
        for page in page_snapshots
    }

    navigation: list[GeneratedNavigationItem] = []
    seen: set[str] = set()
    extracted_navigation, navigation_source = extract_navigation_from_homepage(
        page_snapshots,
        snapshot_root,
        base_url,
    )

    for item in extracted_navigation:
        if item.external:
            if item.url in seen:
                continue
            navigation.append(item)
            seen.add(item.url)
            continue

        path = item.url
        if is_utility_route(path) or path in seen:
            continue
        if path == blog_base_path and posts:
            navigation.append(GeneratedNavigationItem(title=blog_title, url=path))
        else:
            navigation.append(item)
        seen.add(path)

    if not extracted_navigation:
        navigation_source = "probe-links"
        homepage_links = snapshot.get("probe", {}).get("homepage_links", [])
        for link in homepage_links:
            path = normalize_path(urlsplit(link).path)
            if is_utility_route(path):
                continue
            if path in seen:
                continue
            if path == blog_base_path and posts:
                title = blog_title
            elif path == "/":
                title = "Home"
            else:
                title = page_titles.get(path) or snapshot_titles.get(path) or label_from_path(path)
            navigation.append(GeneratedNavigationItem(title=title, url=path))
            seen.add(path)

    if "/" not in seen:
        title = "Home" if navigation_source == "probe-links" else page_titles.get("/") or "Home"
        navigation.insert(0, GeneratedNavigationItem(title=title, url="/"))
        seen.add("/")

    for page in pages:
        if page.home or page.route_path in seen:
            continue
        navigation.append(GeneratedNavigationItem(title=page.title, url=page.route_path))
        seen.add(page.route_path)

    if posts and blog_base_path not in seen:
        navigation.append(GeneratedNavigationItem(title=blog_title, url=blog_base_path))

    return navigation, navigation_source


def extract_navigation_from_homepage(
    page_snapshots: list[dict],
    snapshot_root: Path,
    base_url: str | None,
) -> tuple[list[GeneratedNavigationItem], str]:
    raw_html = raw_html_from_page(find_home_page_snapshot(page_snapshots), snapshot_root)
    if not raw_html:
        return [], "probe-links"

    soup = BeautifulSoup(raw_html, "html.parser")
    for selector in HEADER_NAV_SELECTORS:
        for candidate in soup.select(selector):
            items = navigation_items_from_container(candidate, base_url)
            internal_count = sum(1 for item in items if not item.external)
            if 2 <= internal_count <= 12:
                return items, "homepage-html"

    return [], "probe-links"


def navigation_items_from_container(container: Tag, base_url: str | None) -> list[GeneratedNavigationItem]:
    items: list[GeneratedNavigationItem] = []
    seen: set[str] = set()
    base_host = urlsplit(base_url).netloc if base_url else ""

    for anchor in container.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        text = " ".join(anchor.stripped_strings)
        if not href or text.lower() in NAV_TEXT_IGNORE:
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        resolved = urljoin(base_url or "https://example.invalid", href)
        parsed = urlsplit(resolved)
        external = bool(base_host and parsed.netloc and parsed.netloc != base_host)
        url = href if external else normalize_path(parsed.path)
        if not external and not url:
            continue
        dedupe_key = f"{url}|{external}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(GeneratedNavigationItem(title=text, url=url, external=external))

    return items


def write_project(
    output_dir: Path,
    manifest: AstroManifest,
    base_path: str | None,
    project_name: str | None,
    snapshot_root: Path,
    asset_manifest: dict | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "src/content/pages").mkdir(parents=True, exist_ok=True)
    (output_dir / "src/content/posts").mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "package.json", render_package_json(manifest, project_name))
    write_text(output_dir / "astro.config.mjs", render_astro_config(manifest, base_path))
    write_text(output_dir / "tsconfig.json", render_tsconfig())
    write_text(output_dir / "src/content.config.ts", render_content_config(bool(manifest.posts)))
    write_text(output_dir / "src/layouts/BaseLayout.astro", render_base_layout())
    write_text(output_dir / "src/utils/routing.ts", render_routing_util())
    write_text(output_dir / "src/styles/site.css", render_site_css())
    write_json(output_dir / "src/data/site.json", render_site_data(manifest))
    write_text(output_dir / "src/pages/index.astro", render_home_page())
    write_text(output_dir / "src/pages/[...slug].astro", render_generic_page())
    copy_localized_assets(output_dir, snapshot_root, asset_manifest)

    if manifest.posts:
        blog_segments = [segment for segment in manifest.blog_base_path.strip(
            "/").split("/") if segment]
        blog_dir = output_dir / "src/pages" / Path(*blog_segments)
        import_prefix = "../" * (len(blog_segments) + 1)
        write_text(blog_dir / "index.astro", render_blog_index(import_prefix))
        write_text(blog_dir / "[...slug].astro", render_blog_post(import_prefix))

    write_content_files(output_dir / "src/content/pages", manifest.pages)
    write_content_files(output_dir / "src/content/posts", manifest.posts)


def write_content_files(target_dir: Path, entries: list[GeneratedContentEntry]) -> None:
    used_names: set[str] = set()

    for entry in entries:
        filename = entry.entry_id
        if filename in used_names:
            suffix = 2
            while f"{filename}-{suffix}" in used_names:
                suffix += 1
            filename = f"{filename}-{suffix}"
        used_names.add(filename)

        frontmatter = {
            "title": entry.title,
            "slug": entry.slug,
            "routePath": entry.route_path,
            "description": entry.description,
            "sourceUrl": entry.source_url,
            "canonicalUrl": entry.canonical_url,
            "bodyFormat": entry.body_format,
            "presentation": entry.presentation,
            "home": entry.home if entry.home else None,
            "publishedAt": entry.published_at,
            "categories": entry.categories or None,
            "tags": entry.tags or None,
        }
        rendered = render_markdown_file(frontmatter, entry.body)
        write_text(target_dir / f"{filename}.md", rendered)


def render_markdown_file(frontmatter: dict, body: str) -> str:
    cleaned = {key: value for key, value in frontmatter.items() if value not in (None, [], "")}
    yaml_frontmatter = yaml.safe_dump(cleaned, sort_keys=False, allow_unicode=True).strip()
    body = body.strip()
    return f"---\n{yaml_frontmatter}\n---\n\n{body}\n"


def render_package_json(manifest: AstroManifest, project_name: str | None) -> dict:
    return {
        "name": project_name or slugify_name(manifest.site_title),
        "private": True,
        "type": "module",
        "scripts": {
            "dev": "astro dev",
            "build": "astro build",
            "preview": "astro preview",
        },
        "dependencies": {
            "astro": "^5.0.0",
        },
    }


def render_astro_config(manifest: AstroManifest, base_path: str | None) -> str:
    lines = ["import { defineConfig } from 'astro/config';", "", "export default defineConfig({"]
    if manifest.base_url:
        lines.append(f"  site: '{manifest.base_url}',")
    if base_path:
        lines.append(f"  base: '{normalize_base_path(base_path)}',")
    lines.append("});")
    lines.append("")
    return "\n".join(lines)


def render_tsconfig() -> str:
    return '{\n  "extends": "astro/tsconfigs/strict"\n}\n'


def render_content_config(has_posts: bool) -> str:
    if not has_posts:
        return """import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const pages = defineCollection({
  loader: glob({ base: './src/content/pages', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    slug: z.string().default(''),
    routePath: z.string(),
    description: z.string().optional(),
    sourceUrl: z.string().url().optional(),
    canonicalUrl: z.string().url().optional(),
    bodyFormat: z.enum(['markdown', 'html']).default('markdown'),
        presentation: z.enum(['standard', 'immersive']).default('standard'),
    home: z.boolean().optional(),
  }),
});

export const collections = { pages };
"""

    return """import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const pages = defineCollection({
  loader: glob({ base: './src/content/pages', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    slug: z.string().default(''),
    routePath: z.string(),
    description: z.string().optional(),
    sourceUrl: z.string().url().optional(),
    canonicalUrl: z.string().url().optional(),
    bodyFormat: z.enum(['markdown', 'html']).default('markdown'),
        presentation: z.enum(['standard', 'immersive']).default('standard'),
    home: z.boolean().optional(),
  }),
});

const posts = defineCollection({
  loader: glob({ base: './src/content/posts', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    routePath: z.string(),
    description: z.string().optional(),
    sourceUrl: z.string().url().optional(),
    canonicalUrl: z.string().url().optional(),
    bodyFormat: z.enum(['markdown', 'html']).default('markdown'),
    presentation: z.enum(['standard', 'immersive']).default('standard'),
    publishedAt: z.coerce.date().optional(),
    categories: z.array(z.string()).default([]),
    tags: z.array(z.string()).default([]),
  }),
});

export const collections = { pages, posts };
"""


def render_base_layout() -> str:
    return """---
import site from '../data/site.json';
import '../styles/site.css';
import { withBase } from '../utils/routing';

interface NavItem {
  title: string;
  url: string;
  external?: boolean;
}

interface Props {
  title?: string;
  description?: string;
  currentPath?: string;
}

const { title, description, currentPath = '/' } = Astro.props;
const pageTitle = title ? (title === site.title ? title : `${title} | ${site.title}`) : site.title;
const metaDescription = description || site.description || '';
const canonicalHref = site.baseUrl ? new URL(currentPath, site.baseUrl).toString() : null;
const bodyClasses = [
    `fidelity-${site.fidelityMode || 'high'}`,
    `layout-${site.layoutStrategy || 'hybrid'}`,
    `header-${site.headerStyle || 'solid'}`,
    `background-${site.backgroundStyle || 'editorial'}`,
    `header-width-${site.headerWidth || 'inset'}`,
    `header-layout-${site.headerLayout || 'stacked'}`,
    `header-alignment-${site.headerAlignment || 'left'}`,
].join(' ');
const headerClasses = [
    'site-header',
    site.headerStyle === 'transparent' ? 'site-header--transparent' : 'surface',
].join(' ');
const pageShellStyle = [
    site.pageWidth ? `--site-max-width: ${site.pageWidth};` : '',
    site.pagePadding ? `--site-page-padding: ${site.pagePadding};` : '',
    site.headerPadding ? `--site-header-padding: ${site.headerPadding};` : '',
].filter(Boolean).join(' ');
---

<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{pageTitle}</title>
    {metaDescription && <meta name="description" content={metaDescription} />}
    {canonicalHref && <link rel="canonical" href={canonicalHref} />}
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Manrope:wght@400;500;700;800&display=swap" rel="stylesheet" />
  </head>
    <body class={bodyClasses} data-navigation-source={site.navigationSource || 'probe-links'}>
        <div class="ambient-glow ambient-glow--top" aria-hidden="true"></div>
        <div class="ambient-glow ambient-glow--bottom" aria-hidden="true"></div>
        <div class="page-shell" style={pageShellStyle}>
            <header class={headerClasses}>
        <a class="brand" href={withBase('/')}>{site.title}</a>
        <nav class="site-nav" aria-label="Primary">
          {site.navigation.map((item: NavItem) => (
            <a
              class:list={['nav-link', currentPath === item.url && 'is-active']}
              href={item.external ? item.url : withBase(item.url)}
                            target={item.external ? '_blank' : undefined}
                            rel={item.external ? 'noreferrer' : undefined}
            >
              {item.title}
            </a>
          ))}
        </nav>
                <div class="header-spacer" aria-hidden="true"></div>
      </header>
      <main class="page-main">
        <slot />
      </main>
      <footer class="site-footer surface">
        <p>{site.title}</p>
        <p>Generated from Squarespace content for a static Astro build.</p>
      </footer>
    </div>
  </body>
</html>
"""


def render_routing_util() -> str:
    return r"""export function withBase(path: string): string {
  const normalized = normalizePath(path);
  const base = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '');

  if (normalized === '/') {
    return base ? `${base}/` : '/';
  }

  return `${base}${normalized}`;
}

export function normalizePath(path: string): string {
  if (!path || path === '/') {
    return '/';
  }

  const trimmed = path.replace(/^\/+/, '').replace(/\/+$/, '');
  return `/${trimmed}`;
}
"""


def render_site_css() -> str:
    return """:root {
    --bg: #f6f2eb;
    --bg-alt: #ebe4d9;
    --ink: #1f1b18;
    --muted: #6a6258;
    --accent: #1f1b18;
    --surface: rgba(255, 255, 255, 0.82);
    --surface-border: rgba(31, 27, 24, 0.1);
    --shadow: 0 14px 36px rgba(31, 27, 24, 0.1);
    --radius-lg: 18px;
    --radius-md: 10px;
    --content-width: 88rem;
    --site-max-width: var(--content-width);
    --site-page-padding: 1rem;
    --site-header-padding: 0.95rem;
    --page-background:
        radial-gradient(circle at top left, rgba(168, 80, 45, 0.14), transparent 24%),
        radial-gradient(circle at bottom right, rgba(53, 112, 89, 0.14), transparent 28%),
        linear-gradient(180deg, var(--bg) 0%, #faf7f1 100%);
}

* {
    box-sizing: border-box;
}

html {
    background: var(--page-background);
    color: var(--ink);
    font-family: 'Manrope', system-ui, sans-serif;
}

body {
    margin: 0;
    min-height: 100vh;
    color: var(--ink);
    background: var(--page-background);
}

body.background-plain,
body.background-minimal {
    --page-background: #f6f2eb;
}

body.background-minimal {
    --surface: #ffffff;
    --surface-border: rgba(31, 27, 24, 0.08);
    --shadow: 0 8px 20px rgba(31, 27, 24, 0.06);
}

a {
    color: inherit;
}

.ambient-glow {
    position: fixed;
    inset: auto;
    width: 36rem;
    height: 36rem;
    pointer-events: none;
    filter: blur(70px);
    opacity: 0.65;
    z-index: 0;
}

.ambient-glow--top {
    top: -12rem;
    left: -8rem;
    background: rgba(168, 80, 45, 0.22);
}

.ambient-glow--bottom {
    right: -10rem;
    bottom: -16rem;
    background: rgba(53, 112, 89, 0.18);
}

body.background-plain .ambient-glow,
body.background-minimal .ambient-glow,
body.fidelity-high .ambient-glow {
    display: none;
}

.page-shell {
    position: relative;
    z-index: 1;
    width: min(100%, var(--site-max-width));
    margin: 0 auto;
    padding: 0.85rem var(--site-page-padding) 3rem;
}

body.header-transparent .page-shell {
    padding-top: 0.35rem;
}

.surface {
    backdrop-filter: blur(18px);
    background: var(--surface);
    border: 1px solid var(--surface-border);
    box-shadow: var(--shadow);
}

.site-header,
.site-footer,
.surface--hero,
.surface--article,
.surface--listing {
    border-radius: var(--radius-lg);
}

.site-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    padding: var(--site-header-padding) 1.15rem;
    margin: 0 auto 1.5rem;
}

.site-header--transparent {
    margin-bottom: 1rem;
    padding: calc(var(--site-header-padding) * 0.35) 0 calc(var(--site-header-padding) * 0.85);
    background: transparent;
    border: 0;
    box-shadow: none;
    backdrop-filter: none;
}

.header-spacer {
    display: none;
}

.header-layout-nav-right.header-alignment-center .site-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    column-gap: 1rem;
    align-items: center;
}

.header-layout-nav-right.header-alignment-center .brand {
    justify-self: start;
}

.header-layout-nav-right.header-alignment-center .site-nav {
    justify-self: center;
}

.header-layout-nav-right.header-alignment-center .header-spacer {
    display: block;
}

.brand {
    font-size: clamp(1rem, 1.6vw, 1.2rem);
    font-weight: 600;
    text-decoration: none;
}

body:not(.fidelity-high) .brand {
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.fidelity-high .brand {
    font-weight: 500;
    letter-spacing: 0.01em;
}

.site-nav {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
}

.nav-link {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0;
    border-bottom: 1px solid transparent;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-decoration: none;
    text-transform: uppercase;
    transition: color 180ms ease, border-color 180ms ease;
}

.fidelity-high .nav-link {
    font-size: 0.72rem;
    letter-spacing: 0.16em;
}

.nav-link:hover,
.nav-link.is-active {
    color: var(--ink);
    border-color: currentColor;
}

.page-main {
    display: grid;
    gap: 1.5rem;
}

.site-footer {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: 1rem 1.15rem;
    margin-top: 2rem;
    color: var(--muted);
    font-size: 0.95rem;
}

.fidelity-high .site-footer.surface {
    background: transparent;
    border: 0;
    box-shadow: none;
    padding-inline: 0;
}

.page-intro,
.article-header {
    display: grid;
    gap: 0.45rem;
    margin-bottom: 1.5rem;
}

.eyebrow {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
}

.page-title,
.article-title {
    margin: 0;
    font-family: 'Fraunces', serif;
    font-size: clamp(2.1rem, 5vw, 3.6rem);
    letter-spacing: -0.04em;
    line-height: 0.95;
}

.page-description,
.article-description {
    margin: 0;
    max-width: 42rem;
    color: var(--muted);
    font-size: 1.02rem;
}

.surface--hero,
.surface--article,
.surface--listing {
    padding: clamp(1.1rem, 2vw, 1.8rem);
}

.fidelity-high .surface--hero,
.fidelity-high .surface--article {
    background: transparent;
    border: 0;
    box-shadow: none;
    padding: 0;
}

.fidelity-high .surface--listing {
    background: rgba(255, 255, 255, 0.58);
}

.page-canvas {
    width: 100%;
}

.page-canvas--immersive {
    padding-top: 0.2rem;
}

.post-grid {
    list-style: none;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: 1rem;
    margin: 0;
    padding: 0;
}

.post-card {
    padding: 1rem;
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.64);
    border: 1px solid rgba(31, 27, 24, 0.08);
}

.post-card a {
    text-decoration: none;
}

.post-card h2 {
    margin: 0.35rem 0 0.6rem;
    font-family: 'Fraunces', serif;
    font-size: 1.35rem;
    letter-spacing: -0.03em;
}

.post-meta,
.tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    color: var(--muted);
    font-size: 0.9rem;
}

.tag {
    display: inline-flex;
    padding: 0.28rem 0.6rem;
    border-radius: 999px;
    background: rgba(31, 27, 24, 0.08);
}

.prose {
    max-width: 72rem;
    font-size: 1.02rem;
    line-height: 1.78;
}

.prose--immersive {
    max-width: none;
}

.prose > :first-child {
    margin-top: 0;
}

.prose h1,
.prose h2,
.prose h3 {
    font-family: 'Fraunces', serif;
    line-height: 1.1;
    letter-spacing: -0.03em;
}

.prose h2 {
    margin-top: 2rem;
    font-size: clamp(1.6rem, 4vw, 2.3rem);
}

.prose h3 {
    margin-top: 1.5rem;
    font-size: 1.3rem;
}

.prose p,
.prose li {
    color: #27231f;
}

.prose img {
    width: 100%;
    height: auto;
    border-radius: calc(var(--radius-md) - 2px);
}

.page-canvas .sections,
.page-canvas .page-section,
.page-canvas .content-wrapper,
.page-canvas .content,
.page-canvas .collection-content-wrapper,
.prose .sections,
.prose .page-section,
.prose .content-wrapper,
.prose .content,
.prose .collection-content-wrapper {
    width: 100%;
}

.page-canvas .page-section.full-bleed-section {
    padding: 0;
}

.page-canvas .grid-wrapper,
.page-canvas .portfolio-grid-basic,
.prose .grid-wrapper,
.prose .portfolio-grid-basic,
.s2a-gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    gap: 1rem;
}

.page-canvas .grid-item,
.prose .grid-item,
.s2a-gallery-card {
    display: grid;
    gap: 0.75rem;
    color: inherit;
    text-decoration: none;
}

.page-canvas .grid-image,
.prose .grid-image,
.s2a-gallery-media {
    margin: 0;
    overflow: hidden;
    border-radius: calc(var(--radius-md) - 2px);
    background: rgba(255, 255, 255, 0.5);
}

.page-canvas .grid-image img,
.prose .grid-image img,
.s2a-gallery-media img {
    display: block;
    width: 100%;
    aspect-ratio: 1 / 1;
    object-fit: cover;
    border-radius: 0;
    transition: transform 180ms ease;
}

.page-canvas .grid-item:hover .grid-image img,
.prose .grid-item:hover .grid-image img,
.s2a-gallery-card:hover .s2a-gallery-media img {
    transform: scale(1.02);
}

.page-canvas .portfolio-text,
.prose .portfolio-text,
.s2a-gallery-meta {
    display: grid;
    gap: 0.25rem;
}

.page-canvas .portfolio-title,
.prose .portfolio-title,
.s2a-gallery-title {
    margin: 0;
    font-size: 1rem;
    line-height: 1.25;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

.s2a-gallery-caption {
    margin: 0;
    color: var(--muted);
    font-size: 0.92rem;
}

.page-canvas .fluid-engine,
.prose .fluid-engine,
.s2a-fluid {
    display: grid;
    grid-template-columns: repeat(24, minmax(0, 1fr));
    column-gap: 1rem;
    row-gap: 1rem;
    align-items: start;
}

.page-canvas .fe-block,
.prose .fe-block,
.s2a-fluid-block {
    min-width: 0;
}

.s2a-fluid-block {
    grid-area: var(--s2a-grid-area-mobile, auto);
    z-index: var(--s2a-z-index, auto);
}

.page-canvas iframe,
.prose iframe,
.s2a-fluid-block iframe {
    width: 100%;
    max-width: 100%;
    aspect-ratio: 16 / 9;
    height: auto;
    border: 0;
}

.page-canvas .embed-block-wrapper,
.page-canvas .intrinsic,
.prose .embed-block-wrapper,
.prose .intrinsic,
.s2a-fluid-block .embed-block-wrapper,
.s2a-fluid-block .intrinsic {
    max-width: 100%;
}

.s2a-fluid-block--rule hr {
    margin: 0;
    border: 0;
    border-top: 1px solid rgba(31, 27, 24, 0.18);
}

.prose blockquote {
    margin: 1.5rem 0;
    padding: 0.75rem 1rem;
    border-left: 4px solid rgba(31, 27, 24, 0.28);
    background: rgba(31, 27, 24, 0.05);
}

.prose code {
    font-size: 0.92em;
    background: rgba(31, 27, 24, 0.08);
    padding: 0.1rem 0.3rem;
    border-radius: 6px;
}

@media (min-width: 768px) {
    .s2a-fluid-block {
        grid-area: var(--s2a-grid-area-desktop, var(--s2a-grid-area-mobile, auto));
    }
}

@media (max-width: 720px) {
    .page-shell {
        padding: 0.65rem var(--site-page-padding) 2rem;
    }

    .site-header {
        align-items: flex-start;
        flex-direction: column;
        padding-inline: 0.85rem;
    }

    .site-header--transparent {
        padding-inline: 0;
    }

    .header-layout-nav-right.header-alignment-center .site-header {
        display: flex;
    }

    .header-spacer {
        display: none !important;
    }

    .site-nav {
        gap: 0.7rem;
        justify-content: flex-start;
    }

    .site-footer {
        flex-direction: column;
    }

    .page-canvas .fluid-engine,
    .prose .fluid-engine,
    .s2a-fluid {
        grid-template-columns: 1fr;
    }

    .s2a-fluid-block {
        grid-area: auto;
    }
}
"""


def render_site_data(manifest: AstroManifest) -> dict:
    return {
        "title": manifest.site_title,
        "description": manifest.site_description,
        "baseUrl": manifest.base_url,
        "blogBasePath": manifest.blog_base_path,
        "blogTitle": manifest.blog_title,
        "fidelityMode": manifest.fidelity_mode,
        "layoutStrategy": manifest.layout_strategy,
        "markdownFirst": manifest.markdown_first,
        "navigationSource": manifest.navigation_source,
        "headerStyle": manifest.header_style,
        "backgroundStyle": manifest.background_style,
        "headerWidth": manifest.header_width,
        "headerLayout": manifest.header_layout,
        "headerAlignment": manifest.header_alignment,
        "pageWidth": manifest.page_width,
        "pagePadding": manifest.page_padding,
        "headerPadding": manifest.header_padding,
        "navigation": [
            {"title": item.title, "url": item.url, "external": item.external}
            for item in manifest.navigation
        ],
    }


def render_home_page() -> str:
    return """---
import { getCollection, render } from 'astro:content';
import BaseLayout from '../layouts/BaseLayout.astro';
import site from '../data/site.json';

const home = (await getCollection('pages')).find((entry) => entry.data.home);

if (!home) {
  throw new Error('No home page entry was generated.');
}

const { Content } = await render(home);
const isImmersive = home.data.presentation === 'immersive';
---

<BaseLayout title={home.data.title || site.title} description={home.data.description || site.description} currentPath="/">
    <article class={isImmersive ? 'page-canvas page-canvas--immersive' : 'surface surface--hero'}>
        <div class={isImmersive ? 'prose prose--immersive' : 'prose'}>
            <Content />
        </div>
  </article>
</BaseLayout>
"""


def render_generic_page() -> str:
    return """---
import { getCollection, render } from 'astro:content';
import BaseLayout from '../layouts/BaseLayout.astro';

export async function getStaticPaths() {
  const pages = await getCollection('pages');
  return pages
    .filter((entry) => !entry.data.home && entry.data.slug)
    .map((entry) => ({
      params: { slug: entry.data.slug },
      props: { entry },
    }));
}

const { entry } = Astro.props;
const { Content } = await render(entry);
const isImmersive = entry.data.presentation === 'immersive';
---

<BaseLayout title={entry.data.title} description={entry.data.description} currentPath={entry.data.routePath}>
    {isImmersive ? (
        <article class="page-canvas page-canvas--immersive">
            <div class="prose prose--immersive">
                <Content />
            </div>
        </article>
    ) : (
        <article class="surface surface--article">
            <header class="article-header">
                <p class="eyebrow">Page</p>
                <h1 class="article-title">{entry.data.title}</h1>
                {entry.data.description && <p class="article-description">{entry.data.description}</p>}
            </header>
            <div class="prose">
                <Content />
            </div>
        </article>
    )}
</BaseLayout>
"""


def render_blog_index(import_prefix: str) -> str:
    return """---
import { getCollection } from 'astro:content';
import BaseLayout from '__PREFIX__layouts/BaseLayout.astro';
import site from '__PREFIX__data/site.json';
import { withBase } from '__PREFIX__utils/routing';

const posts = (await getCollection('posts')).sort((left, right) => {
  const leftValue = left.data.publishedAt ? left.data.publishedAt.valueOf() : 0;
  const rightValue = right.data.publishedAt ? right.data.publishedAt.valueOf() : 0;
  return rightValue - leftValue;
});
---

<BaseLayout title={site.blogTitle} description={site.description} currentPath={site.blogBasePath}>
  <section class="surface surface--listing">
    <div class="page-intro">
      <p class="eyebrow">Archive</p>
      <h1 class="page-title">{site.blogTitle}</h1>
      <p class="page-description">Posts migrated from Squarespace and prepared for static Astro publishing.</p>
    </div>

    <ul class="post-grid">
      {posts.map((post) => (
        <li class="post-card">
          <a href={withBase(post.data.routePath)}>
            <div class="post-meta">
              {post.data.publishedAt && (
                <span>{post.data.publishedAt.toLocaleDateString('en-US', { dateStyle: 'medium' })}</span>
              )}
            </div>
            <h2>{post.data.title}</h2>
            {post.data.description && <p>{post.data.description}</p>}
          </a>
        </li>
      ))}
    </ul>
  </section>
</BaseLayout>
""".replace("__PREFIX__", import_prefix)


def render_blog_post(import_prefix: str) -> str:
    return """---
import { getCollection, render } from 'astro:content';
import BaseLayout from '__PREFIX__layouts/BaseLayout.astro';

export async function getStaticPaths() {
  const posts = await getCollection('posts');
  return posts
    .filter((entry) => entry.data.slug)
    .map((entry) => ({
      params: { slug: entry.data.slug },
      props: { entry },
    }));
}

const { entry } = Astro.props;
const { Content } = await render(entry);
const isImmersive = entry.data.presentation === 'immersive';
---

<BaseLayout title={entry.data.title} description={entry.data.description} currentPath={entry.data.routePath}>
    {isImmersive ? (
        <article class="page-canvas page-canvas--immersive">
            <div class="prose prose--immersive">
                <Content />
            </div>
        </article>
    ) : (
        <article class="surface surface--article">
            <header class="article-header">
                <p class="eyebrow">Article</p>
                <h1 class="article-title">{entry.data.title}</h1>
                {entry.data.description && <p class="article-description">{entry.data.description}</p>}
                <div class="post-meta">
                    {entry.data.publishedAt && (
                        <span>{entry.data.publishedAt.toLocaleDateString('en-US', { dateStyle: 'long' })}</span>
                    )}
                    {entry.data.categories.map((category: string) => (
                        <span class="tag">{category}</span>
                    ))}
                </div>
                {entry.data.tags.length > 0 && (
                    <div class="tag-row">
                        {entry.data.tags.map((tag: string) => <span class="tag">#{tag}</span>)}
                    </div>
                )}
            </header>
            <div class="prose">
                <Content />
            </div>
        </article>
    )}
</BaseLayout>
""".replace("__PREFIX__", import_prefix)


def infer_blog_base_path(page_snapshots: list[dict], snapshot_root: Path, xml_items: list[dict]) -> str:
    counts: Counter[str] = Counter()

    for item in xml_items:
        if item.get("post_type") != "post" or item.get("status") != "publish":
            continue
        route_path = normalize_path(urlsplit(item.get("link") or f"/{item.get('slug') or ''}").path)
        blog_path = candidate_blog_base_path(route_path)
        if blog_path:
            counts[blog_path] += 5

    for page in page_snapshots:
        json_blog_path = blog_base_path_from_page_json(page, snapshot_root)
        if json_blog_path:
            counts[json_blog_path] += 4
            continue

        known_blog_path = known_blog_base_path(route_path_for_page(page))
        if known_blog_path:
            counts[known_blog_path] += 2

    if not counts:
        return "/blog"

    return counts.most_common(1)[0][0]


def blog_base_path_from_page_json(page: dict, snapshot_root: Path) -> str | None:
    payload = raw_json_payload_for_page(page, snapshot_root)
    if payload is None:
        return None

    collection = payload.get("collection")
    if not isinstance(collection, dict):
        return None

    type_markers = " ".join(
        str(collection.get(key) or "") for key in ("typeName", "typeLabel")
    ).lower()
    if "blog" not in type_markers:
        return None

    collection_path = normalize_path(urlsplit(str(collection.get("fullUrl") or "")).path)
    if collection_path != "/":
        return collection_path

    item_paths: list[str] = []
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            blog_path = candidate_blog_base_path(urlsplit(str(item.get("fullUrl") or "")).path)
            if blog_path:
                item_paths.append(blog_path)

    if item_paths:
        return Counter(item_paths).most_common(1)[0][0]

    return "/blog"


def raw_json_payload_for_page(page: dict, snapshot_root: Path) -> dict | None:
    relative_path = page.get("raw_json_path")
    if not relative_path:
        return None

    full_path = snapshot_root / relative_path
    if not full_path.exists():
        return None

    try:
        payload = read_json(full_path)
    except (OSError, TypeError, ValueError):
        return None

    return payload if isinstance(payload, dict) else None


def candidate_blog_base_path(route_path: str) -> str | None:
    segments = path_segments(route_path)
    if len(segments) < 2:
        return None
    if segments[0].isdigit():
        return None
    return normalize_path(f"/{segments[0]}")


def known_blog_base_path(route_path: str) -> str | None:
    candidate = candidate_blog_base_path(route_path)
    if not candidate:
        return None
    first_segment = path_segments(candidate)[0]
    if first_segment in KNOWN_BLOG_SEGMENTS:
        return candidate
    return None


def determine_blog_title(page_snapshots: list[dict], blog_base_path: str, site_title: str) -> str:
    for page in page_snapshots:
        if route_path_for_page(page) == blog_base_path and page.get("title"):
            return clean_title(page["title"], site_title)
    return "Journal"


def route_path_for_page(page: dict) -> str:
    candidate = page.get("final_url") or page.get("requested_url") or "/"
    return normalize_path(urlsplit(candidate).path)


def normalize_path(path: str | None) -> str:
    if not path or path == "/":
        return "/"
    trimmed = path.strip()
    if not trimmed.startswith("/"):
        trimmed = f"/{trimmed}"
    trimmed = re.sub(r"/+", "/", trimmed)
    return trimmed.rstrip("/") or "/"


def path_segments(path: str) -> list[str]:
    return [segment for segment in normalize_path(path).strip("/").split("/") if segment]


def is_post_path(route_path: str, blog_base_path: str) -> bool:
    if route_path == blog_base_path:
        return False
    prefix = blog_base_path.rstrip("/") + "/"
    return route_path.startswith(prefix)


def is_utility_route(route_path: str) -> bool:
    segments = path_segments(route_path)
    if not segments:
        return False
    return segments[0] in UTILITY_ROUTE_SEGMENTS


def slug_for_page(route_path: str) -> str:
    if route_path == "/":
        return ""
    return route_path.strip("/")


def relative_post_slug(route_path: str, blog_base_path: str) -> str:
    relative = route_path.removeprefix(blog_base_path).strip("/")
    return relative


def html_from_snapshot(
    page: dict,
    snapshot_root: Path,
    *,
    fidelity_mode: str = "high",
    layout_strategy: str = "hybrid",
) -> str:
    html = raw_html_from_page(page, snapshot_root)
    if not html:
        return ""

    return extract_main_html(html, fidelity_mode=fidelity_mode, layout_strategy=layout_strategy)


def raw_html_from_page(page: dict | None, snapshot_root: Path) -> str:
    if not page:
        return ""

    relative_path = page.get("raw_html_path")
    if not relative_path:
        return ""

    full_path = snapshot_root / relative_path
    if not full_path.exists():
        return ""

    return full_path.read_text(encoding="utf-8")


def extract_main_html(html: str, *, fidelity_mode: str = "high", layout_strategy: str = "hybrid") -> str:
    soup = BeautifulSoup(html, "html.parser")
    candidates = [
        soup.find("article"),
        soup.find("main"),
        soup.select_one("[role='main']"),
        soup.select_one(
            ".main-content, .Main-content, .entry-content, .blog-item-wrapper, .sqs-layout, .page-section"),
        soup.body,
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        fragment = BeautifulSoup(str(candidate), "html.parser")
        preserve_layout_styles = fidelity_mode != "minimal" and contains_structured_layout(fragment)
        remove_noise(
            fragment,
            preserve_embeds=fidelity_mode != "minimal" or layout_strategy == "components",
            preserve_layout_styles=preserve_layout_styles,
        )
        text_length = len(" ".join(fragment.stripped_strings))
        if text_length >= 80 or candidate == soup.body:
            return fragment.decode().strip()

    return ""


def contains_structured_layout(fragment: BeautifulSoup) -> bool:
    return fragment.select_one(
        ".portfolio-grid-basic, .sqs-gallery-design-grid, [data-fluid-engine-section], [data-fluid-engine], .fluid-engine, .fe-block"
    ) is not None


def remove_noise(
    fragment: BeautifulSoup,
    *,
    preserve_embeds: bool = False,
    preserve_layout_styles: bool = False,
) -> None:
    selectors = [
        "script",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
        "svg",
    ]
    if not preserve_embeds:
        selectors.append("iframe")

    for selector in selectors:
        for element in fragment.select(selector):
            element.decompose()

    for style_tag in list(fragment.find_all("style")):
        if preserve_layout_styles and should_keep_style_tag(style_tag):
            continue
        style_tag.decompose()

    for element in list(fragment.find_all(True)):
        attrs = getattr(element, "attrs", None)
        if attrs is None:
            continue
        classes = attrs.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        classes = " ".join(classes)
        element_id = attrs.get("id", "")
        marker = f"{classes} {element_id}".strip()
        if marker and NOISE_PATTERN.search(marker):
            element.decompose()


def should_keep_style_tag(style_tag: Tag) -> bool:
    style_text = style_tag.get_text("\n", strip=True)
    if not style_text:
        return False
    lowered = style_text.lower()
    return any(marker in lowered for marker in LAYOUT_STYLE_MARKERS)


def build_asset_lookup(asset_manifest: dict | None) -> dict[str, str]:
    if not asset_manifest:
        return {}

    lookup: dict[str, str] = {}
    for item in asset_manifest.get("items", []):
        public_path = item.get("public_path")
        source_url = item.get("source_url")
        final_url = item.get("final_url")
        if not public_path:
            continue
        if source_url:
            lookup[str(source_url)] = str(public_path)
        if final_url:
            lookup[str(final_url)] = str(public_path)
        for alias_source_url in item.get("alias_source_urls", []):
            lookup[str(alias_source_url)] = str(public_path)
        for alias_final_url in item.get("alias_final_urls", []):
            lookup[str(alias_final_url)] = str(public_path)
    return lookup


def copy_localized_assets(output_dir: Path, snapshot_root: Path, asset_manifest: dict | None) -> None:
    if not asset_manifest:
        return

    copied_targets: set[str] = set()
    for item in asset_manifest.get("items", []):
        local_path = item.get("local_path")
        public_path = item.get("public_path")
        if not local_path or not public_path:
            continue
        if str(public_path) in copied_targets:
            continue

        source_path = snapshot_root / str(local_path)
        if not source_path.exists():
            continue

        target_path = output_dir / "public" / str(public_path).lstrip("/")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_targets.add(str(public_path))


def localize_content_html(html: str, asset_lookup: dict[str, str]) -> str:
    if not html or not asset_lookup:
        return html

    fragment = BeautifulSoup(html, "html.parser")
    rewrite_asset_attributes(fragment, asset_lookup)
    rewrite_video_audio_blocks(fragment, asset_lookup)
    rewrite_style_tag_urls(fragment, asset_lookup)
    return fragment.decode().strip()


def rewrite_style_tag_urls(fragment: BeautifulSoup, asset_lookup: dict[str, str]) -> None:
    for style_tag in fragment.find_all("style"):
        style_text = style_tag.string or style_tag.get_text()
        if not style_text:
            continue
        style_tag.string = rewrite_style_urls(style_text, asset_lookup)


def rewrite_asset_attributes(fragment: BeautifulSoup, asset_lookup: dict[str, str]) -> None:
    for tag in fragment.find_all("img"):
        rewrite_primary_attribute(tag, "src", ("src", "data-src", "data-image"), asset_lookup)
        rewrite_srcset_attribute(tag, ("srcset", "data-srcset"), asset_lookup)

    for tag in fragment.find_all("source"):
        rewrite_primary_attribute(tag, "src", ("src", "data-src"), asset_lookup)
        rewrite_srcset_attribute(tag, ("srcset", "data-srcset"), asset_lookup)

    for tag in fragment.find_all("video"):
        rewrite_primary_attribute(tag, "src", ("src", "data-src"), asset_lookup)
        rewrite_primary_attribute(tag, "poster", ("poster", "data-poster"), asset_lookup)

    for tag in fragment.find_all("audio"):
        rewrite_primary_attribute(tag, "src", ("src", "data-src"), asset_lookup)

    for tag in fragment.find_all("a"):
        rewrite_primary_attribute(tag, "href", ("href",), asset_lookup)

    for tag in fragment.find_all(True):
        style_value = tag.get("style")
        if style_value:
            tag["style"] = rewrite_style_urls(style_value, asset_lookup)


def rewrite_video_audio_blocks(fragment: BeautifulSoup, asset_lookup: dict[str, str]) -> None:
    for tag_name, label in (("video", "Video"), ("audio", "Audio")):
        for media in list(fragment.find_all(tag_name)):
            replacement = BeautifulSoup("", "html.parser")
            wrapper = replacement.new_tag("figure")
            wrapper["class"] = f"s2a-{tag_name}"

            poster = media.get("poster")
            localized_poster = asset_lookup.get(poster or "", poster)
            if localized_poster:
                poster_tag = replacement.new_tag("img", src=localized_poster)
                poster_tag["alt"] = media.get("aria-label") or f"{label} poster"
                wrapper.append(poster_tag)

            media_url = media.get("src")
            if not media_url:
                source_tag = media.find("source", src=True)
                if source_tag:
                    media_url = source_tag.get("src")

            localized_media_url = asset_lookup.get(media_url or "", media_url)
            if localized_media_url:
                paragraph = replacement.new_tag("p")
                anchor = replacement.new_tag("a", href=localized_media_url)
                anchor.string = media.get("aria-label") or f"{label} download"
                paragraph.append(anchor)
                wrapper.append(paragraph)

            if not wrapper.contents:
                placeholder = replacement.new_tag("p")
                placeholder.string = f"{label} content requires manual review."
                wrapper.append(placeholder)

            media.replace_with(wrapper)


def rewrite_primary_attribute(
    tag: Tag,
    target_attribute: str,
    candidate_attributes: tuple[str, ...],
    asset_lookup: dict[str, str],
) -> None:
    chosen_value: str | None = None

    for attribute in candidate_attributes:
        value = tag.get(attribute)
        if not value:
            continue
        chosen_value = asset_lookup.get(value, value)
        if not is_placeholder_asset_value(value):
            break

    if chosen_value:
        tag[target_attribute] = chosen_value

    for attribute in candidate_attributes:
        if attribute != target_attribute:
            tag.attrs.pop(attribute, None)


def rewrite_srcset_attribute(
    tag: Tag,
    candidate_attributes: tuple[str, ...],
    asset_lookup: dict[str, str],
) -> None:
    for attribute in candidate_attributes:
        value = tag.get(attribute)
        if not value:
            continue
        tag["srcset"] = rewrite_srcset(value, asset_lookup)
        break

    for attribute in candidate_attributes:
        if attribute != "srcset":
            tag.attrs.pop(attribute, None)


def rewrite_srcset(value: str, asset_lookup: dict[str, str]) -> str:
    rewritten: list[str] = []
    for candidate in value.split(","):
        cleaned = candidate.strip()
        if not cleaned:
            continue
        parts = cleaned.split()
        url = parts[0]
        descriptor = f" {parts[1]}" if len(parts) > 1 else ""
        rewritten.append(f"{asset_lookup.get(url, url)}{descriptor}")
    return ", ".join(rewritten)


def rewrite_style_urls(value: str, asset_lookup: dict[str, str]) -> str:
    def replace_url(match: re.Match[str]) -> str:
        original = match.group("url")
        localized = asset_lookup.get(original, original)
        return f"url('{localized}')"

    return re.sub(r"url\((['\"]?)(?P<url>[^)'\"]+)\1\)", replace_url, value)


def is_placeholder_asset_value(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered in {"#", "about:blank"}:
        return True
    return lowered.startswith(("data:", "about:", "javascript:"))


def body_from_html(
    html: str,
    *,
    fidelity_mode: str = "high",
    layout_strategy: str = "hybrid",
    markdown_first: bool = False,
) -> tuple[str, str]:
    body, body_format, _presentation = body_and_presentation_from_html(
        html,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    )
    return body, body_format


def body_and_presentation_from_html(
    html: str,
    *,
    fidelity_mode: str = "high",
    layout_strategy: str = "hybrid",
    markdown_first: bool = False,
) -> tuple[str, str, str]:
    if not html:
        return "", "markdown", "standard"

    cleaned_html = normalize_structured_html(
        html.strip(),
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
    )
    presentation = infer_content_presentation(
        cleaned_html,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
    )
    if should_prefer_html(
        cleaned_html,
        fidelity_mode=fidelity_mode,
        layout_strategy=layout_strategy,
        markdown_first=markdown_first,
    ):
        return cleaned_html, "html", presentation

    markdown = markdownify(
        cleaned_html,
        heading_style="ATX",
        bullets="-",
        escape_asterisks=False,
        escape_underscores=False,
    ).strip()
    text_html = plain_text(cleaned_html)
    text_markdown = plain_text(markdown)

    if not markdown:
        return cleaned_html, "html", presentation

    if len(text_markdown) < max(40, int(len(text_html) * 0.35)):
        return cleaned_html, "html", presentation

    return markdown, "markdown", "standard"


def normalize_structured_html(
    html: str,
    *,
    fidelity_mode: str,
    layout_strategy: str,
) -> str:
    if fidelity_mode == "minimal":
        return html

    if layout_strategy == "components":
        rebuilt_fluid_html = rebuild_fluid_engine_components(html)
        if rebuilt_fluid_html:
            html = rebuilt_fluid_html
        rebuilt_gallery_html = rebuild_gallery_components(html)
        if rebuilt_gallery_html:
            return rebuilt_gallery_html

    return html


def rebuild_fluid_engine_components(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    sections = soup.select("[data-fluid-engine-section]")
    if not sections:
        return None

    rebuilt_any = False
    for section in sections:
        rebuilt_section = build_fluid_engine_section(soup, section)
        if rebuilt_section is None:
            continue
        section.replace_with(rebuilt_section)
        rebuilt_any = True

    if not rebuilt_any:
        return None

    return soup.decode().strip()


def build_fluid_engine_section(soup: BeautifulSoup, section: Tag) -> Tag | None:
    fluid_container = section.select_one("[data-fluid-engine='true'], .fluid-engine")
    fluid_root = section.select_one(".fluid-engine")
    if fluid_root is None:
        return None

    layout_map = parse_fluid_engine_layout(section)
    rebuilt_section = soup.new_tag("section")
    rebuilt_section["class"] = "s2a-fluid-section"

    data_section_theme = section.get("data-section-theme")
    if data_section_theme:
        rebuilt_section["data-section-theme"] = data_section_theme

    rebuilt_grid = soup.new_tag("div")
    rebuilt_grid["class"] = "s2a-fluid s2a-fluid--components"
    rebuilt_section.append(rebuilt_grid)

    for block in fluid_root.find_all(
        lambda tag: isinstance(
            tag, Tag) and tag.name == "div" and "fe-block" in tag.get("class", []),
        recursive=False,
    ):
        block_classes = block.get("class", [])
        block_identifier = next(
            (name for name in block_classes if name.startswith("fe-block-")), None)
        block_kind = fluid_block_kind(block)
        block_html = fluid_block_content_html(block)
        if not block_html:
            continue

        rebuilt_block = soup.new_tag("div")
        rebuilt_block["class"] = f"s2a-fluid-block s2a-fluid-block--{block_kind}"
        if block_identifier:
            rebuilt_block["data-fluid-block"] = block_identifier

        layout_bits: list[str] = []
        block_layout = layout_map.get(block_identifier or "", {})
        mobile_area = block_layout.get("mobile_area")
        desktop_area = block_layout.get("desktop_area")
        z_index = block_layout.get("z_index")
        if mobile_area:
            layout_bits.append(f"--s2a-grid-area-mobile: {mobile_area};")
        if desktop_area:
            layout_bits.append(f"--s2a-grid-area-desktop: {desktop_area};")
        if z_index:
            layout_bits.append(f"--s2a-z-index: {z_index};")
        if layout_bits:
            rebuilt_block["style"] = " ".join(layout_bits)

        block_fragment = BeautifulSoup(block_html, "html.parser")
        for child in list(block_fragment.contents):
            rebuilt_block.append(child)

        rebuilt_grid.append(rebuilt_block)

    if not rebuilt_grid.contents:
        return None

    if fluid_container is not None and fluid_container.get("data-fluid-engine"):
        rebuilt_section["data-fluid-engine"] = "componentized"

    return rebuilt_section


def parse_fluid_engine_layout(section: Tag) -> dict[str, dict[str, str]]:
    layout_map: dict[str, dict[str, str]] = {}
    style_text = "\n".join(style_tag.get_text("\n", strip=True)
                           for style_tag in section.find_all("style"))
    if not style_text:
        return layout_map

    for match in FLUID_BLOCK_STYLE_PATTERN.finditer(style_text):
        block = match.group("block")
        entry = layout_map.setdefault(block, {})
        entry["mobile_area"] = normalize_grid_area(match.group("area"))
        entry["z_index"] = match.group("z").strip()

    for match in FLUID_BLOCK_DESKTOP_STYLE_PATTERN.finditer(style_text):
        block = match.group("block")
        entry = layout_map.setdefault(block, {})
        entry["desktop_area"] = normalize_grid_area(match.group("area"))
        entry["z_index"] = match.group("z").strip()

    return layout_map


def normalize_grid_area(value: str) -> str:
    return " / ".join(part.strip() for part in value.split("/"))


def fluid_block_kind(block: Tag) -> str:
    sqs_block = block.select_one(".sqs-block")
    if sqs_block is None:
        return "html"
    if "horizontalrule-block" in sqs_block.get("class", []) or sqs_block.get("data-block-type") == "47":
        return "rule"
    if sqs_block.get("data-sqsp-block") == "embed" or sqs_block.select_one("iframe") is not None:
        return "embed"
    if sqs_block.select_one("img") is not None:
        return "image"
    if sqs_block.select_one(".sqs-html-content") is not None:
        return "text"
    return "html"


def fluid_block_content_html(block: Tag) -> str:
    sqs_block = block.select_one(".sqs-block")
    if sqs_block is None:
        return ""

    if fluid_block_kind(block) == "rule":
        return "<hr />"

    if fluid_block_kind(block) == "text":
        html_content = sqs_block.select_one(".sqs-html-content")
        if html_content is None:
            return ""
        return "".join(str(child) for child in html_content.contents).strip()

    block_content = sqs_block.select_one(".sqs-block-content")
    if block_content is None:
        return ""
    return "".join(str(child) for child in block_content.contents).strip()


def rebuild_gallery_components(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    grid = soup.select_one(".portfolio-grid-basic, .grid-wrapper, .sqs-gallery-design-grid")
    if grid is None:
        return None

    items = grid.select(".grid-item, .gallery-item, .sqs-gallery-design-grid-slide")
    if not items:
        items = [child for child in grid.find_all(recursive=False) if child.find("img")]
    if len(items) < 3:
        return None

    rebuilt = BeautifulSoup("", "html.parser")
    section = rebuilt.new_tag("section")
    section["class"] = "s2a-gallery s2a-gallery--portfolio"
    gallery_grid = rebuilt.new_tag("div")
    gallery_grid["class"] = "s2a-gallery-grid"
    section.append(gallery_grid)

    for item in items:
        anchor = item if item.name == "a" and item.get("href") else item.find("a", href=True)
        image = item.find("img")
        if image is None:
            continue

        card = rebuilt.new_tag(anchor.name if anchor and anchor.name == "a" else "article")
        card["class"] = "s2a-gallery-card"
        if anchor and anchor.get("href"):
            card["href"] = anchor.get("href")

        media = rebuilt.new_tag("figure")
        media["class"] = "s2a-gallery-media"
        media_fragment = BeautifulSoup(str(image), "html.parser")
        media_image = media_fragment.find("img")
        if media_image is None:
            continue
        media.append(media_image)
        card.append(media)

        title = first_non_empty(
            item.select_one(
                ".portfolio-title") and item.select_one(".portfolio-title").get_text(" ", strip=True),
            item.select_one(
                ".image-title") and item.select_one(".image-title").get_text(" ", strip=True),
            anchor.get_text(" ", strip=True) if anchor else None,
            image.get("alt"),
        )
        caption = first_non_empty(
            item.select_one(
                ".portfolio-description") and item.select_one(".portfolio-description").get_text(" ", strip=True),
            item.select_one(
                ".image-caption") and item.select_one(".image-caption").get_text(" ", strip=True),
        )
        if title or caption:
            meta = rebuilt.new_tag("div")
            meta["class"] = "s2a-gallery-meta"
            if title:
                title_tag = rebuilt.new_tag("h2")
                title_tag["class"] = "s2a-gallery-title"
                title_tag.string = title
                meta.append(title_tag)
            if caption:
                caption_tag = rebuilt.new_tag("p")
                caption_tag["class"] = "s2a-gallery-caption"
                caption_tag.string = caption
                meta.append(caption_tag)
            card.append(meta)

        gallery_grid.append(card)

    if not gallery_grid.contents:
        return None

    rebuilt.append(section)
    return rebuilt.decode().strip()


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def should_prefer_html(
    html: str,
    *,
    fidelity_mode: str = "high",
    layout_strategy: str = "hybrid",
    markdown_first: bool = False,
) -> bool:
    soup = BeautifulSoup(html, "html.parser")

    if soup.select_one(FORCED_HTML_SELECTOR):
        return fidelity_mode != "minimal"

    if soup.select_one(STRUCTURED_CONTENT_SELECTOR):
        return fidelity_mode != "minimal"

    linked_images = 0
    for anchor in soup.find_all("a"):
        if anchor.find("img") is not None:
            linked_images += 1

    image_count = len(soup.find_all("img"))
    paragraph_count = len(soup.find_all("p"))
    heading_count = len(soup.find_all(["h1", "h2", "h3", "h4"]))

    if fidelity_mode == "minimal":
        return False

    if markdown_first and layout_strategy != "components":
        return False

    if linked_images >= 6 and image_count >= 6 and paragraph_count <= 2 and heading_count <= linked_images + 1:
        return True

    return False


def infer_content_presentation(
    html: str,
    *,
    fidelity_mode: str,
    layout_strategy: str,
) -> str:
    if fidelity_mode == "minimal":
        return "standard"

    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(STRUCTURED_CONTENT_SELECTOR) and layout_strategy in {"hybrid", "components"}:
        return "immersive"

    return "standard"


def find_home_page_snapshot(page_snapshots: list[dict]) -> dict | None:
    for page in page_snapshots:
        if route_path_for_page(page) == "/":
            return page
    return page_snapshots[0] if page_snapshots else None


def extract_tweak_value(raw_homepage_html: str, key: str) -> str | None:
    if not raw_homepage_html:
        return None

    match = re.search(rf'"{re.escape(key)}":"([^"]+)"', raw_homepage_html)
    if not match:
        return None

    value = match.group(1).strip()
    return value or None


def class_tokens(element: Tag | None) -> set[str]:
    if element is None:
        return set()

    class_attr = element.get("class", [])
    if isinstance(class_attr, str):
        return {class_attr}
    return {value for value in class_attr if value}


def header_current_styles(raw_homepage_html: str) -> dict[str, object]:
    if not raw_homepage_html:
        return {}

    soup = BeautifulSoup(raw_homepage_html, "html.parser")
    header = soup.select_one("header[data-test='header'], header#header, header")
    if header is None:
        return {}

    raw_styles = header.get("data-current-styles")
    if not raw_styles:
        return {}

    try:
        parsed = json.loads(unescape(raw_styles))
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def infer_header_style(raw_homepage_html: str, fidelity_mode: str) -> str:
    if fidelity_mode == "minimal" or not raw_homepage_html:
        return "solid"

    lowered = raw_homepage_html.lower()
    if any(marker in lowered for marker in TRANSPARENT_HEADER_MARKERS):
        return "transparent"

    return "solid"


def infer_background_style(raw_homepage_html: str, fidelity_mode: str) -> str:
    if fidelity_mode == "minimal":
        return "minimal"

    lowered = raw_homepage_html.lower()
    if any(marker in lowered for marker in ("portfolio-grid-basic", "full-bleed-section", "background-width--full-bleed")):
        return "plain"

    return "editorial"


def infer_header_width(raw_homepage_html: str, fidelity_mode: str) -> str:
    if fidelity_mode == "minimal" or not raw_homepage_html:
        return "inset"

    soup = BeautifulSoup(raw_homepage_html, "html.parser")
    body_classes = class_tokens(soup.body)
    header_inner_classes = class_tokens(soup.select_one("[data-test='header-inner']"))
    tweak_width = extract_tweak_value(raw_homepage_html, "header-width")

    if (
        "header-width-full" in body_classes
        or "container--fluid" in header_inner_classes
        or (tweak_width and tweak_width.lower() == "full")
    ):
        return "full"

    return "inset"


def infer_header_layout(raw_homepage_html: str, fidelity_mode: str) -> str:
    if fidelity_mode == "minimal" or not raw_homepage_html:
        return "stacked"

    current_styles = header_current_styles(raw_homepage_html)
    layout_value = str(current_styles.get("layout") or "").lower()
    if layout_value == "navright":
        return "nav-right"

    if "header-layout-nav-right" in raw_homepage_html:
        return "nav-right"

    return "stacked"


def infer_header_alignment(raw_homepage_html: str, fidelity_mode: str) -> str:
    if fidelity_mode == "minimal" or not raw_homepage_html:
        return "left"

    if "header-overlay-alignment-center" in raw_homepage_html.lower():
        return "center"

    return "left"


def plain_text(value: str) -> str:
    return " ".join(BeautifulSoup(value, "html.parser").stripped_strings)


def clean_title(title: str | None, site_title: str) -> str:
    if not title:
        return "Untitled"

    collapsed = " ".join(title.split())
    for separator in (" — ", " - ", " | "):
        suffix = f"{separator}{site_title}"
        if collapsed.endswith(suffix):
            return collapsed[: -len(suffix)].strip()
    return collapsed


def label_from_path(route_path: str) -> str:
    if route_path == "/":
        return "Home"
    words = route_path.strip("/").replace("-", " ").replace("/", " ")
    return words.title()


def entry_id_for_path(route_path: str, prefix: str) -> str:
    cleaned = route_path.strip("/") or "home"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", cleaned.replace("/", "--")).strip("-")
    return slug or prefix


def excerpt_text(excerpt_html: str | None) -> str | None:
    if not excerpt_html:
        return None
    value = plain_text(excerpt_html)
    return value or None


def find_page_title(page_snapshots: list[dict], route_path: str) -> str | None:
    for page in page_snapshots:
        if route_path_for_page(page) == route_path and page.get("title"):
            return page.get("title")
    return None


def find_page_description(page_snapshots: list[dict], route_path: str) -> str | None:
    for page in page_snapshots:
        if route_path_for_page(page) == route_path and page.get("meta_description"):
            return page.get("meta_description")
    return None


def infer_date_from_route(route_path: str) -> str | None:
    segments = path_segments(route_path)
    if len(segments) >= 4 and all(part.isdigit() for part in segments[1:4]):
        year, month, day = segments[1:4]
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None


def normalize_datetime_string(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def slugify_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "squarespace-migration"


def normalize_base_path(value: str) -> str:
    if not value:
        return "/"
    cleaned = "/" + value.strip("/")
    return cleaned if cleaned != "/" else "/"
