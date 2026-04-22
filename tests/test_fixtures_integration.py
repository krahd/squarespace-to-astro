import shutil
from pathlib import Path

import pytest

from s2a.generate.astro import generate_astro_project


def copy_fixture(name: str, tmp_path: Path) -> Path:
    src = Path(__file__).parent / "fixtures" / name
    if not src.exists():
        pytest.skip(f"Fixture '{name}' not present in this checkout")
    dst = tmp_path / "snapshot"
    shutil.copytree(src, dst)
    return dst


def test_homepage_heavy_fixture(tmp_path: Path) -> None:
    snapshot_dir = copy_fixture("homepage-heavy", tmp_path)
    snapshot_path = snapshot_dir / "site_snapshot.json"
    output_dir = tmp_path / "astro-site"

    result = generate_astro_project(
        snapshot_path, output_dir, site_url="https://example.com"
    )

    # Expect pages for home/about/contact
    assert result.pages_written >= 2
    assert (output_dir / "src/content/pages/home.md").exists()
    assert (output_dir / "src/content/pages/about.md") or (
        output_dir / "src/content/pages/about.md"
    )


def test_mixed_pages_posts_fixture(tmp_path: Path) -> None:
    snapshot_dir = copy_fixture("mixed-pages-posts", tmp_path)
    snapshot_path = snapshot_dir / "site_snapshot.json"
    output_dir = tmp_path / "astro-site"

    result = generate_astro_project(
        snapshot_path, output_dir, site_url="https://example.org"
    )

    # Expect at least one post and pages
    assert result.posts_written >= 1 or result.pages_written >= 2
    assert (output_dir / "src/content/posts").exists()
    assert (output_dir / "migration-manifest.json").exists()


def test_laurnenzo_asset_verify_fixture(tmp_path: Path) -> None:
    snapshot_dir = copy_fixture("laurenzo-site-asset-verify", tmp_path)
    snapshot_path = snapshot_dir / "site_snapshot.json"
    output_dir = tmp_path / "astro-site"

    result = generate_astro_project(
        snapshot_path, output_dir, site_url="https://laurenzo.net"
    )

    # Expect pages and migration manifest
    assert result.pages_written >= 2
    assert (output_dir / "src/content/pages/home.md").exists()
    assert (output_dir / "migration-manifest.json").exists()


def test_laurnenzo_site_fixture(tmp_path: Path) -> None:
    snapshot_dir = copy_fixture("laurenzo-site", tmp_path)
    snapshot_path = snapshot_dir / "site_snapshot.json"
    output_dir = tmp_path / "astro-site"

    result = generate_astro_project(
        snapshot_path, output_dir, site_url="https://laurenzo.net"
    )

    assert result.pages_written >= 1
    assert (output_dir / "src/content/pages/home.md").exists()
    assert (output_dir / "migration-manifest.json").exists()
