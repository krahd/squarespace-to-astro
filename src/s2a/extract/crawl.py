from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from s2a.extract.assets import extract_asset_references
from s2a.extract.json_data import extract_json_links, probe_json_data
from s2a.extract.media import build_media_manifest, extract_media_references
from s2a.files import write_json, write_text
from s2a.net import fetch_text, is_html_content_type
from s2a.normalize.models import CrawlSnapshot, PageSnapshot, SiteProbe
from s2a.url_utils import (
    canonicalize_page_url,
    file_stem_for_url,
    is_crawlable_link,
    make_absolute_url,
    same_origin,
)

ProgressCallback = Callable[[int, int, str | None], None]


def crawl_site(
    client: httpx.Client,
    probe: SiteProbe,
    output_dir: Path | str,
    max_pages: int = 50,
    progress_callback: ProgressCallback | None = None,
) -> CrawlSnapshot:
    output_root = Path(output_dir)
    crawl_warnings: list[str] = []
    queue: deque[str] = deque()
    queued: set[str] = set()
    visited: set[str] = set()
    pages: list[PageSnapshot] = []

    def enqueue(url: str) -> None:
        canonical_url = canonicalize_page_url(url)
        if canonical_url in visited or canonical_url in queued:
            return
        if len(visited) + len(queue) >= max_pages * 4:
            return
        queue.append(canonical_url)
        queued.add(canonical_url)

    for seed_url in seed_urls_from_probe(probe):
        enqueue(seed_url)

    # Supplement the deterministic seed set with feed-discovered URLs and any
    # same-origin URLs published through Squarespace JSON payloads.
    if probe.rss_feeds:
        rss_urls = extract_urls_from_rss_feeds(client, probe.rss_feeds, probe.site_origin)
        for url in rss_urls:
            enqueue(url)
        if rss_urls:
            crawl_warnings.append(
                f"Added {len(rss_urls)} URL(s) from {len(probe.rss_feeds)} RSS/Atom feed(s) as supplementary seeds."
            )

    for url in probe.json_links:
        enqueue(url)

    if progress_callback is not None:
        progress_callback(
            0, crawl_progress_total(queue, completed_pages=0, max_pages=max_pages), None
        )

    while queue and len(pages) < max_pages:
        requested_url = canonicalize_page_url(queue.popleft())
        queued.discard(requested_url)
        if requested_url in visited:
            continue
        visited.add(requested_url)

        fetch = fetch_text(client, requested_url)
        page_warnings: list[str] = []

        if fetch.error:
            pages.append(
                PageSnapshot(
                    requested_url=requested_url,
                    final_url=None,
                    status_code=None,
                    content_type=None,
                    title=None,
                    meta_description=None,
                    canonical_url=None,
                    warnings=[fetch.error],
                )
            )
            if progress_callback is not None:
                progress_callback(
                    len(pages),
                    crawl_progress_total(
                        queue, completed_pages=len(pages), max_pages=max_pages
                    ),
                    None,
                )
            continue

        final_url = canonicalize_page_url(fetch.final_url or requested_url)
        if fetch.final_url and not same_origin(final_url, probe.site_origin):
            warning = f"Final URL redirected off-origin to {final_url}."
            crawl_warnings.append(warning)
            pages.append(
                PageSnapshot(
                    requested_url=requested_url,
                    final_url=final_url,
                    status_code=fetch.status_code,
                    content_type=fetch.content_type,
                    title=None,
                    meta_description=None,
                    canonical_url=requested_url,
                    external_redirect_url=final_url,
                    warnings=[warning],
                )
            )
            if progress_callback is not None:
                progress_callback(
                    len(pages),
                    crawl_progress_total(
                        queue, completed_pages=len(pages), max_pages=max_pages
                    ),
                    None,
                )
            continue

        html_path: str | None = None
        json_path: str | None = None
        title: str | None = None
        meta_description: str | None = None
        canonical_url: str | None = None
        headings: list[str] = []
        internal_links: list[str] = []
        external_links: list[str] = []
        asset_urls: list[str] = []
        assets = []
        media = []
        unresolved_media = []
        squarespace_indicators: list[str] = []
        password_gate_detected = False
        json_probe = None
        json_payload = None

        if not is_html_content_type(fetch.content_type):
            if fetch.text:
                html_path = store_raw_html(output_root, final_url, fetch.text)
            page_warnings.append(
                "Skipped structured parsing because the response was not HTML."
            )
        elif fetch.text:
            soup = BeautifulSoup(fetch.text, "html.parser")
            title = (
                soup.title.string.strip() if soup.title and soup.title.string else None
            )
            meta_description = read_meta_description(soup)
            canonical_url = read_canonical_url(soup, final_url)
            headings = [
                heading.get_text(" ", strip=True)
                for heading in soup.find_all(["h1", "h2", "h3"])
            ]
            internal_links, external_links = extract_links(
                soup, final_url, probe.site_origin
            )
            if canonical_url and canonical_url != final_url and canonical_url in visited:
                crawl_warnings.append(
                    f"Skipped canonical duplicate page: {final_url} -> {canonical_url}"
                )
                if progress_callback is not None:
                    progress_callback(
                        len(pages),
                        crawl_progress_total(
                            queue, completed_pages=len(pages), max_pages=max_pages
                        ),
                        None,
                    )
                continue

            html_path = store_raw_html(output_root, final_url, fetch.text)
            owner_route = urlsplit(final_url).path or "/"
            assets = extract_asset_references(soup, final_url, owner_route)
            asset_urls = list(dict.fromkeys(asset.source_url for asset in assets))
            squarespace_indicators = detect_page_indicators(fetch.text, soup)
            password_gate_detected = detect_page_password_gate(soup)

            for link in internal_links:
                if link not in visited and len(visited) + len(queue) < max_pages * 4:
                    queue.append(link)

            json_probe, json_payload = probe_json_data(client, final_url)
            if json_probe.available and json_payload is not None:
                json_path = store_raw_json(output_root, final_url, json_payload)
                for url in extract_json_links(json_payload, probe.site_origin):
                    enqueue(url)

            media_result = extract_media_references(fetch.text, json_payload)
            media = media_result.references
            unresolved_media = media_result.unresolved

        pages.append(
            PageSnapshot(
                requested_url=requested_url,
                final_url=final_url,
                status_code=fetch.status_code,
                content_type=fetch.content_type,
                title=title,
                meta_description=meta_description,
                canonical_url=canonical_url,
                headings=headings,
                internal_links=internal_links,
                external_links=external_links,
                asset_urls=asset_urls,
                assets=assets,
                media=media,
                unresolved_media=unresolved_media,
                squarespace_indicators=squarespace_indicators,
                password_gate_detected=password_gate_detected,
                json_probe=json_probe,
                raw_html_path=html_path,
                raw_json_path=json_path,
                warnings=page_warnings,
            )
        )

        if progress_callback is not None:
            progress_callback(
                len(pages),
                crawl_progress_total(
                    queue, completed_pages=len(pages), max_pages=max_pages
                ),
                None,
            )

    if len(pages) >= max_pages and queue:
        crawl_warnings.append(
            f"Stopped after reaching the max-pages limit ({max_pages}); additional internal URLs remain uncrawled."
        )

    snapshot = CrawlSnapshot(
        generated_at=datetime.now(UTC).isoformat(),
        target_url=probe.target_url,
        base_url=probe.final_home_url or probe.target_url,
        probe=probe,
        pages=pages,
        warnings=crawl_warnings,
    )
    write_json(output_root / "media_manifest.json", build_media_manifest(snapshot))
    return snapshot


