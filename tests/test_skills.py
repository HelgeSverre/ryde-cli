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
