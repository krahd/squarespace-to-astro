from pathlib import Path

from s2a.generate.redirects import (
    build_redirects_from_manifest,
    write_redirects_json,
    write_netlify_redirects,
)


def test_build_redirects_and_writers(tmp_path: Path) -> None:
    manifest = {
        "pages": [
            {
                "route_path": "/",
                "source_url": "https://example.com/",
                "canonical_url": "https://example.com/",
            },
            {
                "route_path": "/about",
                "source_url": "https://example.com/about",
                "canonical_url": "https://example.com/about",
            },
        ],
        "posts": [
            {
                "route_path": "/blog/post-1",
                "source_url": "https://example.com/blog/post-1",
                "canonical_url": "https://example.com/blog/post-1",
                "published_at": "2026-01-01T00:00:00+00:00",
            },
        ],
    }

    redirects = build_redirects_from_manifest(manifest)
    assert any(r["target"] == "/about" for r in redirects)

    # write JSON and netlify files
    out = tmp_path / "out"
    write_redirects_json(out, redirects)
    write_netlify_redirects(out, redirects)

    assert (out / "redirects.json").exists()
    assert (out / "netlify" / "_redirects").exists()
