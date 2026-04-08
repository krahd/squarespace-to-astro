---
name: tomas-laurenzo-reference-validation
description: 'Run live regression validation for squarespace-to-astro against https://tomas-laurenzo.squarespace.com. Use when testing probe, crawl, generate-astro, migrate, fidelity, layout strategy, markdown output, asset naming, cleanup, and detailed reporting on the Tomas Laurenzo reference site.'
argument-hint: 'Optional focus area like fidelity, naming, migrate, or an explicit target URL override'
---

# Tomas Laurenzo Reference Validation

## What This Skill Does

- Uses `https://tomas-laurenzo.squarespace.com` as the default live reference site for repo validation.
- Exercises the live-site command surface that matters for this project: `probe`, `crawl`, `generate-astro`, and `migrate`.
- Treats visual fidelity as a first-class acceptance criterion: the generated Astro output should look as close as practical to the Squarespace source while staying editable.
- Treats naming conventions as strict requirements, especially route-based localized asset filenames and other readable output paths.
- Deletes only the artifacts created by the current validation run after evidence is captured.
- Finishes with a detailed report using the bundled [report template](./assets/report-template.md).

## When To Use

- The user asks to test or regression-check changes against Tomas Laurenzo's Squarespace site.
- The change touches crawl behavior, asset localization, Astro generation, fidelity controls, layout strategies, or markdown-vs-HTML output.
- The user says a feature should "work perfectly" on the Laurenzo site.
- You need to confirm that a change did not break route-based asset naming or the overall look of the generated Astro site.

## Default Assumptions

- Work from the repository root.
- Prefer the repo virtual environment if it already exists.
- Use `https://tomas-laurenzo.squarespace.com` unless the user explicitly overrides the target.
- Use explicit output directories under `site-output/` and `generated/` so cleanup is precise.
- Use `--yes` for non-interactive runs unless you are intentionally testing interactive prompt behavior.
- Do not treat `import-xml` as part of the live-site download matrix unless the user also provides an XML export file.

## Acceptance Standard

- A command is not "good enough" just because it exits successfully.
- The generated Astro site must build successfully for the variants you evaluate.
- The high-fidelity output must preserve the reference site's editorial feel, navigation structure, and layout-heavy pages as closely as the generator allows.
- Localized asset filenames must remain readable and route-based. Do not accept regressions to generic CDN stems such as `image-asset-*` or legacy hash-suffixed public paths.
- If part of the workflow fails, still produce a partial report with blockers, skipped steps, and recommended fixes.

## Procedure

### 1. Prepare The Run

1. Activate the repo environment and confirm the CLI entry point you will use.
2. Create one run identifier and use it consistently, for example `tomas-laurenzo-YYYYMMDD-HHMMSS`.
3. Create output directories only under that run identifier, for example:
   - `site-output/<run-id>-probe`
   - `site-output/<run-id>-crawl`
   - `site-output/<run-id>-migrate`
   - `generated/<run-id>-high-hybrid`
   - `generated/<run-id>-high-components`
   - `generated/<run-id>-migrate`
4. Record the exact commands you intend to run before cleanup.

### 2. Run The Required Live Command Matrix

Always run these commands unless the user explicitly narrows scope:

1. Probe the live site.

```bash
s2a probe https://tomas-laurenzo.squarespace.com \
  --output-dir ./site-output/<run-id>-probe \
  --yes
```

2. Crawl the live site with asset download enabled.

```bash
s2a crawl https://tomas-laurenzo.squarespace.com \
  --output-dir ./site-output/<run-id>-crawl \
  --max-pages 100 \
  --yes
```

3. Generate a high-fidelity Astro site from the crawl snapshot using `hybrid` layout handling.

```bash
s2a generate-astro ./site-output/<run-id>-crawl/site_snapshot.json \
  --output-dir ./generated/<run-id>-high-hybrid \
  --fidelity-mode high \
  --layout-strategy hybrid \
  --markdown \
  --site https://tomas-laurenzo.squarespace.com
```

4. Generate a second high-fidelity Astro site using `components` layout handling.

```bash
s2a generate-astro ./site-output/<run-id>-crawl/site_snapshot.json \
  --output-dir ./generated/<run-id>-high-components \
  --fidelity-mode high \
  --layout-strategy components \
  --markdown \
  --site https://tomas-laurenzo.squarespace.com
```

5. Run the full end-to-end migration workflow.

