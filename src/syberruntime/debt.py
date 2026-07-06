"""Verification-debt projection types for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from syberruntime.hashing import digest_json
from syberruntime.models import Operation


class ObligationStatus(str, Enum):
    OPEN = "open"
    DISCHARGED = "discharged"


def feature_obligation_id(*, feature_nonce: str, artifact_digest: str, output_index: int) -> str:
    return digest_json(
        {
            "kind": "TestObligation",
            "feature_nonce": feature_nonce,
            "artifact_digest": artifact_digest,
            "output_index": output_index,
        }
    )


def feature_obligation_payload(
    *,
    obligation_id: str,
    artifact_digest: str,
    generative_mass: float,
    blast_radius: float,
    criticality: float,
    accrual_rate: float,
    rigor_profile: str,
    floor_required: bool,
) -> dict[str, Any]:
    """Canonical per-obligation entry stored in Feature params.

    This is the single writer-side counterpart of `obligations_from_feature`;
    keep the two in sync when the obligation schema changes.
    """

    return {
        "id": obligation_id,
        "artifact_digest": artifact_digest,
        "generative_mass": float(generative_mass),
        "blast_radius": float(blast_radius),
        "criticality": float(criticality),
        "accrual_rate": float(accrual_rate),
        "incurred_debt": float(generative_mass) * float(blast_radius) * float(criticality) * float(accrual_rate),
        "rigor_profile": rigor_profile,
        "floor_required": floor_required,
    }


@dataclass(frozen=True)
class DebtObligation:
    id: str
    source_operation_id: str
    artifact_digest: str
    thread_id: str
    center_id: str
    rigor_profile: str
    incurred_debt: float
    residual_debt: float
    floor_required: bool
    status: str = ObligationStatus.OPEN.value
    discharged_by: str | None = None
    verifier_kind: str | None = None
    attempts: tuple[str, ...] = ()

    def mark_attempted(self, operation_id: str) -> "DebtObligation":
        if operation_id in self.attempts:
            return self
        return replace(self, attempts=self.attempts + (operation_id,))

    def discharge(self, *, operation_id: str, verifier_kind: str) -> "DebtObligation":
        return replace(
            self.mark_attempted(operation_id),
            residual_debt=0.0,
            status=ObligationStatus.DISCHARGED.value,
            discharged_by=operation_id,
            verifier_kind=verifier_kind,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_operation_id": self.source_operation_id,
            "artifact_digest": self.artifact_digest,
            "thread_id": self.thread_id,
            "center_id": self.center_id,
            "rigor_profile": self.rigor_profile,
            "incurred_debt": self.incurred_debt,
            "residual_debt": self.residual_debt,
            "floor_required": self.floor_required,
            "status": self.status,
            "discharged_by": self.discharged_by,
            "verifier_kind": self.verifier_kind,
            "attempts": list(self.attempts),
        }


@dataclass(frozen=True)
class DebtLedger:
    obligations: dict[str, DebtObligation]

    def total_residual_debt(self) -> float:
        return round(sum(obligation.residual_debt for obligation in self.obligations.values()), 12)

    def residual_debt_for_center(self, center_id: str) -> float:
        return round(
            sum(
                obligation.residual_debt
                for obligation in self.obligations.values()
                if obligation.center_id == center_id
            ),
            12,
        )

    def open_obligations_for_artifact(self, artifact_digest: str) -> tuple[DebtObligation, ...]:
        return tuple(
            obligation
            for obligation in sorted(self.obligations.values(), key=lambda item: item.id)
            if obligation.artifact_digest == artifact_digest
            and obligation.status == ObligationStatus.OPEN.value
            and obligation.residual_debt > 0
        )

    def open_floor_obligations_for_artifact(self, artifact_digest: str) -> tuple[DebtObligation, ...]:
        return tuple(
            obligation
            for obligation in self.open_obligations_for_artifact(artifact_digest)
            if obligation.floor_required
        )

    def to_dict(self) -> dict[str, Any]:
        by_center: dict[str, float] = {}
        for obligation in self.obligations.values():
            by_center[obligation.center_id] = by_center.get(obligation.center_id, 0.0) + obligation.residual_debt
        return {
            "total_residual_debt": self.total_residual_debt(),
            "residual_debt_by_center": {
                center_id: round(debt, 12) for center_id, debt in sorted(by_center.items())
            },
            "obligations": {
                obligation_id: self.obligations[obligation_id].to_dict()
                for obligation_id in sorted(self.obligations)
            },
        }


def obligations_from_feature(operation: Operation) -> list[DebtObligation]:
    debt_params = operation.params.get("debt", {})
    obligations_payload = {
        str(item.get("id")): item
        for item in debt_params.get("obligations", [])
        if isinstance(item, dict) and item.get("id")
    }
    declared_ids = list(operation.evaluation.obligations)
    obligations: list[DebtObligation] = []

    for index, ref in enumerate(operation.outputs):
        obligation_id = (
            declared_ids[index]
            if index < len(declared_ids)
            else feature_obligation_id(
                feature_nonce=operation.nonce,
                artifact_digest=ref.digest,
                output_index=index,
            )
        )
        payload = obligations_payload.get(obligation_id, {})
        generative_mass = float(payload.get("generative_mass", debt_params.get("generative_mass", 1.0)))
        blast_radius = float(payload.get("blast_radius", debt_params.get("blast_radius", 1.0)))
        criticality = float(payload.get("criticality", debt_params.get("criticality", 1.0)))
        accrual_rate = float(payload.get("accrual_rate", debt_params.get("accrual_rate", 1.0)))
        incurred = float(payload.get("incurred_debt", generative_mass * blast_radius * criticality * accrual_rate))
        obligations.append(
            DebtObligation(
                id=obligation_id,
                source_operation_id=operation.id,
                artifact_digest=ref.digest,
                thread_id=operation.thread_id,
                center_id=operation.center_id,
                rigor_profile=str(payload.get("rigor_profile", debt_params.get("rigor_profile", "production"))),
                incurred_debt=incurred,
                residual_debt=incurred,
                floor_required=bool(payload.get("floor_required", debt_params.get("floor_required", True))),
            )
        )
    return obligations
