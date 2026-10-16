"""Generate the command reference from argparse without contacting Ryde."""

from __future__ import annotations

import argparse
from pathlib import Path

from ryde_cli.cli import build_parser

TARGET = Path(__file__).resolve().parents[1] / "docs" / "commands.md"


def sections(parser: argparse.ArgumentParser) -> list[str]:
    parts = [f"## `{parser.prog}`\n\n```text\n{parser.format_help().rstrip()}\n```\n"]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                parts.extend(sections(child))
    return parts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the reference needs updating")
    args = parser.parse_args()
    content = (
        "# Full command reference\n\n"
        "Generated from the CLI parser. Regenerate with "
        "`uv run scripts/generate_command_reference.py`.\n\n"
        "Run these commands as `uv run ryde …` in a checkout, or "
        "`uvx --from ryde-cli ryde …` anywhere.\n"
        "Usage blocks below show argparse's executable name. Common options "
        "`--format`, `--output`, `--config`, `--base-url`, and `--mobile-type` "
        "also work after subcommands when passed as separate arguments.\n\n"
        + "\n".join(sections(build_parser()))
    )
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != content:
            raise SystemExit(
                "Command reference is stale: uv run scripts/generate_command_reference.py"
            )
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
