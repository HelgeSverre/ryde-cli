import errno

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


def test_config_directory_is_reported_as_a_read_error(tmp_path):
    tmp_path.chmod(0o700)
    with pytest.raises(ConfigError, match="could not read configuration"):
        ConfigStore(str(tmp_path))


@pytest.mark.parametrize("content", [b"not-json", b"\xffsynthetic-private-data"])
def test_malformed_config_is_reported_without_its_contents(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_bytes(content)
    path.chmod(0o600)
    with pytest.raises(ConfigError, match="could not parse") as result:
        ConfigStore(str(path))
    assert "synthetic-private-data" not in str(result.value)


def test_failed_replace_preserves_original_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    secure_write_json(path, {"token": "synthetic-original"})

    def deny_replace(*_):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr("ryde_cli.config.os.replace", deny_replace)
    with pytest.raises(ConfigError, match="could not write file"):
        secure_write_json(path, {"token": "synthetic-replacement"})
    assert ConfigStore(str(path)).token() == "synthetic-original"
    assert list(tmp_path.iterdir()) == [path]
