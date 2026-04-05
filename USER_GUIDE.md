# User Guide

## Quick start

1. Create and activate a virtual environment.
2. Install the package and Playwright Chromium.
3. Export `SQUARESPACE_USER` and `SQUARESPACE_PWD` if you need account-authenticated access.
4. Run `s2a migrate` against the target site.
5. Open the generated [Astro](https://github.com/withastro/astro) project and continue editing there.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium

export SQUARESPACE_USER=owner@example.com
export SQUARESPACE_PWD=owner-password

s2a migrate https://example.squarespace.com --xml-export ./exports/squarespace-wordpress.xml
```

Developer overview page: [krahd.github.io/squarespace-to-astro](https://krahd.github.io/squarespace-to-astro/).

## Authentication notes

- `SQUARESPACE_USER` and `SQUARESPACE_PWD` are the default credentials for `auth-browser`, `probe`, `crawl`, and `migrate`.
- `--username` and `--password` override those environment variables for one-off runs.
- `--site-password` is only for a site-wide password gate. It is separate from account login.
- The automated browser-auth flow does not handle interactive 2FA prompts. If you need private account-authenticated areas, the Squarespace account used for the run must have 2FA disabled.

## Output folders

When you omit `--output-dir`, the CLI creates a unique run folder under `site-output/`.

Example:

```text
site-output/20260405-153000-migrate-example-com/
```

That run folder includes `execution-metadata.json`, which records:

- the command that ran
- the resolved output directory
- the package version
- sanitized command arguments
- the main artifact paths produced by the run

If you need a stable location instead, pass `--output-dir` explicitly.

## Common commands

Probe only:

```bash
s2a probe https://example.squarespace.com
```

Capture authenticated browser state only:

```bash
s2a auth-browser https://example.squarespace.com
```

Crawl without generating [Astro](https://github.com/withastro/astro):

```bash
s2a crawl https://example.squarespace.com --max-pages 100
```

Generate [Astro](https://github.com/withastro/astro) from an existing snapshot:

```bash
s2a generate-astro ./site-output/20260405-153000-crawl-example-com/site_snapshot.json --output-dir ./generated/example-site
```

## Editing the generated [Astro](https://github.com/withastro/astro) site

The generated site is a normal [Astro](https://github.com/withastro/astro) project.

```bash
cd ./generated/example-site
npm install
npm run dev
```

Most hand edits happen in these locations:

- `src/content/pages/`: generated page content in Markdown
- `src/content/posts/`: generated post content in Markdown
- `src/data/site.json`: site title, description, base URL, and navigation
- `src/layouts/`: shared [Astro](https://github.com/withastro/astro) layouts
- `src/pages/`: [Astro](https://github.com/withastro/astro) route files
- `src/styles/site.css`: site styling

## What the generator skips

The generator intentionally skips utility routes that do not belong in a static export, including `/cart`, `/checkout`, and `/account`.

The tool also still does not migrate:

- commerce data and checkout flows
- forms and submissions
- events
- members-only systems
- admin-only Squarespace features
