# AGENTS.md

Repository instructions for AI coding agents working in this project.

This file is the durable source of truth for GitHub Copilot, OpenAI Codex, Claude Code, and compatible coding agents. Read it before making changes.

## 1: Non-negotiable rules

- Keep `STATUS.md` accurate at all times.
- `STATUS.md` must exist in the repository root.
- Do not finish a task that changes the project without reviewing and, when needed, updating `STATUS.md`.
- Do not invent project facts. Inspect the repository and record uncertainty explicitly.
- Do not overwrite user work or unrelated changes.
- Do not commit secrets, credentials, tokens, private keys, local environment files, browser storage-state files, generated site output, release artefacts, or generated sensitive data.
- Prefer small, focused changes over broad rewrites.
- Preserve existing CLI flags and user-visible workflows unless explicitly asked to change them.
- Verify meaningful changes with the narrowest reliable command available.
- Do not claim tests passed unless they were actually run.

## 2: Communication style

Use terse, factual, technical communication. Do not use playful, whimsical, cute, decorative, or filler progress phrases such as "combobulating", "cooking", "thinking...", "working on it", "let me dive in", "I'll get started", or "working my magic".

Allowed status-update style: "Reading files." "Found the issue." "Applying patch." "Tests passed." "Tests failed: <reason>."

No jokes, metaphors, fake enthusiasm, anthropomorphising, or decorative progress messages. Prefer concise present-tense technical updates. Use British English for prose documentation unless the repository consistently uses another variant.

## 3: Standard work loop

1. Read this file and `STATUS.md` before editing.
2. Inspect relevant files, docs, tests, packaging metadata, and CI workflows.
3. Identify the smallest safe change.
4. Search call sites before changing CLI commands, flags, output formats, generated Astro structure, asset manifests, redirect generation, auth handling, or release tooling.
5. Make focused edits.
6. Run relevant verification when possible.
7. Update documentation when behaviour, setup, architecture, commands, public APIs, or release state change.
8. Update `STATUS.md` if project state changed.
9. Report changed files, verification, and remaining issues.

## 4: Project-specific map

### 4.1: Project shape

- Purpose: Python CLI for extracting content from Squarespace and generating editable Astro projects.
- Supported external interface: the `s2a` CLI.
- Main workflows: probe, crawl, auth-browser, import-xml, generate-astro, migrate.
- Distribution: source install, standalone binary bundles, and Homebrew tap publication.
- Python modules under `src/s2a/` are primarily implementation details unless documented otherwise.

### 4.2: Important paths

- `README.md`: repository entry point.
- `STATUS.md`: complete current project status report; mandatory upkeep.
- `USER_GUIDE.md`: end-user installation and migration workflow.
- `CONTRIBUTING.md`: contributor setup and PR expectations.
- `DEVELOPMENT.md`: architecture, testing, and distribution tooling.
- `RELEASE.md`: versioning, tagging, binary publishing, and Homebrew tap publication.
- `CHANGELOG.md`: release history.
- `src/s2a/cli.py`: CLI entry point and command definitions.
- `src/s2a/extract/`: HTTP crawling, browser auth, XML import, and asset handling.
- `src/s2a/normalize/`: reports and data normalisation.
- `src/s2a/generate/`: Astro project and redirect generation.
- `tests/`: CLI, generator, auth, XML, asset, redirect, runtime, fixture, and generated-site tests.
- `scripts/build_binary_release.py`: PyInstaller bundle builder.
- `scripts/render_homebrew_formula.py`: Homebrew formula renderer.
- `.github/workflows/`: CI and release workflows.

### 4.3: Safety invariants

- Do not leak browser-authenticated storage-state files or credentials.
- Preserve confirmation prompts and user control for asset downloads where present.
- Preserve route-based asset naming and manifest compatibility unless explicitly changing the format.
- Keep generated-site output directories and release artefacts out of source control unless intentionally tracked.
- Do not break existing CLI flags without explicit instruction and documentation.
- Generated Astro sites should remain buildable under the documented validation workflow.

## 5: STATUS.md maintenance

`STATUS.md` is mandatory project state, not optional documentation.

Required timestamp line near the top:

```text
Last updated: YYYY-MM-DD HH:MM
```

Use 24-hour local time. If no other timezone is specified, use `America/Montevideo`. Duplicate the exact same line as the final line at the bottom of `STATUS.md`. Update both lines together.

`STATUS.md` must be a complete current snapshot, not a changelog. Include relevant sections for purpose, current state, active focus, architecture, setup/run instructions, configuration, important files, recent changes, tests, risks, pending tasks, next steps, longer-term steps, and decisions.

## 6: Diagrams in STATUS.md

Include useful inline SVG architecture and flow diagrams when the structure is meaningful enough. Keep text inside boxes and canvas bounds. Keep arrows out of unrelated boxes and labels. Prefer generous spacing and simple SVG primitives.

## 7: Validation

Typical validation commands:

```bash
python -m pytest
python -m pytest -q
python scripts/build_binary_release.py
```

For development setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

Run the narrowest relevant checks first. Record tests not run when relevant. Update `CHANGELOG.md` for user-visible changes when appropriate.

## 8: Final response requirements

When finishing a task, report concisely: what changed, files changed, verification commands and results, whether `STATUS.md` was updated, and remaining issues or follow-up work.
