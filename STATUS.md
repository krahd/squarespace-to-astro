# squarespace-to-astro – Project Status

Last updated: 2026-06-06 22:38

## Project purpose

squarespace-to-astro (`s2a`) is a Python 3.11+ CLI for extracting content from Squarespace sites and generating editable Astro projects. It supports probing, crawling, authenticated capture, XML import, Astro generation, redirects, asset download/deduplication, and an end-to-end migration workflow.

## Current implementation state

The project is currently at version `0.5.7` in the status snapshot. It is distributed as a pip package, standalone binary bundles for macOS arm64 and Linux x86_64, and through the `krahd/homebrew-tap` Homebrew tap. Windows installs are source-based until a Windows binary workflow is added.

The CLI exposes six user-facing commands:

- `s2a probe`
- `s2a crawl`
- `s2a auth-browser`
- `s2a import-xml`
- `s2a generate-astro`
- `s2a migrate`

Generation and migration support `--fidelity-mode`, `--layout-strategy`, `--choose-layout-strategy`, and `--markdown`. Component reconstruction covers portfolio grids, gallery blocks, Fluid Engine sections, and classic-editor layouts. Probe, crawl, and migrate validate supplied or captured storage-state files before applying cookies. Crawl output directories are normalised as `Path` values, Atom feeds prefer alternate links, and Squarespace asset hosts are matched by exact host or subdomain.

Localized assets use readable route-based public filenames, with `asset_manifest.json` recording alias URLs and content-hash deduplication metadata. Legacy hash-suffixed manifests are upgraded only when `generate-astro --upgrade-legacy-assets` is passed; default `generate-astro` and `migrate` runs leave input manifests untouched and warn when legacy filenames are detected. Redirect generation is available via `--emit-redirects`, maps source URL paths to generated routes without query strings, and failures now surface warnings instead of disappearing. `--clean` removes only the Astro output directory, with safety checks that reject `/`, the current working directory, and the home directory.

## Active focus

Current focus is maintaining healthy release state, expanding real-world fixture coverage, improving generated-site fidelity, preserving CLI compatibility, and keeping binary/Homebrew distribution tooling aligned.

## Architecture overview

The CLI orchestrates probing, crawling, auth capture, XML import, asset download, data normalisation, Astro generation, and redirect output. The `src/s2a/` package is structured by extraction, normalisation, generation, and runtime helper concerns. Tests cover CLI wiring, assets, auth, XML import, redirects, generated-site builds, fixtures, networking, reports, runtime helpers, and URL utilities.

### Architecture diagram

<svg xmlns="http://www.w3.org/2000/svg" width="1060" height="520" viewBox="0 0 1060 520" role="img" aria-labelledby="s2a-arch-title s2a-arch-desc">
  <title id="s2a-arch-title">squarespace-to-astro architecture</title>
  <desc id="s2a-arch-desc">The s2a CLI orchestrates extraction, normalisation, Astro generation, redirect output, tests, and release tooling.</desc>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="40" y="205" width="160" height="75" rx="10" fill="none" stroke="black" /><text x="120" y="235" text-anchor="middle" font-size="14">s2a CLI</text><text x="120" y="257" text-anchor="middle" font-size="12">src/s2a/cli.py</text>
  <rect x="285" y="55" width="180" height="80" rx="10" fill="none" stroke="black" /><text x="375" y="87" text-anchor="middle" font-size="14">extract/</text><text x="375" y="109" text-anchor="middle" font-size="12">crawl, auth, XML,</text><text x="375" y="127" text-anchor="middle" font-size="12">assets, JSON</text>
  <rect x="285" y="205" width="180" height="75" rx="10" fill="none" stroke="black" /><text x="375" y="235" text-anchor="middle" font-size="14">normalize/</text><text x="375" y="257" text-anchor="middle" font-size="12">models and reports</text>
  <rect x="285" y="355" width="180" height="75" rx="10" fill="none" stroke="black" /><text x="375" y="385" text-anchor="middle" font-size="14">generate/</text><text x="375" y="407" text-anchor="middle" font-size="12">Astro and redirects</text>
  <rect x="560" y="90" width="190" height="75" rx="10" fill="none" stroke="black" /><text x="655" y="120" text-anchor="middle" font-size="14">Squarespace input</text><text x="655" y="142" text-anchor="middle" font-size="12">site, sitemap, XML</text>
  <rect x="560" y="300" width="190" height="80" rx="10" fill="none" stroke="black" /><text x="655" y="330" text-anchor="middle" font-size="14">Astro output</text><text x="655" y="352" text-anchor="middle" font-size="12">project, assets,</text><text x="655" y="370" text-anchor="middle" font-size="12">redirects</text>
  <rect x="815" y="90" width="190" height="75" rx="10" fill="none" stroke="black" /><text x="910" y="120" text-anchor="middle" font-size="14">tests/</text><text x="910" y="142" text-anchor="middle" font-size="12">fixtures and builds</text>
  <rect x="815" y="300" width="190" height="80" rx="10" fill="none" stroke="black" /><text x="910" y="330" text-anchor="middle" font-size="14">release tooling</text><text x="910" y="352" text-anchor="middle" font-size="12">binary bundles and</text><text x="910" y="370" text-anchor="middle" font-size="12">Homebrew formula</text>
  <line x1="200" y1="235" x2="285" y2="95" stroke="black" marker-end="url(#arrow)" /><line x1="200" y1="242" x2="285" y2="242" stroke="black" marker-end="url(#arrow)" /><line x1="200" y1="250" x2="285" y2="392" stroke="black" marker-end="url(#arrow)" /><line x1="465" y1="95" x2="560" y2="128" stroke="black" marker-end="url(#arrow)" /><line x1="465" y1="392" x2="560" y2="340" stroke="black" marker-end="url(#arrow)" /><line x1="750" y1="128" x2="815" y2="128" stroke="black" marker-end="url(#arrow)" /><line x1="750" y1="340" x2="815" y2="340" stroke="black" marker-end="url(#arrow)" />
