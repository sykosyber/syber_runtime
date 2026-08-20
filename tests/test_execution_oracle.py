from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import BlobStore, FixedPolicy, ModelContractError, Runtime, VerifierOutput  # noqa: E402
from syberruntime.errors import VerificationError  # noqa: E402
from syberruntime.verification import (  # noqa: E402
    MODEL_ORACLE_CHECK_KINDS,
    SUPPORTED_DETERMINISTIC_CHECK_KINDS,
    DeterministicVerifier,
)


ADDER_SOURCE = "def add(left, right):\n    return left + right\n"

BROKEN_ADDER_SOURCE = "def add(left, right):\n    return left - right\n"

ADDER_TEST_SOURCE = """
import unittest

from artifact_under_test import add


class AdderTests(unittest.TestCase):
    def test_adds_positive_numbers(self):
        self.assertEqual(add(2, 3), 5)

    def test_adds_negative_numbers(self):
        self.assertEqual(add(-2, -3), -5)
"""

HANGING_SOURCE = "import time\nwhile True:\n    time.sleep(0.05)\n"


def _adder_check(**overrides) -> dict:
    check = {"kind": "python_tests", "test_source": ADDER_TEST_SOURCE}
    check.update(overrides)
    return check


class ExecutionOracleTests(unittest.TestCase):
    def test_python_tests_pass_for_correct_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(ADDER_SOURCE, name="adder.py")

            result = DeterministicVerifier(blobs).run(artifact, _adder_check())

            self.assertTrue(result.passed)
            self.assertEqual(result.kind, "python_tests")

    def test_python_tests_fail_for_behaviorally_wrong_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(BROKEN_ADDER_SOURCE, name="adder.py")

            result = DeterministicVerifier(blobs).run(artifact, _adder_check())

            self.assertFalse(result.passed)
            self.assertIn("test suite failed", result.details)

    def test_python_tests_time_out_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(HANGING_SOURCE, name="hang.py")

            result = DeterministicVerifier(blobs).run(artifact, _adder_check(timeout_seconds=5.0))

            self.assertFalse(result.passed)
            self.assertIn("timed out", result.details)

    def test_python_tests_worker_denies_network_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text("import socket\nsocket.socket()\n", name="network.py")

            result = DeterministicVerifier(blobs).run(
                artifact,
                {"kind": "python_tests", "test_source": "import artifact_under_test\n"},
            )

            self.assertFalse(result.passed)
            self.assertIn("denied network access", result.details)

    def test_python_tests_worker_denies_reads_outside_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root / "outside-secret.txt"
            secret.write_text("must-not-be-readable", encoding="utf-8")
            blobs = BlobStore(root / "runtime")
            artifact = blobs.put_text(
                f"from pathlib import Path\nPath({str(secret)!r}).read_text(encoding='utf-8')\n",
                name="reader.py",
            )

            result = DeterministicVerifier(blobs).run(
                artifact,
                {"kind": "python_tests", "test_source": "import artifact_under_test\n"},
            )

            self.assertFalse(result.passed)
            self.assertIn("outside allowed roots", result.details)

    def test_python_tests_worker_does_not_inherit_provider_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(
                "import os\ndef inherited_secret():\n    return os.environ.get('SYBER_TEST_PROVIDER_SECRET')\n",
                name="environment.py",
            )
            check = {
                "kind": "python_tests",
                "test_source": (
                    "import unittest\n"
                    "from artifact_under_test import inherited_secret\n"
                    "class EnvironmentTests(unittest.TestCase):\n"
                    "    def test_secret_absent(self):\n"
                    "        self.assertIsNone(inherited_secret())\n"
                ),
            }
            previous = os.environ.get("SYBER_TEST_PROVIDER_SECRET")
            os.environ["SYBER_TEST_PROVIDER_SECRET"] = "sensitive-value"
            try:
                result = DeterministicVerifier(blobs).run(artifact, check)
            finally:
                if previous is None:
                    os.environ.pop("SYBER_TEST_PROVIDER_SECRET", None)
                else:
                    os.environ["SYBER_TEST_PROVIDER_SECRET"] = previous

            self.assertTrue(result.passed, result.details)

    def test_python_tests_reject_invalid_resource_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(ADDER_SOURCE, name="adder.py")

            with self.assertRaises(VerificationError):
                DeterministicVerifier(blobs).run(artifact, _adder_check(memory_mb=32))

            for overrides in (
                {"timeout_seconds": float("inf")},
                {"timeout_seconds": 301},
                {"cpu_seconds": 121},
                {"memory_mb": 1025},
            ):
                with self.subTest(overrides=overrides):
                    with self.assertRaises(VerificationError):
                        DeterministicVerifier(blobs).run(artifact, _adder_check(**overrides))

    def test_python_tests_reject_path_traversal_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(ADDER_SOURCE, name="adder.py")

            for bad_name in ("../escape.py", "sub/dir.py", ".."):
                with self.assertRaises(VerificationError):
                    DeterministicVerifier(blobs).run(artifact, _adder_check(artifact_filename=bad_name))

    def test_model_oracle_kinds_exclude_code_execution(self) -> None:
        self.assertIn("python_tests", SUPPORTED_DETERMINISTIC_CHECK_KINDS)
        self.assertNotIn("python_tests", MODEL_ORACLE_CHECK_KINDS)
        with self.assertRaisesRegex(ModelContractError, "supported deterministic check"):
            VerifierOutput.from_payload(
                {
                    "checkable_oracle": {"kind": "python_tests", "test_source": "import os"},
                    "verdict": "pass",
                    "located_errors": [],
                    "obligation_discharged": True,
                }
            )

    def test_python_tests_discharge_obligation_and_gate_stabilize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            thread = runtime.create_thread(intent="Implement an adder with behavioral verification")
            thread_id = thread.operation.thread_id

            feature = runtime.record_feature(
                thread_id,
                artifact_name="adder.py",
                content=ADDER_SOURCE,
                intent="Implement add()",
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(thread_id, artifact_digest=digest, check=_adder_check())
            state = runtime.rebuild_state()
            self.assertEqual(state.debt.total_residual_debt(), 0.0)
            stabilized = runtime.stabilize(thread_id, artifact_digest=digest)
            self.assertEqual(state.artifacts[digest].ref.digest, digest)
            self.assertIsNotNone(stabilized.operation.id)

    def test_failing_python_tests_leave_obligation_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            thread = runtime.create_thread(intent="Broken adder must not stabilize")
            thread_id = thread.operation.thread_id

            feature = runtime.record_feature(
                thread_id,
                artifact_name="adder.py",
                content=BROKEN_ADDER_SOURCE,
                intent="Implement add()",
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(thread_id, artifact_digest=digest, check=_adder_check())
            state = runtime.rebuild_state()
            self.assertGreater(state.debt.total_residual_debt(), 0.0)

    def test_mutation_campaign_with_python_tests_kills_behavioral_mutants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            thread = runtime.create_thread(intent="Mutation-measure the adder oracle")
            thread_id = thread.operation.thread_id
            feature = runtime.record_feature(
                thread_id,
                artifact_name="adder.py",
                content=ADDER_SOURCE,
                intent="Implement add()",
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(thread_id, artifact_digest=digest, check=_adder_check())

            _entry, report = runtime.run_mutation_campaign(
                thread_id,
                artifact_digest=digest,
                check=_adder_check(),
            )

            self.assertTrue(report.baseline_passed)
            self.assertGreater(report.mutant_count, 0)
            self.assertEqual(report.survived_count, 0)
            self.assertEqual(report.discharge_efficiency, 1.0)


if __name__ == "__main__":
    unittest.main()
