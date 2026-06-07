from __future__ import annotations

import json
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from s2a.files import read_json, write_json
from s2a.generate.astro import generate_astro_project
from s2a.probe import probe_site
from s2a.extract.crawl import crawl_site

PROJECTS: list[tuple[str, str]] = [
    ("Montevideo, 1983", "montevideo-1983"),
    ("Hommage Numérique", "hommage-numerique"),
    ("Abandoned Future", "abandoned-future"),
    ("Ave Imperator", "ave-imperator"),
    (
        "The cruel continuity of American foreign policy as shown in the Harris - Trump debate",
        "debate-trump-harris",
    ),
    ("Be Water", "be-water"),
    ("Memoirs of the Blind", "memoirs-of-the-blind"),
    ("Extraordinary Accident", "extraordinary-accident"),
    ("Smile", "smile"),
    ("Ekphrasis", "ekphrasis"),
    ("DOOR and BOX", "door-box"),
    ("The Blind Spot", "the-blind-spot"),
    ("Brain Portraits", "brain-portraits"),
    ("Estudio Generativo #3", "estudio-generativo-3"),
    ("HOMS", "homs"),
    ("Awkward Consequence", "awkward-consequence"),
    ("Walrus", "walrus"),
    ("Improvisatio", "improvisatio"),
    ("Barcelona", "barcelona"),
    ("Celebra", "celebra"),
    ("Nibia", "nibia"),
    ("Foreign helpers", "foreign-helpers"),
    ("Two Systems", "two-systems"),
    ("Face Study", "face-study"),
    ("Poem Race", "poem-race"),
    ("5500", "5500"),
    ("NEXO", "nexo"),
    ("Facing Interaction", "facing-interaction"),
    ("Critical Point", "critical-point"),
    ("TedX", "tedx"),
    ("Lituania Lituania", "lituania-lituania"),
    ("Ribbons", "ribbons"),
    ("Trace Pavilion", "trace-pavilion"),
    ("Creative Coding", "creative-coding"),
]

HOME_URL = "https://laurenzo.net/"
PROJECT_URLS = [f"https://laurenzo.net/projects/{slug}" for _title, slug in PROJECTS]
PROJECT_ROUTE_SET = {f"/projects/{slug}" for _title, slug in PROJECTS}
EXPECTED_INTERNAL_ROUTES = {"/", "/texts", "/about", "/contact", *PROJECT_ROUTE_SET}
REDIRECT_ROUTE = "https://laurenzo.net/projects/abandoned-future"
REDIRECT_TARGET = "https://tomas-laurenzo.carrd.co/"


def _raw_fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "laurenzo-current" / "raw-html"


def _read_fixture_html(name: str) -> str:
    return (_raw_fixture_dir() / name).read_text(encoding="utf-8")


def _html_response(html: str, url: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=html.encode("utf-8"),
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", url),
    )


def _json_response(payload: dict, url: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json; charset=utf-8"},
        request=httpx.Request("GET", url),
    )


def _xml_response(content: str, url: str, content_type: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=content.encode("utf-8"),
        headers={"content-type": content_type},
        request=httpx.Request("GET", url),
    )


def _redirect_response(url: str, location: str) -> httpx.Response:
    return httpx.Response(
        302,
        headers={"location": location},
        request=httpx.Request("GET", url),
    )


def _project_json_payload(slug: str) -> dict:
    index = next(i for i, (_title, current_slug) in enumerate(PROJECTS) if current_slug == slug)
    prev_title, prev_slug = PROJECTS[index - 1 if index > 0 else len(PROJECTS) - 1]
    next_title, next_slug = PROJECTS[(index + 1) % len(PROJECTS)]
    title = next(title for title, current_slug in PROJECTS if current_slug == slug)

    return {
        "collection": {"fullUrl": "/", "title": "Projects"},
        "item": {"fullUrl": f"/projects/{slug}", "title": title},
        "pagination": {
            "prevItem": {"fullUrl": f"/projects/{prev_slug}", "title": prev_title},
            "nextItem": {"fullUrl": f"/projects/{next_slug}", "title": next_title},
        },
    }


def _home_json_payload() -> dict:
    return {
        "collection": {"fullUrl": "/", "title": "Projects"},
        "items": [
            {"fullUrl": "/"},
            *[
                {"fullUrl": f"/projects/{slug}", "title": title}
                for title, slug in PROJECTS
            ],
        ],
    }


