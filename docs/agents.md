# Agent setup

The package provides both a stdio MCP server and a portable `ryde-stats` skill.
MCP supplies typed operations; the skill teaches the authenticated
fetch → poll → show-dashboard workflow. Neither requires a hosted service.

[Claude Code](#claude-code-mcp-setup) · [Codex](#codex-mcp-setup) ·
[Gemini CLI](#gemini-cli) · [GitHub Copilot CLI](#github-copilot-cli) ·
[Amp](#amp) · [Cursor](#cursor) · [VS Code](#vs-code) · [Zed](#zed) ·
[OpenCode](#opencode) · [Other clients](#other-mcp-clients)

## Authenticate first

Do this interactively on the machine that will run the tools:

```sh
uvx --from ryde-cli ryde login
```

**SMS login currently stops when Ryde requires Android reCAPTCHA verification.**
See [login compatibility](api.md#login-status). Registering an MCP server does
not complete that verification or sign you in.

The user's token stays in their local `0600` config. Do not paste tokens, SMS
codes, or config contents into agent chat or project config. A custom
`RYDE_CONFIG` path must be supplied to both login and the MCP launcher.

## Codex MCP setup

```sh
codex mcp add ryde -- uvx --from ryde-cli ryde-mcp
codex mcp list
```

For a non-default config:

```sh
codex mcp add ryde --env RYDE_CONFIG=/absolute/path/to/ryde-config.json -- uvx --from ryde-cli ryde-mcp
```

This registers a user-level stdio server. Remove it with `codex mcp remove ryde`.
Codex also supports MCP configuration in its TOML config; see
[Codex MCP documentation](https://developers.openai.com/codex/mcp/).

To configure it manually, add this to `~/.codex/config.toml` (shared by the CLI,
IDE extension, and desktop app), or `.codex/config.toml` in a trusted project:

```toml
[mcp_servers.ryde]
command = "uvx"
args = ["--from", "ryde-cli", "ryde-mcp"]
```

Use `/mcp` in the Codex CLI to inspect connected servers.

## Claude Code MCP setup

```sh
claude mcp add --transport stdio --scope user ryde -- uvx --from ryde-cli ryde-mcp
claude mcp get ryde
```

For a non-default config, add `--env
RYDE_CONFIG=/absolute/path/to/ryde-config.json` before `--`. User scope makes
this server available across local projects. Remove it with
`claude mcp remove --scope user ryde`. Review the permissions shown by your
client before enabling access to personal data.
[Claude MCP documentation](https://code.claude.com/docs/en/mcp).

Use `/mcp` in Claude Code to inspect the connection. Replace `--scope user`
with `--scope project` for a shared `.mcp.json` entry.

## Gemini CLI

```sh
gemini mcp add --scope user ryde uvx -- --from ryde-cli ryde-mcp
gemini mcp list
```

The `--` passes the remaining flags to `uvx`. User scope writes
`~/.gemini/settings.json`; use `--scope project` for `.gemini/settings.json`.
Use `/mcp` inside Gemini to check the connection. Remove the entry with
`gemini mcp remove --scope user ryde`.

[Gemini CLI MCP documentation](https://geminicli.com/docs/tools/mcp-server/).

## GitHub Copilot CLI

```sh
copilot mcp add ryde -- uvx --from ryde-cli ryde-mcp
copilot mcp list
```

This adds a user entry in `~/.copilot/mcp-config.json`. Use `/mcp` inside
Copilot to inspect the connection. Remove it with `copilot mcp remove ryde`.

[Copilot CLI MCP documentation](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers).

## Amp

```sh
amp mcp add ryde -- uvx --from ryde-cli ryde-mcp
amp mcp list
```

This updates `~/.config/amp/settings.json`. Add `--workspace` before `--` to
use workspace settings instead. Remove the entry with `amp mcp remove ryde`.

[Amp MCP documentation](https://ampcode.com/docs/customize/mcp).

## Cursor

Merge this into `.cursor/mcp.json` in a project, or `~/.cursor/mcp.json` for your user:

```json
{
  "mcpServers": {
    "ryde": {
      "command": "uvx",
      "args": ["--from", "ryde-cli", "ryde-mcp"]
    }
  }
}
```

Check Cursor Settings → Tools & MCP for connection status. Remove the `ryde`
entry to disconnect it.

[Cursor MCP documentation](https://cursor.com/docs/mcp).

## VS Code

Register in your current user profile:

```sh
code --add-mcp '{"name":"ryde","command":"uvx","args":["--from","ryde-cli","ryde-mcp"]}'
```

For a workspace entry, `.vscode/mcp.json` uses `servers` as its top-level key:

```json
{
  "servers": {
    "ryde": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "ryde-cli", "ryde-mcp"]
    }
  }
}
```

Use **MCP: List Servers** to inspect it, and **MCP: Open User Configuration**
to edit or remove the profile entry. Remove workspace entries from `.vscode/mcp.json`.

[VS Code MCP documentation](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

## Zed

Merge this into Zed's `settings.json` (open it with **zed: open settings file**):

```json
{
  "context_servers": {
    "ryde": {
      "command": "uvx",
      "args": ["--from", "ryde-cli", "ryde-mcp"]
    }
  }
}
```

Check Settings → AI → MCP Servers for connection status. Remove the `ryde`
entry to disconnect it.

[Zed MCP documentation](https://zed.dev/docs/ai/mcp).

## OpenCode

Merge this into `opencode.json` in your project:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ryde": {
      "type": "local",
      "command": ["uvx", "--from", "ryde-cli", "ryde-mcp"],
      "enabled": true
    }
  }
}
```

OpenCode uses an array containing the executable and its arguments. Check with
`opencode mcp list`; remove the entry or set `enabled` to `false` to disconnect.

[OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers/).

## Other MCP clients

For clients with a local stdio server form, use:

| Field | Value |
| --- | --- |
| Name | `ryde` |
| Transport | `stdio` / local command |
| Command | `uvx` |
| Arguments | `--from`, `ryde-cli`, `ryde-mcp` (three separate arguments) |

Clients accepting `mcpServers` JSON can use the [Cursor example](#cursor).
Merge entries into existing settings rather than replacing other servers.
The default CLI login is shared automatically; no extra environment is needed.
For a custom config, add `RYDE_CONFIG` to the server environment as in the
[Codex example](#codex-mcp-setup).

If a desktop app cannot find `uvx`, run `command -v uvx` and use that absolute
path as the command. Restart the client after changing its config. The first
launch may take longer while uv downloads the package; increase the client's
startup timeout if necessary. Pin `ryde-cli==0.1.1` in place of `ryde-cli` when
you need a fixed version.

## Install the workflow skill

In a cloned repository, the canonical skill is already exposed in both
`.agents/skills/ryde-stats` and `.claude/skills/ryde-stats` through symlinks.
For another project, explicitly install a copy from the package:

```sh
# Default scope: the current project.
uvx --from ryde-cli ryde skill --agent codex
uvx --from ryde-cli ryde skill --agent claude

# Optional: install for your user rather than the current project.
uvx --from ryde-cli ryde skill --agent codex --scope user
uvx --from ryde-cli ryde skill --agent claude --scope user
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

For city-specific prices, call `list_cities(query="Bergen")` first and use the
returned `cityId` in `pass_catalogue`, `city_fee_rule`, or `recommend_ridepass`.
Resolve ambiguous names before continuing; do not guess IDs.

These tools run on their host machine. Local Claude/Codex sessions can open a
local dashboard; remote/cloud sessions cannot expose the same localhost URL to
a different machine automatically. MCP browser opening is opt-in. No public
tunnel, public dashboard, or remote MCP endpoint is created.

See [distribution and releases](distribution.md) for installation and publishing.
