# squarespace-to-astro

Python tooling for migrating a Squarespace site into a static-site-friendly content snapshot, with Astro as the intended downstream renderer.

## Current status

This repository currently implements the first milestone:

- Probe a target site for Squarespace indicators, sitemap availability, robots rules, RSS feeds, password gates, and `?format=json-pretty` support.
- Crawl a site into a structured snapshot of pages, links, assets, headings, and opportunistic Squarespace JSON data.
- Capture browser-authenticated session state with Playwright and reuse those cookies during probe and crawl runs.
- Import Squarespace WordPress XML exports into a normalized JSON format.
- Generate a buildable Astro project from crawl output plus optional XML content.

Still not implemented:

- Full Squarespace admin automation.
- Asset downloading and redirect generation.
- Commerce, events, forms, and members migration.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

## Authentication

For Squarespace account login, export credentials before running `auth-browser`, `probe`, `crawl`, or `migrate`:

```bash
export SQUARESPACE_USER=owner@example.com
export SQUARESPACE_PWD=owner-password
```

Those commands will use `SQUARESPACE_USER` and `SQUARESPACE_PWD` when `--username` and `--password` are not provided. Use the flags for one-off runs; they override the environment variables.

`--site-password` is separate. It submits a site-wide Squarespace password gate and does not use `SQUARESPACE_USER` or `SQUARESPACE_PWD`.

## Commands

Probe a site and write a capability report:

```bash
s2a probe https://example.squarespace.com --output-dir ./site-output/example
```

Crawl a site and write a structured snapshot plus summary report:

```bash
s2a crawl https://example.squarespace.com --output-dir ./site-output/example --max-pages 75
```

Capture a browser storage state for Squarespace account login:

```bash
s2a auth-browser https://example.squarespace.com --output-dir ./site-output/example
```

Use a site-wide Squarespace password gate instead:

```bash
s2a auth-browser https://example.squarespace.com --output-dir ./site-output/example --site-password 'secret-pass'
```

Import a Squarespace WordPress XML export:

```bash
s2a import-xml ./exports/squarespace-wordpress.xml --output-dir ./site-output/example
```

Generate an Astro site from a crawl snapshot and optional imported XML:

```bash
s2a generate-astro ./site-output/example/site_snapshot.json --output-dir ./generated/site --xml-import ./site-output/example/xml_import.json
```

Run the end-to-end workflow in one command:

```bash
s2a migrate https://example.squarespace.com --output-dir ./site-output/example --xml-export ./exports/squarespace-wordpress.xml --astro-dir ./generated/site
```

## Output files

`probe` writes:

- `probe.json`

`crawl` writes:

- `probe.json`
- `site_snapshot.json`
- `report.json`
- `raw-html/*.html`
- `raw-json/*.json`

`auth-browser` writes:

- `auth.json`
- `auth/storage_state.json`

`import-xml` writes:

- `xml_import.json`

`generate-astro` writes:

- `migration-manifest.json`
- a complete Astro project directory

## Scope notes

This tool is intentionally hybrid. Squarespace's official export is limited, and `?format=json-pretty` is useful but not a supported migration API. The crawler therefore treats rendered HTML as the fallback source of truth and uses structured Squarespace JSON only when available.

The generator converts extracted page bodies to Markdown where possible and falls back to cleaned embedded HTML when conversion quality is weak. That keeps the generated Astro project editable without blocking on perfect HTML-to-Markdown conversion for every Squarespace layout.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Disclaimer

This tool is provided "as is", without warranty of any kind. You assume all responsibility for its use, migration outcomes, and any data loss, service disruption, or downstream issues that may result from running it.