def _sitemap_xml() -> str:
    urls = [
        HOME_URL,
        "https://laurenzo.net/projects",
        "https://laurenzo.net/texts",
        "https://laurenzo.net/about",
        "https://laurenzo.net/contact",
        *PROJECT_URLS,
    ]
    entries = "\n".join(f"  <url><loc>{url}</loc></url>" for url in urls)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def _rss_xml() -> str:
    items = "\n".join(
        f"    <item><title>{title}</title><link>{HOME_URL}projects/{slug}</link></item>"
        for title, slug in PROJECTS[:5]
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<rss version=\"2.0\">\n"
        "  <channel>\n"
        "    <title>Tomas Laurenzo</title>\n"
        f"{items}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def _make_handler() -> Callable[[httpx.Request], httpx.Response]:
    home_html = _read_fixture_html("index.html")
    texts_html = _read_fixture_html("texts.html")
    about_html = _read_fixture_html("about.html")
    contact_html = _read_fixture_html("contact.html")
    generic_html = _read_fixture_html("projects__generic.html")
    special_html = {
        "montevideo-1983": _read_fixture_html("projects__montevideo-1983.html"),
        "hommage-numerique": _read_fixture_html("projects__hommage-numerique.html"),
        "ave-imperator": _read_fixture_html("projects__ave-imperator.html"),
        "debate-trump-harris": _read_fixture_html("projects__debate-trump-harris.html"),
        "memoirs-of-the-blind": _read_fixture_html("projects__memoirs-of-the-blind.html"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        path = urlsplit(url).path
        query = urlsplit(url).query

        if url == HOME_URL:
            return _html_response(home_html, url)
        if url == f"{HOME_URL}projects":
            return _html_response(home_html, url)
        if url == f"{HOME_URL}texts":
            return _html_response(texts_html, url)
        if url == f"{HOME_URL}about":
            return _html_response(about_html, url)
        if url == f"{HOME_URL}contact":
            return _html_response(contact_html, url)
        if url == f"{HOME_URL}robots.txt":
            return _xml_response(
                "User-agent: *\nSitemap: https://laurenzo.net/sitemap.xml\n",
                url,
                "text/plain; charset=utf-8",
            )
        if url == f"{HOME_URL}sitemap.xml":
            return _xml_response(
                _sitemap_xml(), url, "application/xml; charset=utf-8"
            )
        if url == f"{HOME_URL}feed.xml":
            return _xml_response(_rss_xml(), url, "application/rss+xml; charset=utf-8")
        if query == "format=json-pretty":
            if path in {"", "/"}:
                return _json_response(_home_json_payload(), url)
            if path.startswith("/projects/"):
                slug = path.rsplit("/", 1)[-1]
                if slug != "abandoned-future":
                    return _json_response(_project_json_payload(slug), url)
            return httpx.Response(
                404,
                content=b"",
                headers={"content-type": "text/plain; charset=utf-8"},
                request=request,
            )
        if url == REDIRECT_ROUTE:
            return _redirect_response(url, REDIRECT_TARGET)
        if url == REDIRECT_TARGET:
            return _html_response(
                "<!doctype html><html><body><main><article><h1>External destination</h1></article></main></body></html>",
                url,
            )
        if path.startswith("/projects/"):
            slug = path.rsplit("/", 1)[-1]
            html = special_html.get(slug, generic_html)
            if slug == "abandoned-future":
                return _redirect_response(url, REDIRECT_TARGET)
            return _html_response(html, url)

        raise AssertionError(f"Unexpected request: {url}")

    return handler


def test_laurenzo_route_coverage(tmp_path: Path) -> None:
    home_html = _read_fixture_html("index.html")
    soup = BeautifulSoup(home_html, "html.parser")
    grid_cards = soup.select("a.grid-item[href]")

    assert len(grid_cards) == 34
    assert [card.get_text(" ", strip=True) for card in grid_cards] == [
        title for title, _slug in PROJECTS
    ]

    with httpx.Client(
        transport=httpx.MockTransport(_make_handler()), follow_redirects=True
    ) as client:
        probe = probe_site(client, HOME_URL)
        project_links = [url for url in probe.homepage_links if "/projects/" in url]
        assert len(project_links) == 34
        assert set(project_links) == set(PROJECT_URLS)
        assert probe.rss_feeds == [f"{HOME_URL}feed.xml"]
        assert probe.json_links == [HOME_URL, *PROJECT_URLS]
        assert "https://laurenzo.net/projects" in probe.sitemap_entries

        snapshot = crawl_site(client, probe, tmp_path / "crawl", max_pages=200)

    route_paths = {
        urlsplit(page.requested_url).path or "/" for page in snapshot.pages
    }
    assert len(snapshot.pages) == len(EXPECTED_INTERNAL_ROUTES)
    assert "/projects" not in route_paths
    assert route_paths == EXPECTED_INTERNAL_ROUTES

    redirected = next(
        page for page in snapshot.pages if page.requested_url == REDIRECT_ROUTE
    )
    assert redirected.final_url == REDIRECT_TARGET
    assert redirected.external_redirect_url == REDIRECT_TARGET
    assert redirected.raw_html_path is None
    assert redirected.raw_json_path is None
    assert any("redirected off-origin" in warning for warning in redirected.warnings)

    snapshot_path = tmp_path / "crawl" / "site_snapshot.json"
    write_json(snapshot_path, snapshot)

    output_dir = tmp_path / "astro"
    result = generate_astro_project(snapshot_path, output_dir, site_url=HOME_URL)
    manifest = read_json(output_dir / "migration-manifest.json")
    manifest_pages = {page["route_path"]: page for page in manifest["pages"]}

    assert result.pages_written == len(EXPECTED_INTERNAL_ROUTES)
    assert set(manifest_pages) == EXPECTED_INTERNAL_ROUTES
    assert "/projects" not in manifest_pages
    assert "https://tomas-laurenzo.carrd.co/" in manifest_pages[
        "/projects/abandoned-future"
    ]["body"]
    assert "/projects/abandoned-future" in manifest_pages[
        "/projects/hommage-numerique"
    ]["body"]
    assert "/projects/debate-trump-harris" in manifest_pages[
        "/projects/ave-imperator"
    ]["body"]
