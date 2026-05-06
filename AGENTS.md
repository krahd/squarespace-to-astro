# Agent Instructions

This file provides instructions for AI coding agents (GitHub Copilot, OpenAI Codex, Anthropic Claude, and compatible tools) working in this repository.

---

## Project overview

`squarespace-to-astro` (`s2a`) is a Python CLI that extracts content from Squarespace sites and generates editable [Astro](https://github.com/withastro/astro) projects. The supported external interface is the `s2a` CLI; the Python modules under `src/s2a/` are implementation details.

Key documents:
- [README.md](README.md) — repository entry point
- [DEVELOPMENT.md](DEVELOPMENT.md) — architecture, testing, and distribution tooling
- [CONTRIBUTING.md](CONTRIBUTING.md) — contributor setup and pull-request expectations
- [ROADMAP.md](ROADMAP.md) — planned work and current boundaries
- [CHANGELOG.md](CHANGELOG.md) — released changes by version
- [STATUS.md](STATUS.md) — **live project and repository status** (must be kept current)

---

## STATUS.md — mandatory maintenance

**`STATUS.md` must be kept up to date at all times.**

Every time you make a change to the codebase — including code, tests, documentation, configuration, scripts, or any other tracked file — you must update `STATUS.md` before finishing the task. The file records the overall health and current state of the project so any agent or contributor can orient themselves quickly.

Required fields in `STATUS.md`:

- **Last updated**: date and time in local timezone using `YYYY-MM-DD hh:mm`, e.g. `2026-05-06 08:39`
- **Current version**: the version string from `pyproject.toml`
- **Branch**: the active branch
- **Overall status**: a one-line summary (e.g. `Healthy — all tests passing`)
- **Test suite**: pass/fail/count of the latest local run
- **Open work**: a short bullet list of active or pending tasks
- **Known issues**: any known failures, broken tests, or blockers
- **Recent changes**: a brief description of the most recent change made

Failing to update `STATUS.md` after making changes is an error. Update it as the last step of every task.

---

## Development environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

Python 3.11 or newer is required.

---

## Running the test suite

```bash
python -m pytest
```

Run the full suite before completing any task that touches source code or tests. Record the result in `STATUS.md`.

---

## Code conventions

- The CLI entry point and all command definitions live in `src/s2a/cli.py`.
- Extraction logic goes in `src/s2a/extract/`.
- Normalization and report building go in `src/s2a/normalize/`.
- Astro project generation goes in `src/s2a/generate/`.
- Shared helpers live in `src/s2a/files.py`, `runtime.py`, `net.py`, and `url_utils.py`.
- Tests live in `tests/` and mirror the module they cover.
- Do not add public Python API surface without a matching test.
- Do not break backward compatibility of existing CLI flags.
- Follow the existing code style (no reformatting of unrelated files).

---

## Commit and PR discipline

- Write clear, concise commit messages that describe *what* changed and *why*.
- Keep commits focused; avoid bundling unrelated changes.
- Update [CHANGELOG.md](CHANGELOG.md) under `## [Unreleased]` for every user-visible change.
- Update [STATUS.md](STATUS.md) in every commit that touches the tracked codebase.

---

## What NOT to do

- Do not delete or overwrite `generated/`, `site-output/`, or `tests/fixtures/` content without explicit instruction.
- Do not push to remote branches, open pull requests, or publish releases without explicit instruction.
- Do not modify `pyproject.toml` version strings without explicit instruction.
- Do not add optional dependencies, new CLI flags, or new commands unless asked.
- Do not reformat files unrelated to the task at hand.
