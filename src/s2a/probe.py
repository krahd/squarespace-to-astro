from __future__ import annotations

from collections import deque
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from s2a.extract.json_data import probe_json_data
from s2a.net import fetch_text, is_html_content_type
from s2a.normalize.models import SiteProbe
from s2a.url_utils import (
    canonicalize_page_url,
    coerce_url,
    is_crawlable_link,
    make_absolute_url,
    origin_for,
)


def probe_site(client: httpx.Client, target_url: str, max_sitemap_urls: int = 200) -> SiteProbe:
    target_url = coerce_url(target_url)
    home_fetch = fetch_text(client, target_url)
    final_home_url = home_fetch.final_url or target_url
    site_origin = origin_for(final_home_url)
    warnings: list[str] = []

    squarespace_indicators: list[str] = []
    version_hint: str | None = None
    homepage_title: str | None = None
    password_gate_detected = False
    homepage_links: list[str] = []
    rss_feeds: list[str] = []

    if home_fetch.error:
        warnings.append(f"Homepage fetch failed: {home_fetch.error}")
    elif home_fetch.status_code and home_fetch.status_code >= 400:
        warnings.append(f"Homepage returned HTTP {home_fetch.status_code}.")

    if home_fetch.text and is_html_content_type(home_fetch.content_type):
        soup = BeautifulSoup(home_fetch.text, "html.parser")
        squarespace_indicators = detect_squarespace_indicators(
            home_fetch.text, home_fetch.headers, soup)
        version_hint = detect_version_hint(home_fetch.text)
        password_gate_detected = detect_password_gate(soup)
        homepage_title = soup.title.string.strip() if soup.title and soup.title.string else None
        homepage_links = extract_internal_links(soup, final_home_url, site_origin)
        rss_feeds = extract_rss_feeds(soup, final_home_url)
    elif home_fetch.text:
        warnings.append("Homepage did not appear to be HTML; extraction signals may be incomplete.")

    json_probe, _ = probe_json_data(client, final_home_url)
    robots_url, robots_status_code, robots_disallow_all, robots_sitemaps, robots_warnings = fetch_robots(
        client, site_origin
    )
    warnings.extend(robots_warnings)

    sitemap_url = robots_sitemaps[0] if robots_sitemaps else f"{site_origin}/sitemap.xml"
    sitemap_status_code, sitemap_entries, sitemap_warnings = fetch_sitemap_urls(
        client, sitemap_url, max_urls=max_sitemap_urls
    )
    warnings.extend(sitemap_warnings)

    probably_squarespace = bool(squarespace_indicators)
    if not probably_squarespace:
        warnings.append("Squarespace markers were not strongly detected on the homepage.")

    if version_hint is None and probably_squarespace:
        warnings.append(
            "Squarespace was detected, but the site version could not be inferred reliably.")

    return SiteProbe(
        target_url=target_url,
        final_home_url=final_home_url,
        site_origin=site_origin,
        homepage_status_code=home_fetch.status_code,
        homepage_title=homepage_title,
        probably_squarespace=probably_squarespace,
        squarespace_indicators=squarespace_indicators,
        version_hint=version_hint,
        password_gate_detected=password_gate_detected,
        json_probe=json_probe,
        robots_url=robots_url,
        robots_status_code=robots_status_code,
        robots_disallow_all=robots_disallow_all,
        robots_sitemaps=robots_sitemaps,
        sitemap_url=sitemap_url,
        sitemap_status_code=sitemap_status_code,
        sitemap_entries=sitemap_entries,
        homepage_links=homepage_links,
        rss_feeds=rss_feeds,
        warnings=list(dict.fromkeys(warnings)),
    )


def detect_squarespace_indicators(
    html: str, headers: dict[str, str], soup: BeautifulSoup
) -> list[str]:
    indicators: list[str] = []
    lowered_html = html.lower()

    generator = soup.find("meta", attrs={"name": "generator"})
    if generator and "squarespace" in generator.get("content", "").lower():
        indicators.append("meta-generator")

    if "static1.squarespace.com" in lowered_html or "static.squarespace.com" in lowered_html:
        indicators.append("static-assets")

    if "squarespace-cdn.com" in lowered_html:
        indicators.append("cdn-assets")

    if "sqs-" in lowered_html:
        indicators.append("sqs-markup")

    server_header = headers.get("server", "")
    if "squarespace" in server_header.lower():
        indicators.append("server-header")

    return list(dict.fromkeys(indicators))


