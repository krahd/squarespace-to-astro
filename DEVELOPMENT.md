# Development Guide

This document explains how the repository is organized, how the CLI workflows fit together, and how the build and distribution tooling works.

## Development environment

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

The editable install provides the `s2a` entry point defined in `pyproject.toml`.

## Repository structure

- `src/s2a/cli.py`: argument parsing, command wiring, output directory resolution, and execution metadata
- `src/s2a/probe.py`: site probing and capability detection
- `src/s2a/extract/`: crawl, auth, XML import, and asset-handling helpers
- `src/s2a/normalize/`: report building and normalized data transforms
- `src/s2a/generate/astro.py`: Astro project generation
- `src/s2a/files.py`, `runtime.py`, `net.py`, and `url_utils.py`: shared runtime and utility helpers
- `tests/`: automated coverage for assets, Astro generation, auth, CLI behavior, reporting, runtime helpers, URL handling, and XML import
- `scripts/`: binary packaging and Homebrew formula rendering

## CLI workflows

The CLI is the supported external interface.

Main commands:

- `probe`: inspect a target site and write a capability report
- `crawl`: produce a structured site snapshot and crawl report
- `auth-browser`: capture Playwright storage state for later authenticated requests
- `import-xml`: normalize a Squarespace WordPress XML export into JSON
- `generate-astro`: turn a crawl snapshot and optional XML import into an Astro project
- `migrate`: run probe, crawl, optional XML import, and Astro generation as one workflow

The source of truth for command names, flags, defaults, and help text is [src/s2a/cli.py](src/s2a/cli.py).

Current generator-specific behavior to keep in mind while changing the codebase:

- `generate-astro` and `migrate` support `--fidelity-mode`, `--layout-strategy`, `--choose-layout-strategy`, and `--markdown` to trade off editability against visual fidelity.
- localized assets are written under route-based public paths such as `/assets/images/be-water-1.webp`, while `asset_manifest.json` keeps alias URLs and content-hash deduplication metadata.
- older snapshot-root `asset_manifest.json` files that still contain hash-suffixed localized filenames are upgraded automatically during generation before the Astro project is written.

## Execution flow

The common migration path is:

1. `probe` inspects target behavior and writes a capability summary.
2. `crawl` captures pages, discovered links, available structured data, and optional localized asset downloads into a snapshot.
3. `import-xml` optionally normalizes a Squarespace WordPress XML export.
4. `generate-astro` converts the snapshot and optional XML data into an editable Astro project.
5. `migrate` orchestrates the above as a single command.

When `--output-dir` is omitted, `probe`, `crawl`, `auth-browser`, `import-xml`, and `migrate` create a timestamped run folder under `site-output/`.

## Output artifacts

Important outputs include:

- `execution-metadata.json`: sanitized command metadata and primary artifact paths
- `probe.json`: probe results
- `site_snapshot.json`: normalized crawl snapshot
- `report.json`: crawl summary
- `asset_manifest.json`: localized asset metadata, alias tracking, and deduplication details
- `downloaded-assets/`: localized files staged before Astro output rewriting
- `auth/storage_state.json`: Playwright storage state for authenticated reuse
- `xml_import.json`: normalized XML import data
- `astro_generation.json`: generator summary
- `migration-manifest.json`: generated Astro content manifest

The generated Astro project itself is written either to the directory passed via `--output-dir` for `generate-astro` or to `--astro-dir` for `migrate`. When no posts are detected, the generator emits a pages-only content configuration instead of a posts collection scaffold.

## Testing

Run the test suite with:

```bash
python -m pytest
```

The current test set covers:

- asset extraction and asset-related behavior
- Astro generation output
- authentication flows
- CLI parsing and command execution behavior
- reporting helpers
- runtime helpers
- URL normalization
- XML import behavior

## Binary build tooling

The standalone bundle is built by [scripts/build_binary_release.py](scripts/build_binary_release.py).

Key details:

- it uses PyInstaller in `--onedir` mode
- it copies the installed Playwright browser directory into the release bundle
- it expects `PLAYWRIGHT_BROWSERS_PATH` to point at an installed browser cache before the build runs
- it writes artifacts under `build/binary-release/`

Typical local smoke test:

```bash
PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" \
python scripts/build_binary_release.py
```

## Homebrew tooling

The Homebrew formula is rendered by [scripts/render_homebrew_formula.py](scripts/render_homebrew_formula.py) from release version and checksum data.

The formula is published into the shared tap repository `krahd/homebrew-tap` through [.github/workflows/publish-homebrew-tap.yml](.github/workflows/publish-homebrew-tap.yml).

Current Homebrew support is intentionally limited to the release assets that exist for macOS arm64 and Linux x86_64.

## Release automation

- [.github/workflows/release-binaries.yml](.github/workflows/release-binaries.yml) builds Linux, macOS, and Windows standalone bundles and uploads them to the GitHub Release.
- [.github/workflows/publish-homebrew-tap.yml](.github/workflows/publish-homebrew-tap.yml) resolves release asset checksums, renders the formula, and updates `krahd/homebrew-tap`.

See [RELEASE.md](RELEASE.md) for the operational release checklist.

## Stability notes

The CLI is the intended stable interface. Internal Python modules are documented here so contributors can work on the codebase, not as a guarantee of long-term library API stability.
