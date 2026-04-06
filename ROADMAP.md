# Roadmap

This roadmap reflects the current `0.3.x` codebase and is meant to guide contribution priorities. It describes the main areas the project should improve next; it is not a release guarantee.

## Current baseline

The project already provides a usable end-to-end migration pipeline for many public Squarespace sites:

- `s2a probe` inspects Squarespace signals, JSON endpoint availability, sitemap and robots behavior, RSS feeds, and password gates.
- `s2a crawl` discovers internal pages, stores raw HTML and opportunistic `?format=json-pretty` payloads, records links, headings, and assets, and writes crawl reports.
- `s2a auth-browser` captures Playwright storage state for account-authenticated or password-gated content.
- `s2a import-xml` normalizes Squarespace WordPress XML exports into JSON.
- `s2a generate-astro` builds an editable Astro project with content collections, navigation, asset localization, and migration warnings.
- `s2a migrate` orchestrates probe, crawl, optional XML import, asset download, and Astro generation in one workflow.
- release tooling already covers standalone bundles, Homebrew publication, and the project documentation site.

## Toward 1.0

Before the CLI should be treated as a stable general-purpose migration path, these areas need more work.

### 1. Generated site fidelity

- make generated homepages match source-site structure more closely instead of falling back to generic content when extraction is thin
- improve navigation, page hierarchy, headings, metadata, and section ordering in generated output
- preserve more of the source site's styling intent while keeping the generated Astro project easy to edit by hand
- strengthen asset localization for responsive images, downloadable files, and media-heavy pages

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
- expand migration reports so users can see what was migrated, skipped, downgraded, or still needs manual cleanup
- make reruns easier to compare by improving manifest detail and output consistency
- add clearer guidance for manual follow-up tasks inside the generated project and CLI summaries

### 5. Validation and contributor tooling

- grow fixture coverage around real-world Squarespace layouts, especially homepage-heavy sites and mixed page or post structures
- add stronger smoke-test guidance or automation for generated Astro builds on representative fixtures
- keep release packaging, Homebrew publication, and documentation aligned with actual CLI behavior

## Longer-horizon work

- richer theme and styling parity between the source Squarespace site and the generated Astro starter
- more deliberate support for portfolios, galleries, and other media-heavy site structures
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
