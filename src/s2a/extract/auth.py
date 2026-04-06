from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

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
    insecure: bool = False,
) -> AuthCaptureReport:
    configure_bundled_playwright_environment()

    try:
        from playwright.sync_api import Error as PlaywrightError
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
    if insecure:
        warnings.append("TLS certificate verification was disabled for browser auth capture.")

    auth_dir = output_dir / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    storage_state_path = auth_dir / "storage_state.json"

    mode = "passthrough"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context(ignore_https_errors=insecure)
            page = context.new_page()
            try:
                page.goto(login_url, wait_until="domcontentloaded", timeout=30_000)
            except PlaywrightError as exc:
                rewritten_error = _rewrite_navigation_error(exc, login_url, insecure=insecure)
                if rewritten_error is not None:
                    raise rewritten_error from exc
                raise

            if site_password:
                mode = "site-password"
                password_field = page.locator(DEFAULT_PASSWORD_SELECTOR).first
                try:
                    password_field.wait_for(timeout=10_000)
                except PlaywrightTimeoutError as exc:
                    raise _rewrite_auth_timeout_error(login_url, mode=mode) from exc
                password_field.fill(site_password)
                click_submit(page)
            elif username and password:
                mode = "credentials"
                username_field = page.locator(DEFAULT_USERNAME_SELECTOR).first
                password_field = page.locator(DEFAULT_PASSWORD_SELECTOR).first
                try:
                    username_field.wait_for(timeout=10_000)
                    password_field.wait_for(timeout=10_000)
                except PlaywrightTimeoutError as exc:
                    raise _rewrite_auth_timeout_error(login_url, mode=mode) from exc
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
        finally:
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


def _rewrite_navigation_error(
    exc: Exception,
    url: str,
    *,
    insecure: bool,
) -> RuntimeError | None:
    message = str(exc)
    if "ERR_CERT_" not in message:
        return None

    host = urlsplit(url).hostname or url
    guidance = [
        f"TLS certificate validation failed while opening {url}.",
        f"The server certificate does not match {host} or is otherwise invalid.",
        "Check that the target URL or --login-url value is correct.",
    ]

    if host.endswith(".squarespace.com"):
        preview_prefix = host[: -len(".squarespace.com")]
        if "." in preview_prefix:
            guidance.append(
                "Squarespace preview domains usually look like https://site.squarespace.com, not a multi-label subdomain."
            )

    if not insecure:
        guidance.append(
            "If you intentionally need to connect to a host with a broken certificate, rerun with --insecure."
        )

    return RuntimeError(" ".join(guidance))


def _rewrite_auth_timeout_error(url: str, *, mode: str) -> RuntimeError:
    if mode == "credentials":
        guidance = [
            f"Timed out waiting for a login form at {url}.",
            "The page did not expose the expected username and password fields.",
            "If this site is public, rerun without auth options or unset SQUARESPACE_USER and SQUARESPACE_PWD.",
            "If auth is required, pass --login-url to the actual login page or use --manual-auth.",
        ]
    else:
        guidance = [
            f"Timed out waiting for a site-password form at {url}.",
            "The page did not expose the expected password field.",
            "Check that the target URL or --login-url points at the gated page before using --site-password.",
        ]

    return RuntimeError(" ".join(guidance))


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
