from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import SCHEMA_VERSION


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_run_dirs(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "crops").mkdir(exist_ok=True)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, *, records: list[Any] | None = None, meta: dict[str, Any] | None = None) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "records": records or [],
        "meta": meta or {},
    }
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def write_object(path: Path, obj: dict[str, Any]) -> None:
    payload = {"schema_version": SCHEMA_VERSION, **obj}
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def read_artifact(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