def crawl_progress_total(
    queue: deque[str], *, completed_pages: int, max_pages: int
) -> int:
    return max(completed_pages, min(max_pages, completed_pages + len(queue)))


def seed_urls_from_probe(probe: SiteProbe) -> list[str]:
    seeds = [probe.final_home_url or probe.target_url]
    seeds.extend(probe.sitemap_entries)
    seeds.extend(probe.homepage_links)
    return list(dict.fromkeys(seeds))


def extract_urls_from_rss_feeds(
    client: httpx.Client,
    feed_urls: list[str],
    site_origin: str,
) -> list[str]:
    """Fetch each RSS feed URL and extract ``<link>`` item URLs.

    Only URLs that belong to the same site origin are returned so the crawl
    stays scoped to the target site. Errors for individual feeds are silently
    ignored — RSS supplement is best-effort.
    """
    discovered: list[str] = []
    for feed_url in feed_urls:
        fetch = fetch_text(client, feed_url)
        if fetch.error or not fetch.text:
            continue
        try:
            root = ET.fromstring(fetch.text)
        except (ET.ParseError, DefusedXmlException):
            continue
        # Handle both RSS 2.0 (<rss>/<channel>/<item>/<link>) and Atom
        # (<feed>/<entry>/<link href=...>).
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for item in root.iter("item"):
            link_el = item.find("link")
            if link_el is not None and link_el.text:
                url = canonicalize_page_url(link_el.text.strip())
                if is_crawlable_link(url, site_origin):
                    discovered.append(url)
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            link_el = entry.find("atom:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                href = link_el.get("href", "")
                if href:
                    url = canonicalize_page_url(href)
                    if is_crawlable_link(url, site_origin):
                        discovered.append(url)
    return list(dict.fromkeys(discovered))


def store_raw_html(output_dir: Path, url: str, html: str) -> str:
    stem = file_stem_for_url(url)
    path = output_dir / "raw-html" / f"{stem}.html"
    write_text(path, html)
    return f"raw-html/{stem}.html"


def store_raw_json(output_dir: Path, url: str, payload: dict) -> str:
    stem = file_stem_for_url(url)
    path = output_dir / "raw-json" / f"{stem}.json"
    write_json(path, payload)
    return f"raw-json/{stem}.json"


def read_meta_description(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    return None


def read_canonical_url(soup: BeautifulSoup, base_url: str) -> str | None:
    link = soup.find(
        "link", attrs={"rel": lambda value: value and "canonical" in value}
    )
    if link and link.get("href"):
        return canonicalize_page_url(make_absolute_url(base_url, link["href"]))
    return None


def extract_links(
    soup: BeautifulSoup, base_url: str, site_origin: str
) -> tuple[list[str], list[str]]:
    internal_links: list[str] = []
    external_links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        absolute = make_absolute_url(base_url, anchor["href"])

        if is_crawlable_link(absolute, site_origin):
            internal_links.append(canonicalize_page_url(absolute))
        else:
            external_links.append(absolute)

    return list(dict.fromkeys(internal_links)), list(dict.fromkeys(external_links))


def detect_page_indicators(html: str, soup: BeautifulSoup) -> list[str]:
    indicators: list[str] = []
    lowered_html = html.lower()

    if "static1.squarespace.com" in lowered_html:
        indicators.append("static-assets")

    if "sqs-" in lowered_html:
        indicators.append("sqs-markup")

    generator = soup.find("meta", attrs={"name": "generator"})
    if generator and "squarespace" in generator.get("content", "").lower():
        indicators.append("meta-generator")

    return list(dict.fromkeys(indicators))


def detect_page_password_gate(soup: BeautifulSoup) -> bool:
    text = soup.get_text(" ", strip=True).lower()
    if "enter site password" in text or "password protected" in text:
        return True
    return bool(soup.find_all("input", attrs={"type": "password"}))
