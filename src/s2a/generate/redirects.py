from __future__ import annotations

from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from s2a.files import write_json, write_text


def build_redirects_from_manifest(manifest: dict) -> list[dict]:
    """Build a simple list of redirects from a migration manifest dict.

    Each redirect maps a discovered `source_url` or `canonical_url` to the generated
    `route_path` for that page or post.
    """
    redirects: list[dict] = []
    items = list(manifest.get("pages", [])) + list(manifest.get("posts", []))

    for item in items:
        source = item.get("canonical_url") or item.get("source_url")
        if not source:
            continue
        parsed = urlsplit(source)
        source_path = parsed.path or "/"
        target = item.get("route_path") or "/"
        redirects.append(
            {
                "source_url": source,
                "source_path": source_path,
                "target": target,
                "type": "post" if item.get("published_at") else "page",
            }
        )

    return redirects


def write_redirects_json(output_dir: Path, redirects: Iterable[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "redirects.json", list(redirects))


def write_netlify_redirects(output_dir: Path, redirects: Iterable[dict]) -> None:
    """Write a simple Netlify `_redirects` file under `output_dir/netlify/_redirects`.

    Lines are formatted as: `/from/path  /to/path  301`
    """
    lines: list[str] = []
    for r in redirects:
        from_path = r.get("source_path") or "/"
        to_path = r.get("target") or "/"
        lines.append(f"{from_path} {to_path} 301")

    netlify_dir = output_dir / "netlify"
    netlify_dir.mkdir(parents=True, exist_ok=True)
    write_text(netlify_dir / "_redirects", "\n".join(lines) + "\n")
