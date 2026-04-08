# User Guide

This guide is for end users who want to install s2a, run a migration, and continue working with the generated [Astro](https://github.com/withastro/astro) project. For repository setup and contributor workflows, see [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [DEVELOPMENT.md](DEVELOPMENT.md).

## Before you start

Prepare the inputs you need for the migration:

- the Squarespace site URL
- a writable local directory for migration output
- a Squarespace WordPress XML export if you want s2a to merge XML content into the result
- Node.js and npm only when you are ready to preview or keep editing the generated Astro site

If you need account-authenticated Squarespace content, the account used with s2a must have 2FA disabled. The current automated auth flow does not support interactive 2FA prompts.

## Install

### Homebrew

Homebrew is the recommended install path on macOS arm64 and Linux x86_64.

```bash
brew tap krahd/tap
brew install s2a
```

This path installs the bundled binary release and does not require a separate Python installation or `python -m playwright install chromium`.

### Standalone release archive

If you are on Windows or another environment where Homebrew is not the right fit, download the archive for your platform from [GitHub Releases](https://github.com/krahd/squarespace-to-astro/releases), unpack it, and run the bundled `s2a` executable.

The standalone bundles already include the Chromium payload used by `auth-browser`.

### Source install

If you need to run s2a from source instead of using Homebrew or the standalone bundles:

```bash
python -m venv .venv
source .venv/bin/activate
pip install "git+https://github.com/krahd/squarespace-to-astro.git@v0.4.0"
python -m playwright install chromium
```

Replace the tag with the version you actually want to install if you are not targeting the latest release branch.

## First migration

For a public Squarespace site, the shortest path is:

```bash
s2a migrate https://example.squarespace.com \
  --astro-dir ./generated/example-site
```

If you have a Squarespace WordPress XML export, include it with the run:

```bash
s2a migrate https://example.squarespace.com \
  --xml-export ./exports/squarespace-wordpress.xml \
  --astro-dir ./generated/example-site
```

If you omit `--output-dir`, s2a creates a timestamped run directory under `site-output/`.

Example:

```text
site-output/20260405-153000-migrate-example-com/
```

If you want a stable location for repeated runs, pass `--output-dir` explicitly.

During `crawl` and `migrate`, s2a now estimates the Squarespace-hosted asset download size after page discovery and asks for confirmation before downloading those assets.

- use `-y` or `--yes` to auto-confirm that prompt for non-interactive runs
- use `-q` or `--quiet` to suppress progress bars and final summaries while still allowing prompts and fatal errors
- if you decline the prompt, s2a keeps the crawl artifacts it already wrote; `migrate` stops before Astro generation for that run

## Authentication and private content

For account-authenticated areas, export your Squarespace credentials before running `auth-browser`, `probe`, `crawl`, or `migrate`:

```bash
export SQUARESPACE_USER=owner@example.com
export SQUARESPACE_PWD=owner-password
```

Behavior notes:

- `SQUARESPACE_USER` and `SQUARESPACE_PWD` are the default credentials for `auth-browser`.
- For `probe`, `crawl`, and `migrate`, those environment variables are only used after you explicitly request browser auth with `--login-url`, `--manual-auth`, `--username`, or `--password`.
- Plain public runs do not auto-start browser auth just because those environment variables are set.
- `--username` and `--password` override those environment variables for one-off runs.
- `--site-password` is only for a site-wide Squarespace password gate. It is separate from account login.
- `--yes` only auto-confirms CLI download prompts; it does not bypass `--manual-auth`.
- `--insecure` disables TLS certificate verification for both Playwright auth capture and later HTTP crawl requests. Use it only after confirming the URL is correct.
- The automated browser-auth flow does not support interactive 2FA prompts.

If you want to capture a browser session first and reuse it later:

```bash
s2a auth-browser https://example.squarespace.com \
  --manual-auth \
  --no-auth-headless \
  --output-dir ./site-output/example-auth

s2a crawl https://example.squarespace.com \
  --storage-state ./site-output/example-auth/auth/storage_state.json \
  --output-dir ./site-output/example-crawl
```

## Output folders and files

Each run writes `execution-metadata.json`, which records:

- the command that ran
- the resolved output directory
- the package version
- sanitized command arguments
- the main artifact paths produced by the run

The other files depend on the command you run.

`probe` writes:

- `probe.json`

`crawl` writes:

- `probe.json`
- `site_snapshot.json`
- `asset_manifest.json`
  Records canonical localized asset paths, plus any alias Squarespace URLs that were merged into the same downloaded file.
- `report.json`
- `downloaded-assets/`
  Stores localized files under deterministic family directories (`images/`, `videos/`, `audio/`, and `files/`). Media assets are named from the page route with stable per-page numbering such as `barcelona-1.webp` or `barcelona-2-poster.jpg`, while downloadable files keep readable names such as `pricing-guide.pdf`. When Squarespace exposes multiple width-specific variants inside the same size bucket, the filename keeps the width token instead of falling back to a bare counter, for example `barcelona-1-large-1500w.webp`. When two Squarespace asset URLs resolve to identical content, the crawler keeps one canonical file and reuses that path everywhere. The extension matches the bytes actually returned by Squarespace, so CDN-optimized images may end up as `.webp` even when the original URL looked like `.jpg` or `.png`.
- `raw-html/`
- `raw-json/`

`auth-browser` writes:

- `auth.json`
- `auth/storage_state.json`

`import-xml` writes:

- `xml_import.json`

`generate-astro` writes:

- `astro_generation.json`
- `migration-manifest.json`
- a complete [Astro](https://github.com/withastro/astro) project directory

## Common commands

Probe only:

```bash
s2a probe https://example.squarespace.com
```

Crawl without generating [Astro](https://github.com/withastro/astro):

```bash
s2a crawl https://example.squarespace.com --max-pages 100
```

Import a Squarespace WordPress XML export:

```bash
s2a import-xml ./exports/squarespace-wordpress.xml --output-dir ./site-output/example
```

Generate [Astro](https://github.com/withastro/astro) from an existing snapshot:

```bash
s2a generate-astro ./site-output/example/site_snapshot.json \
  --output-dir ./generated/example-site \
  --xml-import ./site-output/example/xml_import.json
```

Generate a higher-fidelity Astro site while keeping Markdown where the conversion stays clean:

```bash
s2a generate-astro ./site-output/example/site_snapshot.json \
  --output-dir ./generated/example-site \
  --fidelity-mode high \
  --layout-strategy hybrid \
  --markdown
```

Generation controls:

- `--fidelity-mode high|balanced|minimal`: controls how aggressively the generator preserves Squarespace layout structure. `high` is the default.
- `--layout-strategy hybrid|components`: chooses how layout-heavy pages are handled. `hybrid` preserves more original Squarespace HTML and embedded layout styling; `components` rebuilds known gallery and Fluid Engine patterns into Astro-friendly markup.
- `--choose-layout-strategy`: prompts at runtime instead of silently using the default strategy.
- `-md`, `--markdown`: prefers Markdown output when the conversion is clean, but still keeps HTML for layout-heavy content such as galleries, embeds, and Fluid Engine sections.

## Edit the generated Astro site

The generated site is a normal [Astro](https://github.com/withastro/astro) project.

```bash
cd ./generated/example-site
npm install
npm run dev
```

Most hand edits happen in these locations:

- `src/content/pages/`: generated page content, usually Markdown with HTML preserved where layout fidelity needs it
- `src/content/posts/`: generated post content, usually Markdown with HTML preserved where layout fidelity needs it
- `src/data/site.json`: site title, description, base URL, and navigation
- `src/layouts/`: shared layouts
- `src/pages/`: route files
- `src/styles/site.css`: site styling

## Troubleshooting

- Homebrew support currently covers macOS arm64 and Linux x86_64. Use the standalone release archive or source install on other platforms.
- The binary bundles are large because they include a Playwright Chromium payload for `auth-browser`.
- `python -m playwright install chromium` is only required for source-based installs.
- If you see `ERR_CERT_COMMON_NAME_INVALID`, verify the site URL first. Squarespace preview domains usually look like `https://site.squarespace.com`; a multi-label host such as `https://foo.bar.squarespace.com` will not match Squarespace's wildcard certificate.
- If the URL is correct but the site still presents a broken certificate, rerun the command with `--insecure`.
- Utility routes such as `/cart`, `/checkout`, and `/account` are intentionally skipped during Astro generation.

## Current migration boundaries

s2a does not currently migrate:

- commerce data and checkout flows
- forms and submissions
- events
- members-only systems
- full Squarespace admin automation
- redirect generation
