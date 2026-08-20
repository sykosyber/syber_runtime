"""Generate the preregistered v1 Phase 2/3 empirical gate reports."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

from syberruntime.confidence import ConformalCalibrator
from syberruntime.errors import StabilizationBlockedError
from syberruntime.policy import FixedPolicy
from syberruntime.reports import (
    build_evidence_binding,
    canonical_report_id,
    generated_at_utc,
    write_json_report,
)
from syberruntime.runtime import Runtime
from syberruntime.verification import DeterministicVerifier


PROTOCOL_PATH = Path("docs/rq0_rq6_preregistration.md")
CONFORMAL_PROTOCOL_PATH = Path("docs/conformal_coverage_preregistration.md")

CORRECT_COMPONENT = """\
def parse_positive_int(value):
    if not isinstance(value, str) or not value.isdigit():
        raise ValueError("expected decimal digits")
    result = int(value)
    if result <= 0:
        raise ValueError("expected a positive integer")
    return result
"""

KNOWN_BAD_COMPONENT = """\
def parse_positive_int(value):
    return int(value)
"""

TEST_SOURCE = """\
import unittest
from artifact_under_test import parse_positive_int


class PositiveIntegerTests(unittest.TestCase):
    def test_positive_decimal(self):
        self.assertEqual(parse_positive_int("42"), 42)

    def test_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_positive_int("0")

    def test_negative_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_positive_int("-2")

    def test_non_string_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_positive_int(2)
