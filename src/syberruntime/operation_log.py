"""Append-only hash-chained operation log.

Reads and appends are amortized O(new entries): each instance keeps an
in-process cache of validated entries keyed by the file's (size, mtime_ns).
A cold instance fully reads and validates the chain; afterwards only appended
bytes are parsed, and the appended suffix must chain onto the cached tail.

The cache is a performance layer, not the tamper-evidence mechanism: a fresh
instance (every CLI invocation) always revalidates the whole chain, and any
suffix that fails to chain triggers a full revalidating re-read.

Appends take an advisory lock on a sidecar file so concurrent writers cannot
interleave and break the hash chain.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable, Iterator

from syberruntime.hashing import canonical_json, digest_json
from syberruntime.merkle import ConsistencyProof, InclusionProof, MerkleHistoryTree
from syberruntime.models import Operation
from syberruntime.schema import upcast_operation_record

if os.name == "nt":
    import msvcrt
else:
    import fcntl


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
        self._entries: list[LogEntry] = []
        self._validated_stat: tuple[int, int] | None = None
        self.full_read_count = 0

    def append(self, operation: Operation) -> LogEntry:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_lock(self._lock_path()):
            self._refresh()
            prev_hash = self._entries[-1].entry_hash if self._entries else None
            index = len(self._entries)
            linked_operation = operation.with_prev_hash(prev_hash)
            linked_operation.validate_id()
            entry_hash = self.compute_entry_hash(index, linked_operation)
            entry = LogEntry(index=index, entry_hash=entry_hash, operation=linked_operation)

            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(canonical_json(entry.to_dict()))
                handle.write("\n")
            self._entries.append(entry)
            self._validated_stat = self._stat()
            return entry

    def entries(self, *, validate: bool = True) -> list[LogEntry]:
        self._refresh()
        return list(self._entries)

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

    def _refresh(self) -> None:
        stat = self._stat()
        if stat is None:
            self._entries = []
            self._validated_stat = None
            return
        if stat == self._validated_stat:
            return
        if self._validated_stat is not None and stat[0] > self._validated_stat[0]:
            try:
                suffix = self._read_entries(offset=self._validated_stat[0], first_line_number=len(self._entries) + 1)
                self.validate_entries(
                    suffix,
                    start_index=len(self._entries),
                    previous_hash=self._entries[-1].entry_hash if self._entries else None,
                )
            except LogIntegrityError:
                # The suffix did not chain onto the cached tail (offset landed
                # mid-line or the file was rewritten). Fall back to a full
                # revalidating read, which raises if the log is corrupt.
                self._full_read(stat)
                return
            self._entries.extend(suffix)
            self._validated_stat = stat
            return
        self._full_read(stat)

    def _full_read(self, stat: tuple[int, int]) -> None:
        self.full_read_count += 1
        entries = self._read_entries(offset=0, first_line_number=1)
        self.validate_entries(entries)
        self._entries = entries
        self._validated_stat = stat

    def _read_entries(self, *, offset: int, first_line_number: int) -> list[LogEntry]:
        entries: list[LogEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            handle.seek(offset)
            for line_number, line in enumerate(handle, start=first_line_number):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entries.append(LogEntry.from_dict(json.loads(stripped)))
                except Exception as exc:  # noqa: BLE001 - wrap parse and model validation as log integrity.
                    raise LogIntegrityError(f"Invalid log entry at line {line_number}: {exc}") from exc
        return entries

    def _stat(self) -> tuple[int, int] | None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_size, stat.st_mtime_ns)

    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def validate_entries(
        self,
        entries: Iterable[LogEntry],
        *,
        start_index: int = 0,
        previous_hash: str | None = None,
    ) -> None:
        for expected_index, entry in enumerate(entries, start=start_index):
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


@contextmanager
def _exclusive_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        _lock_handle(handle)
        try:
            yield
        finally:
            _unlock_handle(handle)


if os.name == "nt":

    def _lock_handle(handle: IO[bytes]) -> None:
        # msvcrt.LK_LOCK gives up after ~10 seconds; retry until acquired.
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                continue

    def _unlock_handle(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:

    def _lock_handle(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_EX)

    def _unlock_handle(handle: IO[bytes]) -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)
