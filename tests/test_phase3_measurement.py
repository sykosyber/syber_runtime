from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import FixedPolicy, Runtime, Verb  # noqa: E402


class Phase3MeasurementTests(unittest.TestCase):
    def test_mutation_campaign_measures_full_discharge_efficiency_for_exact_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            created = runtime.create_thread(intent="Measure exact verifier")
            feature = runtime.record_feature(
                created.operation.thread_id,
                artifact_name="exact.txt",
                content="release-token\n",
                intent="Create an exactly checked artifact",
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(
                created.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_equals", "expected": "release-token\n"},
            )
            runtime.stabilize(created.operation.thread_id, artifact_digest=digest)

            entry, report = runtime.run_mutation_campaign(
                created.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_equals", "expected": "release-token\n"},
            )
            metrics = runtime.metrics()

            self.assertEqual(entry.operation.type, Verb.VERIFY.value)
            self.assertEqual(entry.operation.params["measurement"]["kind"], "mutation_campaign")
            self.assertGreater(report.mutant_count, 0)
            self.assertEqual(report.discharge_efficiency, 1.0)
            self.assertEqual(report.false_discharge_rate, 0.0)
            self.assertEqual(metrics.discharge_efficiency_by_profile["production"], 1.0)
            self.assertEqual(metrics.false_discharge_rate, 0.0)

    def test_survived_mutants_report_false_discharge_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            created = runtime.create_thread(intent="Measure weak verifier")
            feature = runtime.record_feature(
                created.operation.thread_id,
                artifact_name="weak.txt",
                content="release-token\n",
                intent="Create a weakly checked artifact",
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(
                created.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_contains", "expected": "release-token"},
            )
            runtime.stabilize(created.operation.thread_id, artifact_digest=digest)

            _entry, report = runtime.run_mutation_campaign(
                created.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_contains", "expected": "release-token"},
            )
            metrics = runtime.metrics()

            self.assertGreater(report.survived_count, 0)
            self.assertLess(report.discharge_efficiency, 1.0)
            self.assertGreater(report.false_discharge_rate, 0.0)
            self.assertEqual(metrics.false_discharge_rate, report.false_discharge_rate)
            self.assertEqual(
                metrics.discharge_efficiency_by_profile["production"],
                report.discharge_efficiency,
            )

    def test_runtime_metrics_compute_generativity_and_structural_rigor_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            created = runtime.create_thread(intent="Metrics test")
            feature = runtime.record_feature(
                created.operation.thread_id,
                artifact_name="metrics.txt",
                content="metric token\n",
                intent="Create measured artifact",
                assumptions=(
                    {
                        "claim": "Text is enough",
                        "depends_on": "The check is textual",
                        "confidence_rationale": "The deterministic check observes the token",
                        "alternatives_considered": "Binary artifact",
                    },
                ),
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(
                created.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_equals", "expected": "metric token\n"},
            )
            runtime.stabilize(created.operation.thread_id, artifact_digest=digest)
            runtime.run_mutation_campaign(
                created.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_equals", "expected": "metric token\n"},
            )

            metrics = runtime.metrics()

            self.assertEqual(metrics.validated_artifacts, 1)
            self.assertEqual(metrics.residual_debt, 0.0)
            self.assertGreater(metrics.generative_return, 0.0)
            self.assertEqual(metrics.provenance_completeness, 1.0)
            self.assertEqual(metrics.assumption_ledger_coverage, 1.0)
            self.assertGreater(metrics.structural_rigor, 0.9)


if __name__ == "__main__":
    unittest.main()
