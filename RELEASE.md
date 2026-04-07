# Release Process

This document describes the current release workflow for `s2a`, including binary bundle publication and Homebrew tap updates.

## Version sources

The project version must stay aligned in:

- [pyproject.toml](pyproject.toml)
- [src/s2a/__init__.py](src/s2a/__init__.py)

## Before tagging a release

Verify the repository state before publishing:

```bash
python -m pytest
PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" \
python scripts/build_binary_release.py
```

Recommended checks:

- version numbers are updated consistently
- `CHANGELOG.md` reflects the user-visible changes in the release
- end-user docs still match the current install and workflow behavior
- contributor and release docs still match the current automation
- the bundled executable starts successfully after the local binary build

## Tagging and GitHub release publication

The release tag format is `vX.Y.Z`.

Typical manual flow:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Create the GitHub Release and attach the source distributions if needed. The binary assets are handled by workflow automation described below.

## Binary bundle automation

[.github/workflows/release-binaries.yml](.github/workflows/release-binaries.yml) runs on release publication or manual dispatch.

It:

- checks out the tagged ref
- installs project dependencies
- installs Playwright Chromium
- builds standalone bundles with [scripts/build_binary_release.py](scripts/build_binary_release.py)
- smoke-tests the bundled executable with `s2a --help`
- uploads the generated archives to the GitHub Release

Current bundle targets are:

- Linux
- macOS
- Windows

## Homebrew tap publication

[.github/workflows/publish-homebrew-tap.yml](.github/workflows/publish-homebrew-tap.yml) runs after [.github/workflows/release-binaries.yml](.github/workflows/release-binaries.yml) completes successfully for a published release, or by manual dispatch.

It:

- waits for the release assets to be visible through the GitHub Releases API
- reads the release assets for the selected tag
- resolves the SHA256 digests for the macOS arm64 and Linux x86_64 standalone archives
- renders `Formula/s2a.rb` with [scripts/render_homebrew_formula.py](scripts/render_homebrew_formula.py)
- pushes the updated formula into `krahd/homebrew-tap`

The workflow requires the repository secret `HOMEBREW_TAP_TOKEN` so it can push to the separate tap repository.
Each repository that publishes into the shared tap must define its own `HOMEBREW_TAP_TOKEN` Actions secret, even when the repositories live under the same personal GitHub account.
The tap push step rebases onto `main` and retries pushes so different repos can update separate formula files in `krahd/homebrew-tap` without manual intervention.

Shared tap rollout guidance for additional projects lives in [HOMEBREW_TAP.md](HOMEBREW_TAP.md).

## Shared tap conventions

If additional repositories publish formulas into `krahd/homebrew-tap`:

- keep formula names lowercase and kebab-case
- keep binary archive prefixes aligned with the installed CLI name
- update only one formula file per publishing repo
- keep Homebrew asset names stable across releases so checksum resolution stays mechanical

## Post-release verification

After a release is published, confirm:

- the GitHub Release includes the expected binary archives and source distributions
- the Homebrew tap formula references the new version and checksums
- `brew tap krahd/tap && brew install krahd/tap/s2a` works on a supported platform
- the project website and documentation still match the released behavior

## Roll-forward approach

If a release needs correction, prefer publishing a new version rather than mutating documented release history or relying on manual drift between the repository and the tap.