</svg>

### Flow chart

<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="350" viewBox="0 0 1080 350" role="img" aria-labelledby="s2a-flow-title s2a-flow-desc">
  <title id="s2a-flow-title">s2a migration flow</title>
  <desc id="s2a-flow-desc">The migrate command probes a site, crawls content, optionally imports XML and downloads assets, normalises data, generates Astro, and emits redirects.</desc>
  <defs><marker id="flowarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="25" y="140" width="115" height="65" rx="10" fill="none" stroke="black" /><text x="82" y="168" text-anchor="middle" font-size="12">Probe</text><text x="82" y="186" text-anchor="middle" font-size="12">site</text>
  <rect x="180" y="140" width="115" height="65" rx="10" fill="none" stroke="black" /><text x="237" y="168" text-anchor="middle" font-size="12">Crawl</text><text x="237" y="186" text-anchor="middle" font-size="12">pages</text>
  <rect x="335" y="140" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="395" y="168" text-anchor="middle" font-size="12">Import XML</text><text x="395" y="186" text-anchor="middle" font-size="12">optional</text>
  <rect x="495" y="140" width="125" height="65" rx="10" fill="none" stroke="black" /><text x="557" y="168" text-anchor="middle" font-size="12">Download</text><text x="557" y="186" text-anchor="middle" font-size="12">assets</text>
  <rect x="660" y="140" width="125" height="65" rx="10" fill="none" stroke="black" /><text x="722" y="168" text-anchor="middle" font-size="12">Normalise</text><text x="722" y="186" text-anchor="middle" font-size="12">snapshot</text>
  <rect x="825" y="140" width="125" height="65" rx="10" fill="none" stroke="black" /><text x="887" y="168" text-anchor="middle" font-size="12">Generate</text><text x="887" y="186" text-anchor="middle" font-size="12">Astro</text>
  <rect x="990" y="140" width="70" height="65" rx="10" fill="none" stroke="black" /><text x="1025" y="168" text-anchor="middle" font-size="12">Emit</text><text x="1025" y="186" text-anchor="middle" font-size="12">files</text>
  <line x1="140" y1="172" x2="180" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="295" y1="172" x2="335" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="455" y1="172" x2="495" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="620" y1="172" x2="660" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="785" y1="172" x2="825" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="950" y1="172" x2="990" y2="172" stroke="black" marker-end="url(#flowarrow)" />
</svg>

## Setup and run instructions

