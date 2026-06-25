"""Canonical hashing utilities for operation and log identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def canonicalize(value: Any) -> Any:
    """Return a JSON-serializable value with deterministic ordering."""

    if is_dataclass(value):
        return canonicalize(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(canonicalize(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported value in canonical JSON: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def normalize_json(value: Any) -> Any:
    """Round-trip a value through canonical JSON to reject non-JSON inputs."""

    return json.loads(canonical_json(value))


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json(value).encode("utf-8"))
