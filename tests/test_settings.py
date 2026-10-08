"""The .env reader fills in missing settings without overriding real ones."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.settings import load_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_env_file_is_loaded_but_never_overrides(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nAGENT_MODEL="test-model"\nANTHROPIC_API_KEY=\nOTHER_SETTING=from-file\n')
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OTHER_SETTING", "from-shell")
    loaded = load_env(env)
    assert loaded == {"AGENT_MODEL": "test-model"}
    assert os.environ["AGENT_MODEL"] == "test-model"
    assert "ANTHROPIC_API_KEY" not in os.environ  # empty value means demo mode
    assert os.environ["OTHER_SETTING"] == "from-shell"  # the shell always wins


def test_missing_file_is_fine(tmp_path):
    assert load_env(tmp_path / "missing.env") == {}


def test_env_file_is_ignored_by_git():
    result = subprocess.run(["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, text=True)
    assert result.stdout.strip() == ".env"
    assert (ROOT / ".env.example").exists()
