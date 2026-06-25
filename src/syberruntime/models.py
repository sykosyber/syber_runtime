"""Core data model for the Phase 0 operation-primary kernel."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from syberruntime.hashing import digest_json, normalize_json


SCHEMA_VERSION = 1


class Verb(str, Enum):
    """Open, versioned operation verbs.

    The first eight verbs come from the v0.6 ontology. ThreadCreate and
    ThreadFork are Phase 0 lifecycle operations required to build the thread DAG.
    """

    FEATURE = "Feature"
    TEST = "Test"
    REFACTOR = "Refactor"
    RESEARCH = "Research"
    VERIFY = "Verify"
    COMPRESS = "Compress"
    SIMULATE = "Simulate"
    STABILIZE = "Stabilize"
    THREAD_CREATE = "ThreadCreate"
    THREAD_FORK = "ThreadFork"


class EvaluationStatus(str, Enum):
    UNVERIFIED = "unverified"
    PARTIAL = "partial"
    FULL = "full"


def _verb_value(value: Verb | str) -> str:
    return value.value if isinstance(value, Verb) else str(value)


def _status_value(value: EvaluationStatus | str) -> str:
    return value.value if isinstance(value, EvaluationStatus) else str(value)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class ArtifactRef:
    digest: str
    size: int
    media_type: str = "application/octet-stream"
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "size": self.size,
            "media_type": self.media_type,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactRef":
        return cls(
            digest=str(data["digest"]),
            size=int(data["size"]),
            media_type=str(data.get("media_type", "application/octet-stream")),
            name=data.get("name"),
        )


@dataclass(frozen=True)
class Evaluation:
    question: str
    obligations: tuple[str, ...] = ()
    status: str = EvaluationStatus.UNVERIFIED.value

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligations", tuple(str(item) for item in self.obligations))
        object.__setattr__(self, "status", _status_value(self.status))

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "obligations": list(self.obligations),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evaluation":
        return cls(
            question=str(data["question"]),
            obligations=tuple(str(item) for item in data.get("obligations", [])),
            status=str(data.get("status", EvaluationStatus.UNVERIFIED.value)),
        )


@dataclass(frozen=True)
class Provenance:
    actor: str = "human"
    retrievals: tuple[dict[str, Any], ...] = ()
    decisions: tuple[Any, ...] = ()
    assumptions: tuple[dict[str, Any], ...] = ()
    ts: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "retrievals", tuple(normalize_json(item) for item in self.retrievals))
        object.__setattr__(self, "decisions", tuple(normalize_json(item) for item in self.decisions))
        object.__setattr__(self, "assumptions", tuple(normalize_json(item) for item in self.assumptions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "retrievals": list(self.retrievals),
            "decisions": list(self.decisions),
            "assumptions": list(self.assumptions),
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Provenance":
        return cls(
            actor=str(data.get("actor", "human")),
            retrievals=tuple(data.get("retrievals", [])),
            decisions=tuple(data.get("decisions", [])),
            assumptions=tuple(data.get("assumptions", [])),
            ts=str(data["ts"]),
        )


@dataclass(frozen=True)
class Operation:
    id: str
    prev_hash: str | None
    type: str
    thread_id: str
    center_id: str
    parents: tuple[str, ...]
    inputs: tuple[ArtifactRef, ...]
    params: dict[str, Any]
    outputs: tuple[ArtifactRef, ...]
    evaluation: Evaluation
    provenance: Provenance
    nonce: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", _verb_value(self.type))
        object.__setattr__(self, "parents", tuple(str(item) for item in self.parents))
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "params", normalize_json(self.params))
        object.__setattr__(self, "outputs", tuple(self.outputs))

    @classmethod
    def build(
        cls,
        *,
        type: Verb | str,
        thread_id: str,
        center_id: str = "root",
        parents: tuple[str, ...] = (),
        inputs: tuple[ArtifactRef, ...] = (),
        params: dict[str, Any] | None = None,
        outputs: tuple[ArtifactRef, ...] = (),
        evaluation: Evaluation,
        provenance: Provenance | None = None,
        nonce: str | None = None,
        prev_hash: str | None = None,
    ) -> "Operation":
        operation = cls(
            id="",
            prev_hash=prev_hash,
            type=_verb_value(type),
            thread_id=thread_id,
            center_id=center_id,
            parents=parents,
            inputs=inputs,
            params=params or {},
            outputs=outputs,
            evaluation=evaluation,
            provenance=provenance or Provenance(),
            nonce=nonce or uuid4().hex,
        )
        return replace(operation, id=operation.compute_id())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "type": self.type,
            "thread_id": self.thread_id,
            "center_id": self.center_id,
            "parents": list(self.parents),
            "inputs": [item.to_dict() for item in self.inputs],
            "params": self.params,
            "outputs": [item.to_dict() for item in self.outputs],
            "evaluation": self.evaluation.to_dict(),
            "nonce": self.nonce,
        }

    def compute_id(self) -> str:
        return digest_json(self.identity_payload())

    def with_prev_hash(self, prev_hash: str | None) -> "Operation":
        return replace(self, prev_hash=prev_hash)

    def validate_id(self) -> None:
        expected = self.compute_id()
        if self.id != expected:
            raise ValueError(f"Operation id mismatch: expected {expected}, found {self.id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "prev_hash": self.prev_hash,
            "type": self.type,
            "thread_id": self.thread_id,
            "center_id": self.center_id,
            "parents": list(self.parents),
            "inputs": [item.to_dict() for item in self.inputs],
            "params": self.params,
            "outputs": [item.to_dict() for item in self.outputs],
            "evaluation": self.evaluation.to_dict(),
            "provenance": self.provenance.to_dict(),
            "nonce": self.nonce,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operation":
        operation = cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            id=str(data["id"]),
            prev_hash=data.get("prev_hash"),
            type=str(data["type"]),
            thread_id=str(data["thread_id"]),
            center_id=str(data.get("center_id", "root")),
            parents=tuple(str(item) for item in data.get("parents", [])),
            inputs=tuple(ArtifactRef.from_dict(item) for item in data.get("inputs", [])),
            params=dict(data.get("params", {})),
            outputs=tuple(ArtifactRef.from_dict(item) for item in data.get("outputs", [])),
            evaluation=Evaluation.from_dict(data["evaluation"]),
            provenance=Provenance.from_dict(data["provenance"]),
            nonce=str(data["nonce"]),
        )
        operation.validate_id()
        return operation
