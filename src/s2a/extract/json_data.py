from __future__ import annotations

import json
from typing import Any

import httpx

from s2a.net import fetch_text, is_json_content_type
from s2a.normalize.models import JsonDataProbe
from s2a.url_utils import with_query_param


def build_json_data_url(url: str) -> str:
    return with_query_param(url, "format", "json-pretty")


def probe_json_data(client: httpx.Client, url: str) -> tuple[JsonDataProbe, dict[str, Any] | None]:
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

    if not is_json_content_type(fetch.content_type) and not fetch.text.lstrip().startswith("{"):
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
