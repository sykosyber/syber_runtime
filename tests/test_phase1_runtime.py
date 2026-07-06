from __future__ import annotations

import itertools
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import (  # noqa: E402
    ArtifactRef,
    BudgetExceededError,
    Evaluation,
    EvaluationStatus,
    FixedPolicy,
    Operation,
    Provenance,
    StabilizationBlockedError,
    Verb,
    fold_operations,
)
from syberruntime.debt import feature_obligation_id  # noqa: E402
from syberruntime.merge import merge_operation_sequences  # noqa: E402
from syberruntime.hashing import digest_bytes  # noqa: E402


class Phase1RuntimeTests(unittest.TestCase):
    def test_feature_accrues_debt_and_deterministic_test_discharges_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = _runtime(tmp, profile="production")
            created = runtime.create_thread(intent="Exercise the grammar")
            feature = runtime.record_feature(
                created.operation.thread_id,
                artifact_name="contract.txt",
                content="verified content\n",
                intent="Create a production artifact",
            )
            artifact_digest = feature.operation.outputs[0].digest
            state = runtime.rebuild_state()

            self.assertEqual(len(feature.operation.evaluation.obligations), 1)
            obligation_id = feature.operation.evaluation.obligations[0]
            obligation = state.debt.obligations[obligation_id]
            self.assertEqual(obligation.status, "open")
            self.assertEqual(obligation.residual_debt, 1.0)
            self.assertEqual(state.debt.total_residual_debt(), 1.0)

            with self.assertRaises(StabilizationBlockedError):
                runtime.stabilize(created.operation.thread_id, artifact_digest=artifact_digest)

            test = runtime.record_test(
                created.operation.thread_id,
                artifact_digest=artifact_digest,
                check={"kind": "text_contains", "expected": "verified"},
            )
            state = runtime.rebuild_state()
            obligation = state.debt.obligations[obligation_id]

            self.assertEqual(test.operation.type, Verb.TEST.value)
            self.assertEqual(obligation.status, "discharged")
            self.assertEqual(obligation.discharged_by, test.operation.id)
            self.assertEqual(state.debt.total_residual_debt(), 0.0)

            stabilized = runtime.stabilize(created.operation.thread_id, artifact_digest=artifact_digest)
            self.assertEqual(
                runtime.rebuild_state().artifacts[artifact_digest].stabilized_by,
                stabilized.operation.id,
            )

    def test_budget_exceeded_halts_before_feature_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = _runtime(tmp, profile="production", max_debt=0.5)
            created = runtime.create_thread(intent="Budget guard")

            with self.assertRaises(BudgetExceededError):
                runtime.record_feature(
                    created.operation.thread_id,
                    artifact_name="too-expensive.txt",
                    content="this should not be appended",
                    intent="Exceed the center budget",
                )

            state = runtime.rebuild_state()
            self.assertEqual(len(state.operations), 1)
            self.assertEqual(state.debt.total_residual_debt(), 0.0)

    def test_failed_deterministic_test_does_not_discharge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = _runtime(tmp, profile="production")
            created = runtime.create_thread(intent="Failed verification")
            feature = runtime.record_feature(
                created.operation.thread_id,
                artifact_name="artifact.txt",
                content="actual content",
                intent="Create something to check",
            )
            artifact_digest = feature.operation.outputs[0].digest
            obligation_id = feature.operation.evaluation.obligations[0]

            runtime.record_test(
                created.operation.thread_id,
                artifact_digest=artifact_digest,
                check={"kind": "text_contains", "expected": "missing"},
            )
            state = runtime.rebuild_state()
            obligation = state.debt.obligations[obligation_id]

            self.assertEqual(obligation.status, "open")
            self.assertEqual(obligation.residual_debt, 1.0)
            self.assertEqual(len(obligation.attempts), 1)
            with self.assertRaises(StabilizationBlockedError):
                runtime.stabilize(created.operation.thread_id, artifact_digest=artifact_digest)

    def test_independent_merge_commutes_for_operation_graphs(self) -> None:
        root = _thread_create()
        left = _feature(root, nonce="left", artifact_name="left.txt", content=b"left")
        right = _feature(root, nonce="right", artifact_name="right.txt", content=b"right")

        expected_ids = None
        expected_state = None
        for first, second in itertools.permutations(([root, left], [root, right]), 2):
            result = merge_operation_sequences(first, second)
            ids = tuple(operation.id for operation in result.operations)
            state = fold_operations(result.operations).to_dict()
            expected_ids = expected_ids or ids
            expected_state = expected_state or state
            self.assertEqual(ids, expected_ids)
            self.assertEqual(state, expected_state)
            self.assertEqual(result.conflicts, ())

    def test_conflicting_independent_features_surface_first_class_conflict(self) -> None:
        root = _thread_create()
        left = _feature(root, nonce="left-conflict", artifact_name="same.txt", content=b"left")
        right = _feature(root, nonce="right-conflict", artifact_name="same.txt", content=b"right")

        result = merge_operation_sequences([root, left], [root, right])
        repeated = merge_operation_sequences(result.operations, [right])

        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].kind, "artifact_name_conflict")
        self.assertEqual(result.conflicts, repeated.conflicts)


def _runtime(tmp: str, *, profile: str, max_debt: float = 10.0) -> object:
    from syberruntime import Runtime

    return Runtime(tmp, policy=FixedPolicy(default_profile=profile, default_max_debt=max_debt))


def _thread_create() -> Operation:
    return Operation.build(
        type=Verb.THREAD_CREATE,
        thread_id="thread-1",
        center_id="root",
        params={"intent": "Create merge test thread"},
        evaluation=Evaluation(question="Thread exists", status=EvaluationStatus.FULL),
        provenance=Provenance(actor="test", decisions=[{"kind": "thread_create"}], ts="2026-01-01T00:00:00+00:00"),
        nonce="thread-create",
    )


def _feature(root: Operation, *, nonce: str, artifact_name: str, content: bytes) -> Operation:
    ref = ArtifactRef(
        digest=digest_bytes(content),
        size=len(content),
        media_type="text/plain; charset=utf-8",
        name=artifact_name,
    )
    obligation_id = feature_obligation_id(feature_nonce=nonce, artifact_digest=ref.digest, output_index=0)
    return Operation.build(
        type=Verb.FEATURE,
        thread_id=root.thread_id,
        center_id="root",
        parents=(root.id,),
        params={
            "intent": f"Write {artifact_name}",
            "artifact_name": artifact_name,
            "debt": {
                "generative_mass": 1.0,
                "blast_radius": 1.0,
                "criticality": 1.0,
                "accrual_rate": 1.0,
                "rigor_profile": "production",
                "floor_required": True,
                "obligations": [
                    {
                        "id": obligation_id,
                        "artifact_digest": ref.digest,
                        "incurred_debt": 1.0,
                        "rigor_profile": "production",
                        "floor_required": True,
                    }
                ],
            },
        },
        outputs=(ref,),
        evaluation=Evaluation(
            question="Did useful possibility increase?",
            obligations=(obligation_id,),
            status=EvaluationStatus.UNVERIFIED,
        ),
        provenance=Provenance(actor="test", decisions=[{"kind": "feature"}], ts="2026-01-01T00:00:00+00:00"),
        nonce=nonce,
    )


if __name__ == "__main__":
    unittest.main()
