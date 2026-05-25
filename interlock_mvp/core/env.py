from __future__ import annotations

import os
from pathlib import Path


DEFAULT_ENV_FILE = Path(os.environ.get("INTERLOCK_ENV_FILE", ".env.local"))
DEFAULT_OLD_REPO_ENV = DEFAULT_ENV_FILE
DEFAULT_OPENAI_KEY_FILE = Path.home() / "oumi" / ".openai.key"


def load_env_file(path: Path | None) -> list[str]:
    loaded: list[str] = []
    env_path = path or (DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None)
    if not env_path or not env_path.exists():
        return loaded
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_assignment(line)
        if not parsed:
            continue
        key, value = parsed
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def load_key_files() -> list[str]:
    loaded: list[str] = []
    if DEFAULT_OPENAI_KEY_FILE.exists() and not os.environ.get("OPENAI_API_KEY"):
        raw_key = DEFAULT_OPENAI_KEY_FILE.read_text(encoding="utf-8").strip()
        parsed = _parse_env_assignment(raw_key)
        key = parsed[1] if parsed and parsed[0] == "OPENAI_API_KEY" else raw_key
        if key:
            os.environ["OPENAI_API_KEY"] = key
            loaded.append("OPENAI_API_KEY")
    return loaded


def _parse_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    return (key, value) if key else None
