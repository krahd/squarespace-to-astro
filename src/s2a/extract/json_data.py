from __future__ import annotations

import json
from typing import Any

import httpx

from s2a.net import fetch_text, is_json_content_type
from s2a.normalize.models import JsonDataProbe
from s2a.url_utils import canonicalize_page_url, is_crawlable_link, make_absolute_url, with_query_param


def build_json_data_url(url: str) -> str:
    return with_query_param(url, "format", "json-pretty")


def probe_json_data(
    client: httpx.Client, url: str
) -> tuple[JsonDataProbe, dict[str, Any] | None]:
    json_url = build_json_data_url(url)
    fetch = fetch_text(client, json_url)

    if fetch.error:
        return (
            JsonDataProbe(
                source_url=url,
                json_url=json_url,
                attempted=True,
                available=False,
                status_code=None,
                top_level_keys=[],
                error=fetch.error,
            ),
            None,
        )

    if fetch.status_code != 200 or not fetch.text:
        return (
            JsonDataProbe(
                source_url=url,
                json_url=json_url,
                attempted=True,
                available=False,
                status_code=fetch.status_code,
                top_level_keys=[],
                error=None,
            ),
            None,
        )

    if not is_json_content_type(
        fetch.content_type
    ) and not fetch.text.lstrip().startswith("{"):
        return (
            JsonDataProbe(
                source_url=url,
                json_url=json_url,
                attempted=True,
                available=False,
                status_code=fetch.status_code,
                top_level_keys=[],
                error="Response was not JSON.",
            ),
            None,
        )

    try:
        parsed = json.loads(fetch.text)
    except json.JSONDecodeError as exc:
        return (
            JsonDataProbe(
                source_url=url,
                json_url=json_url,
                attempted=True,
                available=False,
                status_code=fetch.status_code,
                top_level_keys=[],
                error=f"Invalid JSON: {exc}",
            ),
            None,
        )

    keys = sorted(parsed.keys()) if isinstance(parsed, dict) else []
    return (
        JsonDataProbe(
            source_url=url,
            json_url=json_url,
            attempted=True,
            available=True,
            status_code=fetch.status_code,
            top_level_keys=keys,
            error=None,
        ),
        parsed if isinstance(parsed, dict) else None,
    )


def extract_json_links(payload: Any, site_origin: str) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()
    base_url = site_origin if site_origin.endswith("/") else f"{site_origin}/"

    def add_candidate(raw_value: Any) -> None:
        if not isinstance(raw_value, str):
            if isinstance(raw_value, list):
                for item in raw_value:
                    add_candidate(item)
            elif isinstance(raw_value, dict):
                for nested_value in raw_value.values():
                    add_candidate(nested_value)
            return

        candidate = raw_value.strip()
        if not candidate or candidate.startswith("#"):
            return
        if not candidate.startswith(("http://", "https://", "/")) and "/" not in candidate:
            return

        absolute = make_absolute_url(base_url, candidate)
        canonical = canonicalize_page_url(absolute)
        if not is_crawlable_link(canonical, site_origin) or canonical in seen:
            return

        seen.add(canonical)
        discovered.append(canonical)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if lowered in {"fullurl", "href", "url", "link", "canonicalurl"} or lowered.endswith(
                    ("url", "href", "link")
                ):
                    add_candidate(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return discovered
