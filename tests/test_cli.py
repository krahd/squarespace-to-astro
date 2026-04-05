import argparse

import s2a.cli as cli
from s2a.normalize.models import AuthCaptureReport


def make_auth_namespace(
    *,
    storage_state: str | None = None,
    site_password: str | None = None,
    login_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    manual_auth: bool = False,
    auth_headless: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        target="https://example.com",
        storage_state=storage_state,
        site_password=site_password,
        login_url=login_url,
        username=username,
        password=password,
        manual_auth=manual_auth,
        auth_headless=auth_headless,
    )


def test_resolve_auth_credentials_uses_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("SQUARESPACE_USER", "env@example.com")
    monkeypatch.setenv("SQUARESPACE_PWD", "env-password")

    args = make_auth_namespace()

    assert cli.resolve_auth_credentials(args) == ("env@example.com", "env-password")


def test_resolve_auth_credentials_prefers_cli_values(monkeypatch) -> None:
    monkeypatch.setenv("SQUARESPACE_USER", "env@example.com")
    monkeypatch.setenv("SQUARESPACE_PWD", "env-password")

    args = make_auth_namespace(username="cli@example.com", password="cli-password")

    assert cli.resolve_auth_credentials(args) == ("cli@example.com", "cli-password")


def test_auth_browser_main_uses_resolved_env_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQUARESPACE_USER", "env@example.com")
    monkeypatch.setenv("SQUARESPACE_PWD", "env-password")
    calls: dict[str, object] = {}

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:
        calls.update(kwargs)
        return AuthCaptureReport(
            generated_at="2026-04-05T00:00:00+00:00",
            target_url="https://example.com",
            login_url="https://example.com",
            storage_state_path="auth/storage_state.json",
            mode="credentials",
            cookies_saved=1,
            headless=True,
        )

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    result = cli.main([
        "auth-browser",
        "https://example.com",
        "--output-dir",
        str(tmp_path),
    ])

    assert result == 0
    assert calls["username"] == "env@example.com"
    assert calls["password"] == "env-password"


def test_prepare_storage_state_uses_resolved_env_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SQUARESPACE_USER", "env@example.com")
    monkeypatch.setenv("SQUARESPACE_PWD", "env-password")
    calls: dict[str, object] = {}

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:
        calls.update(kwargs)
        return AuthCaptureReport(
            generated_at="2026-04-05T00:00:00+00:00",
            target_url="https://example.com",
            login_url="https://example.com",
            storage_state_path="auth/storage_state.json",
            mode="credentials",
            cookies_saved=1,
            headless=True,
        )

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    args = make_auth_namespace()

    result = cli.prepare_storage_state(args, tmp_path)

    assert calls["username"] == "env@example.com"
    assert calls["password"] == "env-password"
    assert result == tmp_path / "auth/storage_state.json"


def test_prepare_storage_state_skips_capture_without_auth_inputs(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("SQUARESPACE_USER", raising=False)
    monkeypatch.delenv("SQUARESPACE_PWD", raising=False)

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:  # pragma: no cover
        raise AssertionError("capture_storage_state should not be called")

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    args = make_auth_namespace()

    assert cli.prepare_storage_state(args, tmp_path) is None
