import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from s2a.generate.astro import generate_astro_project


def _has_node() -> bool:
    return bool(shutil.which("node") and shutil.which("npm"))


def _npm_install_command(project_dir: Path) -> list[str]:
    if any(
        (project_dir / lockfile).exists()
        for lockfile in ("package-lock.json", "npm-shrinkwrap.json")
    ):
        return ["npm", "ci"]
    return ["npm", "install"]


def _assert_non_empty_dist(project_dir: Path) -> None:
    dist = project_dir / "dist"
    assert dist.is_dir(), f"Expected dist/ after npm run build in {project_dir}"
    files = [path for path in dist.rglob("*") if path.is_file()]
    assert files, f"Expected dist/ to contain files in {project_dir}"
    assert any(path.name == "index.html" for path in files), (
        f"Expected dist/ to contain an index.html file in {project_dir}"
    )


def _build_generated_project(project_dir: Path) -> None:
    node_modules = project_dir / "node_modules"
    if node_modules.exists():
        _remove_tree(node_modules)
    subprocess.check_call(_npm_install_command(project_dir), cwd=str(project_dir))
    subprocess.check_call(["npm", "run", "build"], cwd=str(project_dir))
    _assert_non_empty_dist(project_dir)


def _remove_tree(path: Path) -> None:
    if os.name == "nt":
        shutil.rmtree(path)
        return

    for _ in range(5):
        if not path.exists():
            return
        ds_store = path / ".DS_Store"
        if ds_store.exists():
            ds_store.unlink(missing_ok=True)
        try:
            shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.1)

    shutil.rmtree(path, ignore_errors=True)
    if path.exists():
        raise OSError(f"Could not remove {path}")


@pytest.mark.skipif(not _has_node(), reason="Node.js/npm not available")
def test_build_generated_sites() -> None:
    """Run install and build for each generated project with `package.json`.

    This test is skipped when Node/npm are not installed locally. CI uses a separate
    workflow to exercise builds more broadly.
    """
    generated_root = Path("generated")
    if not generated_root.exists():
        pytest.skip("No generated projects present")

    for d in sorted(generated_root.iterdir()):
        if not (d / "package.json").exists():
            continue
        _build_generated_project(d)


@pytest.mark.skipif(not _has_node(), reason="Node.js/npm not available")
def test_generate_from_fixture_and_build(tmp_path: Path) -> None:
    """Generate an Astro project from the laurenzo-site fixture and run npm build.

    This is the primary CI smoke-test: it validates that the full generation
    pipeline produces a project that Astro can actually compile.  The test is
    skipped when Node/npm are not available (e.g. local environments without
    Node), but the CI workflow installs Node so this always runs there.
    """
    fixture = Path(__file__).parent / "fixtures" / "laurenzo-site"
    if not fixture.exists():
        pytest.skip("laurenzo-site fixture not present in this checkout")

    snapshot_path = fixture / "site_snapshot.json"
    output_dir = tmp_path / "astro-site"

    result = generate_astro_project(
        snapshot_path, output_dir, site_url="https://example.com"
    )
    assert result.pages_written >= 1, "Expected at least one page to be written"
    assert (output_dir / "package.json").exists(), "package.json missing from generated output"

    _build_generated_project(output_dir)
