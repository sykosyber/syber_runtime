"""Fail-closed empirical evidence loaders and acceptance predicates.

These reports close the held-out conformal and controlled RQ0/RQ6 gates
required by v1 Phase 2 acceptance, Phase 3 acceptance, and v1 section 7.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from syberruntime.confidence import ConformalCalibrator
from syberruntime.reports import (
    discover_json_reports,
    read_json_report,
    validate_canonical_report_id,
    validate_evidence_binding,
    validate_generated_at,
)


def discover_empirical_reports(directory: str | Path) -> tuple[Path, ...]:
    return discover_json_reports(directory)


def load_empirical_report(path: str | Path) -> dict[str, Any]:
    data = read_json_report(path)
    validate_canonical_report_id(data, label="empirical")
    validate_evidence_binding(data.get("evidence_binding"), label="empirical")
    validate_generated_at(data.get("generated_at"), label="empirical")
    if data.get("scope") != "n=1 feasibility evidence":
        raise ValueError("empirical scope must be n=1 feasibility evidence")
    if data.get("report_type") not in {"heldout_conformal_coverage", "rq0_rq6_controlled_baseline"}:
        raise ValueError("empirical report_type is not recognized")
    return data


def conformal_gate_passes(report: dict[str, Any]) -> bool:
    if report.get("report_type") != "heldout_conformal_coverage":
        return False
    result = report.get("result")
    if not isinstance(result, dict):
        return False
    calibration_count = _positive_int(result.get("calibration_count"))
    heldout_count = _positive_int(result.get("heldout_count"))
    alpha = _probability(result.get("alpha"))
    coverage = _probability(result.get("empirical_coverage"))
    threshold = result.get("threshold")
    calibration_scores = result.get("calibration_scores")
    heldout_scores = result.get("heldout_scores")
    if None in {calibration_count, heldout_count, alpha, coverage}:
        return False
    if not isinstance(calibration_scores, list) or not isinstance(heldout_scores, list):
        return False
    try:
        calibrator = ConformalCalibrator(
            calibration_scores=tuple(float(score) for score in calibration_scores),
            alpha=alpha,
        )
        recomputed_coverage = calibrator.empirical_coverage(
            [float(score) for score in heldout_scores]
        )
    except (TypeError, ValueError):
        return False
    return (
        calibration_count >= 5
        and heldout_count >= 5
        and calibration_count == len(calibration_scores)
        and heldout_count == len(heldout_scores)
        and isinstance(threshold, (int, float))
        and float(threshold) == calibrator.threshold
        and coverage == recomputed_coverage
        and coverage >= 1.0 - alpha
        and set(calibration_scores).isdisjoint(heldout_scores)
        and result.get("cohorts_disjoint") is True
        and result.get("scores_from_model_verbal_confidence") is False
    )


def rq0_rq6_gate_passes(report: dict[str, Any]) -> bool:
    if report.get("report_type") != "rq0_rq6_controlled_baseline":
        return False
    result = report.get("result")
    if not isinstance(result, dict) or result.get("preregistered_before_execution") is not True:
        return False
    rq0 = result.get("rq0")
    rq6 = result.get("rq6")
    if not isinstance(rq0, dict) or not isinstance(rq6, dict):
        return False
    operation_arm = rq0.get("operation_primary")
    baseline_arm = rq0.get("snapshot_baseline")
    grammar_arm = rq6.get("grammar_enforced")
    unbounded_arm = rq6.get("unbounded_generation")
    return (
        _completed_arm(operation_arm)
        and _completed_arm(baseline_arm)
        and isinstance(operation_arm.get("recomprehension_seconds"), (int, float))
        and isinstance(baseline_arm.get("recomprehension_seconds"), (int, float))
        and _completed_arm(grammar_arm)
        and _completed_arm(unbounded_arm)
        and grammar_arm.get("known_bad_test_passed") is False
        and grammar_arm.get("stabilization_blocked") is True
        and grammar_arm.get("accepted_downstream") is False
        and unbounded_arm.get("accepted_before_verification") is True
        and unbounded_arm.get("downstream_defect_detected") is True
    )


def _completed_arm(value: Any) -> bool:
    return isinstance(value, dict) and value.get("completed") is True


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _probability(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0.0 <= parsed <= 1.0 else None