def detect_version_hint(html: str) -> str | None:
    lowered_html = html.lower()

    if "data-fluid-engine" in lowered_html or "fluid-engine" in lowered_html:
        return "7.1"

    if "sqs-block" in lowered_html or "static1.squarespace.com" in lowered_html:
        return "7.x"

    if "squarespace 5" in lowered_html:
        return "5"

    return None


def detect_password_gate(soup: BeautifulSoup) -> bool:
    text = soup.get_text(" ", strip=True).lower()

    if "enter site password" in text or "password protected" in text:
        return True

    password_inputs = soup.find_all("input", attrs={"type": "password"})
    return bool(password_inputs)


def extract_internal_links(soup: BeautifulSoup, base_url: str, site_origin: str) -> list[str]:
    discovered: list[str] = []

    for anchor in soup.find_all("a", href=True):
        absolute = make_absolute_url(base_url, anchor["href"])
        if is_crawlable_link(absolute, site_origin):
            discovered.append(canonicalize_page_url(absolute))

    return list(dict.fromkeys(discovered))


def extract_rss_feeds(soup: BeautifulSoup, base_url: str) -> list[str]:
    feeds: list[str] = []

    for link in soup.find_all("link", href=True):
        rel = {value.lower() for value in link.get("rel", [])}
        link_type = link.get("type", "").lower()
        if "alternate" in rel and "rss" in link_type:
            feeds.append(make_absolute_url(base_url, link["href"]))

    return list(dict.fromkeys(feeds))


def fetch_robots(
    client: httpx.Client, site_origin: str
) -> tuple[str, int | None, bool, list[str], list[str]]:
    robots_url = f"{site_origin}/robots.txt"
    fetch = fetch_text(client, robots_url)
    warnings: list[str] = []

    if fetch.error:
        warnings.append(f"robots.txt fetch failed: {fetch.error}")
        return robots_url, None, False, [], warnings

    if fetch.status_code != 200 or not fetch.text:
        return robots_url, fetch.status_code, False, [], warnings

    disallow_all = False
    sitemaps: list[str] = []

    for raw_line in fetch.text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith("disallow:"):
            value = line.split(":", 1)[1].strip()
            if value == "/":
                disallow_all = True
        elif lowered.startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())

    return robots_url, fetch.status_code, disallow_all, list(dict.fromkeys(sitemaps)), warnings


def fetch_sitemap_urls(
    client: httpx.Client, sitemap_url: str, max_urls: int
) -> tuple[int | None, list[str], list[str]]:
    queue = deque([sitemap_url])
    visited: set[str] = set()
    collected_urls: list[str] = []
    warnings: list[str] = []
    root_status: int | None = None

    while queue and len(collected_urls) < max_urls:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        fetch = fetch_text(client, current_url)
        if current_url == sitemap_url:
            root_status = fetch.status_code

        if fetch.error:
            warnings.append(f"Sitemap fetch failed for {current_url}: {fetch.error}")
            continue

        if fetch.status_code != 200 or not fetch.text:
            continue

        try:
            root = ET.fromstring(fetch.text)
        except ET.ParseError as exc:
            warnings.append(f"Could not parse sitemap XML from {current_url}: {exc}")
            continue

        tag_name = strip_namespace(root.tag)
        if tag_name == "sitemapindex":
            locations = [
                element.text.strip()
                for element in root.findall("./{*}sitemap/{*}loc")
                if element.text
            ]
            for location in locations:
                if location not in visited:
                    queue.append(location)
            continue

        if tag_name != "urlset":
            warnings.append(f"Unexpected sitemap root element '{tag_name}' from {current_url}.")
            continue

        locations = [
            element.text.strip()
            for element in root.findall("./{*}url/{*}loc")
            if element.text
        ]
        for location in locations:
            collected_urls.append(canonicalize_page_url(location))
            if len(collected_urls) >= max_urls:
                break

    deduped_urls = list(dict.fromkeys(collected_urls))
    return root_status, deduped_urls, list(dict.fromkeys(warnings))


def strip_namespace(tag_name: str) -> str:
    return tag_name.rsplit("}", 1)[-1]
