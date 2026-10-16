# Contributing

Use [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.11+
on macOS or Linux. uv can download a compatible interpreter automatically.

```sh
git clone https://github.com/HelgeSverre/ryde-cli.git
cd ryde-cli
uv sync --locked
uv run ryde --help
uv run pytest --cov=ryde_cli --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run scripts/generate_command_reference.py --check
uv build
uvx --from ./dist/ryde_cli-0.1.0-py3-none-any.whl ryde --version
```

Tests use synthetic data and mocked requests. They must never require an account,
send an SMS, or call the live API. Keep the CLI and MCP tools limited to reading
account data; authentication is the only intentional account-side effect.

After editing parser options, regenerate the full command reference:

```sh
uv run scripts/generate_command_reference.py
```

Update the README command table when adding a command. Keep every executable
Python, CLI, test, and packaging example in documentation prefixed with `uv` or
`uvx`. Shell setup and Git commands can use their usual executables.

Use `uv add` / `uv add --dev` to change dependencies and commit `uv.lock` with
`pyproject.toml`. CI checks the lockfile, lint/format, generated docs, offline
tests, built distributions, and known dependency vulnerabilities. Dependabot
checks dependencies and GitHub Actions weekly; CodeQL runs on pushes, pull
requests, and a weekly schedule.

Never commit config files, tokens, real phone numbers, exports, routes, addresses,
or payment references. Share minimal synthetic fixtures when reporting bugs.

See [the distribution plan](docs/distribution.md) before preparing a release.


## Dashboard changes

The frontend source is `web/`; end users receive precompiled assets. After
editing it, run `npm ci`, `npm test`, `npm run build`, and `npm run test:e2e`
inside `web/`. Commit `src/ryde_cli/web/` with the source changes. Builds include
third-party license notices and never read private `public/data`. CI verifies
that rebuilding does not change the checked-in bundle.

Before pushing, run `uv run scripts/check_public_tree.py` after staging the
intended files and building distributions. This checks common private artifact
paths in Git and archives; it complements a secret scan and human review.
