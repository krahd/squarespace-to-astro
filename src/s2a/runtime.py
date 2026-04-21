from __future__ import annotations

import os
import sys
from pathlib import Path

BUNDLED_BROWSER_DIR_NAMES = ("playwright-browsers", "ms-playwright")


def bundled_playwright_browsers_path(
    *,
    frozen: bool | None = None,
    executable: str | None = None,
    meipass: str | None = None,
) -> Path | None:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    if not frozen:
        return None

    candidate_roots: list[Path] = []
    executable_path = executable or getattr(sys, "executable", None)
    if executable_path:
        candidate_roots.append(Path(executable_path).resolve().parent)

    meipass_path = meipass or getattr(sys, "_MEIPASS", None)
    if meipass_path:
        candidate_roots.append(Path(meipass_path).resolve())

    seen: set[Path] = set()
    for root in candidate_roots:
        if root in seen:
            continue
        seen.add(root)
        for directory_name in BUNDLED_BROWSER_DIR_NAMES:
            candidate = root / directory_name
            if candidate.exists():
                return candidate

    return None


def configure_bundled_playwright_environment() -> Path | None:
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured:
        return Path(configured)

    bundled_path = bundled_playwright_browsers_path()
    if bundled_path is None:
        return None

    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_path)
    return bundled_path
