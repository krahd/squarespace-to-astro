# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning for tagged releases.

## [Unreleased]

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
