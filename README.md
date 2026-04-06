# squarespace-to-astro (s2a)

Python tooling for migrating a Squarespace site into a static-site-friendly content snapshot, with [Astro](https://github.com/withastro/astro) as the intended downstream renderer.

## Current status

This repository currently implements the first milestone:

- Probe a target site for Squarespace indicators, sitemap availability, robots rules, RSS feeds, password gates, and `?format=json-pretty` support.
- Crawl a site into a structured snapshot of pages, links, assets, headings, and opportunistic Squarespace JSON data.
- Capture browser-authenticated session state with Playwright and reuse those cookies during probe and crawl runs.
- Import Squarespace WordPress XML exports into a normalized JSON format.
- Generate a buildable [Astro](https://github.com/withastro/astro) project from crawl output plus optional XML content.

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

## Binary Releases

Prebuilt CLI bundles for Linux, macOS, and Windows are attached to GitHub Releases. Those bundles include a Chromium browser payload for `auth-browser`, so you do not need a separate Python install to run the binary distribution.

Download the archive for your platform from the Releases page, unpack it, and run the bundled `s2a` executable.

See `USER_GUIDE.md` for a step-by-step workflow, generated [Astro](https://github.com/withastro/astro) editing notes, and output-folder conventions.

Developer overview page: [krahd.github.io/squarespace-to-astro](https://krahd.github.io/squarespace-to-astro/).

## Authentication

For Squarespace account login, export credentials before running `auth-browser`, `probe`, `crawl`, or `migrate`:

```bash
export SQUARESPACE_USER=owner@example.com
export SQUARESPACE_PWD=owner-password
```

Those commands will use `SQUARESPACE_USER` and `SQUARESPACE_PWD` when `--username` and `--password` are not provided. Use the flags for one-off runs; they override the environment variables.

To access private Squarespace areas with the automated browser-auth flow, the Squarespace account used by this tool must have two-factor authentication (2FA) disabled. The current auth flow does not handle interactive 2FA challenges.

`--site-password` is separate. It submits a site-wide Squarespace password gate and does not use `SQUARESPACE_USER` or `SQUARESPACE_PWD`.

## Commands

If you omit `--output-dir` for `probe`, `crawl`, `auth-browser`, `import-xml`, or `migrate`, the CLI creates a unique run folder under `site-output/` and writes `execution-metadata.json` alongside the generated artifacts.

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

Generate an [Astro](https://github.com/withastro/astro) site from a crawl snapshot and optional imported XML:

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
- `execution-metadata.json`

`crawl` writes:

- `probe.json`
- `site_snapshot.json`
- `report.json`
- `execution-metadata.json`
- `raw-html/*.html`
- `raw-json/*.json`

`auth-browser` writes:

- `auth.json`
- `auth/storage_state.json`
- `execution-metadata.json`

`import-xml` writes:

- `xml_import.json`
- `execution-metadata.json`

`generate-astro` writes:

- `astro_generation.json`
- `execution-metadata.json`
- `migration-manifest.json`
- a complete [Astro](https://github.com/withastro/astro) project directory

## Scope notes

This tool is intentionally hybrid. Squarespace's official export is limited, and `?format=json-pretty` is useful but not a supported migration API. The crawler therefore treats rendered HTML as the fallback source of truth and uses structured Squarespace JSON only when available.

The generator converts extracted page bodies to Markdown where possible and falls back to cleaned embedded HTML when conversion quality is weak. That keeps the generated [Astro](https://github.com/withastro/astro) project editable without blocking on perfect HTML-to-Markdown conversion for every Squarespace layout.

Utility routes such as `/cart`, `/checkout`, and `/account` are intentionally skipped during Astro generation because they do not map cleanly to a static site.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Disclaimer

This tool is provided "as is", without warranty of any kind. You assume all responsibility for its use, migration outcomes, and any data loss, service disruption, or downstream issues that may result from running it.
