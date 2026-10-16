"""Reject runtime/private artifacts from Git and built Python distributions."""

from __future__ import annotations

import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {
    ".cache",
    ".routes",
    ".jobs",
    "node_modules",
    ".venv",
    "__pycache__",
    "stats-data",
    "exports",
}


def check(name: str) -> None:
    path = Path(name)
    if FORBIDDEN_PARTS.intersection(path.parts):
        raise SystemExit(f"Private/runtime artifact is included: {name}")
    if (
        path.name
        in {
            "config.json",
            ".ryde-token.json",
            ".owner.json",
            "manifest.json",
            "routes-checkpoint.jsonl",
        }
        or ".raw.json" in name
        or "public/data/" in name
    ):
        raise SystemExit(f"Private data/config filename is included: {name}")


def main() -> None:
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for name in filter(None, files):
        check(name)
        path = ROOT / name
        if path.is_file() and not path.is_symlink() and path.stat().st_size < 500_000:
            content = path.read_text(encoding="utf-8", errors="replace")
            if "/Users/" in content and name != "scripts/check_public_tree.py":
                raise SystemExit(f"Personal absolute path is included: {name}")
    for archive in (ROOT / "dist").glob("*"):
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as wheel:
                for name in wheel.namelist():
                    check(name)
                if (
                    "ryde_cli/web/index.html" not in wheel.namelist()
                    or "ryde_cli/agent_skill/SKILL.md" not in wheel.namelist()
                ):
                    raise SystemExit("Wheel is missing dashboard or agent skill")
        elif archive.name.endswith(".tar.gz"):
            with tarfile.open(archive) as source:
                for name in source.getnames():
                    check(name)
    print("Public tree and distribution artifact checks passed.")


if __name__ == "__main__":
    main()