```bash
s2a migrate https://tomas-laurenzo.squarespace.com \
  --output-dir ./site-output/<run-id>-migrate \
  --astro-dir ./generated/<run-id>-migrate \
  --max-pages 100 \
  --fidelity-mode high \
  --layout-strategy hybrid \
  --markdown \
  --yes
```

### 3. Add Branch-Specific Checks When Relevant

- If the change touches prompt handling or default-selection logic, also run one `generate-astro` command with `--choose-layout-strategy` and verify the default selection behavior separately from `--yes` behavior.
- If the change touches fidelity fallback behavior, add focused `balanced` or `minimal` runs only for the affected path. Do not explode the matrix without a reason.
- If the change touches authentication or private content, add `auth-browser` only when credentials or a manual-auth workflow are actually in scope.
- If the user provides a Squarespace XML export, add `import-xml` plus one combined generation pass. Otherwise keep the validation centered on the live website.

### 4. Verify Artifacts, Not Just Exit Codes

For each run, confirm the expected artifacts exist:

- `probe`: `probe.json` and `execution-metadata.json`
- `crawl`: `probe.json`, `site_snapshot.json`, `asset_manifest.json`, `report.json`, `downloaded-assets/`, `raw-html/`, `raw-json/`, and `execution-metadata.json`
- `generate-astro`: `astro_generation.json`, `migration-manifest.json`, the generated Astro project, and `execution-metadata.json`
- `migrate`: the combined crawl artifacts plus the generated Astro project and migration outputs

Inspect the generated metadata for the selected fidelity mode and layout strategy. Do not assume those settings were applied correctly just because the command line included them.

### 5. Enforce Naming Conventions Strictly

Check both crawl outputs and generated Astro outputs for naming regressions.

- No localized public asset path should fall back to generic CDN-style stems such as `image-asset-*`.
- No localized public asset path should expose legacy hash-suffixed filenames when route-based names should exist.
- Readable downloadable filenames should remain readable.
- Route-driven asset naming should remain stable on image-heavy pages.

At minimum:

1. Inspect `asset_manifest.json` from crawl and migrate runs.
2. Spot-check generated `public/assets/` output for route-based filenames.
3. Review at least one image-heavy project page and confirm its referenced assets match the naming rules.

### 6. Build And Compare The Generated Astro Sites

For each generated Astro project that will appear in the report:

1. Install dependencies.
2. Run the Astro build.
3. If browser preview is available, compare the live Squarespace site and the generated Astro output visually.

Focus the comparison on:

- homepage chrome and navigation
- one image-heavy project page
- one text-heavy page
- spacing, page width, and header treatment
- embedded or layout-heavy sections that often regress when fidelity logic changes

When choosing a recommended output variant, prefer the one that best matches the live Squarespace presentation while still honoring the repo's output conventions.

### 7. Decide Pass, Fail, Or Partial Pass

Mark the run as passing only when all of the following are true:

- required commands finished successfully for the chosen scope
- expected artifacts were written
- the selected Astro outputs built successfully
- naming conventions remained intact
- no major structural or visual regression was found on the key comparison pages

If the run is mixed, say so explicitly. Do not collapse partial success into a blanket pass.

### 8. Clean Up Current-Run Artifacts

After capturing all evidence needed for the report:

1. Delete only the directories created for the current run.
2. Leave pre-existing fixtures, golden outputs, and historical generated folders alone.
3. If the user explicitly asks to keep artifacts for manual inspection, skip deletion and document that choice in the report.

### 9. Write The Report

Use the bundled [report template](./assets/report-template.md).

The report must clearly cover:

- the exact command matrix that was executed
- what worked
- what did not work
- which output variant best matched the live site and why
- whether naming conventions were preserved
- whether cleanup was completed
- the next fixes that would most improve the Laurenzo migration quality

## Decision Points

- If the user asks whether a specific feature works on the Laurenzo site, still run the narrowest command set that proves the answer, but include at least one end-to-end generation path when the feature affects final Astro output.
- If the user asks for the closest possible visual match, treat `high + hybrid + --markdown` as the baseline and compare `components` only when it may improve layout-heavy sections.
- If asset naming is under scrutiny, prioritize crawl and migrate outputs plus one image-heavy page review over broader visual polish.
- If the site becomes inaccessible or unstable, stop expanding the matrix, report the blocker, and avoid treating network failure as a product regression without evidence.

## Completion Checklist

- Required command matrix executed for the relevant scope
- Outputs inspected, not just generated
- Build verified for reported Astro outputs
- Naming conventions checked explicitly
- Visual fidelity reviewed on key pages
- Current-run artifacts deleted or intentionally retained with explanation
- Detailed report completed