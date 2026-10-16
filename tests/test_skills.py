import shutil

import pytest

from ryde_cli.client import RydeError
from ryde_cli.skills import install_skill


def test_skill_install_is_explicit_scoped_and_does_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for agent, folder in [("codex", ".agents"), ("claude", ".claude")]:
        result = install_skill(agent, "project")
        target = tmp_path / folder / "skills" / "ryde-stats" / "SKILL.md"
        assert target.is_file()
        assert result["status"] == "installed"
        target.write_text("Existing user skill")
        with pytest.raises(RydeError, match="already exists"):
            install_skill(agent, "project")
        assert target.read_text() == "Existing user skill"
        assert install_skill(agent, "project", force=True)["status"] == "installed"
        assert "name: ryde-stats" in target.read_text()


def test_force_rejects_a_file_as_the_skill_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / ".agents" / "skills" / "ryde-stats"
    target.parent.mkdir(parents=True)
    target.write_text("existing file")
    with pytest.raises(RydeError, match="not a directory"):
        install_skill("codex", "project", force=True)
    assert target.read_text() == "existing file"


@pytest.mark.parametrize(
    "failure",
    [PermissionError("Permission denied"), shutil.Error([("source", "target", "copy failed")])],
)
def test_skill_copy_failures_are_reported_as_domain_errors(tmp_path, monkeypatch, failure):
    monkeypatch.chdir(tmp_path)

    def fail_copy(*args, **kwargs):
        raise failure

    monkeypatch.setattr("ryde_cli.skills.shutil.copytree", fail_copy)
    with pytest.raises(RydeError, match="could not install skill"):
        install_skill("claude", "project")
