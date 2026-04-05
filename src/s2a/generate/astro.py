from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
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


def generate_astro_project(
    snapshot_path: Path,
    output_dir: Path,
    xml_import_path: Path | None = None,
    site_url: str | None = None,
    base_path: str | None = None,
    project_name: str | None = None,
) -> AstroGenerationResult:
    snapshot = read_json(snapshot_path)
    xml_import = read_json(xml_import_path) if xml_import_path else None

    manifest = build_astro_manifest(snapshot, snapshot_path.parent, xml_import)
    if site_url:
        manifest.base_url = site_url.rstrip("/")

    write_project(output_dir, manifest, base_path=base_path, project_name=project_name)
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

    pages = build_page_entries(page_snapshots, snapshot_root, xml_items, blog_base_path, site_title)
    posts = build_post_entries(page_snapshots, snapshot_root, xml_items, blog_base_path, site_title)
    navigation = build_navigation(snapshot, page_snapshots, pages, posts,
                                  blog_base_path, blog_title, site_title)
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

    return AstroManifest(
        generated_at=datetime.now(UTC).isoformat(),
        site_title=site_title,
        site_description=site_description,
        base_url=base_url,
        blog_base_path=blog_base_path,
        blog_title=blog_title,
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

        entry = generated_entry_from_snapshot(page, snapshot_root, route_path, site_title)
        xml_page = xml_pages.pop(route_path, None)
        if xml_page and xml_page.get("content_html"):
            body, body_format = body_from_html(xml_page.get("content_html"))
            entry = replace(
                entry,
                title=clean_title(xml_page.get("title") or entry.title, site_title),
                description=excerpt_text(xml_page.get("excerpt_html")) or entry.description,
                source_url=xml_page.get("link") or entry.source_url,
                canonical_url=xml_page.get("link") or entry.canonical_url,
                body=body,
                body_format=body_format,
            )
        entries[route_path] = entry

    for route_path, xml_page in xml_pages.items():
        if is_utility_route(route_path):
            continue
        if route_path == blog_base_path and posts_exist:
            continue
        if is_post_path(route_path, blog_base_path):
            continue
        entries[route_path] = generated_entry_from_xml_item(xml_page, route_path, site_title)

    ordered = sorted(entries.values(), key=lambda entry: (not entry.home, entry.route_path))
    return ordered


def build_post_entries(
    page_snapshots: list[dict],
    snapshot_root: Path,
    xml_items: list[dict],
    blog_base_path: str,
    site_title: str,
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
            xml_item, route_path, blog_base_path, site_title)

    for page in page_snapshots:
        route_path = route_path_for_page(page)
        if is_utility_route(route_path):
            continue
        if not is_post_path(route_path, blog_base_path):
            continue
        if route_path in entries:
            continue
        entries[route_path] = generated_post_from_snapshot(
            page, snapshot_root, route_path, blog_base_path, site_title)

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
) -> GeneratedContentEntry:
    html_fragment = html_from_snapshot(page, snapshot_root)
    body, body_format = body_from_html(html_fragment)
    title = clean_title(page.get("title") or label_from_path(route_path), site_title)
    source_url = page.get("final_url") or page.get("requested_url")
    description = page.get("meta_description")

    if not body:
        body = f"# {title}\n\nThis page was discovered during migration, but the crawler could not extract a clean body automatically."
        body_format = "markdown"

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
        home=route_path == "/",
    )


def generated_entry_from_xml_item(xml_item: dict, route_path: str, site_title: str) -> GeneratedContentEntry:
    body, body_format = body_from_html(xml_item.get(
        "content_html") or xml_item.get("excerpt_html") or "")
    title = clean_title(xml_item.get("title") or label_from_path(route_path), site_title)

    if not body:
        body = f"# {title}\n"
        body_format = "markdown"

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
        home=route_path == "/",
    )


def generated_post_from_snapshot(
    page: dict,
    snapshot_root: Path,
    route_path: str,
    blog_base_path: str,
    site_title: str,
) -> GeneratedContentEntry:
    html_fragment = html_from_snapshot(page, snapshot_root)
    body, body_format = body_from_html(html_fragment)
    title = clean_title(page.get("title") or label_from_path(route_path), site_title)
    source_url = page.get("final_url") or page.get("requested_url")
    published_at = infer_date_from_route(route_path)

    if not body:
        body = f"# {title}\n\nThis post was discovered during migration, but its body could not be converted cleanly."
        body_format = "markdown"

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
        published_at=published_at,
    )


