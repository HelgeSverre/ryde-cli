import pytest

from ryde_cli.config import ConfigError, ConfigStore, secure_write_json


def test_rejects_readable_secret_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}")
    path.chmod(0o644)
    with pytest.raises(ConfigError, match="insecure"):
        ConfigStore(str(path))


def test_config_saved_privately_and_env_token_wins(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    secure_write_json(path, {"token": "synthetic-saved"})
    store = ConfigStore(str(path))
    assert store.token() == "synthetic-saved"
    monkeypatch.setenv("RYDE_TOKEN", "synthetic-env")
    assert store.token() == "synthetic-env"
    assert path.stat().st_mode & 0o777 == 0o600
