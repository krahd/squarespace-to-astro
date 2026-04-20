from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from s2a import __version__


DEFAULT_HEADERS = {
    "User-Agent": f"squarespace-to-astro/{__version__} (+https://github.com/krahd/squarespace-to-astro)"
}


@dataclass(slots=True)
class TextFetch:
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    text: str | None
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def build_client(timeout: float, verify: bool = True) -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
        timeout=httpx.Timeout(timeout),
        verify=verify,
    )


def fetch_text(client: httpx.Client, url: str) -> TextFetch:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return TextFetch(
            requested_url=url,
            final_url=None,
            status_code=None,
            content_type=None,
            text=None,
            error=str(exc),
        )

    return TextFetch(
        requested_url=url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        text=response.text,
        headers=dict(response.headers),
    )


def is_html_content_type(content_type: str | None) -> bool:
    if not content_type:
        return True
    return "text/html" in content_type.lower() or "application/xhtml+xml" in content_type.lower()


def is_json_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    lowered = content_type.lower()
    return "application/json" in lowered or lowered.endswith("+json") or "text/json" in lowered
