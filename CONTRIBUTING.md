# Contributing

This project accepts focused contributions that improve the CLI, generated output, release tooling, or documentation.

If you are choosing a feature area or planning a larger change, review [ROADMAP.md](ROADMAP.md) first. The roadmap summarizes the implemented baseline, the main gaps to close before `1.0`, and the larger areas that are still outside the current core workflow.

## Development prerequisites

- Python 3.11 or newer
- a virtual environment for local development
- Playwright Chromium for auth-related workflows and binary bundle work
- GitHub access if you need to test release or tap automation

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

Confirm the CLI is available:

```bash
s2a --help
```

## Running checks

Run the automated test suite before submitting a change:

```bash
python -m pytest
```

If your change affects the standalone bundle or release packaging, smoke-test the binary build as well:

```bash
PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" \
python scripts/build_binary_release.py
```

If your change affects install flows, keep the website, [USER_GUIDE.md](USER_GUIDE.md), and [README.md](README.md) aligned.

## Scope and style expectations

- Keep pull requests focused on one change area when possible.
- When proposing roadmap-level work, explain which item in [ROADMAP.md](ROADMAP.md) the change advances or why the roadmap should expand.
- Avoid unrelated refactors while addressing a specific bug or feature.
- Add or update tests when behavior changes.
- Update documentation when command behavior, install guidance, release behavior, or generated output expectations change.
- Preserve existing repository style unless the change requires a deliberate restructuring.

## Pull requests

For a pull request to be reviewable, it should include:

- a clear summary of the behavior change
- tests or a reason why tests do not apply
- documentation updates for any user-visible change
- notes about release impact if the change affects packaging, distribution, or Homebrew publication

## Release-sensitive changes

Be explicit when a change touches any of these areas:

- `src/s2a/cli.py`
- `scripts/build_binary_release.py`
- `scripts/render_homebrew_formula.py`
- `.github/workflows/release-binaries.yml`
- `.github/workflows/publish-homebrew-tap.yml`

Those files affect installation, release artifacts, or the Homebrew tap and usually require extra verification.

## Further documentation

- [ROADMAP.md](ROADMAP.md): current priorities, gaps, and `1.0` direction
- [DEVELOPMENT.md](DEVELOPMENT.md): architecture, module layout, tests, and build tooling
- [RELEASE.md](RELEASE.md): versioning and release workflow
- [USER_GUIDE.md](USER_GUIDE.md): end-user workflow and command examples
