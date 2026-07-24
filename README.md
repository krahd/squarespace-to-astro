# squarespace-to-astro

`s2a` is a command-line tool that extracts content and assets from Squarespace sites and creates editable [Astro](https://astro.build/) projects.

Current release: `v0.5.8`. The `main` branch may include unreleased options listed in [CHANGELOG.md](CHANGELOG.md).

## Install

### Homebrew

Homebrew is the recommended installation method on macOS arm64 and Linux x86_64.

```bash
brew tap krahd/tap
brew install s2a
```

Verify the installation:

```bash
s2a --help
```

To update an existing installation:

```bash
brew update
brew upgrade s2a
```

The Homebrew package includes the standalone binary and browser dependencies. It does not require a separate Python installation.

### Other installation methods

Standalone release archives and source installation instructions are available in the [user guide](USER_GUIDE.md#install). Windows currently requires a source installation.

## Basic use

Migrate a public Squarespace site:

```bash
s2a migrate https://example.squarespace.com \
  --astro-dir ./generated/example-site
```

Include a Squarespace WordPress XML export when one is available:

```bash
s2a migrate https://example.squarespace.com \
  --xml-export ./exports/squarespace-wordpress.xml \
  --astro-dir ./generated/example-site
```

Run the generated Astro project:

```bash
cd ./generated/example-site
npm install
npm run dev
```

The generated project should be reviewed and edited before deployment, particularly its layout, navigation, asset paths, and redirects.

## What it does

`s2a` can:

- inspect a site for Squarespace endpoints, sitemaps, feeds, password gates, and JSON data
- crawl pages into a structured local snapshot
- import content from a Squarespace WordPress XML export
- download Squarespace-hosted assets after confirmation
- generate an Astro project with pages, content, site data, layouts, and local assets
- write redirect mappings with `--emit-redirects`
- reuse browser session state for account-authenticated content

## Commands

```text
s2a probe
s2a crawl
s2a auth-browser
s2a import-xml
s2a generate-astro
s2a migrate
```

Run `s2a COMMAND --help` for command-specific options.

## Limitations

The current version does not migrate:

- commerce and checkout data
- events
- forms or form submissions
- members-only systems
- Squarespace administration settings

The automated browser-authentication flow does not support interactive two-factor authentication. Complex Squarespace layouts may require manual revision after generation.

## Documentation

- [User guide](USER_GUIDE.md): installation, migration, authentication, and generated-site editing
- [Contributing](CONTRIBUTING.md): contributor setup and pull requests
- [Development](DEVELOPMENT.md): architecture, tests, and distribution tooling
- [Release process](RELEASE.md): versioning and publication
- [Changelog](CHANGELOG.md): release history
- [Project website](https://krahd.github.io/squarespace-to-astro/)

## Development

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
python -m pytest
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for the repository structure and validation workflows.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This tool is provided without warranty. Review migration output before replacing or deploying an existing site.