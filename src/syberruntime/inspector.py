"""Readable inspection projections for artifacts."""

from __future__ import annotations

from typing import Any

from syberruntime.projections import RuntimeState


def inspect_artifact(state: RuntimeState, artifact_digest: str) -> dict[str, Any]:
    if artifact_digest not in state.artifacts:
        raise KeyError(f"Unknown artifact: {artifact_digest}")
    artifact = state.artifacts[artifact_digest]
    created_by = state.operations[artifact.created_by]
    lineage = _operation_lineage(state, created_by.id)
    verification_ops = [
        operation
        for operation in state.operations.values()
        if operation.type in {"Test", "Verify"}
        and any(ref.digest == artifact_digest for ref in operation.inputs)
    ]
    obligations = [
        obligation.to_dict()
        for obligation in state.debt.obligations.values()
        if obligation.artifact_digest == artifact_digest
    ]

    return {
        "artifact": artifact.to_dict(),
        "created_by": created_by.to_dict(),
        "lineage": [operation.to_dict() for operation in lineage],
        "assumptions": list(created_by.provenance.assumptions),
        "verification": [operation.to_dict() for operation in sorted(verification_ops, key=lambda item: item.id)],
        "debt_obligations": obligations,
        "stabilized_by": state.operations[artifact.stabilized_by].to_dict()
        if artifact.stabilized_by
        else None,
    }


def _operation_lineage(state: RuntimeState, operation_id: str) -> tuple[Any, ...]:
    visited: set[str] = set()
    ordered: list[Any] = []

    def visit(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)
        operation = state.operations[current_id]
        for parent in operation.parents:
            visit(parent)
        ordered.append(operation)

    visit(operation_id)
    return tuple(ordered)
