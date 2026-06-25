"""Append-only hash-chained operation log."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from syberruntime.hashing import canonical_json, digest_json
from syberruntime.merkle import ConsistencyProof, InclusionProof, MerkleHistoryTree
from syberruntime.models import Operation
from syberruntime.schema import upcast_operation_record


class LogIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class LogEntry:
    index: int
    entry_hash: str
    operation: Operation

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "entry_hash": self.entry_hash,
            "operation": self.operation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LogEntry":
        return cls(
            index=int(data["index"]),
            entry_hash=str(data["entry_hash"]),
            operation=Operation.from_dict(upcast_operation_record(data["operation"])),
        )


class OperationLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, operation: Operation) -> LogEntry:
        entries = self.entries(validate=True)
        prev_hash = entries[-1].entry_hash if entries else None
        index = len(entries)
        linked_operation = operation.with_prev_hash(prev_hash)
        linked_operation.validate_id()
        entry_hash = self.compute_entry_hash(index, linked_operation)
        entry = LogEntry(index=index, entry_hash=entry_hash, operation=linked_operation)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(entry.to_dict()))
            handle.write("\n")
        return entry

    def operations(self, *, validate: bool = True) -> list[Operation]:
        return [entry.operation for entry in self.entries(validate=validate)]

    def merkle_tree(self) -> MerkleHistoryTree:
        return MerkleHistoryTree(tuple(entry.entry_hash for entry in self.entries(validate=True)))

    def merkle_root_hash(self) -> str:
        return self.merkle_tree().root_hash()

    def inclusion_proof(self, index: int) -> InclusionProof:
        return self.merkle_tree().inclusion_proof(index)

    def consistency_proof(self, old_size: int, new_size: int | None = None) -> ConsistencyProof:
        return self.merkle_tree().consistency_proof(old_size, new_size)

    def entries(self, *, validate: bool = True) -> list[LogEntry]:
        if not self.path.exists():
            return []

        entries: list[LogEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entries.append(LogEntry.from_dict(json.loads(stripped)))
                except Exception as exc:  # noqa: BLE001 - wrap parse and model validation as log integrity.
                    raise LogIntegrityError(f"Invalid log entry at line {line_number}: {exc}") from exc

        if validate:
            self.validate_entries(entries)
        return entries

    def validate_entries(self, entries: Iterable[LogEntry]) -> None:
        previous_hash: str | None = None
        for expected_index, entry in enumerate(entries):
            if entry.index != expected_index:
                raise LogIntegrityError(f"Unexpected log index {entry.index}; expected {expected_index}")
            if entry.operation.prev_hash != previous_hash:
                raise LogIntegrityError(
                    f"Broken hash chain at index {entry.index}: "
                    f"expected prev_hash {previous_hash}, found {entry.operation.prev_hash}"
                )
            try:
                entry.operation.validate_id()
            except ValueError as exc:
                raise LogIntegrityError(str(exc)) from exc
            expected_hash = self.compute_entry_hash(entry.index, entry.operation)
            if entry.entry_hash != expected_hash:
                raise LogIntegrityError(
                    f"Entry hash mismatch at index {entry.index}: "
                    f"expected {expected_hash}, found {entry.entry_hash}"
                )
            previous_hash = entry.entry_hash

    @staticmethod
    def compute_entry_hash(index: int, operation: Operation) -> str:
        return digest_json(
            {
                "index": index,
                "operation": operation.to_dict(),
            }
        )
