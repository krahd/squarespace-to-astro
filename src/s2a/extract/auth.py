from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from s2a.files import read_json
from s2a.normalize.models import AuthCaptureReport
from s2a.runtime import configure_bundled_playwright_environment
from s2a.url_utils import coerce_url


DEFAULT_USERNAME_SELECTOR = "input[type='email'], input[name='email'], input[name='username'], input[name='login']"
DEFAULT_PASSWORD_SELECTOR = "input[type='password']"
DEFAULT_SUBMIT_SELECTOR = "button[type='submit'], input[type='submit'], button"


def capture_storage_state(
    target_url: str,
    output_dir: Path,
    login_url: str | None = None,
    site_password: str | None = None,
    username: str | None = None,
    password: str | None = None,
    manual: bool = False,
    headless: bool = True,
) -> AuthCaptureReport:
    configure_bundled_playwright_environment()

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on environment setup
        raise RuntimeError(
            "Playwright is not installed. Install project dependencies and run 'python -m playwright install chromium'."
        ) from exc

    warnings: list[str] = []
    target_url = coerce_url(target_url)
    login_url = coerce_url(login_url or target_url)

    if manual and headless:
        headless = False
        warnings.append("Manual auth requires a visible browser, so headless mode was disabled.")

    auth_dir = output_dir / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    storage_state_path = auth_dir / "storage_state.json"

    mode = "passthrough"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)

        if site_password:
            mode = "site-password"
            password_field = page.locator(DEFAULT_PASSWORD_SELECTOR).first
            password_field.wait_for(timeout=10_000)
            password_field.fill(site_password)
            click_submit(page)
        elif username and password:
            mode = "credentials"
            username_field = page.locator(DEFAULT_USERNAME_SELECTOR).first
            password_field = page.locator(DEFAULT_PASSWORD_SELECTOR).first
            username_field.wait_for(timeout=10_000)
            password_field.wait_for(timeout=10_000)
            username_field.fill(username)
            password_field.fill(password)
            click_submit(page)

        if manual:
            input("Complete the login flow in the browser, then press Enter to save storage state... ")

        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            warnings.append(
                "Browser auth capture timed out waiting for a fully idle page, but storage state was still saved.")

        context.storage_state(path=str(storage_state_path))
        browser.close()

    state = read_json(storage_state_path)
    cookies_saved = len(state.get("cookies", []))

    return AuthCaptureReport(
        generated_at=datetime.now(UTC).isoformat(),
        target_url=target_url,
        login_url=login_url,
        storage_state_path=str(storage_state_path.relative_to(output_dir)),
        mode=mode,
        cookies_saved=cookies_saved,
        headless=headless,
        warnings=warnings,
    )


def click_submit(page) -> None:
    submit = page.locator(DEFAULT_SUBMIT_SELECTOR).first
    if submit.count() > 0:
        submit.click()
    else:
        page.keyboard.press("Enter")


def apply_storage_state_cookies(client: httpx.Client, storage_state_path: Path) -> None:
    state = read_json(storage_state_path)

    for cookie in state.get("cookies", []):
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain")
        path = cookie.get("path", "/")

        if not name or value is None:
            continue

        client.cookies.set(name, value, domain=domain, path=path)
