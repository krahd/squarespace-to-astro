import argparse
from pathlib import Path

import s2a.cli as cli
from s2a.extract.assets import AssetDownloadEstimate
from s2a.normalize.models import (
    AstroGenerationResult,
    AssetManifest,
    AssetReference,
    AuthCaptureReport,
    CrawlReport,
    CrawlSnapshot,
    SiteProbe,
)


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
    yes: bool = False,
    quiet: bool = False,
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
        yes=yes,
        quiet=quiet,
    )


class DummyClientContext:
    def __init__(self, client: object | None = None) -> None:
        self.client = client if client is not None else object()

    def __enter__(self) -> object:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def make_probe() -> SiteProbe:
    return SiteProbe(
        target_url="https://example.com",
        final_home_url="https://example.com",
        site_origin="https://example.com",
        homepage_status_code=200,
        homepage_title="Example",
        probably_squarespace=True,
    )


def make_snapshot() -> CrawlSnapshot:
    probe = make_probe()
    return CrawlSnapshot(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url=probe.target_url,
        base_url=probe.final_home_url or probe.target_url,
        probe=probe,
        pages=[],
    )


def make_report() -> CrawlReport:
    return CrawlReport(
        generated_at="2026-04-05T00:00:00+00:00",
        target_url="https://example.com",
        probably_squarespace=True,
        version_hint="7.1",
        pages_crawled=3,
        ok_pages=3,
        pages_with_json=2,
        password_gated_pages=0,
        unique_assets=1,
        unique_internal_links=3,
        sitemap_entries=3,
    )


