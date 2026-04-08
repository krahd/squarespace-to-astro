# Roadmap

This roadmap reflects the current `0.5.x` codebase and is meant to guide contribution priorities. It describes the main areas the project should improve next; it is not a release guarantee.

## Current baseline

The project already provides a usable end-to-end migration pipeline for many public Squarespace sites:

- `s2a probe` inspects Squarespace signals, JSON endpoint availability, sitemap and robots behavior, RSS feeds, and password gates.
- `s2a crawl` discovers internal pages, stores raw HTML and opportunistic `?format=json-pretty` payloads, records links, headings, and assets, can estimate and download localized assets, and writes crawl reports plus an `asset_manifest.json`.
- `s2a auth-browser` captures Playwright storage state for account-authenticated or password-gated content.
- `s2a import-xml` normalizes Squarespace WordPress XML exports into JSON.
- `s2a generate-astro` builds an editable Astro project with fidelity controls, content collections, navigation, route-based asset localization, and migration warnings.
- `s2a migrate` orchestrates probe, crawl, optional XML import, asset download, and Astro generation in one workflow.
- layout-heavy generation already supports `--fidelity-mode`, `--layout-strategy`, `--choose-layout-strategy`, and `--markdown`, with hybrid HTML preservation and component reconstruction for supported portfolio grids, gallery blocks, Fluid Engine sections, and classic-editor layouts.
- localized media now use readable route-based filenames, deduplicate identical bytes across pages, and automatically upgrade older hash-suffixed snapshot manifests during generation.
- release tooling already covers standalone bundles, Homebrew publication, and the project documentation site.

## Toward 1.0

Before the CLI should be treated as a stable general-purpose migration path, these areas need more work.

### 1. Generated site fidelity

- make generated homepages, folders, and index-style pages match source-site structure more closely when extraction falls back from structured data to raw HTML
- expand component reconstruction beyond the current portfolio-grid, gallery, Fluid Engine, and classic-editor coverage so more layout-heavy pages avoid generic wrappers
- preserve more of the source site's styling intent while keeping the generated Astro project easy to edit by hand
- improve how reusable blocks, responsive media variants, and mixed Markdown/HTML sections are represented in output

### 2. Content coverage and extraction depth

- improve crawl coverage when sitemap data is incomplete or internal navigation is sparse
- extract more useful structured data from Squarespace JSON payloads when it is available
- better distinguish blogs, portfolios, folders, index pages, and other collection types
- surface clearer warnings when the crawler had to fall back from structured data to raw HTML parsing

### 3. Authenticated and restricted content

- make private-content capture more predictable for password-gated and account-authenticated sites
- improve auth diagnostics so login form mismatches, cookie reuse problems, and TLS issues are easier to resolve
- evaluate safe ways to support more real-world auth flows without turning the CLI into brittle browser automation

### 4. Migration follow-up and reporting

- add redirect-planning output based on discovered URLs, canonical URLs, and generated routes
- expand migration reports so users can see what was migrated, skipped, downgraded, auto-upgraded, or still needs manual cleanup
- make reruns easier to compare by improving manifest detail and output consistency
- add clearer guidance for manual follow-up tasks inside the generated project and CLI summaries

### 5. Validation and contributor tooling

- grow fixture coverage around real-world Squarespace layouts, especially homepage-heavy sites and mixed page or post structures
- add stronger smoke-test guidance or automation for generated Astro builds on representative fixtures
- keep release packaging, Homebrew publication, and documentation aligned with actual CLI behavior

## Longer-horizon work

- richer theme and styling parity between the source Squarespace site and the generated Astro starter
- broader support for portfolios, galleries, and other media-heavy site structures beyond the patterns already reconstructed today
- optional post-migration helpers for content cleanup, route review, or template refinement
- broader installation and verification coverage across supported binary targets

## Known gaps outside the current core

These areas matter, but they are larger workstreams and should not be assumed to be covered by the current migration pipeline.

- redirect generation is not implemented yet
- commerce data and checkout flows are not migrated
- forms and form submissions are not migrated
- events are not migrated
- members-only systems are not migrated
- full Squarespace admin automation is not implemented

## Contribution notes

Contributions are most useful when they improve one of the roadmap areas above while keeping the CLI's current strengths intact:

- reliable crawl artifacts
- transparent warnings and reports
- editable Astro output
- practical install and release workflows

If you want to work outside this roadmap, document the use case clearly first so the change can be evaluated against the project's intended scope.
