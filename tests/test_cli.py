import argparse
import shutil
from pathlib import Path

import pytest

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


def make_astro_result(output_dir: Path) -> AstroGenerationResult:
    return AstroGenerationResult(
        generated_at="2026-04-05T00:00:00+00:00",
        output_dir=str(output_dir),
        manifest_path="migration-manifest.json",
        pages_written=1,
        posts_written=0,
        warnings=[],
    )


def _require_symlink_support(tmp_path: Path) -> None:
    target_dir = tmp_path / ".symlink-support-target"
    link_path = tmp_path / ".symlink-support-link"
    target_dir.mkdir()
    try:
        link_path.symlink_to(target_dir, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("Symlinks are not supported on this platform")
    finally:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        if target_dir.exists():
            shutil.rmtree(target_dir)


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
            "--upgrade-legacy-assets",
            "--clean",
        ]
    )
    migrate_args = parser.parse_args(
        [
            "migrate",
            "https://example.com",
            "--choose-layout-strategy",
            "--clean",
        ]
    )

    assert generate_args.fidelity_mode == "balanced"
    assert generate_args.layout_strategy == "components"
    assert generate_args.markdown_first is True
    assert generate_args.upgrade_legacy_assets is True
    assert generate_args.clean is True
    assert migrate_args.choose_layout_strategy is True
    assert migrate_args.clean is True
    assert not hasattr(migrate_args, "upgrade_legacy_assets")


def test_probe_main_checks_storage_state_warnings_before_network_work(
    monkeypatch, tmp_path, capsys
) -> None:
    storage_state = tmp_path / "storage_state.json"
    cli.write_json(storage_state, {"cookies": [], "origins": []})
    events: list[str] = []

    class TrackingClientContext:
        def __enter__(self) -> object:
            events.append("build_client")
            assert events[0] == "check"
            return object()

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_check_storage_state(path: Path) -> list[str]:
        events.append("check")
        assert path == storage_state
        return ["Storage state file contains no cookies."]

    def fake_apply_storage_state_cookies(client, path) -> None:
        events.append("apply")
        assert path == storage_state

    def fake_probe_site(*args, **kwargs):
        events.append("probe")
        return make_probe()

    monkeypatch.setattr(cli, "check_storage_state", fake_check_storage_state)
    monkeypatch.setattr(
        cli, "build_client", lambda *args, **kwargs: TrackingClientContext()
    )
    monkeypatch.setattr(cli, "apply_storage_state_cookies", fake_apply_storage_state_cookies)
    monkeypatch.setattr(cli, "probe_site", fake_probe_site)

    result = cli.main(
        [
            "probe",
            "https://example.com",
            "--output-dir",
            str(tmp_path),
            "--storage-state",
            str(storage_state),
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert events == ["check", "build_client", "apply", "probe"]
    assert "Warning: Storage state file contains no cookies." in captured.out


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
            "--upgrade-legacy-assets",
        ]
    )

    assert result == 0
    assert captured["fidelity_mode"] == "balanced"
    assert captured["layout_strategy"] == "components"
    assert captured["markdown_first"] is True
    assert captured["upgrade_legacy_assets"] is True


def test_generate_astro_main_clean_removes_stale_files(monkeypatch, tmp_path) -> None:
    output_dir = tmp_path / "astro-site"
    output_dir.mkdir(parents=True)
    (output_dir / "stale.txt").write_text("stale", encoding="utf-8")

    def fake_generate_astro_project(*, snapshot_path, output_dir, **kwargs):
        cli.write_json(
            output_dir / "migration-manifest.json",
            {"pages": [], "posts": []},
        )
        return make_astro_result(output_dir)

    monkeypatch.setattr(cli, "generate_astro_project", fake_generate_astro_project)

    result = cli.main(
        [
            "generate-astro",
            "site_snapshot.json",
            "--output-dir",
            str(output_dir),
            "--clean",
        ]
    )

    assert result == 0
    assert not (output_dir / "stale.txt").exists()
    assert (output_dir / "astro_generation.json").exists()


def test_generate_astro_main_clean_rejects_dangerous_paths(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli,
        "generate_astro_project",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generate_astro_project should not be called")
        ),
    )

    result = cli.main(
        [
            "generate-astro",
            "site_snapshot.json",
            "--output-dir",
            "/",
            "--clean",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "refusing to clean dangerous path /" in captured.out


def test_clean_output_dir_refuses_symlink_to_protected_snapshot(
    tmp_path: Path,
) -> None:
    _require_symlink_support(tmp_path)

    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    output_dir = tmp_path / "astro-site"
    output_dir.symlink_to(snapshot_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="protected path"):
        cli.clean_output_dir(output_dir, protected_paths=[snapshot_dir])

    assert output_dir.is_symlink()
    assert snapshot_dir.exists()


def test_clean_output_dir_unlinks_non_protected_symlink_without_deleting_target(
    tmp_path: Path,
) -> None:
    _require_symlink_support(tmp_path)

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "keep.txt").write_text("keep", encoding="utf-8")
    output_dir = tmp_path / "astro-site"
    output_dir.symlink_to(target_dir, target_is_directory=True)

    cli.clean_output_dir(output_dir)

    assert not output_dir.exists()
    assert target_dir.exists()
    assert (target_dir / "keep.txt").exists()


def test_shutil_rmtree_removes_symlink_entry_without_deleting_target(
    tmp_path: Path,
) -> None:
    _require_symlink_support(tmp_path)

    output_dir = tmp_path / "astro-site"
    output_dir.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "keep.txt").write_text("keep", encoding="utf-8")
    child_link = output_dir / "linked-child"
    child_link.symlink_to(target_dir, target_is_directory=True)

    assert child_link.is_symlink()

    shutil.rmtree(output_dir)

    assert not output_dir.exists()
    assert target_dir.exists()
    assert (target_dir / "keep.txt").exists()


