"""Patch-style operation graph merge helpers for Phase 1 tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from syberruntime.hashing import canonical_json
from syberruntime.models import Operation, Verb


class MergeError(RuntimeError):
    pass


@dataclass(frozen=True)
class MergeConflict:
    kind: str
    operation_ids: tuple[str, ...]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "operation_ids": list(self.operation_ids),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class MergeResult:
    operations: tuple[Operation, ...]
    conflicts: tuple[MergeConflict, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_ids": [operation.id for operation in self.operations],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }


def merge_operation_sequences(*sequences: Iterable[Operation]) -> MergeResult:
    operation_map: dict[str, Operation] = {}
    for sequence in sequences:
        for operation in sequence:
            existing = operation_map.get(operation.id)
            if existing is not None:
                if canonical_json(existing.to_dict()) != canonical_json(operation.to_dict()):
                    raise MergeError(f"Conflicting payloads for operation id {operation.id}")
                continue
            operation_map[operation.id] = operation

    ordered = tuple(_topological_order(operation_map))
    return MergeResult(operations=ordered, conflicts=_detect_artifact_name_conflicts(ordered))


def _topological_order(operation_map: dict[str, Operation]) -> list[Operation]:
    remaining = dict(operation_map)
    ordered: list[Operation] = []
    emitted: set[str] = set()

    while remaining:
        ready = [
            operation
            for operation in remaining.values()
            if all(parent in operation_map for parent in operation.parents)
            and all(parent in emitted for parent in operation.parents)
        ]
        missing_parent_ops = [
            operation
            for operation in remaining.values()
            if any(parent not in operation_map for parent in operation.parents)
        ]
        if missing_parent_ops:
            operation = sorted(missing_parent_ops, key=lambda item: item.id)[0]
            missing = sorted(parent for parent in operation.parents if parent not in operation_map)
            raise MergeError(f"Operation {operation.id} has missing parents: {missing}")
        if not ready:
            raise MergeError("Operation graph contains a cycle or unresolved dependency")
        operation = sorted(ready, key=lambda item: item.id)[0]
        ordered.append(operation)
        emitted.add(operation.id)
        del remaining[operation.id]
    return ordered


def _detect_artifact_name_conflicts(operations: tuple[Operation, ...]) -> tuple[MergeConflict, ...]:
    seen: dict[tuple[str, str], Operation] = {}
    conflicts: dict[tuple[str, str], MergeConflict] = {}

    for operation in operations:
        if operation.type != Verb.FEATURE.value:
            continue
        artifact_name = operation.params.get("artifact_name")
        if not artifact_name or not operation.outputs:
            continue
        key = (operation.thread_id, str(artifact_name))
        prior = seen.get(key)
        if prior is None:
            seen[key] = operation
            continue
        prior_digests = tuple(ref.digest for ref in prior.outputs)
        current_digests = tuple(ref.digest for ref in operation.outputs)
        if prior_digests != current_digests:
            operation_ids = tuple(sorted((prior.id, operation.id)))
            conflict_key = (key[0], key[1], operation_ids[0], operation_ids[1])
            conflicts[conflict_key] = MergeConflict(
                kind="artifact_name_conflict",
                operation_ids=operation_ids,
                detail=f"Independent Feature operations write different content for artifact name {artifact_name!r}",
            )

    return tuple(conflicts[key] for key in sorted(conflicts))
