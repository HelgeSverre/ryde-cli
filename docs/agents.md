# Claude Code and Codex

The package provides both a stdio MCP server and a portable `ryde-stats` skill.
MCP supplies typed operations; the skill teaches the authenticated
fetch → poll → show-dashboard workflow. Neither requires a hosted service.

## Authenticate first

Do this interactively on the machine that will run the tools:

```sh
uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde login
```

The user's token stays in their local `0600` config. Do not paste tokens, SMS
codes, or config contents into agent chat or project config. A custom
`RYDE_CONFIG` path must be supplied to both login and the MCP launcher.

## Codex MCP setup

```sh
codex mcp add ryde -- uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde-mcp
codex mcp list
```

For a non-default config:

```sh
codex mcp add ryde --env RYDE_CONFIG=/absolute/path/to/ryde-config.json -- uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde-mcp
```

This registers a user-level stdio server. Remove it with `codex mcp remove ryde`.
Codex also supports MCP configuration in its TOML config; see
[Codex MCP documentation](https://developers.openai.com/codex/mcp/).

## Claude Code MCP setup

```sh
claude mcp add --scope user ryde -- uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde-mcp
claude mcp get ryde
```

For a non-default config, add `--env
RYDE_CONFIG=/absolute/path/to/ryde-config.json` before `--`. User scope makes
this server available across local projects. Remove it with
`claude mcp remove --scope user ryde`. Review the permissions shown by your
client before enabling access to personal data.
[Claude MCP documentation](https://code.claude.com/docs/en/mcp).

Desktop applications may require the absolute path to `uvx` if their PATH does
not match the shell's. Pin the Git URL to `@<commit-sha>` for repeatable setups.
The MCP server shares the CLI's default config automatically; no token belongs
in a reusable MCP definition.

## Install the workflow skill

In a cloned repository, the canonical skill is already exposed in both
`.agents/skills/ryde-stats` and `.claude/skills/ryde-stats` through symlinks.
For another project, explicitly install a copy from the package:

```sh
# Default scope: the current project.
uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde skill --agent codex
uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde skill --agent claude

# Optional: install for your user rather than the current project.
uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde skill --agent codex --scope user
uvx --from git+https://github.com/HelgeSverre/ryde-cli ryde skill --agent claude --scope user
```

The installer writes `.agents/skills/ryde-stats` for Codex or
`.claude/skills/ryde-stats` for Claude, under the current directory or home
according to scope. Existing skills are preserved unless `--force` is supplied;
symlinked skills must be updated at their source. Remove the installed skill
directory to uninstall it.

Invoke `$ryde-stats` in Codex or `/ryde-stats` in Claude Code, or ask naturally
for your Ryde stats. The skill permits normal automatic discovery and respects
existing user authorization. Authentication remains interactive; agents never
need to extract or inspect the saved token.

[Codex skill discovery](https://developers.openai.com/codex/skills/),
[Claude skill discovery](https://code.claude.com/docs/en/skills), and the
[Agent Skills specification](https://agentskills.io/specification) describe the
shared SKILL.md format and different discovery paths. This repository uses one
canonical skill source to keep those copies consistent. Root `AGENTS.md`
contains development guidance; `CLAUDE.md` imports it.

## Ask an agent to show your stats

Example request after authentication:

> Fetch my Ryde ride history, including precise recorded routes, and show my
> stats in the local dashboard. Keep the export private.

The agent calls `open_stats(include_sensitive_location=true)`, polls
`stats_job_status`, then returns the completed job's URL and counts. Without
precise-route authorization it leaves that parameter false; standard ride
records still contain endpoint locations. See [the dashboard contract](dashboard.md)
for tool parameters, storage, resumability, and server lifetime.

These tools run on their host machine. Local Claude/Codex sessions can open a
local dashboard; remote/cloud sessions cannot expose the same localhost URL to
a different machine automatically. MCP browser opening is opt-in. No public
tunnel, public dashboard, or remote MCP endpoint is created.

## Distribution decisions

| Surface | Current approach | Reason |
| --- | --- | --- |
| CLI and MCP | One Python wheel, run through uv | One login/config contract and no Node requirement for users |
| Dashboard | UI source in this repo; compiled assets in the wheel | Git and PyPI installs work without a frontend build |
| Agent skill | Portable SKILL.md, bundled in the wheel; explicit installer | Supports both clients without post-install configuration changes |
| Claude/Codex plugins | Deferred | MCP plus a skill already covers the local workflow |
| Remote hosting | Deferred | Would require separate authentication, access, and retention design |

Primary documentation supports the client configuration and skill formats
above. The packaging, background job, and local-server choices are this
project's design decisions. PyPI publishing remains a separate step; see
[distribution](distribution.md).
