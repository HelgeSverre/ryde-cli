"""Local configuration and secret-token handling."""

from __future__ import annotations

import json
import os
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://qw-test.ryde.vip/"
DEFAULT_MOBILE_TYPE = "Android/samsung/SM-G991B/samsung"
DEFAULT_PHONE_INFO = "Android 14; SM-G991B"


class ConfigError(RuntimeError):
    """A local configuration file could not be safely used."""


def config_path(value: str | None = None) -> Path:
    """Return the explicit/configured default config path."""
    if value:
        return Path(value).expanduser()
    if os.environ.get("RYDE_CONFIG"):
        return Path(os.environ["RYDE_CONFIG"]).expanduser()
    return Path.home() / ".config" / "ryde-cli" / "config.json"


def secure_read_json(path: Path) -> dict[str, Any]:
    """Read config, rejecting group/world-readable secret files."""
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise ConfigError(f"refusing insecure configuration file {path} (expected mode 0600)")
        result = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(
            f"could not read configuration file {path}: {exc.strerror or exc}"
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"could not parse configuration file {path}") from exc
    if not isinstance(result, dict):
        raise ConfigError(f"configuration file {path} must contain a JSON object")
    return result


def secure_write_text(path: Path, content: str) -> None:
    """Atomically write an owner-only file, reporting filesystem failures."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.chmod(temp, 0o600)
            os.replace(temp, path)
            os.chmod(path, 0o600)
        finally:
            temp.unlink(missing_ok=True)
    except OSError as exc:
        raise ConfigError(f"could not write file {path}: {exc.strerror or exc}") from exc


def secure_write_json(path: Path, value: Any) -> None:
    """Atomically save JSON with owner-only permissions."""
    secure_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


class ConfigStore:
    """A tiny 0600 JSON-backed store; it never emits token values."""

    def __init__(self, path: str | None = None) -> None:
        self.path = config_path(path)
        self.data = secure_read_json(self.path)

    def save(self) -> None:
        secure_write_json(self.path, self.data)

    def token(self) -> str:
        return os.environ.get("RYDE_TOKEN") or str(self.data.get("token") or "")

    def device_id(self) -> str:
        return os.environ.get("RYDE_DEVICE_ID") or str(
            self.data.setdefault("device_id", "and" + secrets.token_hex(8))
        )

    def base_url(self) -> str:
        return os.environ.get("RYDE_BASE_URL") or str(self.data.get("base_url") or DEFAULT_BASE_URL)

    def mobile_type(self) -> str:
        return os.environ.get("RYDE_MOBILE_TYPE") or str(
            self.data.get("mobile_type") or DEFAULT_MOBILE_TYPE
        )

    def phone_info(self) -> str:
        return os.environ.get("RYDE_PHONE_INFO") or str(
            self.data.get("phone_info") or DEFAULT_PHONE_INFO
        )
