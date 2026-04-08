# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning for tagged releases.

## [Unreleased]

## [0.5.0] - 2026-04-07

### Added in 0.5.0

- automatic in-place upgrades for legacy `asset_manifest.json` files that still reference hash-suffixed localized filenames during `generate-astro`

### Changed in 0.5.0

- generated Astro output now keeps route-based localized asset names even when the source snapshot was crawled before the filename cleanup
- CLI generation summaries now surface upgrade warnings and fail cleanly when a legacy asset manifest cannot be repaired because the expected localized files are missing

## [0.4.0] - 2026-04-07

### Added in 0.4.0

- deterministic localized asset filenames with content-hash deduplication and alias tracking in `asset_manifest.json`
- generation controls for `--fidelity-mode`, `--layout-strategy`, `--choose-layout-strategy`, and `-md` / `--markdown`
- homepage-derived navigation and chrome hints plus component reconstruction for portfolio grids and Fluid Engine sections

### Changed in 0.4.0

- layout-heavy pages now stay in HTML with immersive presentation when fidelity needs to win over Markdown conversion
- generated Astro projects now omit the posts collection when a migration has no posts and rewrite duplicate Squarespace asset URLs to one shared localized file

## [0.3.0] - 2026-04-05

### Added in 0.3.0

- default asset-download size estimation and confirmation for `crawl` and `migrate`
- `-y` / `--yes` to auto-confirm CLI download prompts for non-interactive runs
- text progress bars for page crawling, asset-size estimation, and asset downloading

### Changed in 0.3.0

- `-q` / `--quiet` now suppresses progress output and final summaries while still allowing prompts and fatal errors
- declining the asset-download confirmation keeps the crawl artifacts already written and stops the remaining asset-download work for that run

## [0.2.5] - 2026-04-05

### Fixed in 0.2.5

- plain `probe`, `crawl`, and `migrate` runs no longer auto-start browser auth just because `SQUARESPACE_USER` and `SQUARESPACE_PWD` are set, and explicit auth attempts now fail with clearer guidance when the page does not expose a login form

## [0.2.4] - 2026-04-05

### Fixed in 0.2.4

- Homebrew tap publication now waits for `Release Binaries` to finish and retries release-asset discovery before resolving checksums, avoiding the release-publish race that required a manual rerun for `v0.2.3`
- plain `probe`, `crawl`, and `migrate` runs no longer auto-start browser auth just because `SQUARESPACE_USER` and `SQUARESPACE_PWD` are set, and explicit auth attempts now fail with clearer guidance when the page does not expose a login form

## [0.2.3] - 2026-04-05

### Added in 0.2.3

- `--insecure` support for browser auth capture and crawl requests when a site has a known-bad TLS certificate

### Fixed in 0.2.3

- browser auth capture now reports actionable guidance for certificate hostname mismatches instead of surfacing a raw Playwright exception

## [0.2.2] - 2026-04-05

### Added in 0.2.2

- standalone binary bundles for macOS arm64, Linux x86_64, and Windows x86_64
- Homebrew installation through the shared tap `krahd/homebrew-tap`
- credential defaults through `SQUARESPACE_USER` and `SQUARESPACE_PWD`
- expanded project documentation for end users, contributors, and release operations

### Changed in 0.2.2

- installation guidance now distinguishes Homebrew, standalone bundle, and source-based workflows
- documentation split now separates the public website, user guide, repository overview, contributor guide, development guide, and release process

### Fixed in 0.2.2

- Astro generation no longer infers blog collections too broadly for page routes such as `/projects/...`
- generated output verification for the Laurenzo migration now matches the expected page inventory and served-route behavior

## [0.2.1]

### Added in 0.2.1

- package metadata in `pyproject.toml`
- GitHub Pages project website published from `docs/`
- GitHub Release publication with source distribution artifacts

### Changed in 0.2.1

- repository metadata now includes the project homepage and updated developer-facing references