def test_generate_astro_main_reports_redirect_emission_failures(
    monkeypatch, tmp_path, capsys
) -> None:
    output_dir = tmp_path / "astro-site"

    def fake_generate_astro_project(*, snapshot_path, output_dir, **kwargs):
        cli.write_json(
            output_dir / "migration-manifest.json",
            {"pages": [], "posts": []},
        )
        return make_astro_result(output_dir)

    def fake_write_redirects_json(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "generate_astro_project", fake_generate_astro_project)
    monkeypatch.setattr(cli, "write_redirects_json", fake_write_redirects_json)

    result = cli.main(
        [
            "generate-astro",
            "site_snapshot.json",
            "--output-dir",
            str(output_dir),
            "--emit-redirects",
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "Warning: failed to emit redirects: boom" in captured.out


def test_migrate_main_clean_removes_stale_astro_output_without_touching_crawl_output(
    monkeypatch, tmp_path
) -> None:
    output_dir = tmp_path
    astro_dir = output_dir / "astro-site"
    astro_dir.mkdir(parents=True)
    (astro_dir / "stale.txt").write_text("stale", encoding="utf-8")
    (output_dir / "crawl-stale.txt").write_text("crawl", encoding="utf-8")
    captured: dict[str, object] = {}

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
        return AssetManifest(generated_at="2026-04-05T00:00:00+00:00")

    def fake_generate_astro_project(*, snapshot_path, output_dir, **kwargs):
        captured.update(kwargs)
        cli.write_json(
            output_dir / "migration-manifest.json",
            {"pages": [], "posts": []},
        )
        return make_astro_result(output_dir)

    monkeypatch.setattr(cli, "download_snapshot_assets", fake_download_snapshot_assets)
    monkeypatch.setattr(cli, "generate_astro_project", fake_generate_astro_project)

    result = cli.main(
        [
            "migrate",
            "https://example.com",
            "--output-dir",
            str(output_dir),
            "--clean",
            "--yes",
        ]
    )

    assert result == 0
    assert captured["upgrade_legacy_assets"] is False
    assert not (astro_dir / "stale.txt").exists()
    assert (output_dir / "crawl-stale.txt").exists()


def test_migrate_main_reports_redirect_emission_failures(
    monkeypatch, tmp_path, capsys
) -> None:
    output_dir = tmp_path
    astro_dir = output_dir / "astro-site"
    captured: dict[str, object] = {}

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
        return AssetManifest(generated_at="2026-04-05T00:00:00+00:00")

    def fake_generate_astro_project(*, snapshot_path, output_dir, **kwargs):
        captured.update(kwargs)
        cli.write_json(
            output_dir / "migration-manifest.json",
            {"pages": [], "posts": []},
        )
        return make_astro_result(output_dir)

    def fake_write_redirects_json(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "download_snapshot_assets", fake_download_snapshot_assets)
    monkeypatch.setattr(cli, "generate_astro_project", fake_generate_astro_project)
    monkeypatch.setattr(cli, "write_redirects_json", fake_write_redirects_json)

    result = cli.main(
        [
            "migrate",
            "https://example.com",
            "--output-dir",
            str(output_dir),
            "--emit-redirects",
            "--yes",
        ]
    )

    captured_out = capsys.readouterr().out

    assert result == 0
    assert captured["upgrade_legacy_assets"] is False
    assert "Warning: failed to emit redirects: boom" in captured_out


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


def test_crawl_main_passes_path_output_dir_to_crawl_site(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli, "build_client", lambda *args, **kwargs: DummyClientContext()
    )
    monkeypatch.setattr(cli, "prepare_storage_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "probe_site", lambda *args, **kwargs: make_probe())

    def fake_crawl_site(client, probe, output_dir, **kwargs) -> CrawlSnapshot:
        captured["output_dir"] = output_dir
        return make_snapshot()

    monkeypatch.setattr(cli, "crawl_site", fake_crawl_site)
    monkeypatch.setattr(cli, "build_report", lambda *args, **kwargs: make_report())
    monkeypatch.setattr(
        cli,
        "estimate_snapshot_asset_download",
        lambda *args, **kwargs: make_asset_estimate(),
    )
    monkeypatch.setattr(
        cli,
        "download_snapshot_assets",
        lambda *args, **kwargs: AssetManifest(generated_at="2026-04-05T00:00:00+00:00"),
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
    assert isinstance(captured["output_dir"], Path)
    assert captured["output_dir"] == tmp_path


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
