import argparse
from pathlib import Path

import s2a.cli as cli
from s2a.normalize.models import AuthCaptureReport


def make_auth_namespace(
    *,
    command: str = "crawl",
    target: str = "https://example.com",
    output_dir: str | None = None,
    xml_file: str | None = None,
    storage_state: str | None = None,
    site_password: str | None = None,
    login_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    manual_auth: bool = False,
    auth_headless: bool = True,
    insecure: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        command=command,
        target=target,
        output_dir=output_dir,
        xml_file=xml_file,
        storage_state=storage_state,
        site_password=site_password,
        login_url=login_url,
        username=username,
        password=password,
        manual_auth=manual_auth,
        auth_headless=auth_headless,
        insecure=insecure,
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


def test_auth_browser_main_passes_insecure_flag(monkeypatch, tmp_path) -> None:
    calls: dict[str, object] = {}

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:
        calls.update(kwargs)
        return AuthCaptureReport(
            generated_at="2026-04-05T00:00:00+00:00",
            target_url="https://example.com",
            login_url="https://example.com",
            storage_state_path="auth/storage_state.json",
            mode="passthrough",
            cookies_saved=0,
            headless=True,
        )

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    result = cli.main([
        "auth-browser",
        "https://example.com",
        "--output-dir",
        str(tmp_path),
        "--insecure",
    ])

    assert result == 0
    assert calls["insecure"] is True


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


def test_resolve_output_dir_uses_unique_site_output_by_default(monkeypatch) -> None:
    monkeypatch.setattr(cli, "output_dir_timestamp", lambda: "20260405-123456")

    args = make_auth_namespace(command="crawl", output_dir=None, target="https://Example.com/blog")

    assert cli.resolve_output_dir(args) == (
        Path("site-output/20260405-123456-crawl-example-com"),
        True,
    )


def test_build_execution_metadata_redacts_sensitive_arguments() -> None:
    args = make_auth_namespace(
        command="migrate",
        output_dir=None,
        password="secret-password",
        site_password="secret-gate",
    )

    metadata = cli.build_execution_metadata(
        args,
        Path("site-output/20260405-123456-migrate-example-com"),
        used_default_output_dir=True,
        artifacts={"report": "report.json"},
    )

    assert metadata["used_default_output_dir"] is True
    assert metadata["parameters"]["password"] == "<redacted>"
    assert metadata["parameters"]["site_password"] == "<redacted>"
    assert metadata["artifacts"] == {"report": "report.json"}