Development setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
s2a --help
```

Tests:

```bash
python -m pytest
python -m pytest -q
```

Release smoke build:

```bash
PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" \
python scripts/build_binary_release.py
```

## Configuration and environment variables

- Python 3.11 or newer is required.
- Playwright Chromium is required for browser-auth capture and some release smoke workflows.
- `PLAYWRIGHT_BROWSERS_PATH` may be set for standalone bundle smoke testing.

## Important files and directories

- `src/s2a/cli.py`: CLI command definitions.
- `src/s2a/extract/`: crawling, auth, assets, JSON, XML import.
- `src/s2a/normalize/`: data models and report building.
- `src/s2a/generate/`: Astro generation and redirects.
- `tests/`: automated test suite and fixtures.
- `docs/`: static project website.
- `USER_GUIDE.md`, `CONTRIBUTING.md`, `DEVELOPMENT.md`, `RELEASE.md`, `CHANGELOG.md`: user, developer, release, and history docs.
- `scripts/build_binary_release.py`: standalone bundle builder.
- `scripts/render_homebrew_formula.py`: Homebrew formula renderer.
- `.github/workflows/release-binaries.yml`: binary bundle publication workflow.
- `.github/workflows/publish-homebrew-tap.yml`: Homebrew tap synchronisation workflow.

## Recent changes

- The Astro generator now renders `astro.config.mjs` string values with JSON escaping and sanitizes generated HTML, including event-handler attributes, `javascript:` URLs, iframe `srcdoc`, iframe `sandbox`, and unsafe `srcset` candidates.
- `generate-astro` now keeps legacy asset-manifest upgrades opt-in via `--upgrade-legacy-assets`, adds safe `--clean` deletion for Astro output directories, and surfaces redirect/report failures as warnings instead of swallowing them.
- `probe`, `crawl`, and `migrate` now validate any supplied or captured storage-state file before applying cookies.
- The crawler now normalises output directories as `Path` objects, prefers Atom alternate links, and matches Squarespace asset hosts by exact host or subdomain.
- WordPress XML import now uses `defusedxml` for XML parsing, and the duplicate temporary-file cleanup loop in asset download handling was removed.
- CI now tests Python 3.11, 3.12, and 3.13, pins Node 20 in both GitHub Actions workflows, restores the Playwright browser cache before installation, and treats generated Astro install/build failures as fatal with explicit `dist/` and `index.html` checks.
- The generated-site build helper clears stale `node_modules` before `npm ci`, which keeps repeated local and CI reruns idempotent.
- The repository README and user guide now distinguish the tagged `v0.5.7` release from `main` / next-release options, and the guide labels `--clean` and `--upgrade-legacy-assets` accordingly.
- Release and installation docs now state that standalone bundles cover macOS arm64 and Linux x86_64 only; Windows users are directed to source installs until a Windows binary workflow is added.
- The static project website in `docs/` was refreshed with current `v0.5.7` messaging, updated migration guidance, and an improved responsive visual design.
- The top-level `ignored/` scratch directory is now excluded from source control via `.gitignore`.
- `v0.5.7` added CI Node-backed Astro build smoke testing, redirect summary/report output, identity redirect filtering, RSS feed crawl seeding fallback, sparse-sitemap guidance improvements, and auth storage-state staleness checks.
- `v0.5.6` included post-release housekeeping and older release/tag removal.
- `v0.5.2` added streaming asset downloads, redirect generation, auth artefact permission hardening, CI workflow, and redirect tests.
- Root-level agent and status governance is being standardised.

## Tests and verification status

Latest local verification:

- `.venv/bin/python -m pytest -q tests/test_astro_generator.py tests/test_cli.py tests/test_generated_sites_build.py` -> 51 passed.
- `.venv/bin/python -m pytest -q` -> 88 passed.
- CI now runs Python 3.11-3.13, Node 20, and the generated Astro smoke workflow separately.
- Binary bundles are built with PyInstaller for macOS arm64 and Linux x86_64.
- Homebrew formula is rendered by `scripts/render_homebrew_formula.py` and published to `krahd/homebrew-tap`.

## Known issues, risks, and limitations

Known gaps outside current scope:

- commerce data and checkout flows are not migrated
- forms and form submissions are not migrated
- events are not migrated
- members-only systems are not migrated
- full Squarespace admin automation is not implemented

Current risks:

- Real-world Squarespace layouts vary widely and need broad fixture coverage.
- Browser-auth storage state can be sensitive and must not be leaked.
- Generated-site fidelity remains a continuing improvement area for complex homepages, folders, and index-style pages.
- Generated-site build verification still depends on live npm registry access when a generated project has no lockfile, so offline environments will fail `npm install`.

## Pending tasks

- Expand fixture coverage for more real-world Squarespace layouts.
- Improve generated-site fidelity for homepage-heavy, folder, and index-style pages.
- Keep distribution documentation aligned with binary and Homebrew workflows.

## Next steps

1. Add more real-world fixture coverage.
2. Improve generated output for homepage, folder, and index-style pages.
3. Continue validating generated Astro sites with build smoke tests.

## Longer-term steps

1. Preserve CLI compatibility while migration fidelity improves.
2. Keep asset manifest compatibility and automatic legacy upgrades reliable.
3. Continue treating commerce, forms, events, members-only systems, and admin automation as explicit out-of-scope boundaries unless project scope changes.

## Decisions and rationale

- The supported external interface is the `s2a` CLI.
- Internal Python modules may change between releases unless explicitly documented as stable.
- Migration output prioritises editability while offering fidelity controls for layout-heavy pages.
---

Last updated: 2026-06-06 22:38