def generated_post_from_xml_item(
    xml_item: dict,
    route_path: str,
    blog_base_path: str,
    site_title: str,
) -> GeneratedContentEntry:
    body, body_format = body_from_html(xml_item.get(
        "content_html") or xml_item.get("excerpt_html") or "")
    title = clean_title(xml_item.get("title") or label_from_path(route_path), site_title)

    if not body:
        body = f"# {title}\n"
        body_format = "markdown"

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
        published_at=normalize_datetime_string(xml_item.get("published_at")),
        categories=list(dict.fromkeys(xml_item.get("categories", []))),
        tags=list(dict.fromkeys(xml_item.get("tags", []))),
    )


def build_navigation(
    snapshot: dict,
    page_snapshots: list[dict],
    pages: list[GeneratedContentEntry],
    posts: list[GeneratedContentEntry],
    blog_base_path: str,
    blog_title: str,
    site_title: str,
) -> list[GeneratedNavigationItem]:
    page_titles = {
        page.route_path: page.title for page in pages
    }
    snapshot_titles = {
        route_path_for_page(page): clean_title(page.get("title") or label_from_path(route_path_for_page(page)), site_title)
        for page in page_snapshots
    }

    navigation: list[GeneratedNavigationItem] = []
    seen: set[str] = set()
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
        navigation.insert(0, GeneratedNavigationItem(title="Home", url="/"))
        seen.add("/")

    for page in pages:
        if page.home or page.route_path in seen:
            continue
        navigation.append(GeneratedNavigationItem(title=page.title, url=page.route_path))
        seen.add(page.route_path)

    if posts and blog_base_path not in seen:
        navigation.append(GeneratedNavigationItem(title=blog_title, url=blog_base_path))

    return navigation


def write_project(
    output_dir: Path,
    manifest: AstroManifest,
    base_path: str | None,
    project_name: str | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "package.json", render_package_json(manifest, project_name))
    write_text(output_dir / "astro.config.mjs", render_astro_config(manifest, base_path))
    write_text(output_dir / "tsconfig.json", render_tsconfig())
    write_text(output_dir / "src/content.config.ts", render_content_config())
    write_text(output_dir / "src/layouts/BaseLayout.astro", render_base_layout())
    write_text(output_dir / "src/utils/routing.ts", render_routing_util())
    write_text(output_dir / "src/styles/site.css", render_site_css())
    write_json(output_dir / "src/data/site.json", render_site_data(manifest))
    write_text(output_dir / "src/pages/index.astro", render_home_page())
    write_text(output_dir / "src/pages/[...slug].astro", render_generic_page())

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


def render_content_config() -> str:
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
  <body>
    <div class="ambient-glow ambient-glow--top"></div>
    <div class="ambient-glow ambient-glow--bottom"></div>
    <div class="page-shell">
      <header class="site-header surface">
        <a class="brand" href={withBase('/')}>{site.title}</a>
        <nav class="site-nav" aria-label="Primary">
          {site.navigation.map((item: NavItem) => (
            <a
              class:list={['nav-link', currentPath === item.url && 'is-active']}
              href={item.external ? item.url : withBase(item.url)}
            >
              {item.title}
            </a>
          ))}
        </nav>
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
  --bg: #f5efe1;
  --bg-deep: #e8dfc8;
  --ink: #1f241f;
  --muted: #5f635c;
  --accent: #a8502d;
  --accent-soft: #e8b596;
  --surface: rgba(255, 250, 240, 0.76);
  --surface-border: rgba(53, 44, 37, 0.12);
  --shadow: 0 16px 40px rgba(43, 33, 25, 0.12);
  --radius-lg: 28px;
  --radius-md: 18px;
  --content-width: 78rem;
}

* {
  box-sizing: border-box;
}

