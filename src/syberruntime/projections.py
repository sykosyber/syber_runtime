"""Deterministic folds from the operation log into readable state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from syberruntime.debt import DebtLedger, obligations_from_feature
from syberruntime.models import ArtifactRef, Operation, Verb


class ProjectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactState:
    ref: ArtifactRef
    created_by: str
    thread_id: str
    stabilized_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref.to_dict(),
            "created_by": self.created_by,
            "thread_id": self.thread_id,
            "stabilized_by": self.stabilized_by,
        }


@dataclass(frozen=True)
class ThreadState:
    thread_id: str
    created_by: str
    forked_from: str | None
    operations: tuple[str, ...]
    heads: tuple[str, ...]
    artifacts: tuple[str, ...]
    stabilized_artifacts: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "created_by": self.created_by,
            "forked_from": self.forked_from,
            "operations": list(self.operations),
            "heads": list(self.heads),
            "artifacts": list(self.artifacts),
            "stabilized_artifacts": dict(sorted(self.stabilized_artifacts.items())),
        }


@dataclass(frozen=True)
class RuntimeState:
    operations: dict[str, Operation]
    threads: dict[str, ThreadState]
    artifacts: dict[str, ArtifactState]
    edges: tuple[tuple[str, str], ...]
    debt: DebtLedger

    def to_dict(self) -> dict[str, Any]:
        return {
            "operations": {key: self.operations[key].to_dict() for key in sorted(self.operations)},
            "threads": {key: self.threads[key].to_dict() for key in sorted(self.threads)},
            "artifacts": {key: self.artifacts[key].to_dict() for key in sorted(self.artifacts)},
            "edges": [list(edge) for edge in self.edges],
            "debt": self.debt.to_dict(),
        }

    def operation_graph(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": operation.id,
                    "type": operation.type,
                    "thread_id": operation.thread_id,
                    "center_id": operation.center_id,
                }
                for operation in sorted(self.operations.values(), key=lambda item: item.id)
            ],
            "edges": [list(edge) for edge in self.edges],
        }


def fold_operations(operations: list[Operation] | tuple[Operation, ...]) -> RuntimeState:
    operation_map: dict[str, Operation] = {}
    thread_builders: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, ArtifactState] = {}
    edges: list[tuple[str, str]] = []
    obligations = {}

    for operation in operations:
        if operation.id in operation_map:
            raise ProjectionError(f"Duplicate operation id: {operation.id}")

        for parent in operation.parents:
            if parent not in operation_map:
                raise ProjectionError(f"Operation {operation.id} references unknown parent {parent}")
            edges.append((parent, operation.id))

        operation_map[operation.id] = operation

        if operation.type == Verb.THREAD_CREATE.value:
            _create_thread_builder(thread_builders, operation, forked_from=None)
        elif operation.type == Verb.THREAD_FORK.value:
            source_thread_id = operation.params.get("source_thread_id")
            if not source_thread_id or source_thread_id not in thread_builders:
                raise ProjectionError(f"ThreadFork {operation.id} references unknown source thread")
            _create_thread_builder(thread_builders, operation, forked_from=str(source_thread_id))
        else:
            if operation.thread_id not in thread_builders:
                raise ProjectionError(f"Operation {operation.id} references unknown thread {operation.thread_id}")
            _append_to_thread(thread_builders[operation.thread_id], operation)

        for ref in operation.outputs:
            artifacts[ref.digest] = ArtifactState(ref=ref, created_by=operation.id, thread_id=operation.thread_id)
            builder = thread_builders[operation.thread_id]
            if ref.digest not in builder["artifacts"]:
                builder["artifacts"].append(ref.digest)

        if operation.type == Verb.FEATURE.value:
            for obligation in obligations_from_feature(operation):
                if obligation.id in obligations:
                    raise ProjectionError(f"Duplicate debt obligation id: {obligation.id}")
                obligations[obligation.id] = obligation

        if operation.type in {Verb.TEST.value, Verb.VERIFY.value}:
            _apply_verification(operation, obligations)

        if operation.type == Verb.STABILIZE.value:
            _apply_stabilize(operation, thread_builders[operation.thread_id], artifacts)

    threads = {
        thread_id: ThreadState(
            thread_id=thread_id,
            created_by=builder["created_by"],
            forked_from=builder["forked_from"],
            operations=tuple(builder["operations"]),
            heads=tuple(sorted(builder["heads"])),
            artifacts=tuple(builder["artifacts"]),
            stabilized_artifacts=dict(sorted(builder["stabilized_artifacts"].items())),
        )
        for thread_id, builder in thread_builders.items()
    }

    return RuntimeState(
        operations=operation_map,
        threads=threads,
        artifacts=artifacts,
        edges=tuple(edges),
        debt=DebtLedger(obligations=obligations),
    )


def _create_thread_builder(
    thread_builders: dict[str, dict[str, Any]],
    operation: Operation,
    *,
    forked_from: str | None,
) -> None:
    if operation.thread_id in thread_builders:
        raise ProjectionError(f"Thread already exists: {operation.thread_id}")
    thread_builders[operation.thread_id] = {
        "created_by": operation.id,
        "forked_from": forked_from,
        "operations": [operation.id],
        "heads": {operation.id},
        "artifacts": [],
        "stabilized_artifacts": {},
    }


def _append_to_thread(builder: dict[str, Any], operation: Operation) -> None:
    builder["operations"].append(operation.id)
    for parent in operation.parents:
        if parent in builder["operations"]:
            builder["heads"].discard(parent)
    builder["heads"].add(operation.id)


def _apply_stabilize(
    operation: Operation,
    builder: dict[str, Any],
    artifacts: dict[str, ArtifactState],
) -> None:
    digests = [ref.digest for ref in operation.inputs]
    if not digests and operation.params.get("artifact_digest"):
        digests = [str(operation.params["artifact_digest"])]
    if not digests:
        digests = list(builder["artifacts"])

    for digest in digests:
        if digest not in artifacts:
            raise ProjectionError(f"Stabilize references unknown artifact {digest}")
        builder["stabilized_artifacts"][digest] = operation.id
        artifacts[digest] = replace(artifacts[digest], stabilized_by=operation.id)


def _apply_verification(operation: Operation, obligations: dict[str, Any]) -> None:
    verification = operation.params.get("verification", {})
    attempted = tuple(str(item) for item in verification.get("attempted_obligations", []))
    discharged = tuple(str(item) for item in verification.get("discharged_obligations", []))
    verifier_kind = str(verification.get("kind", "deterministic"))

    for obligation_id in attempted:
        if obligation_id not in obligations:
            raise ProjectionError(f"Verification references unknown obligation {obligation_id}")
        obligations[obligation_id] = obligations[obligation_id].mark_attempted(operation.id)

    if verification.get("passed") is not True:
        return

    for obligation_id in discharged:
        if obligation_id not in obligations:
            raise ProjectionError(f"Verification discharges unknown obligation {obligation_id}")
        obligations[obligation_id] = obligations[obligation_id].discharge(
            operation_id=operation.id,
            verifier_kind=verifier_kind,
        )
