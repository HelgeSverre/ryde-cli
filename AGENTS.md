# Ryde CLI

Unofficial account-data CLI, local map dashboard, and stdio MCP server.

- Use uv for Python installation, execution, tests, and packaging. Document
  `uv run` in a checkout and `uvx --from` outside it.
- Keep auth/configs, real account records, GPS traces, checkpoints, and dashboard
  session URLs out of Git, test fixtures, build output, and documentation.
- The original sibling stats workspace is private. Copy code selectively;
  never copy its data, `.cache`, `public/data`, or `dist` into this repository.
- Tests use synthetic records and mocked HTTP; do not call the live Ryde API
  or send SMS as part of validation.
- The frontend source is `web/`. The Python package ships compiled UI only
  under `src/ryde_cli/web/`. `publicDir: false` prevents copying private data.
  Rebuild with `npm ci` and `npm run build` inside `web/` after frontend edits.
- Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run scripts/generate_command_reference.py --check`, and `uv build --clear`.
- Keep the CLI/MCP account operations read only. Login may send an explicitly
  requested SMS. Route traces require explicit location acknowledgement.
- The portable user workflow skill is `src/ryde_cli/agent_skill/SKILL.md`,
  exposed through `.agents/skills` and `.claude/skills`. Keep one source.
