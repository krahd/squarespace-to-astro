from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from s2a.extract.auth import apply_storage_state_cookies, capture_storage_state
from s2a.extract.crawl import crawl_site
from s2a.extract.xml_import import import_wordpress_xml
from s2a.files import write_json
from s2a.generate.astro import generate_astro_project
from s2a.net import build_client
from s2a.normalize.transform import build_report
from s2a.probe import probe_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s2a",
        description="Probe, extract, and generate a static-site migration path for Squarespace.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser(
        "probe", help="Inspect a site and write a capability report.")
    add_shared_arguments(probe_parser)
    add_auth_arguments(probe_parser)
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

    xml_parser = subparsers.add_parser(
        "import-xml", help="Import a Squarespace WordPress XML export into normalized JSON."
    )
    xml_parser.add_argument("xml_file", help="Path to the WordPress XML export file.")
    xml_parser.add_argument(
        "--output-dir",
        default="site-output/xml-import",
        help="Directory for the normalized XML import JSON file.",
    )

    astro_parser = subparsers.add_parser(
        "generate-astro", help="Generate a buildable Astro project from crawl output."
    )
    astro_parser.add_argument("snapshot", help="Path to site_snapshot.json.")
    astro_parser.add_argument(
        "--output-dir",
        default="generated/astro-site",
        help="Directory where the Astro project should be created.",
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

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Run probe, crawl, optional XML import, and Astro generation as one workflow.",
    )
    add_shared_arguments(migrate_parser)
    add_auth_arguments(migrate_parser)
    migrate_parser.add_argument(
        "--max-pages",
        type=int,
        default=75,
        help="Maximum number of HTML pages to crawl.",
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

    return parser


def add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="Target site URL or host name.")
    parser.add_argument(
        "--output-dir",
        default="site-output/run",
        help="Directory for JSON reports and raw page captures.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
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


def resolve_auth_credentials(args: argparse.Namespace) -> tuple[str | None, str | None]:
    username = getattr(args, "username", None) or os.environ.get("SQUARESPACE_USER")
    password = getattr(args, "password", None) or os.environ.get("SQUARESPACE_PWD")
    return username, password


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "import-xml":
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        xml_import = import_wordpress_xml(Path(args.xml_file))
        write_json(output_dir / "xml_import.json", xml_import)
        print_xml_summary(output_dir, xml_import)
        return 0

    if args.command == "generate-astro":
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        xml_input_path = resolve_xml_input(
            xml_import_path=args.xml_import,
            xml_export_path=args.xml_export,
            work_dir=output_dir,
        )
        result = generate_astro_project(
            snapshot_path=Path(args.snapshot),
            output_dir=output_dir,
            xml_import_path=xml_input_path,
            site_url=args.site,
            base_path=args.base,
            project_name=args.project_name,
        )
        write_json(output_dir / "astro_generation.json", result)
        print_astro_summary(output_dir, result)
        return 0

    output_dir = Path(args.output_dir)
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
        )
        write_json(output_dir / "auth.json", report)
        print_auth_summary(output_dir, report)
        return 0

    storage_state_path = prepare_storage_state(
        args,
        output_dir,
        username=username,
        password=password,
    )

    with build_client(args.timeout) as client:
        if storage_state_path:
            apply_storage_state_cookies(client, storage_state_path)

        if args.command == "probe":
            probe = probe_site(client, args.target, max_sitemap_urls=args.max_sitemap_urls)
            write_json(output_dir / "probe.json", probe)
            print_probe_summary(output_dir, probe)
            return 0

        if args.command == "crawl":
            probe = probe_site(client, args.target, max_sitemap_urls=args.max_sitemap_urls)
            snapshot = crawl_site(client, probe, str(output_dir), max_pages=args.max_pages)
            report = build_report(snapshot)
            write_json(output_dir / "probe.json", probe)
            write_json(output_dir / "site_snapshot.json", snapshot)
            write_json(output_dir / "report.json", report)
            print_crawl_summary(output_dir, report)
            return 0

        if args.command == "migrate":
            probe = probe_site(client, args.target, max_sitemap_urls=args.max_sitemap_urls)
            snapshot = crawl_site(client, probe, str(output_dir), max_pages=args.max_pages)
            report = build_report(snapshot)
            write_json(output_dir / "probe.json", probe)
            write_json(output_dir / "site_snapshot.json", snapshot)
            write_json(output_dir / "report.json", report)

            xml_import_path = None
            if args.xml_export:
                xml_import = import_wordpress_xml(Path(args.xml_export))
                xml_import_path = output_dir / "xml_import.json"
                write_json(xml_import_path, xml_import)

            astro_dir = Path(args.astro_dir) if args.astro_dir else output_dir / "astro-site"
            astro_dir.mkdir(parents=True, exist_ok=True)
            astro_result = generate_astro_project(
                snapshot_path=output_dir / "site_snapshot.json",
                output_dir=astro_dir,
                xml_import_path=xml_import_path,
                site_url=args.site,
                base_path=args.base,
                project_name=args.project_name,
            )
            write_json(output_dir / "astro_generation.json", astro_result)
            print_migrate_summary(output_dir, report, astro_dir, astro_result)
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

    if username is None and password is None:
        username, password = resolve_auth_credentials(args)

    should_capture = any(
        (
            getattr(args, "site_password", None),
            getattr(args, "login_url", None),
            username,
            password,
        )
    ) or getattr(args, "manual_auth", False)

    if not should_capture:
        return None

    report = capture_storage_state(
        target_url=args.target,
        output_dir=output_dir,
        login_url=args.login_url,
        site_password=args.site_password,
        username=username,
        password=password,
        manual=args.manual_auth,
        headless=args.auth_headless,
    )
    write_json(output_dir / "auth.json", report)
    return output_dir / report.storage_state_path


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


def print_probe_summary(output_dir: Path, probe) -> None:
    print(
        f"Wrote {output_dir / 'probe.json'} | squarespace={probe.probably_squarespace} | "
        f"json={bool(probe.json_probe and probe.json_probe.available)} | sitemap_urls={len(probe.sitemap_entries)}"
    )


def print_crawl_summary(output_dir: Path, report) -> None:
    print(
        f"Wrote crawl output to {output_dir} | pages={report.pages_crawled} | ok={report.ok_pages} | "
        f"json_pages={report.pages_with_json} | password_pages={report.password_gated_pages}"
    )


def print_auth_summary(output_dir: Path, report) -> None:
    print(
        f"Wrote auth output to {output_dir} | mode={report.mode} | cookies={report.cookies_saved} | "
        f"storage_state={report.storage_state_path}"
    )


def print_xml_summary(output_dir: Path, xml_import) -> None:
    print(
        f"Wrote {output_dir / 'xml_import.json'} | items={len(xml_import.items)} | site={xml_import.site_title or 'unknown'}"
    )


def print_astro_summary(output_dir: Path, result) -> None:
    print(
        f"Generated Astro project at {output_dir} | pages={result.pages_written} | posts={result.posts_written} | "
        f"manifest={result.manifest_path}"
    )


def print_migrate_summary(output_dir: Path, report, astro_dir: Path, result) -> None:
    print(
        f"Wrote migration output to {output_dir} | crawled={report.pages_crawled} | astro_pages={result.pages_written} | "
        f"astro_posts={result.posts_written} | astro_dir={astro_dir}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
