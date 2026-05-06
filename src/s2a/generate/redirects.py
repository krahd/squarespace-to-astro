from __future__ import annotations

from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from s2a.files import write_json, write_text


def build_redirects_from_manifest(manifest: dict) -> list[dict]:
    """Build a list of redirects from a migration manifest dict.

    Each redirect maps a discovered ``source_url`` / ``canonical_url`` to the
    generated ``route_path`` for that page or post.  Identity redirects — where
    ``source_path`` already equals ``target`` — are omitted because they would
    produce no-op ``/path -> /path 301`` rules.
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
        # Skip identity redirects — they add noise without any effect.
        if source_path == target:
            continue
        redirects.append(
            {
                "source_url": source,
                "source_path": source_path,
                "target": target,
                "type": "post" if item.get("published_at") else "page",
            }
        )

    return redirects


def build_redirect_summary(
    manifest: dict, redirects: list[dict]
) -> dict:
    """Return a summary dict describing redirect coverage for the migration.

    Fields:
    - ``total_items``: total pages + posts in the manifest.
    - ``redirects_generated``: number of non-identity redirects produced.
    - ``identity_skipped``: items whose source path already matches the target.
    - ``no_source_skipped``: items with no source or canonical URL recorded.
    - ``pages``: redirect count for page-type entries.
    - ``posts``: redirect count for post-type entries.
    """
    items = list(manifest.get("pages", [])) + list(manifest.get("posts", []))
    total = len(items)
    with_source = sum(
        1 for i in items if i.get("canonical_url") or i.get("source_url")
    )
    no_source = total - with_source
    identity = 0
    for item in items:
        source = item.get("canonical_url") or item.get("source_url")
        if not source:
            continue
        source_path = urlsplit(source).path or "/"
        target = item.get("route_path") or "/"
        if source_path == target:
            identity += 1

    return {
        "total_items": total,
        "redirects_generated": len(redirects),
        "identity_skipped": identity,
        "no_source_skipped": no_source,
        "pages": sum(1 for r in redirects if r["type"] == "page"),
        "posts": sum(1 for r in redirects if r["type"] == "post"),
    }


def write_redirects_json(output_dir: Path, redirects: Iterable[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "redirects.json", list(redirects))


def write_netlify_redirects(output_dir: Path, redirects: Iterable[dict]) -> None:
    """Write a Netlify ``_redirects`` file under ``output_dir/netlify/_redirects``.

    Lines are formatted as: ``/from/path  /to/path  301``
    """
    lines: list[str] = []
    for r in redirects:
        from_path = r.get("source_path") or "/"
        to_path = r.get("target") or "/"
        lines.append(f"{from_path} {to_path} 301")

    netlify_dir = output_dir / "netlify"
    netlify_dir.mkdir(parents=True, exist_ok=True)
    write_text(netlify_dir / "_redirects", "\n".join(lines) + "\n")


def write_redirect_report(
    output_dir: Path,
    redirects: list[dict],
    summary: dict,
) -> None:
    """Write a human-readable Markdown redirect report to ``output_dir/redirect-report.md``.

    The report lists every redirect rule and a coverage summary so the
    site owner can review the mapping before deploying.
    """
    lines: list[str] = ["# Redirect Report\n"]
    lines.append(
        f"Generated {summary['redirects_generated']} redirect rule(s) "
        f"from {summary['total_items']} migrated item(s).\n"
    )
    if summary["identity_skipped"]:
        lines.append(
            f"- {summary['identity_skipped']} item(s) skipped — "
            "source path already matches the generated route (no redirect needed).\n"
        )
    if summary["no_source_skipped"]:
        lines.append(
            f"- {summary['no_source_skipped']} item(s) skipped — "
            "no source or canonical URL was recorded during crawl.\n"
        )
    lines.append("")

    if redirects:
        lines.append("## Rules\n")
        lines.append("| Type | From | To |")
        lines.append("|------|------|----|")
        for r in redirects:
            lines.append(
                f"| {r['type']} | `{r['source_path']}` | `{r['target']}` |"
            )
        lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_text(output_dir / "redirect-report.md", "\n".join(lines))
