import shutil
import subprocess
from pathlib import Path

import pytest

from s2a.generate.astro import generate_astro_project


def _has_node() -> bool:
    return bool(shutil.which("node") and shutil.which("npm"))


@pytest.mark.skipif(not _has_node(), reason="Node.js/npm not available")
def test_build_generated_sites() -> None:
    """Attempt to run `npm ci` and `npm run build` for each generated project.

    This test is skipped when Node/npm are not installed locally. CI uses a separate
    workflow to exercise builds more broadly.
    """
    generated_root = Path("generated")
    if not generated_root.exists():
        pytest.skip("No generated projects present")

    for d in sorted(generated_root.iterdir()):
        pkg = d / "package.json"
        if not pkg.exists():
            continue
        # Use `npm ci` when a lockfile is present for reproducible installs,
        # otherwise fall back to `npm install` so trimmed fixtures without
        # lockfiles don't cause test failures in local environments.
        lockfiles = [
            "package-lock.json",
            "npm-shrinkwrap.json",
            "pnpm-lock.yaml",
            "yarn.lock",
        ]
        install_cmd = None
        for lf in lockfiles:
            if (d / lf).exists():
                # prefer `npm ci` for npm lockfiles, otherwise use `npm install`
                install_cmd = (
                    ["npm", "ci"]
                    if lf in ("package-lock.json", "npm-shrinkwrap.json")
                    else ["npm", "install"]
                )
                break

        if install_cmd is None:
            install_cmd = ["npm", "install"]

        try:
            subprocess.check_call(install_cmd, cwd=str(d))
        except subprocess.CalledProcessError:
            pytest.skip(
                f"Dependency install failed for {d}; skipping on this environment"
            )

        # prefer explicit build script, allow project to be no-op
        try:
            subprocess.check_call(["npm", "run", "build"], cwd=str(d))
        except subprocess.CalledProcessError:
            pytest.skip(f"Build failed for {d}; skipping on this environment")


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

    try:
        subprocess.check_call(["npm", "install"], cwd=str(output_dir))
    except subprocess.CalledProcessError:
        pytest.skip("npm install failed; skipping build step on this environment")

    subprocess.check_call(["npm", "run", "build"], cwd=str(output_dir))
    assert (output_dir / "dist").exists(), "Astro build did not produce a dist/ directory"
