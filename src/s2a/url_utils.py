from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


NON_HTML_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".xml",
    ".rss",
    ".json",
    ".js",
    ".css",
    ".map",
    ".txt",
    ".mp4",
    ".mp3",
    ".mov",
    ".wav",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


def coerce_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    parts = urlsplit(value)
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def origin_for(url: str) -> str:
    parts = urlsplit(coerce_url(url))
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def canonicalize_page_url(url: str) -> str:
    parts = urlsplit(coerce_url(url))
    path = parts.path or "/"

    if path != "/" and path.endswith("/"):
        path = path[:-1]

    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def same_origin(left: str, right: str) -> bool:
    left_parts = urlsplit(coerce_url(left))
    right_parts = urlsplit(coerce_url(right))
    return (left_parts.scheme, left_parts.netloc) == (right_parts.scheme, right_parts.netloc)


def make_absolute_url(base_url: str, candidate: str) -> str:
    return urljoin(base_url, candidate)


def is_crawlable_link(url: str, site_origin: str) -> bool:
    parts = urlsplit(url)

    if parts.scheme in {"mailto", "tel", "javascript"}:
        return False

    if not same_origin(url, site_origin):
        return False

    lowered_path = (parts.path or "/").lower()
    for suffix in NON_HTML_SUFFIXES:
        if lowered_path.endswith(suffix):
            return False

    return True


def with_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(coerce_url(url))
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def file_stem_for_url(url: str) -> str:
    parts = urlsplit(canonicalize_page_url(url))
    path = parts.path.strip("/") or "index"
    combined = path.replace("/", "__")
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", combined)
