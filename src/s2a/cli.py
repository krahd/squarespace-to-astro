from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

from s2a import __version__
from s2a.extract.assets import (
    AssetDownloadEstimate,
    AssetManifestUpgradeError,
    download_snapshot_assets,
    estimate_snapshot_asset_download,
)
from s2a.extract.auth import apply_storage_state_cookies, capture_storage_state
from s2a.extract.auth import check_storage_state
from s2a.extract.crawl import crawl_site
from s2a.extract.xml_import import import_wordpress_xml
from s2a.files import write_json, read_json
from s2a.generate.astro import generate_astro_project as _generate_astro_project
from s2a.generate.redirects import (
    build_redirect_summary,
    build_redirects_from_manifest,
    write_redirect_report,
    write_redirects_json,
    write_netlify_redirects,
)
from s2a.net import build_client
from s2a.normalize.models import AssetManifest, AstroGenerationResult
from s2a.normalize.transform import build_report
from s2a.probe import probe_site

EXECUTION_METADATA_FILE = "execution-metadata.json"
SENSITIVE_ARGUMENTS = {"password", "site_password"}
FIDELITY_MODES = ("high", "balanced", "minimal")
LAYOUT_STRATEGIES = ("hybrid", "components")


def generate_astro_project(
    snapshot_path: Path,
    output_dir: Path,
    xml_import_path: Path | None = None,
    site_url: str | None = None,
    base_path: str | None = None,
    project_name: str | None = None,
    fidelity_mode: str = "high",
    layout_strategy: str = "hybrid",
    markdown_first: bool = False,
    upgrade_legacy_assets: bool = False,
) -> AstroGenerationResult:
    kwargs: dict[str, Any] = {
        "snapshot_path": snapshot_path,
        "output_dir": output_dir,
        "xml_import_path": xml_import_path,
        "site_url": site_url,
        "base_path": base_path,
        "project_name": project_name,
        "fidelity_mode": fidelity_mode,
        "layout_strategy": layout_strategy,
        "markdown_first": markdown_first,
        "upgrade_legacy_assets": upgrade_legacy_assets,
    }
    return _generate_astro_project(**kwargs)


