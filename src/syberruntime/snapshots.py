"""Projection snapshots for deterministic rebuild checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.hashing import canonical_json, digest_json


@dataclass(frozen=True)
class Snapshot:
    log_size: int
    merkle_root_hash: str
    state_hash: str
    state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_size": self.log_size,
            "merkle_root_hash": self.merkle_root_hash,
            "state_hash": self.state_hash,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Snapshot":
        return cls(
            log_size=int(data["log_size"]),
            merkle_root_hash=str(data["merkle_root_hash"]),
            state_hash=str(data["state_hash"]),
            state=dict(data["state"]),
        )


class SnapshotStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "snapshots" / "latest.json"

    def write(self, snapshot: Snapshot) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(canonical_json(snapshot.to_dict()), encoding="utf-8")
        return self.path

    def read(self) -> Snapshot:
        return Snapshot.from_dict(json.loads(self.path.read_text(encoding="utf-8")))


def make_snapshot(*, log_size: int, merkle_root_hash: str, state: dict[str, Any]) -> Snapshot:
    return Snapshot(
        log_size=log_size,
        merkle_root_hash=merkle_root_hash,
        state_hash=digest_json(state),
        state=state,
    )
