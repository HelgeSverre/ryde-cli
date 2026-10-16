# Distribution and releases

## Install from PyPI

Run the CLI or MCP server without cloning:

```sh
uvx --from ryde-cli ryde --help
uvx --from ryde-cli ryde-mcp
```

For a persistent installation:

```sh
uv tool install ryde-cli
```

Pin a version with `--from ryde-cli==0.1.1`. Upgrade a persistent installation
with `uv tool upgrade ryde-cli`.

## Install from GitHub

To run a particular source revision:

```sh
uvx --from git+https://github.com/HelgeSverre/ryde-cli@v0.1.1 ryde --help
```

Replace `v0.1.1` with a commit or tag. Git-based installation requires Git.

## PyPI configuration

The publishing workflow is `.github/workflows/publish.yml`. Its
[PyPI Trusted Publisher](https://pypi.org/manage/project/ryde-cli/settings/publishing/)
uses these values:

| Field | Value |
| --- | --- |
| PyPI project name | `ryde-cli` |
| Owner | `HelgeSverre` |
| Repository name | `ryde-cli` |
| Workflow name | `publish.yml` |
| Environment name | Leave blank |

The workflow uses GitHub OIDC with `uv publish --trusted-publishing always`.
Only the publishing job receives `id-token: write`. It downloads the validated
wheel and source archive from a separate build job and generates PEP 740
attestations. No GitHub environment or PyPI API token is required.

## Validate a release

Run the workflow manually to build and check the distributions **without uploading**:

```sh
gh workflow run publish.yml --ref main
gh run list --workflow publish.yml
```

It runs the Python tests, linting, generated documentation check, archive checks,
strict README validation, and installed-package smoke tests for both the wheel
and source archive. The compiled dashboard is included in both archives.
The CI workflow separately verifies frontend builds and browser behavior.

Local validation:

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run scripts/generate_command_reference.py --check
uv build --clear
uv run scripts/check_public_tree.py
uvx --from twine twine check --strict dist/*
```

## Publish a version

1. Set the version with `uv version <version>`, update `CHANGELOG.md`,
   and push the changes to `main`.
2. Wait for CI and the manual publishing validation to pass for that commit.
3. Create a GitHub release with tag `v<version>`, targeting that commit. Review
   the release notes before publishing the release.
4. Publishing the GitHub release starts the upload workflow. The tag must match
   the package version, and its commit must belong to `main`.
5. Check the workflow and the new [PyPI project page](https://pypi.org/project/ryde-cli/).
   Test installation with `uvx --refresh --from ryde-cli ryde --version`.

Draft releases and manual workflow runs do not upload. Uploaded versions cannot
be overwritten; publish a new version for fixes.

References: [uv publishing](https://docs.astral.sh/uv/guides/integration/github/#publishing-to-pypi),
[PyPI pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
