from pathlib import Path

from s2a.runtime import bundled_playwright_browsers_path


def test_bundled_playwright_browsers_path_returns_none_when_not_frozen(
    tmp_path: Path,
) -> None:
    assert (
        bundled_playwright_browsers_path(
            frozen=False,
            executable=str(tmp_path / "s2a"),
        )
        is None
    )


def test_bundled_playwright_browsers_path_prefers_playwright_browsers_dir(
    tmp_path: Path,
) -> None:
    executable_dir = tmp_path / "bundle"
    executable_dir.mkdir()
    browser_dir = executable_dir / "playwright-browsers"
    browser_dir.mkdir()

    assert (
        bundled_playwright_browsers_path(
            frozen=True,
            executable=str(executable_dir / "s2a"),
        )
        == browser_dir
    )


def test_bundled_playwright_browsers_path_uses_meipass_when_needed(
    tmp_path: Path,
) -> None:
    meipass_dir = tmp_path / "_internal"
    meipass_dir.mkdir()
    browser_dir = meipass_dir / "ms-playwright"
    browser_dir.mkdir()

    assert (
        bundled_playwright_browsers_path(
            frozen=True,
            executable=str(tmp_path / "missing" / "s2a"),
            meipass=str(meipass_dir),
        )
        == browser_dir
    )
