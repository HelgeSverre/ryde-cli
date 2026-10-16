# Distribution plan

## Available now: GitHub and uv

The source repository is the initial distribution channel. No PyPI package has
been released by this project yet. Run the CLI directly from GitHub:

```sh
uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde --help
```

Install both entry points into a persistent tool environment if desired:

```sh
uv tool install git+https://github.com/HelgeSverre/ryde-cli
uv tool run --from git+https://github.com/HelgeSverre/ryde-cli ryde --help
```

For reproducibility, append `@<commit-sha>` to the Git URL. Once release tags
exist, a tag can be used in the same position. Git-based installation requires
Git. See [uv's tool guide](https://docs.astral.sh/uv/guides/tools/).

CI builds a wheel and source archive and uploads them as a GitHub Actions
artifact. This checks packaging without publishing to an index.

## Proposed next step: PyPI

PyPI is a good fit for this pure-Python package: it distributes both the CLI
and MCP entry points, works with uv, and avoids requiring Git for installation.
There is no need for a separate npm package or container to use the CLI.

The desired project name is `ryde-cli`. A lookup returned no project on
2026-10-16; availability is not reserved and must be checked again at release.

Before the first upload:

1. Confirm the package name and sign in to the intended PyPI and TestPyPI
   accounts with two-factor authentication.
2. Add a pending Trusted Publisher for `HelgeSverre/ryde-cli`, choosing a
   publishing workflow filename (for example `publish.yml`) and a GitHub
   environment (for example `pypi`). Pending publishers allow the first upload
   to create the project. TestPyPI has separate account/publisher settings.
3. Add that workflow and environment. Build and verify distributions in a job
   with read-only permissions. Give only the publishing job `id-token: write`,
   bind it to the selected environment, and use `uv publish --trusted-publishing
   always`. Do not store a long-lived PyPI API token.
4. Test publishing to TestPyPI first. TestPyPI does not mirror all dependencies;
   install the tested wheel with dependencies from PyPI rather than treating
   TestPyPI as the main dependency index.
5. Check the tag against the package version, run CI, and review archive contents.
   Create the release only after the publisher setup is verified. Uploaded
   versions cannot be overwritten; fixes require a new version.

Local release validation uses:

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run scripts/generate_command_reference.py --check
uv build
uvx --from ./dist/ryde_cli-0.1.0-py3-none-any.whl ryde --version
uvx --from twine twine check --strict dist/*
```

After this project's first PyPI release, the shorter distribution commands
would become available:

```sh
# Future commands: use only after this project's PyPI release exists.
uvx --from ryde-cli ryde --help
uvx --from ryde-cli ryde-mcp
uv tool install ryde-cli
```

No publishing workflow is enabled yet. The repository CI cannot upload to PyPI.
The remaining decision is whether to keep GitHub-only distribution initially
or configure PyPI Trusted Publishing for the first tagged release.

References: [uv build and publish](https://docs.astral.sh/uv/guides/package/),
[PyPI pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
[uv GitHub Actions publishing](https://docs.astral.sh/uv/guides/integration/github/).
