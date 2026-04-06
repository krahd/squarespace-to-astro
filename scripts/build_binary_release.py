from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from s2a import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PROJECT_ROOT / "build" / "binary-release"
DIST_ROOT = BUILD_ROOT / "dist"
WORK_ROOT = BUILD_ROOT / "work"
SPEC_ROOT = BUILD_ROOT / "spec"
RELEASE_ROOT = BUILD_ROOT / "release"
ENTRYPOINT = PROJECT_ROOT / "scripts" / "s2a_binary_entry.py"
APP_NAME = "s2a"
WINDOWS = os.name == "nt"


def main() -> None:
    browser_root = resolve_browser_root()
    prepare_output_dirs()
    build_pyinstaller_bundle()

    bundle_root = DIST_ROOT / APP_NAME
    release_dir = RELEASE_ROOT / release_directory_name()
    shutil.copytree(bundle_root, release_dir, dirs_exist_ok=True)
    shutil.copytree(browser_root, release_dir / "playwright-browsers", dirs_exist_ok=True)
    shutil.copy2(PROJECT_ROOT / "README.md", release_dir / "README.md")
    shutil.copy2(PROJECT_ROOT / "LICENSE", release_dir / "LICENSE")
    (release_dir / "BINARY-README.txt").write_text(binary_readme(), encoding="utf-8")

    archive_path = create_archive(release_dir)
    print(f"Created binary release bundle: {archive_path}")


def resolve_browser_root() -> Path:
    browser_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browser_root:
        raise RuntimeError(
            "PLAYWRIGHT_BROWSERS_PATH must point to an installed Playwright browser directory before building binaries."
        )

    path = Path(browser_root).resolve()
    if not path.exists() or not any(path.iterdir()):
        raise RuntimeError(
            f"PLAYWRIGHT_BROWSERS_PATH does not contain installed browsers: {path}"
        )

    return path


def prepare_output_dirs() -> None:
    for path in (DIST_ROOT, WORK_ROOT, SPEC_ROOT, RELEASE_ROOT):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)


def build_pyinstaller_bundle() -> None:
    try:
        from PyInstaller.__main__ import run as pyinstaller_run
    except ImportError as exc:  # pragma: no cover - depends on build environment
        raise RuntimeError(
            "PyInstaller is not installed. Install the dev dependencies before building binary releases."
        ) from exc

    pyinstaller_run(
        [
            "--noconfirm",
            "--clean",
            "--onedir",
            "--console",
            f"--name={APP_NAME}",
            f"--distpath={DIST_ROOT}",
            f"--workpath={WORK_ROOT}",
            f"--specpath={SPEC_ROOT}",
            "--collect-all=playwright",
            "--copy-metadata=squarespace-to-astro",
            str(ENTRYPOINT),
        ]
    )


def create_archive(release_dir: Path) -> Path:
    archive_base = RELEASE_ROOT / release_dir.name
    archive_format = "zip" if WINDOWS else "gztar"
    archive_path = shutil.make_archive(
        str(archive_base),
        archive_format,
        root_dir=RELEASE_ROOT,
        base_dir=release_dir.name,
    )
    return Path(archive_path)


def release_directory_name() -> str:
    return f"s2a-{__version__}-{platform_slug()}-{architecture_slug()}"


def platform_slug() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in {"win32", "cygwin"}:
        return "windows"
    return sys.platform


def architecture_slug() -> str:
    machine = platform.machine().lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    return aliases.get(machine, machine or "unknown")

def binary_readme() -> str:
    executable_name = "s2a.exe" if WINDOWS else "s2a"
    return (
        f"s2a {__version__} standalone bundle\n\n"
        f"Run the CLI with ./{executable_name} after unpacking this archive.\n"
        "This bundle includes a Playwright Chromium browser payload for auth-browser.\n"
        "Linux users may still need common Chromium runtime libraries supplied by their distro.\n"
    )


if __name__ == "__main__":
    main()
