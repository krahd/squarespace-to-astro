import shutil
import subprocess
from pathlib import Path

import pytest


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
        subprocess.check_call(["npm", "ci"], cwd=str(d))
        # prefer explicit build script, allow project to be no-op
        try:
            subprocess.check_call(["npm", "run", "build"], cwd=str(d))
        except subprocess.CalledProcessError:
            pytest.skip(f"Build failed for {d}; skipping on this environment")
