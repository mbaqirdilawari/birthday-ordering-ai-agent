"""The terminal chat must stop cleanly on quit, Ctrl+C and the end of input."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_chat  # noqa: E402


def scripted(lines, ending):
    feed = iter(lines)

    def read(_prompt):
        try:
            return next(feed)
        except StopIteration:
            raise ending

    return read


@pytest.mark.parametrize("ending", [KeyboardInterrupt(), EOFError()])
def test_chat_ends_cleanly(ending, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    run_chat.main(read=scripted(["Show me the menu"], ending))
    out = capsys.readouterr().out
    assert "Mini Party Pack" in out
    assert run_chat.GOODBYE in out


def test_quit_command(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    run_chat.main(read=scripted(["quit"], EOFError()))
    assert run_chat.GOODBYE in capsys.readouterr().out
