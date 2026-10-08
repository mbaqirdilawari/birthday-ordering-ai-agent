"""Read settings from a local .env file, if there is one.

Lines look like NAME=value. Empty values and comment lines (starting with #) are
ignored, and a value already set in the environment always wins, so the file is
only a convenient default.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env(path: Path = ENV_FILE) -> dict[str, str]:
    """Load NAME=value pairs into os.environ. Returns the values that were set."""
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        value = value.strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value
            loaded[name] = value
    return loaded