html {
  background:
    radial-gradient(circle at top left, rgba(168, 80, 45, 0.14), transparent 24%),
    radial-gradient(circle at bottom right, rgba(53, 112, 89, 0.14), transparent 28%),
    linear-gradient(180deg, var(--bg) 0%, #f9f4eb 100%);
  color: var(--ink);
  font-family: 'Manrope', system-ui, sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
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

.page-shell {
  position: relative;
  z-index: 1;
  width: min(calc(100% - 2rem), var(--content-width));
  margin: 0 auto;
  padding: 1.25rem 0 4rem;
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
  gap: 1rem;
  padding: 1rem 1.25rem;
  margin: 0 auto 1.5rem;
}

.brand {
  font-family: 'Fraunces', serif;
  font-size: clamp(1.2rem, 2vw, 1.6rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  text-decoration: none;
}

.site-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 0.9rem;
  border-radius: 999px;
  text-decoration: none;
  color: var(--muted);
  transition: background 180ms ease, color 180ms ease, transform 180ms ease;
}

.nav-link:hover,
.nav-link.is-active {
  background: rgba(168, 80, 45, 0.1);
  color: var(--ink);
  transform: translateY(-1px);
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
  padding: 1rem 1.25rem;
  margin-top: 2rem;
  color: var(--muted);
  font-size: 0.95rem;
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
  color: var(--accent);
}

.page-title,
.article-title {
  margin: 0;
  font-family: 'Fraunces', serif;
  font-size: clamp(2.3rem, 6vw, 4rem);
  letter-spacing: -0.04em;
  line-height: 0.95;
}

.page-description,
.article-description {
  margin: 0;
  max-width: 42rem;
  color: var(--muted);
  font-size: 1.05rem;
}

.surface--hero,
.surface--article,
.surface--listing {
  padding: clamp(1.25rem, 2vw, 2rem);
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
  background: rgba(255, 255, 255, 0.54);
  border: 1px solid rgba(53, 44, 37, 0.08);
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
  background: rgba(168, 80, 45, 0.1);
}

.prose {
  font-size: 1.04rem;
  line-height: 1.8;
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
  color: #272d27;
}

.prose img {
  width: 100%;
  height: auto;
  border-radius: calc(var(--radius-md) - 4px);
}

.prose blockquote {
  margin: 1.5rem 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--accent);
  background: rgba(168, 80, 45, 0.08);
}

.prose code {
  font-size: 0.92em;
  background: rgba(31, 36, 31, 0.08);
  padding: 0.1rem 0.3rem;
  border-radius: 6px;
}

@media (max-width: 720px) {
  .page-shell {
    width: min(calc(100% - 1rem), var(--content-width));
    padding-top: 0.75rem;
  }

  .site-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .site-footer {
    flex-direction: column;
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
---

<BaseLayout title={home.data.title || site.title} description={home.data.description || site.description} currentPath="/">
  <article class="surface surface--hero prose">
    <Content />
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
---

<BaseLayout title={entry.data.title} description={entry.data.description} currentPath={entry.data.routePath}>
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
---

<BaseLayout title={entry.data.title} description={entry.data.description} currentPath={entry.data.routePath}>
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


def html_from_snapshot(page: dict, snapshot_root: Path) -> str:
    relative_path = page.get("raw_html_path")
    if not relative_path:
        return ""

    full_path = snapshot_root / relative_path
    if not full_path.exists():
        return ""

    html = full_path.read_text(encoding="utf-8")
    return extract_main_html(html)


def extract_main_html(html: str) -> str:
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
        remove_noise(fragment)
        text_length = len(" ".join(fragment.stripped_strings))
        if text_length >= 80 or candidate == soup.body:
            return fragment.decode().strip()

    return ""


def remove_noise(fragment: BeautifulSoup) -> None:
    for selector in (
        "script",
        "style",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
        "iframe",
        "svg",
    ):
        for element in fragment.select(selector):
            element.decompose()

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


def body_from_html(html: str) -> tuple[str, str]:
    if not html:
        return "", "markdown"

    cleaned_html = html.strip()
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
        return cleaned_html, "html"

    if len(text_markdown) < max(40, int(len(text_html) * 0.35)):
        return cleaned_html, "html"

    return markdown, "markdown"


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
