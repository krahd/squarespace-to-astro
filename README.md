# squarespace-to-astro (s2a)

`s2a` is a Python CLI for extracting content from Squarespace and generating an editable [Astro](https://github.com/withastro/astro) project. This README is the repository entry point for developers, contributors, and advanced users who want to run the project from source or understand how the codebase is organized.

Current release: `v0.5.7`.
The `main` branch may document unreleased options listed under `[Unreleased]` in `CHANGELOG.md`.

For end-user installation and day-to-day usage:

- Project website: [krahd.github.io/squarespace-to-astro](https://krahd.github.io/squarespace-to-astro/)
- Detailed usage guide: [USER_GUIDE.md](USER_GUIDE.md)

## Documentation map

- [USER_GUIDE.md](USER_GUIDE.md): end-user installation, migration workflow, and generated Astro editing
- [CONTRIBUTING.md](CONTRIBUTING.md): contributor setup and pull request expectations
- [DEVELOPMENT.md](DEVELOPMENT.md): codebase layout, architecture, testing, and distribution tooling
- [RELEASE.md](RELEASE.md): versioning, tagging, binary publishing, and Homebrew tap publication
- [CHANGELOG.md](CHANGELOG.md): released changes by version

## Project status

The current implementation supports these main workflows:

- probing a target site for Squarespace indicators, sitemap availability, robots behavior, password gates, and `?format=json-pretty` support
- crawling a site into a structured snapshot of pages, links, assets, headings, and opportunistic Squarespace JSON data
- estimating and downloading Squarespace-hosted assets during `crawl` and `migrate`, with a confirmation prompt, text progress output, route-based public filenames, and content-hash deduplication recorded in `asset_manifest.json`
- capturing browser-authenticated session state with Playwright and reusing those cookies during probe and crawl runs
- importing Squarespace WordPress XML exports into a normalized JSON format
- generating a buildable [Astro](https://github.com/withastro/astro) project from crawl output plus optional XML content, including `--fidelity-mode`, `--layout-strategy`, `--choose-layout-strategy`, `--markdown`, `--upgrade-legacy-assets`, and `--clean` controls for layout-heavy pages, with `components` reconstruction for portfolio grids, gallery blocks, Fluid Engine sections, and classic-editor layouts
- orchestrating probe, crawl, optional XML import, asset download, and Astro generation in one `s2a migrate` workflow
- keeping legacy snapshot-root `asset_manifest.json` upgrades opt-in via `generate-astro --upgrade-legacy-assets`, so default generation leaves input manifests untouched and warns when legacy filenames are detected

Current boundaries:

- full Squarespace admin automation is not implemented
- redirect generation implemented (use the `--emit-redirects` flag to write redirect mappings as JSON and a Netlify `_redirects` file)
- commerce, events, forms, and members migration are not implemented

## Supported interfaces

The supported interface for external use is the `s2a` CLI.

The Python modules under `src/s2a/` are intended primarily as implementation details for the CLI and may change between releases. If you import them directly in your own code, pin the project version and review the relevant module before depending on internal behavior.

## Repository layout

- `src/s2a/cli.py`: CLI entry point and command definitions
- `src/s2a/extract/`: HTTP crawling, browser auth capture, XML import, and asset handling
- `src/s2a/normalize/`: report building and data normalization
- `src/s2a/generate/`: Astro project generation
- `scripts/build_binary_release.py`: PyInstaller bundle and standalone release archive builder
- `scripts/render_homebrew_formula.py`: Homebrew formula renderer from release metadata
- `.github/workflows/release-binaries.yml`: GitHub Actions workflow for binary bundle publication
- `.github/workflows/publish-homebrew-tap.yml`: GitHub Actions workflow for tap synchronization
- `tests/`: CLI, generator, auth, XML import, asset, and runtime tests
- `docs/`: static project website published from the repository

## Development quickstart

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

Once installed, check the CLI entry point:

```bash
s2a --help
```

## Running tests

Run the automated test suite with:

```bash
python -m pytest
```

For release-related smoke testing, build the standalone bundle after installing Playwright Chromium and pointing `PLAYWRIGHT_BROWSERS_PATH` at the installed browser cache:

```bash
PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" \
python scripts/build_binary_release.py
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for a fuller explanation of the test layout, output directories, and build artifacts.

## CLI workflows

The CLI exposes six user-facing commands, including the combined migration workflow:

- `s2a probe`
- `s2a crawl`
- `s2a auth-browser`
- `s2a import-xml`
- `s2a generate-astro`
- `s2a migrate`

Usage examples and end-user task flows live in [USER_GUIDE.md](USER_GUIDE.md). The authoritative command definitions and help text live in [src/s2a/cli.py](src/s2a/cli.py).

## Distribution

This project currently ships in three ways. The current release is `v0.5.7`.

- standalone binary bundles for macOS arm64 and Linux x86_64 attached to GitHub Releases
- a Homebrew formula published through `krahd/homebrew-tap`
- source-based installation from this repository

Distribution automation is documented in [RELEASE.md](RELEASE.md) and [DEVELOPMENT.md](DEVELOPMENT.md).

## Contributing

Contribution guidance lives in [CONTRIBUTING.md](CONTRIBUTING.md). Keep changes focused, add or update tests when behavior changes, and update end-user documentation when install or workflow behavior changes.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Disclaimer

This tool is provided "as is", without warranty of any kind. You assume responsibility for its use, migration outcomes, and any downstream issues that may result from running it.
