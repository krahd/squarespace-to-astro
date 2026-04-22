Release 0.5.2 (2026-04-20)
=================================

Highlights
----------

- Redirect generator: emit canonical/source → generated-route mappings as `redirects.json` and Netlify `_redirects` via the new `--emit-redirects` CLI flag (see [src/s2a/generate/redirects.py](src/s2a/generate/redirects.py) and the CLI wiring in [src/s2a/cli.py](src/s2a/cli.py)).

- Streaming asset downloads: large assets are streamed to temporary files and hashed incrementally to avoid high memory usage and to allow atomic finalization on disk ([src/s2a/extract/assets.py](src/s2a/extract/assets.py)).

- Auth hardening: captured `storage_state.json` and `auth.json` are now written with an attempt at restrictive owner-only permissions where supported; `auth` flows also guard interactive/manual modes in non-TTY contexts ([src/s2a/extract/auth.py](src/s2a/extract/auth.py)).

- CI: GitHub Actions workflow added to run the test suite and install Playwright browsers in CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

Developer notes
---------------

- New file: [src/s2a/generate/redirects.py](src/s2a/generate/redirects.py) — contains `build_redirects_from_manifest`, `write_redirects_json`, and `write_netlify_redirects` helpers.

- CLI: use `--emit-redirects` with `generate-astro` or `migrate` to create redirect artifacts alongside generated sites. Example:

```bash
s2a generate-astro path/to/site_snapshot.json --output-dir generated/site --emit-redirects
```

- Auth capture (manual login requires a TTY):

```bash
s2a auth-browser example.com --output-dir auth-out --manual-auth
```

- Run tests locally (use the project `.venv` to ensure dev dependencies are available):

```bash
source .venv/bin/activate
python -m pytest -q
```

- Quick release tagging (optional):

```bash
git tag -a v0.5.2 -m "Release v0.5.2"
git push origin v0.5.2
```

PyPI publish workflow
--------------------

- The repository adds an optional `.github/workflows/publish-pypi.yml` workflow that can publish the package to PyPI on release or by manual dispatch. The workflow checks for an Actions secret `PYPI_API_TOKEN` and will skip the publish step if the token is not configured.

To publish via the workflow manually, set the secret and use `workflow_dispatch` in the Actions UI, or create a GitHub Release to trigger the release workflow.

Notable files changed
---------------------

- [CHANGELOG.md](CHANGELOG.md) — added this release entry.
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — short, user-focused summary.
- [src/s2a/generate/redirects.py](src/s2a/generate/redirects.py) — new redirect generator.
- [src/s2a/cli.py](src/s2a/cli.py) — `--emit-redirects` flag and hooks.
- [src/s2a/extract/assets.py](src/s2a/extract/assets.py) — streaming download improvements.
- [src/s2a/extract/auth.py](src/s2a/extract/auth.py) — permission hardening and TTY guard.
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — CI job for tests & Playwright.

Tests
-----

- Added unit test: [tests/test_redirects.py](tests/test_redirects.py).
- Local test run: `58 passed` using the project's `.venv`.

Next steps
----------

- Optionally tag the release (commands above) and create a GitHub release using this changelog entry.
- If you want, I can open a GitHub release and draft the release notes on the repository using the changelog text.
