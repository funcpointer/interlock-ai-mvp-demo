from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonlLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, name: str, **fields: Any) -> None:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "event": name,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
