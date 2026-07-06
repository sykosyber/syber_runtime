"""Shared IO for JSON evidence reports (harness, dogfood, acceptance).

All evidence reports are canonical-JSON files in a flat directory. Writers and
discovery live here so every report kind serializes and sorts identically.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from syberruntime.hashing import canonical_json


def write_json_report(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload), encoding="utf-8")
    return path


def discover_json_reports(directory: str | Path) -> tuple[Path, ...]:
    path = Path(directory)
    if not path.exists():
        return ()
    return tuple(sorted(item for item in path.glob("*.json") if item.is_file()))


def read_json_report(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Report must be a JSON object: {path}")
    return data