@dataclass(slots=True)
class Console:
    quiet: bool
    progress_width: int = 28
    _progress_active: bool = False
    _last_progress_length: int = 0

    def emit(self, message: str, *, always: bool = False) -> None:
        if self.quiet and not always:
            return
        self.finish_progress()
        print(message)

    def prompt_confirm(
        self,
        message: str,
        *,
        assume_yes: bool = False,
        default: bool = False,
    ) -> bool:
        self.finish_progress()
        if assume_yes:
            return True

        prompt_suffix = "[Y/n]" if default else "[y/N]"
        while True:
            response = input(f"{message} {prompt_suffix} ").strip().lower()
            if not response:
                return default
            if response in {"y", "yes"}:
                return True
            if response in {"n", "no"}:
                return False
            print("Please respond with 'y' or 'n'.")

    def progress_callback(self, label: str):
        def callback(completed: int, total: int, detail: str | None = None) -> None:
            self.render_progress(label, completed, total, detail)

        return callback

    def render_progress(
        self, label: str, completed: int, total: int, detail: str | None = None
    ) -> None:
        if self.quiet or total <= 0:
            return

        safe_total = max(total, 1)
        safe_completed = max(0, min(completed, safe_total))
        percentage = int((safe_completed / safe_total) * 100)
        filled_width = int((safe_completed / safe_total) * self.progress_width)
        bar = "#" * filled_width + "-" * (self.progress_width - filled_width)
        detail_suffix = f" {detail}" if detail else ""
        line = f"{label:<20} [{bar}] {percentage:>3}% {safe_completed}/{safe_total}{detail_suffix}"
        padding = " " * max(0, self._last_progress_length - len(line))
        print(f"\r{line}{padding}", end="", flush=True)
        self._progress_active = True
        self._last_progress_length = len(line)

        if safe_completed >= safe_total:
            self.finish_progress()

    def finish_progress(self) -> None:
        if not self._progress_active:
            return

        print()
        self._progress_active = False
        self._last_progress_length = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s2a",
        description="Probe, extract, and generate a static-site migration path for Squarespace.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser(
        "probe", help="Inspect a site and write a capability report."
    )
    add_shared_arguments(probe_parser)
    add_auth_arguments(probe_parser)
    add_interaction_arguments(probe_parser)
    probe_parser.add_argument(
        "--max-sitemap-urls",
        type=int,
        default=200,
        help="Maximum number of sitemap URLs to record in the probe output.",
    )

    crawl_parser = subparsers.add_parser(
        "crawl", help="Probe and crawl a site into a structured snapshot."
    )
    add_shared_arguments(crawl_parser)
    add_auth_arguments(crawl_parser)
    add_interaction_arguments(crawl_parser)
    crawl_parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum number of HTML pages to crawl.",
    )
    crawl_parser.add_argument(
        "--max-sitemap-urls",
        type=int,
        default=200,
        help="Maximum number of sitemap URLs to record and use as crawl seeds.",
    )

    auth_parser = subparsers.add_parser(
        "auth-browser",
        help="Open a Chromium session with Playwright and save storage_state.json for later crawl runs.",
    )
    add_shared_arguments(auth_parser)
    add_auth_arguments(auth_parser)
    add_interaction_arguments(auth_parser)

    xml_parser = subparsers.add_parser(
        "import-xml",
        help="Import a Squarespace WordPress XML export into normalized JSON.",
    )
    add_interaction_arguments(xml_parser)
    xml_parser.add_argument("xml_file", help="Path to the WordPress XML export file.")
    xml_parser.add_argument(
        "--output-dir",
        help="Directory for the normalized XML import JSON file. Defaults to a unique folder under site-output/.",
    )

    astro_parser = subparsers.add_parser(
        "generate-astro", help="Generate a buildable Astro project from crawl output."
    )
    add_interaction_arguments(astro_parser)
    astro_parser.add_argument("snapshot", help="Path to site_snapshot.json.")
    astro_parser.add_argument(
        "--output-dir",
        help="Directory where the Astro project should be created. Defaults to generated/astro-site.",
    )
    astro_parser.add_argument(
        "--xml-import",
        help="Optional path to xml_import.json from the import-xml command.",
    )
    astro_parser.add_argument(
        "--xml-export",
        help="Optional path to the raw Squarespace WordPress XML export file.",
    )
    astro_parser.add_argument(
        "--site",
        help="Optional final production site URL to write into astro.config.mjs.",
    )
    astro_parser.add_argument(
        "--base",
        help="Optional Astro base path, useful for GitHub Pages project sites.",
    )
    astro_parser.add_argument(
        "--project-name",
        help="Optional package name for the generated Astro project.",
    )
    astro_parser.add_argument(
        "--emit-redirects",
        action="store_true",
        help="Emit redirects.json and netlify/_redirects for the generated site.",
    )
    astro_parser.add_argument(
        "--upgrade-legacy-assets",
        action="store_true",
        help="Upgrade legacy asset_manifest.json filenames in the snapshot root before generating the Astro project.",
    )
    astro_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the Astro output directory before writing the generated project.",
    )
    add_fidelity_arguments(astro_parser)

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Run probe, crawl, optional XML import, and Astro generation as one workflow.",
    )
    add_shared_arguments(migrate_parser)
    add_auth_arguments(migrate_parser)
    add_interaction_arguments(migrate_parser)
    migrate_parser.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Maximum number of HTML pages to crawl during migrate. Defaults to 200.",
    )
    migrate_parser.add_argument(
        "--max-sitemap-urls",
        type=int,
        default=200,
        help="Maximum number of sitemap URLs to record and use as crawl seeds.",
    )
    migrate_parser.add_argument(
        "--xml-export",
        help="Optional path to a Squarespace WordPress XML export to merge into the migration.",
    )
    migrate_parser.add_argument(
        "--astro-dir",
        help="Optional output directory for the generated Astro site. Defaults to <output-dir>/astro-site.",
    )
    migrate_parser.add_argument(
        "--site",
        help="Optional final production site URL to write into astro.config.mjs.",
    )
    migrate_parser.add_argument(
        "--base",
        help="Optional Astro base path, useful for GitHub Pages project sites.",
    )
    migrate_parser.add_argument(
        "--project-name",
        help="Optional package name for the generated Astro project.",
    )
    add_fidelity_arguments(migrate_parser)
    migrate_parser.add_argument(
        "--emit-redirects",
        action="store_true",
        help="Emit redirects.json and netlify/_redirects when generate-astro runs inside migrate.",
    )
    migrate_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the Astro output directory before writing the generated project.",
    )

    return parser


def add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="Target site URL or host name.")
    parser.add_argument(
        "--output-dir",
        help="Directory for JSON reports and raw page captures. Defaults to a unique folder under site-output/.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for browser auth capture and crawl requests. Use only after confirming the URL is correct.",
    )


