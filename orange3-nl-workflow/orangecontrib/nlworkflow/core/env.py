"""Environment loading helpers."""

from __future__ import annotations

import os
from pathlib import Path


def addon_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    env_path = Path(path).expanduser() if path else addon_root() / ".env"
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def get_env(name: str, default: str | None = None) -> str | None:
    load_env_file()
    return os.environ.get(name, default)