def make_asset_estimate() -> AssetDownloadEstimate:
    return AssetDownloadEstimate(
        assets=[
            AssetReference(
                source_url="https://images.squarespace-cdn.com/content/hero.jpg?w=1200",
                asset_type="image",
                attribute="src",
                owner_route="/",
                group_key="img-1",
                variant_hint="large",
            )
        ],
        estimated_size_bytes=5 * 1024 * 1024,
        unknown_size_count=0,
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

    result = cli.main(
        [
            "auth-browser",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
        ]
    )

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

    result = cli.main(
        [
            "auth-browser",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
            "--insecure",
        ]
    )

    assert result == 0
    assert calls["insecure"] is True


def test_prepare_storage_state_skips_capture_with_only_env_credentials(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SQUARESPACE_USER", "env@example.com")
    monkeypatch.setenv("SQUARESPACE_PWD", "env-password")

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:  # pragma: no cover
        raise AssertionError("capture_storage_state should not be called")

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    args = make_auth_namespace()

    assert cli.prepare_storage_state(args, tmp_path) is None


def test_prepare_storage_state_uses_env_credentials_when_auth_is_explicit(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SQUARESPACE_USER", "env@example.com")
    monkeypatch.setenv("SQUARESPACE_PWD", "env-password")
    calls: dict[str, object] = {}

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:
        calls.update(kwargs)
        return AuthCaptureReport(
            generated_at="2026-04-05T00:00:00+00:00",
            target_url="https://example.com",
            login_url="https://auth.example.com",
            storage_state_path="auth/storage_state.json",
            mode="credentials",
            cookies_saved=1,
            headless=True,
        )

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    args = make_auth_namespace(login_url="https://auth.example.com")

    result = cli.prepare_storage_state(args, tmp_path)

    assert calls["username"] == "env@example.com"
    assert calls["password"] == "env-password"
    assert result == tmp_path / "auth/storage_state.json"


def test_prepare_storage_state_skips_capture_without_auth_inputs(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("SQUARESPACE_USER", raising=False)
    monkeypatch.delenv("SQUARESPACE_PWD", raising=False)

    def fake_capture_storage_state(**kwargs) -> AuthCaptureReport:  # pragma: no cover
        raise AssertionError("capture_storage_state should not be called")

    monkeypatch.setattr(cli, "capture_storage_state", fake_capture_storage_state)

    args = make_auth_namespace()

    assert cli.prepare_storage_state(args, tmp_path) is None


def test_resolve_output_dir_uses_unique_site_output_by_default(monkeypatch) -> None:
    monkeypatch.setattr(cli, "output_dir_timestamp", lambda: "20260405-123456")

    args = make_auth_namespace(
        command="crawl", output_dir=None, target="https://Example.com/blog"
    )

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


def test_build_parser_accepts_yes_and_quiet_flags_for_all_commands() -> None:
    parser = cli.build_parser()
    command_vectors = [
        ["probe", "https://example.com"],
        ["crawl", "https://example.com"],
        ["auth-browser", "https://example.com"],
        ["import-xml", "example.xml"],
        ["generate-astro", "site_snapshot.json"],
        ["migrate", "https://example.com"],
    ]

    for command_vector in command_vectors:
        args = parser.parse_args([*command_vector, "--yes", "--quiet"])
        assert args.yes is True
        assert args.quiet is True


def test_build_parser_accepts_fidelity_flags_for_generate_astro_and_migrate() -> None:
    parser = cli.build_parser()

    generate_args = parser.parse_args(
        [
            "generate-astro",
            "site_snapshot.json",
            "--fidelity-mode",
            "balanced",
            "--layout-strategy",
            "components",
            "--markdown",
        ]
    )
    migrate_args = parser.parse_args(
        [
            "migrate",
            "https://example.com",
            "--choose-layout-strategy",
        ]
    )

    assert generate_args.fidelity_mode == "balanced"
    assert generate_args.layout_strategy == "components"
    assert generate_args.markdown_first is True
    assert migrate_args.choose_layout_strategy is True


def test_resolve_generation_options_prompts_for_layout_strategy(monkeypatch) -> None:
    console = cli.Console(quiet=False)
    args = argparse.Namespace(
        fidelity_mode="high",
        layout_strategy=None,
        choose_layout_strategy=True,
        yes=False,
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "2")

    fidelity_mode, layout_strategy, markdown_first = cli.resolve_generation_options(
        console, args
    )

    assert fidelity_mode == "high"
    assert layout_strategy == "components"
    assert markdown_first is False


def test_generate_astro_main_passes_fidelity_settings_to_generator(
    monkeypatch, tmp_path
) -> None:
    captured: dict[str, object] = {}

    def fake_generate_astro_project(*, snapshot_path, output_dir, **kwargs):
        captured["snapshot_path"] = snapshot_path
        captured["output_dir"] = output_dir
        captured.update(kwargs)
        return AstroGenerationResult(
            generated_at="2026-04-05T00:00:00+00:00",
            output_dir=str(output_dir),
            manifest_path="migration-manifest.json",
            pages_written=1,
            posts_written=0,
            warnings=[],
        )

    monkeypatch.setattr(cli, "generate_astro_project", fake_generate_astro_project)

    result = cli.main(
        [
            "generate-astro",
            "site_snapshot.json",
            "--output-dir",
            str(tmp_path),
            "--fidelity-mode",
            "balanced",
            "--layout-strategy",
            "components",
            "--markdown",
        ]
    )

    assert result == 0
    assert captured["fidelity_mode"] == "balanced"
    assert captured["layout_strategy"] == "components"
    assert captured["markdown_first"] is True


def test_crawl_main_skips_confirmation_prompt_with_yes(monkeypatch, tmp_path) -> None:
    calls = {"download": 0}

    monkeypatch.setattr(
        cli, "build_client", lambda *args, **kwargs: DummyClientContext()
    )
    monkeypatch.setattr(cli, "prepare_storage_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "probe_site", lambda *args, **kwargs: make_probe())
    monkeypatch.setattr(cli, "crawl_site", lambda *args, **kwargs: make_snapshot())
    monkeypatch.setattr(cli, "build_report", lambda *args, **kwargs: make_report())
    monkeypatch.setattr(
        cli,
        "estimate_snapshot_asset_download",
        lambda *args, **kwargs: make_asset_estimate(),
    )

    def fake_download_snapshot_assets(
        _client, _snapshot, _output_dir, **_kwargs
    ) -> AssetManifest:
        calls["download"] += 1
        return AssetManifest(generated_at="2026-04-05T00:00:00+00:00")

    monkeypatch.setattr(cli, "download_snapshot_assets", fake_download_snapshot_assets)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (_ for _ in ()).throw(
            AssertionError("input should not be called")
        ),
    )

    result = cli.main(
        [
            "crawl",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
            "--yes",
        ]
    )

    assert result == 0
    assert calls["download"] == 1


def test_crawl_main_can_skip_asset_download_after_prompt(monkeypatch, tmp_path) -> None:
    calls = {"download": 0}

    monkeypatch.setattr(
        cli, "build_client", lambda *args, **kwargs: DummyClientContext()
    )
    monkeypatch.setattr(cli, "prepare_storage_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "probe_site", lambda *args, **kwargs: make_probe())
    monkeypatch.setattr(cli, "crawl_site", lambda *args, **kwargs: make_snapshot())
    monkeypatch.setattr(cli, "build_report", lambda *args, **kwargs: make_report())
    monkeypatch.setattr(
        cli,
        "estimate_snapshot_asset_download",
        lambda *args, **kwargs: make_asset_estimate(),
    )

    def fake_download_snapshot_assets(
        _client, _snapshot, _output_dir, **_kwargs
    ) -> AssetManifest:
        calls["download"] += 1
        return AssetManifest(generated_at="2026-04-05T00:00:00+00:00")

    monkeypatch.setattr(cli, "download_snapshot_assets", fake_download_snapshot_assets)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    result = cli.main(
        [
            "crawl",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert calls["download"] == 0
    assert (tmp_path / "asset_manifest.json").exists()


def test_migrate_main_can_skip_asset_download_and_exit_zero(
    monkeypatch, tmp_path
) -> None:
    calls = {"download": 0, "astro": 0}

    monkeypatch.setattr(
        cli, "build_client", lambda *args, **kwargs: DummyClientContext()
    )
    monkeypatch.setattr(cli, "prepare_storage_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "probe_site", lambda *args, **kwargs: make_probe())
    monkeypatch.setattr(cli, "crawl_site", lambda *args, **kwargs: make_snapshot())
    monkeypatch.setattr(cli, "build_report", lambda *args, **kwargs: make_report())
    monkeypatch.setattr(
        cli,
        "estimate_snapshot_asset_download",
        lambda *args, **kwargs: make_asset_estimate(),
    )

    def fake_download_snapshot_assets(
        _client, _snapshot, _output_dir, **_kwargs
    ) -> AssetManifest:
        calls["download"] += 1
        return AssetManifest(generated_at="2026-04-05T00:00:00+00:00")

    def fake_generate_astro_project(*_args, **_kwargs):
        calls["astro"] += 1
        raise AssertionError("generate_astro_project should not be called")

    monkeypatch.setattr(cli, "download_snapshot_assets", fake_download_snapshot_assets)
    monkeypatch.setattr(cli, "generate_astro_project", fake_generate_astro_project)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    result = cli.main(
        [
            "migrate",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert calls["download"] == 0
    assert calls["astro"] == 0
    assert (tmp_path / "asset_manifest.json").exists()


def test_probe_main_quiet_suppresses_summary_output(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(
        cli, "build_client", lambda *args, **kwargs: DummyClientContext()
    )
    monkeypatch.setattr(cli, "prepare_storage_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "probe_site", lambda *args, **kwargs: make_probe())

    result = cli.main(
        [
            "probe",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
            "--quiet",
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert captured.out == ""
