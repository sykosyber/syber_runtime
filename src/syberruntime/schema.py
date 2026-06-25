"""Event schema versioning and upcasting."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from syberruntime.models import SCHEMA_VERSION


def upcast_operation_record(data: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(data)
    version = int(record.get("schema_version", 0))
    if version == SCHEMA_VERSION:
        return record
    if version < 1:
        record = _upcast_v0_to_v1(record)
        version = 1
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported operation schema version: {version}")
    return record


def _upcast_v0_to_v1(record: dict[str, Any]) -> dict[str, Any]:
    record.setdefault("schema_version", 1)
    record.setdefault("center_id", "root")
    record.setdefault("parents", [])
    record.setdefault("inputs", [])
    record.setdefault("outputs", [])
    record.setdefault("params", {})
    record.setdefault("nonce", record.get("id", "legacy"))
    record.setdefault(
        "evaluation",
        {
            "question": "Legacy operation imported without an explicit success question.",
            "obligations": [],
            "status": "unverified",
        },
    )
    record.setdefault(
        "provenance",
        {
            "actor": "legacy",
            "retrievals": [],
            "decisions": [],
            "assumptions": [],
            "ts": "1970-01-01T00:00:00+00:00",
        },
    )
    return record
