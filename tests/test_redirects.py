from pathlib import Path

from s2a.generate.redirects import (
    build_redirect_summary,
    build_redirects_from_manifest,
    write_redirect_report,
    write_redirects_json,
    write_netlify_redirects,
)


_MANIFEST = {
    "pages": [
        {
            "route_path": "/",
            "source_url": "https://example.com/",
            "canonical_url": "https://example.com/",
        },
        {
            # Non-identity: source /old-about -> target /about
            "route_path": "/about",
            "source_url": "https://example.com/old-about",
            "canonical_url": "https://example.com/old-about",
        },
    ],
    "posts": [
        {
            "route_path": "/blog/post-1",
            "source_url": "https://example.com/posts/post-1",
            "canonical_url": "https://example.com/posts/post-1",
            "published_at": "2026-01-01T00:00:00+00:00",
        },
    ],
}


def test_build_redirects_and_writers(tmp_path: Path) -> None:
    manifest = _MANIFEST
    redirects = build_redirects_from_manifest(manifest)
    assert any(r["target"] == "/about" for r in redirects)

    # write JSON and netlify files
    out = tmp_path / "out"
    write_redirects_json(out, redirects)
    write_netlify_redirects(out, redirects)

    assert (out / "redirects.json").exists()
    assert (out / "netlify" / "_redirects").exists()


def test_identity_redirects_excluded() -> None:
    """Items where source path == route_path must be omitted."""
    redirects = build_redirects_from_manifest(_MANIFEST)
    for r in redirects:
        assert r["source_path"] != r["target"], (
            f"Identity redirect found: {r['source_path']} -> {r['target']}"
        )


def test_build_redirect_summary_counts() -> None:
    manifest = {
        "pages": [
            # Will become a redirect (source_path /old-about != target /about)
            {"route_path": "/about", "source_url": "https://example.com/old-about"},
            # Identity — should be skipped
            {"route_path": "/contact", "source_url": "https://example.com/contact"},
            # No source URL — no_source_skipped
            {"route_path": "/mystery"},
        ],
        "posts": [
            {
                "route_path": "/blog/hello",
                "source_url": "https://example.com/posts/hello",
                "published_at": "2026-01-01",
            },
        ],
    }
    redirects = build_redirects_from_manifest(manifest)
    summary = build_redirect_summary(manifest, redirects)

    assert summary["total_items"] == 4
    assert summary["redirects_generated"] == len(redirects)
    assert summary["identity_skipped"] == 1
    assert summary["no_source_skipped"] == 1
    assert summary["pages"] + summary["posts"] == summary["redirects_generated"]


def test_write_redirect_report_creates_file(tmp_path: Path) -> None:
    redirects = build_redirects_from_manifest(_MANIFEST)
    summary = build_redirect_summary(_MANIFEST, redirects)
    write_redirect_report(tmp_path, redirects, summary)

    report_path = tmp_path / "redirect-report.md"
    assert report_path.exists()
    content = report_path.read_text()
    assert "redirect" in content.lower()
