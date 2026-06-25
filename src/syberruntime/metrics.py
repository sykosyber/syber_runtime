"""Phase 3 runtime metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syberruntime.models import Operation, Verb
from syberruntime.projections import RuntimeState


@dataclass(frozen=True)
class RuntimeMetrics:
    action_cost: int
    generated_artifacts: int
    validated_artifacts: int
    generative_return: float
    residual_debt: float
    provenance_completeness: float
    assumption_ledger_coverage: float
    false_discharge_rate: float
    discharge_efficiency_by_profile: dict[str, float]
    structural_rigor: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_cost": self.action_cost,
            "generated_artifacts": self.generated_artifacts,
            "validated_artifacts": self.validated_artifacts,
            "generative_return": self.generative_return,
            "residual_debt": self.residual_debt,
            "provenance_completeness": self.provenance_completeness,
            "assumption_ledger_coverage": self.assumption_ledger_coverage,
            "false_discharge_rate": self.false_discharge_rate,
            "discharge_efficiency_by_profile": dict(sorted(self.discharge_efficiency_by_profile.items())),
            "structural_rigor": self.structural_rigor,
        }


def compute_runtime_metrics(state: RuntimeState) -> RuntimeMetrics:
    operations = tuple(state.operations.values())
    feature_ops = tuple(operation for operation in operations if operation.type == Verb.FEATURE.value)
    generated_artifacts = len(state.artifacts)
    validated_artifacts = _validated_artifact_count(state)
    action_cost = len(operations)
    generative_return = _ratio(validated_artifacts, action_cost)
    provenance_completeness = _ratio(
        sum(1 for operation in operations if _has_minimal_provenance(operation)),
        len(operations),
    )
    assumption_ledger_coverage = _ratio(
        sum(1 for operation in feature_ops if operation.provenance.assumptions),
        len(feature_ops),
    )
    discharge_efficiency_by_profile = _discharge_efficiency_by_profile(state, operations)
    false_discharge_rate = _latest_false_discharge_rate(operations)
    debt_score = 1.0 / (1.0 + state.debt.total_residual_debt())
    structural_rigor = (provenance_completeness + assumption_ledger_coverage + debt_score + (1.0 - false_discharge_rate)) / 4

    return RuntimeMetrics(
        action_cost=action_cost,
        generated_artifacts=generated_artifacts,
        validated_artifacts=validated_artifacts,
        generative_return=generative_return,
        residual_debt=state.debt.total_residual_debt(),
        provenance_completeness=provenance_completeness,
        assumption_ledger_coverage=assumption_ledger_coverage,
        false_discharge_rate=false_discharge_rate,
        discharge_efficiency_by_profile=discharge_efficiency_by_profile,
        structural_rigor=structural_rigor,
    )


def _validated_artifact_count(state: RuntimeState) -> int:
    count = 0
    for digest, artifact in state.artifacts.items():
        if artifact.stabilized_by is None:
            continue
        if state.debt.open_obligations_for_artifact(digest):
            continue
        count += 1
    return count


def _has_minimal_provenance(operation: Operation) -> bool:
    return bool(operation.provenance.actor and operation.provenance.ts)


def _latest_false_discharge_rate(operations: tuple[Operation, ...]) -> float:
    rates = []
    for operation in operations:
        measurement = operation.params.get("measurement", {})
        if not measurement:
            continue
        if "false_discharge_rate" in measurement:
            rates.append(float(measurement["false_discharge_rate"]))
    return rates[-1] if rates else 0.0


def _discharge_efficiency_by_profile(state: RuntimeState, operations: tuple[Operation, ...]) -> dict[str, float]:
    samples: dict[str, list[float]] = {}
    artifact_profiles = {
        obligation.artifact_digest: obligation.rigor_profile
        for obligation in state.debt.obligations.values()
    }
    for operation in operations:
        measurement = operation.params.get("measurement", {})
        if measurement.get("kind") != "mutation_campaign":
            continue
        artifact_digest = str(measurement.get("artifact_digest", ""))
        profile = artifact_profiles.get(artifact_digest, "unknown")
        samples.setdefault(profile, []).append(float(measurement.get("discharge_efficiency", 0.0)))
    return {
        profile: sum(values) / len(values)
        for profile, values in sorted(samples.items())
        if values
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