def add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--storage-state",
        help="Path to a Playwright storage_state.json file whose cookies should be reused for crawl requests.",
    )
    parser.add_argument(
        "--site-password",
        help="Password to submit on a site-wide Squarespace password gate before crawling.",
    )
    parser.add_argument(
        "--login-url",
        help="Optional login page URL for browser auth capture. Defaults to the target URL.",
    )
    parser.add_argument(
        "--username",
        help="Optional username or email to auto-fill in a browser auth flow. Overrides SQUARESPACE_USER.",
    )
    parser.add_argument(
        "--password",
        help="Optional password to auto-fill in a browser auth flow. Overrides SQUARESPACE_PWD.",
    )
    parser.add_argument(
        "--manual-auth",
        action="store_true",
        help="Pause for an interactive login in the Playwright browser before saving storage state.",
    )
    parser.add_argument(
        "--auth-headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Playwright auth capture in headless mode unless interactive login is required.",
    )


def add_interaction_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-confirm CLI confirmation prompts.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output and final summaries while still showing prompts and fatal errors.",
    )


def add_fidelity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fidelity-mode",
        choices=FIDELITY_MODES,
        default="high",
        help="How aggressively the generator should preserve Squarespace layout structure. Defaults to high.",
    )
    parser.add_argument(
        "--layout-strategy",
        choices=LAYOUT_STRATEGIES,
        help="How to handle layout-heavy pages such as gallery and portfolio grids.",
    )
    parser.add_argument(
        "--choose-layout-strategy",
        action="store_true",
        help="Prompt for the layout strategy at runtime instead of silently using the default.",
    )
    parser.add_argument(
        "-md",
        "--markdown",
        dest="markdown_first",
        action="store_true",
        help="Prefer Markdown output when the conversion is acceptable, only keeping HTML for layout-heavy content.",
    )


def resolve_auth_credentials(args: argparse.Namespace) -> tuple[str | None, str | None]:
    username = getattr(args, "username", None) or os.environ.get("SQUARESPACE_USER")
    password = getattr(args, "password", None) or os.environ.get("SQUARESPACE_PWD")
    return username, password


def default_layout_strategy_for_mode(_fidelity_mode: str) -> str:
    return "hybrid"


def prompt_layout_strategy(console: Console, default: str) -> str:
    console.finish_progress()
    default_choice = "1" if default == "hybrid" else "2"
    console.emit("Choose layout strategy for layout-heavy pages:", always=True)
    console.emit(
        "  1. hybrid     Preserve Squarespace HTML and style it in Astro.", always=True
    )
    console.emit(
        "  2. components Rebuild known gallery/grid patterns into Astro-friendly markup.",
        always=True,
    )

    while True:
        response = input(f"Layout strategy [{default_choice}]: ").strip().lower()
        if not response:
            return default
        if response in {"1", "hybrid"}:
            return "hybrid"
        if response in {"2", "components"}:
            return "components"
        print("Please choose 1/hybrid or 2/components.")


