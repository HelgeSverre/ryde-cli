"""Explicit, opt-in installation of the bundled portable agent skill."""

from __future__ import annotations

import shutil
from pathlib import Path

from .client import RydeError

SOURCE = Path(__file__).with_name("agent_skill")


def install_skill(agent: str, scope: str, *, force: bool = False) -> dict[str, str]:
    root = Path.home() if scope == "user" else Path.cwd()
    target = root / (".agents" if agent == "codex" else ".claude") / "skills" / "ryde-stats"
    if target.resolve() == SOURCE.resolve():
        return {"path": str(target), "status": "already available"}
    if target.exists() or target.is_symlink():
        if not force:
            raise RydeError(f"skill already exists at {target}; use --force to replace its files")
        if target.is_symlink():
            raise RydeError("refusing to overwrite a symlinked skill; update its source instead")
    shutil.copytree(SOURCE, target, dirs_exist_ok=True)
    return {"path": str(target), "status": "installed"}