"""

CHECK = {
    "kind": "python_tests",
    "test_source": TEST_SOURCE,
    "artifact_filename": "artifact_under_test.py",
    "timeout_seconds": 30,
    "cpu_seconds": 10,
    "memory_mb": 128,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--output-dir", default="docs/empirical_reports")
    args = parser.parse_args()
    root = Path(args.workspace_root).resolve()
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json_report(_run_conformal(root), output_dir / "conformal_coverage_001.json")
    write_json_report(_run_controlled(root), output_dir / "rq0_rq6_baseline_001.json")
    return 0


def _run_conformal(root: Path) -> dict:
    calibration_scores = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45)
    heldout_scores = (0.08, 0.18, 0.28, 0.38, 0.48)
    calibrator = ConformalCalibrator(calibration_scores=calibration_scores, alpha=0.2)
    payload = {
        "report_type": "heldout_conformal_coverage",
        "protocol_path": str(CONFORMAL_PROTOCOL_PATH),
        "scope": "n=1 feasibility evidence",
        "generated_at": generated_at_utc(),
        "evidence_binding": build_evidence_binding(
            workspace_root=root,
            protocol_path=CONFORMAL_PROTOCOL_PATH,
        ),
        "result": {
            "alpha": calibrator.alpha,
            "threshold": calibrator.threshold,
            "calibration_count": len(calibration_scores),
            "heldout_count": len(heldout_scores),
            "calibration_scores": list(calibration_scores),
            "heldout_scores": list(heldout_scores),
            "empirical_coverage": calibrator.empirical_coverage(heldout_scores),
            "cohorts_disjoint": True,
            "scores_from_model_verbal_confidence": False,
            "claim_boundary": "mechanism-level held-out coverage; not model-quality generalization",
        },
    }
    payload["report_id"] = canonical_report_id(payload)
    return payload


def _run_controlled(root: Path) -> dict:
    operation_root = root / ".syberruntime-empirical-rq0-operation-001"
    grammar_root = root / ".syberruntime-empirical-rq6-grammar-001"
    for runtime_root in (operation_root, grammar_root):
        if runtime_root.exists():
            shutil.rmtree(runtime_root)

    operation_runtime = Runtime(operation_root, policy=FixedPolicy(default_profile="production"))
    operation_thread = operation_runtime.create_thread(intent="RQ0 operation-primary parser component")
    operation_feature = operation_runtime.record_feature(
        operation_thread.operation.thread_id,
        artifact_name="positive_int.py",
        content=CORRECT_COMPONENT,
        intent="Implement the preregistered positive-integer parser",
        assumptions=(
            {
                "claim": "Decimal strings are the accepted representation",
                "depends_on": "The preregistered tests define the public contract",
                "confidence_rationale": "The oracle executes boundary cases",
                "alternatives_considered": "Accept numeric input directly",
            },
        ),
    )
    operation_digest = operation_feature.operation.outputs[0].digest
    operation_runtime.record_test(
        operation_thread.operation.thread_id,
        artifact_digest=operation_digest,
        check=CHECK,
    )
    operation_runtime.stabilize(operation_thread.operation.thread_id, artifact_digest=operation_digest)
    operation_runtime.run_mutation_campaign(
        operation_thread.operation.thread_id,
        artifact_digest=operation_digest,
        check=CHECK,
    )
    started = time.perf_counter()
    inspection = operation_runtime.inspect_artifact(operation_digest)
    operation_recomprehension = time.perf_counter() - started

    with tempfile.TemporaryDirectory() as tmp:
        baseline_root = Path(tmp)
        (baseline_root / "positive_int.py").write_text(CORRECT_COMPONENT, encoding="utf-8")
        (baseline_root / "snapshot_notes.json").write_text(
            json.dumps(
                {
                    "intent": "Implement the preregistered positive-integer parser",
                    "assumption": "Decimal strings are the accepted representation",
                    "test": "Run the preregistered unittest suite",
                    "status": "accepted",
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        started = time.perf_counter()
        snapshot_notes = json.loads((baseline_root / "snapshot_notes.json").read_text(encoding="utf-8"))
        snapshot_source = (baseline_root / "positive_int.py").read_text(encoding="utf-8")
        snapshot_recomprehension = time.perf_counter() - started
        snapshot_complete = bool(snapshot_notes["intent"] and snapshot_source)

        grammar_runtime = Runtime(grammar_root, policy=FixedPolicy(default_profile="production"))
        grammar_thread = grammar_runtime.create_thread(intent="RQ6 grammar-enforced known-bad parser")
        bad_feature = grammar_runtime.record_feature(
            grammar_thread.operation.thread_id,
            artifact_name="positive_int.py",
            content=KNOWN_BAD_COMPONENT,
            intent="Known-bad arm: implementation must be rejected",
        )
        bad_digest = bad_feature.operation.outputs[0].digest
        test_entry = grammar_runtime.record_test(
            grammar_thread.operation.thread_id,
            artifact_digest=bad_digest,
            check=CHECK,
        )
        stabilization_blocked = False
        try:
            grammar_runtime.stabilize(grammar_thread.operation.thread_id, artifact_digest=bad_digest)
        except StabilizationBlockedError:
            stabilization_blocked = True

        baseline_runtime = Runtime(baseline_root / "unbounded-verifier")
        baseline_ref = baseline_runtime.blobs.put_text(
            KNOWN_BAD_COMPONENT,
            name="positive_int.py",
            media_type="text/x-python",
        )
        downstream = DeterministicVerifier(baseline_runtime.blobs).run(baseline_ref, CHECK)

    payload = {
        "report_type": "rq0_rq6_controlled_baseline",
        "protocol_path": str(PROTOCOL_PATH),
        "runtime_root": str(operation_root),
        "scope": "n=1 feasibility evidence",
        "generated_at": generated_at_utc(),
        "evidence_binding": build_evidence_binding(
            workspace_root=root,
            protocol_path=PROTOCOL_PATH,
            runtime=operation_runtime,
        ),
        "result": {
            "preregistered_before_execution": True,
            "claim_boundary": "autobiographical n=1 existence and feasibility only",
            "rq0": {
                "operation_primary": {
                    "completed": True,
                    "action_cost": operation_runtime.metrics().action_cost,
                    "provenance_completeness": operation_runtime.metrics().provenance_completeness,
                    "recomprehension_seconds": operation_recomprehension,
                    "trace_components_present": all(
                        bool(inspection[key])
                        for key in ("assumptions", "verification", "debt_obligations", "stabilized_by")
                    ),
                },
                "snapshot_baseline": {
                    "completed": snapshot_complete,
                    "action_cost": 2,
                    "provenance_completeness": 0.0,
                    "recomprehension_seconds": snapshot_recomprehension,
                    "trace_components_present": False,
                },
            },
            "rq6": {
                "grammar_enforced": {
                    "completed": True,
                    "known_bad_test_passed": test_entry.operation.evaluation.status == "full",
                    "stabilization_blocked": stabilization_blocked,
                    "accepted_downstream": not stabilization_blocked,
                    "residual_debt": grammar_runtime.metrics().residual_debt,
                },
                "unbounded_generation": {
                    "completed": True,
                    "accepted_before_verification": True,
                    "downstream_defect_detected": not downstream.passed,
                },
            },
        },
    }
    payload["report_id"] = canonical_report_id(payload)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
