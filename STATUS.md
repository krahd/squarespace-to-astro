# squarespace-to-astro — Project Status

<!-- Agents: update this file after every change. See AGENTS.md for the required fields. -->

Last updated: 2026-05-06 13:28

---

Current version: 0.5.7
Branch: main
Overall status: Healthy - all tests passing
Test suite: 71 passed, 0 failed (`python -m pytest -q`, 2026-05-06)

---

## Current state

`squarespace-to-astro` (`s2a`) is a Python 3.11+ CLI at version **0.5.7** on branch `main`.
The package is distributed as a pip package (`squarespace-to-astro`), standalone
binaries for macOS arm64 and Linux x86_64, and via the Homebrew tap
`krahd/homebrew-tap`.

The CLI exposes six commands:

| Command | Purpose |
|---|---|
| `s2a probe` | Inspect Squarespace signals, sitemap, robots, password gates, JSON endpoint availability |
| `s2a crawl` | Capture pages, links, headings, raw HTML, JSON payloads, and optionally download localized assets |
| `s2a auth-browser` | Capture Playwright storage state for authenticated / password-gated content |
| `s2a import-xml` | Normalize a Squarespace WordPress XML export into JSON |
| `s2a generate-astro` | Convert crawl snapshot + optional XML into a buildable Astro project |
| `s2a migrate` | Orchestrate probe → crawl → XML import → asset download → Astro generation |

`generate-astro` and `migrate` accept `--fidelity-mode`, `--layout-strategy`,
`--choose-layout-strategy`, and `--markdown` to trade editability against visual
fidelity. Component reconstruction covers portfolio grids, gallery blocks, Fluid
Engine sections, and classic-editor layouts.

Localized assets use readable route-based public filenames
(e.g. `/assets/images/be-water-1.webp`). `asset_manifest.json` records alias
URLs and content-hash deduplication metadata. Legacy hash-suffixed manifests are
upgraded automatically during generation.

Redirect generation is available via `--emit-redirects` (writes `redirects.json`,
a Netlify `_redirects` file, and a `redirect-report.md` coverage report).
Identity redirects are filtered out automatically.

---

## Source layout

```
src/s2a/
  cli.py              — argument parsing, command wiring, output directory resolution, execution metadata
  probe.py            — site probing and capability detection
  net.py              — HTTP client, User-Agent, shared request helpers
  files.py            — output directory helpers, file I/O utilities
  runtime.py          — shared runtime helpers
  url_utils.py        — URL normalization and manipulation
  extract/
    crawl.py          — page crawling, link discovery, sitemap handling, RSS feed seeding
    auth.py           — Playwright storage-state capture, credential guards, stale-cookie detection
    assets.py         — streaming asset download, content-hash dedup, manifest writing
    json_data.py      — opportunistic Squarespace JSON extraction
    xml_import.py     — Squarespace WordPress XML → normalized JSON
  normalize/
    models.py         — normalized data models
    transform.py      — report building and data normalization
  generate/
    astro.py          — Astro project generation, fidelity/layout controls, component reconstruction
    redirects.py      — redirect mapping, identity filtering, Netlify _redirects emission, coverage report
```

---

## Tests

```
tests/
  test_assets.py                 — asset download, dedup, manifest writing
  test_astro_generator.py        — Astro generation correctness
  test_auth.py                   — auth-capture guards and permission hardening
  test_cli.py                    — CLI argument parsing and command wiring
  test_fixtures_integration.py   — real-world fixture-based integration tests
  test_generated_sites_build.py  — generated Astro sites build without errors
  test_net.py                    — HTTP client helpers
  test_redirects.py              — redirect generation
  test_report.py                 — normalization and report building
  test_runtime.py                — runtime helpers
  test_url_utils.py              — URL normalization
  test_xml_import.py             — XML import pipeline
  fixtures/                      — trimmed real-world snapshots (laurenzo-site, laurenzo-site-asset-verify, homepage-heavy, …)
```

Latest run: **71 passed, 0 failed** (`python -m pytest -q`, 2026-05-06).

---

## Recent changes

- `v0.5.7` (2026-05-06): CI Node-backed Astro build smoke test; redirect summary/report output and identity-filtering; RSS feed crawl seeding fallback; sparse-sitemap follow-up guidance improvements; auth storage-state staleness checks.
- `v0.5.6` (2026-04-22): post-release housekeeping; removed older GitHub releases and tags.
- `v0.5.2` (2026-04-20): streaming asset downloads; redirect generation (`--emit-redirects`); auth artifact permission hardening; CI workflow; redirect tests.
- `v0.5.1` (2026-04-08): classic-editor layout reconstruction in `components` mode; gallery block matching fix.
- `v0.5.0` (2026-04-07): automatic in-place upgrade for legacy hash-suffixed `asset_manifest.json` files.
- Added `AGENTS.md` cross-agent instruction file and this `STATUS.md`.

---

## Open work

- None currently.

---

## Next steps (from roadmap)

1. **Expand fixture coverage** — more real-world Squarespace layouts (homepage-heavy, mixed post/page structures).
2. **Generated site fidelity** — closer structural match for homepage, folder, and index-style pages.

---

## Known gaps (outside current scope)

- Commerce data, checkout flows — not migrated
- Forms and form submissions — not migrated
- Events — not migrated
- Members-only systems — not migrated
- Full Squarespace admin automation — not implemented

---

## Known issues

None. All 71 tests pass locally and in CI.

---

## Validation

- `python -m pytest -q` → **71 passed** (2026-05-06)
- CI: `.github/workflows/ci.yml` runs tests and installs Playwright browsers on every push
- Binary bundles built with PyInstaller for macOS arm64 and Linux x86_64
- Homebrew formula rendered by `scripts/render_homebrew_formula.py` and published to `krahd/homebrew-tap`