def resolve_generation_options(
    console: Console, args: argparse.Namespace
) -> tuple[str, str, bool]:
    fidelity_mode = getattr(args, "fidelity_mode", "high")
    layout_strategy = getattr(args, "layout_strategy", None)
    choose_layout_strategy = getattr(args, "choose_layout_strategy", False)
    markdown_first = getattr(args, "markdown_first", False)

    if layout_strategy:
        return fidelity_mode, layout_strategy, markdown_first

    default_layout_strategy = default_layout_strategy_for_mode(fidelity_mode)

    if not choose_layout_strategy:
        return fidelity_mode, default_layout_strategy, markdown_first

    if getattr(args, "yes", False):
        console.emit(
            f"Layout strategy defaulted to {default_layout_strategy} because --yes skips interactive selection."
        )
        return fidelity_mode, default_layout_strategy, markdown_first

    return (
        fidelity_mode,
        prompt_layout_strategy(console, default_layout_strategy),
        markdown_first,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console(quiet=getattr(args, "quiet", False))
    output_dir, used_default_output_dir = resolve_output_dir(args)

    if args.command == "import-xml":
        output_dir.mkdir(parents=True, exist_ok=True)
        xml_import = import_wordpress_xml(Path(args.xml_file))
        write_json(output_dir / "xml_import.json", xml_import)
        write_execution_metadata(
            output_dir,
            args,
            used_default_output_dir=used_default_output_dir,
            artifacts={"xml_import": "xml_import.json"},
        )
        print_xml_summary(console, output_dir, xml_import)
        return 0

    if args.command == "generate-astro":
        if getattr(args, "clean", False):
            try:
                clean_output_dir(
                    output_dir, protected_paths=[Path(args.snapshot).parent]
                )
            except (OSError, ValueError) as exc:
                console.emit(f"Warning: {exc}", always=True)
                return 1
        output_dir.mkdir(parents=True, exist_ok=True)
        fidelity_mode, layout_strategy, markdown_first = resolve_generation_options(
            console, args
        )
        args.fidelity_mode = fidelity_mode
        args.layout_strategy = layout_strategy
        args.markdown_first = markdown_first
        xml_input_path = resolve_xml_input(
            xml_import_path=args.xml_import,
            xml_export_path=args.xml_export,
            work_dir=output_dir,
        )
        try:
            result = generate_astro_project(
                snapshot_path=Path(args.snapshot),
                output_dir=output_dir,
                xml_import_path=xml_input_path,
                site_url=args.site,
                base_path=args.base,
                project_name=args.project_name,
                fidelity_mode=fidelity_mode,
                layout_strategy=layout_strategy,
                markdown_first=markdown_first,
                upgrade_legacy_assets=args.upgrade_legacy_assets,
            )
        except AssetManifestUpgradeError as exc:
            console.emit(str(exc), always=True)
            return 1
        write_json(output_dir / "astro_generation.json", result)

        # Write a lightweight migration report summarizing counts (non-fatal)
        try:
            manifest = read_json(output_dir / "migration-manifest.json")
            astro_gen = read_json(output_dir / "astro_generation.json")
            pages = manifest.get("pages", [])
            posts = manifest.get("posts", [])
            assets = manifest.get("assets", [])
            report_summary = {
                "pages": len(pages),
                "posts": len(posts),
                "assets": len(assets),
                "pages_written": (
                    astro_gen.get("pages_written")
                    if isinstance(astro_gen, dict)
                    else None
                ),
                "posts_written": (
                    astro_gen.get("posts_written")
                    if isinstance(astro_gen, dict)
                    else None
                ),
                "warnings": manifest.get("warnings", []),
            }
            write_json(output_dir / "migration-report.json", report_summary)
        except Exception as exc:
            # Non-fatal: do not block generation on report serialization
            console.emit(f"Warning: failed to write migration report: {exc}")
        # Optionally emit redirects based on the generated migration manifest
        if getattr(args, "emit_redirects", False):
            try:
                manifest = read_json(output_dir / "migration-manifest.json")
                redirects = build_redirects_from_manifest(manifest)
                summary = build_redirect_summary(manifest, redirects)
                write_redirects_json(output_dir, redirects)
                write_netlify_redirects(output_dir, redirects)
                write_redirect_report(output_dir, redirects, summary)
            except Exception as exc:
                # Non-fatal: redirect generation should not block normal output
                console.emit(f"Warning: failed to emit redirects: {exc}", always=True)
        write_execution_metadata(
            output_dir,
            args,
            used_default_output_dir=used_default_output_dir,
            artifacts={
                "astro_generation": "astro_generation.json",
                "migration_manifest": "migration-manifest.json",
                "asset_manifest": relative_artifact_if_exists(
                    Path(args.snapshot).parent, output_dir
                ),
            },
        )
        print_astro_summary(console, output_dir, result)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    username, password = resolve_auth_credentials(args)

    if args.command == "auth-browser":
        report = capture_storage_state(
            target_url=args.target,
            output_dir=output_dir,
            login_url=args.login_url,
            site_password=args.site_password,
            username=username,
            password=password,
            manual=args.manual_auth,
            headless=args.auth_headless,
            insecure=args.insecure,
        )
        write_json(output_dir / "auth.json", report)
        try:
            (output_dir / "auth.json").chmod(0o600)
            (output_dir / "auth").chmod(0o700)
        except OSError:
            pass
        write_execution_metadata(
            output_dir,
            args,
            used_default_output_dir=used_default_output_dir,
            artifacts={
                "auth_report": "auth.json",
                "storage_state": report.storage_state_path,
            },
        )
        print_auth_summary(console, output_dir, report)
        return 0

    storage_state_path = prepare_storage_state(
        args,
        output_dir,
        username=username,
        password=password,
    )
    if storage_state_path is not None:
        emit_storage_state_warnings(console, storage_state_path)

    with build_client(args.timeout, verify=not args.insecure) as client:
        if storage_state_path:
            apply_storage_state_cookies(client, storage_state_path)

        if args.command == "probe":
            probe = probe_site(
                client, args.target, max_sitemap_urls=args.max_sitemap_urls
            )
            write_json(output_dir / "probe.json", probe)
            write_execution_metadata(
                output_dir,
                args,
                used_default_output_dir=used_default_output_dir,
                artifacts=build_probe_artifacts(output_dir),
            )
            print_probe_summary(console, output_dir, probe)
            return 0

        if args.command == "crawl":
            probe = probe_site(
                client, args.target, max_sitemap_urls=args.max_sitemap_urls
            )
            snapshot = crawl_site(
                client,
                probe,
                output_dir,
                max_pages=args.max_pages,
                progress_callback=console.progress_callback("Crawling pages"),
            )
            report = build_report(snapshot)
            asset_manifest, asset_download_skipped = run_asset_download_workflow(
                console,
                client=client,
                snapshot=snapshot,
                output_dir=output_dir,
                assume_yes=args.yes,
            )
            write_crawl_output_files(
                output_dir, probe, snapshot, asset_manifest, report
            )
            write_execution_metadata(
                output_dir,
                args,
                used_default_output_dir=used_default_output_dir,
                artifacts=build_crawl_artifacts(output_dir),
            )
            print_crawl_summary(
                console,
                output_dir,
                report,
                asset_manifest,
                note=(
                    "asset download skipped by user" if asset_download_skipped else None
                ),
            )
            return 0

        if args.command == "migrate":
            probe = probe_site(
                client, args.target, max_sitemap_urls=args.max_sitemap_urls
            )
            snapshot = crawl_site(
                client,
                probe,
                output_dir,
                max_pages=args.max_pages,
                progress_callback=console.progress_callback("Crawling pages"),
            )
            report = build_report(snapshot)
            asset_manifest, asset_download_skipped = run_asset_download_workflow(
                console,
                client=client,
                snapshot=snapshot,
                output_dir=output_dir,
                assume_yes=args.yes,
            )
            write_crawl_output_files(
                output_dir, probe, snapshot, asset_manifest, report
            )

            if asset_download_skipped:
                write_execution_metadata(
                    output_dir,
                    args,
                    used_default_output_dir=used_default_output_dir,
                    artifacts=build_migrate_artifacts(output_dir),
                )
                print_migrate_cancelled_summary(console, output_dir, report)
                return 0

            xml_import_path = None
            if args.xml_export:
                xml_import = import_wordpress_xml(Path(args.xml_export))
                xml_import_path = output_dir / "xml_import.json"
                write_json(xml_import_path, xml_import)

            astro_dir = (
                Path(args.astro_dir) if args.astro_dir else output_dir / "astro-site"
            )
            if getattr(args, "clean", False):
                try:
                    clean_output_dir(astro_dir, protected_paths=[output_dir])
                except (OSError, ValueError) as exc:
                    console.emit(f"Warning: {exc}", always=True)
                    return 1
            astro_dir.mkdir(parents=True, exist_ok=True)
            fidelity_mode, layout_strategy, markdown_first = resolve_generation_options(
                console, args
            )
            args.fidelity_mode = fidelity_mode
            args.layout_strategy = layout_strategy
            args.markdown_first = markdown_first
            try:
                astro_result = generate_astro_project(
                    snapshot_path=output_dir / "site_snapshot.json",
                    output_dir=astro_dir,
                    xml_import_path=xml_import_path,
                    site_url=args.site,
                    base_path=args.base,
                    project_name=args.project_name,
                    fidelity_mode=fidelity_mode,
                    layout_strategy=layout_strategy,
                    markdown_first=markdown_first,
                    upgrade_legacy_assets=False,
                )
            except AssetManifestUpgradeError as exc:
                console.emit(str(exc), always=True)
                return 1
            write_json(output_dir / "astro_generation.json", astro_result)
            # Optionally emit redirects into the Astro output dir
            if getattr(args, "emit_redirects", False):
                try:
                    manifest = read_json(astro_dir / "migration-manifest.json")
                    redirects = build_redirects_from_manifest(manifest)
                    summary = build_redirect_summary(manifest, redirects)
                    write_redirects_json(astro_dir, redirects)
                    write_netlify_redirects(astro_dir, redirects)
                    write_redirect_report(astro_dir, redirects, summary)
                except Exception as exc:
                    console.emit(f"Warning: failed to emit redirects: {exc}", always=True)
            write_execution_metadata(
                output_dir,
                args,
                used_default_output_dir=used_default_output_dir,
                artifacts=build_migrate_artifacts(
                    output_dir, astro_dir=astro_dir, xml_import_path=xml_import_path
                ),
            )
            print_migrate_summary(
                console, output_dir, report, astro_dir, astro_result, asset_manifest
            )
            return 0

    return 1


def prepare_storage_state(
    args: argparse.Namespace,
    output_dir: Path,
    username: str | None = None,
    password: str | None = None,
) -> Path | None:
    if getattr(args, "storage_state", None):
        return Path(args.storage_state)

    should_capture = any(
        (
            getattr(args, "site_password", None),
            getattr(args, "login_url", None),
            getattr(args, "username", None),
            getattr(args, "password", None),
        )
    ) or getattr(args, "manual_auth", False)

    if not should_capture:
        return None

    if username is None or password is None:
        resolved_username, resolved_password = resolve_auth_credentials(args)
        if username is None:
            username = resolved_username
        if password is None:
            password = resolved_password

    report = capture_storage_state(
        target_url=args.target,
        output_dir=output_dir,
        login_url=args.login_url,
        site_password=args.site_password,
        username=username,
        password=password,
        manual=args.manual_auth,
        headless=args.auth_headless,
        insecure=args.insecure,
    )
    write_json(output_dir / "auth.json", report)
    try:
        (output_dir / "auth.json").chmod(0o600)
        (output_dir / "auth").chmod(0o700)
    except OSError:
        pass
    return output_dir / report.storage_state_path


def emit_storage_state_warnings(console: Console, storage_state_path: Path) -> None:
    for warning in check_storage_state(storage_state_path):
        console.emit(f"Warning: {warning}", always=True)


def resolve_xml_input(
    xml_import_path: str | None, xml_export_path: str | None, work_dir: Path
) -> Path | None:
    if xml_import_path:
        return Path(xml_import_path)

    if not xml_export_path:
        return None

    imported = import_wordpress_xml(Path(xml_export_path))
    target_path = work_dir / "xml_import.json"
    write_json(target_path, imported)
    return target_path


def resolve_output_dir(args: argparse.Namespace) -> tuple[Path, bool]:
    requested_output_dir = getattr(args, "output_dir", None)
    if requested_output_dir:
        return Path(requested_output_dir), False

    if args.command == "generate-astro":
        return Path("generated/astro-site"), True

    if args.command == "import-xml":
        return (
            build_default_output_dir(args.command, slugify_file_label(args.xml_file)),
            True,
        )

    return (
        build_default_output_dir(args.command, slugify_target_label(args.target)),
        True,
    )


def build_default_output_dir(command: str, label: str) -> Path:
    return Path("site-output") / f"{output_dir_timestamp()}-{command}-{label}"


def clean_output_dir(
    output_dir: Path, *, protected_paths: Sequence[Path] = ()
) -> None:
    validate_clean_output_dir(output_dir, protected_paths=protected_paths)
    if output_dir.is_symlink():
        output_dir.unlink()
        return

    if not output_dir.exists():
        return

    if output_dir.is_file():
        output_dir.unlink()
        return

    shutil.rmtree(output_dir)


def validate_clean_output_dir(
    output_dir: Path, *, protected_paths: Sequence[Path] = ()
) -> Path:
    if not str(output_dir).strip():
        raise ValueError("refusing to clean an empty path")

    resolved_output_dir = output_dir.expanduser().resolve(strict=False)
    forbidden_paths = {
        Path("/").resolve(),
        Path.cwd().resolve(),
        Path.home().resolve(),
    }
    if resolved_output_dir in forbidden_paths:
        raise ValueError(f"refusing to clean dangerous path {resolved_output_dir}")

    for protected_path in protected_paths:
        resolved_protected_path = protected_path.expanduser().resolve(strict=False)
        if resolved_protected_path == resolved_output_dir:
            raise ValueError(
                f"refusing to clean {resolved_output_dir} because it would delete the protected path {resolved_protected_path}"
            )
        if resolved_protected_path.is_relative_to(resolved_output_dir):
            raise ValueError(
                f"refusing to clean {resolved_output_dir} because it contains the protected path {resolved_protected_path}"
            )

    return resolved_output_dir


def output_dir_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def slugify_target_label(target: str) -> str:
    parsed = urlsplit(target if "://" in target else f"https://{target}")
    candidate = parsed.netloc or parsed.path.split("/")[0] or target
    return slugify_label(candidate)


def slugify_file_label(path_value: str) -> str:
    return slugify_label(Path(path_value).stem or path_value)


def slugify_label(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "run"


def write_execution_metadata(
    output_dir: Path,
    args: argparse.Namespace,
    *,
    used_default_output_dir: bool,
    artifacts: dict[str, Any],
) -> None:
    write_json(
        output_dir / EXECUTION_METADATA_FILE,
        build_execution_metadata(
            args,
            output_dir,
            used_default_output_dir=used_default_output_dir,
            artifacts=artifacts,
        ),
    )


def build_execution_metadata(
    args: argparse.Namespace,
    output_dir: Path,
    *,
    used_default_output_dir: bool,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "tool_version": __version__,
        "command": args.command,
        "output_dir": str(output_dir),
        "used_default_output_dir": used_default_output_dir,
        "parameters": sanitize_arguments(args),
        "artifacts": {
            key: value for key, value in artifacts.items() if value is not None
        },
    }


def sanitize_arguments(args: argparse.Namespace) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}

    for key, value in sorted(vars(args).items()):
        if key == "command":
            continue
        if key in SENSITIVE_ARGUMENTS and value is not None:
            sanitized[key] = "<redacted>"
            continue
        sanitized[key] = str(value) if isinstance(value, Path) else value

    return sanitized


def build_probe_artifacts(output_dir: Path) -> dict[str, str]:
    artifacts = {"probe": "probe.json"}
    if (output_dir / "auth.json").exists():
        artifacts["auth_report"] = "auth.json"
    return artifacts


def build_crawl_artifacts(output_dir: Path) -> dict[str, str]:
    artifacts = {
        "probe": "probe.json",
        "site_snapshot": "site_snapshot.json",
        "asset_manifest": "asset_manifest.json",
        "report": "report.json",
    }
    if (output_dir / "auth.json").exists():
        artifacts["auth_report"] = "auth.json"
    return artifacts


def build_migrate_artifacts(
    output_dir: Path,
    astro_dir: Path | None = None,
    xml_import_path: Path | None = None,
) -> dict[str, str]:
    artifacts = {
        "probe": "probe.json",
        "site_snapshot": "site_snapshot.json",
        "asset_manifest": "asset_manifest.json",
        "report": "report.json",
    }
    if astro_dir is not None:
        artifacts["astro_generation"] = "astro_generation.json"
        artifacts["astro_output_dir"] = relative_artifact_path(output_dir, astro_dir)
    if xml_import_path:
        artifacts["xml_import"] = relative_artifact_path(output_dir, xml_import_path)
    if (output_dir / "auth.json").exists():
        artifacts["auth_report"] = "auth.json"
    return artifacts


def relative_artifact_path(output_dir: Path, artifact_path: Path) -> str:
    try:
        return str(artifact_path.relative_to(output_dir))
    except ValueError:
        return str(artifact_path)


def relative_artifact_if_exists(snapshot_root: Path, output_dir: Path) -> str | None:
    asset_manifest_path = snapshot_root / "asset_manifest.json"
    if not asset_manifest_path.exists():
        return None
    try:
        return str(asset_manifest_path.relative_to(output_dir))
    except ValueError:
        return str(asset_manifest_path)


def write_crawl_output_files(
    output_dir: Path, probe, snapshot, asset_manifest: AssetManifest, report
) -> None:
    write_json(output_dir / "probe.json", probe)
    write_json(output_dir / "site_snapshot.json", snapshot)
    write_json(output_dir / "asset_manifest.json", asset_manifest)
    write_json(output_dir / "report.json", report)


def run_asset_download_workflow(
    console: Console,
    *,
    client,
    snapshot,
    output_dir: Path,
    assume_yes: bool,
) -> tuple[AssetManifest, bool]:
    asset_estimate = estimate_snapshot_asset_download(
        client,
        snapshot,
        progress_callback=console.progress_callback("Estimating assets"),
    )

    if asset_estimate.asset_count == 0:
        console.emit("No Squarespace-hosted assets detected for download.")
        return build_empty_asset_manifest(), False

    estimate_message = describe_asset_download_estimate(asset_estimate)
    if assume_yes:
        console.emit(f"{estimate_message} Auto-confirmed by --yes.")
    elif not console.prompt_confirm(
        f"{estimate_message} Continue with asset download?"
    ):
        return (
            build_skipped_asset_manifest(
                "Asset download skipped after confirmation prompt."
            ),
            True,
        )

    return (
        download_snapshot_assets(
            client,
            snapshot,
            output_dir,
            estimate=asset_estimate,
            progress_callback=console.progress_callback("Downloading assets"),
        ),
        False,
    )


def build_empty_asset_manifest() -> AssetManifest:
    return AssetManifest(generated_at=datetime.now(UTC).isoformat())


def build_skipped_asset_manifest(reason: str) -> AssetManifest:
    return AssetManifest(
        generated_at=datetime.now(UTC).isoformat(),
        warnings=[reason],
    )


def describe_asset_download_estimate(asset_estimate: AssetDownloadEstimate) -> str:
    asset_label = "asset" if asset_estimate.asset_count == 1 else "assets"
    if asset_estimate.unknown_size_count == 0:
        return (
            f"Estimated asset download: {format_download_size(asset_estimate.estimated_size_bytes)} "
            f"across {asset_estimate.asset_count} {asset_label}."
        )

    if asset_estimate.estimated_size_bytes == 0:
        return (
            f"Estimated asset download size is unknown across {asset_estimate.asset_count} {asset_label}; "
            "no size metadata was available."
        )

    unknown_label = (
        "asset has" if asset_estimate.unknown_size_count == 1 else "assets have"
    )
    return (
        f"Estimated asset download: at least {format_download_size(asset_estimate.estimated_size_bytes)} "
        f"across {asset_estimate.asset_count} {asset_label}; "
        f"{asset_estimate.unknown_size_count} {unknown_label} unknown size metadata."
    )


def format_download_size(size_bytes: int) -> str:
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
    return f"{size_bytes / (1024 ** 2):.2f} MB"


def print_probe_summary(console: Console, output_dir: Path, probe) -> None:
    console.emit(
        f"Wrote {output_dir / 'probe.json'} | squarespace={probe.probably_squarespace} | "
        f"json={bool(probe.json_probe and probe.json_probe.available)} | sitemap_urls={len(probe.sitemap_entries)} | "
        f"metadata={output_dir / EXECUTION_METADATA_FILE}"
    )


def print_crawl_summary(
    console: Console,
    output_dir: Path,
    report,
    asset_manifest: AssetManifest,
    *,
    note: str | None = None,
) -> None:
    message = (
        f"Wrote crawl output to {output_dir} | pages={report.pages_crawled} | ok={report.ok_pages} | "
        f"json_pages={report.pages_with_json} | password_pages={report.password_gated_pages} | "
        f"downloaded_assets={len(asset_manifest.items)} | metadata={output_dir / EXECUTION_METADATA_FILE}"
    )
    if note:
        message = f"{message} | note={note}"
    console.emit(message)


def print_auth_summary(console: Console, output_dir: Path, report) -> None:
    console.emit(
        f"Wrote auth output to {output_dir} | mode={report.mode} | cookies={report.cookies_saved} | "
        f"storage_state={report.storage_state_path} | metadata={output_dir / EXECUTION_METADATA_FILE}"
    )


def print_xml_summary(console: Console, output_dir: Path, xml_import) -> None:
    console.emit(
        f"Wrote {output_dir / 'xml_import.json'} | items={len(xml_import.items)} | site={xml_import.site_title or 'unknown'} | "
        f"metadata={output_dir / EXECUTION_METADATA_FILE}"
    )


def print_astro_summary(console: Console, output_dir: Path, result) -> None:
    console.emit(
        f"Generated Astro project at {output_dir} | pages={result.pages_written} | posts={result.posts_written} | "
        f"manifest={result.manifest_path} | metadata={output_dir / EXECUTION_METADATA_FILE}"
    )
    for warning in result.warnings:
        console.emit(f"Warning: {warning}")


def print_migrate_summary(
    console: Console,
    output_dir: Path,
    report,
    astro_dir: Path,
    result,
    asset_manifest: AssetManifest,
) -> None:
    console.emit(
        f"Wrote migration output to {output_dir} | crawled={report.pages_crawled} | downloaded_assets={len(asset_manifest.items)} | "
        f"astro_pages={result.pages_written} | astro_posts={result.posts_written} | astro_dir={astro_dir} | "
        f"metadata={output_dir / EXECUTION_METADATA_FILE}"
    )
    for warning in result.warnings:
        console.emit(f"Warning: {warning}")


def print_migrate_cancelled_summary(console: Console, output_dir: Path, report) -> None:
    console.emit(
        f"Wrote partial migration output to {output_dir} | crawled={report.pages_crawled} | "
        f"asset_download=skipped | astro_generation=skipped | metadata={output_dir / EXECUTION_METADATA_FILE}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
