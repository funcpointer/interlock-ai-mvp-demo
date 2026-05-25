from __future__ import annotations

import os
from pathlib import Path


DEFAULT_OLD_REPO_ENV = Path("/Users/kc/Documents/Claude/Projects/interlock-ai-v2/.env")
DEFAULT_OPENAI_KEY_FILE = Path.home() / "oumi" / ".openai.key"


def load_env_file(path: Path | None) -> list[str]:
    loaded: list[str] = []
    env_path = path or (DEFAULT_OLD_REPO_ENV if DEFAULT_OLD_REPO_ENV.exists() else None)
    if not env_path or not env_path.exists():
        return loaded
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def load_key_files() -> list[str]:
    loaded: list[str] = []
    if DEFAULT_OPENAI_KEY_FILE.exists() and not os.environ.get("OPENAI_API_KEY"):
        key = DEFAULT_OPENAI_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            os.environ["OPENAI_API_KEY"] = key
            loaded.append("OPENAI_API_KEY")
    return loaded
