from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import LogIntegrityError, OperationLog, Runtime, Verb  # noqa: E402


class Phase0RuntimeTests(unittest.TestCase):
    def test_first_validation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp)

            created = runtime.create_thread(intent="Build the first walking skeleton")
            root_thread_id = created.operation.thread_id
            feature = runtime.record_feature(
                root_thread_id,
                artifact_name="hello.txt",
                content="hello from syberruntime\n",
                intent="Produce the first materialized artifact",
            )
            forked = runtime.fork_thread(root_thread_id, intent="Explore an alternate artifact wording")
            fork_thread_id = forked.operation.thread_id
            fork_feature = runtime.record_feature(
                fork_thread_id,
                artifact_name="hello-alt.txt",
                content="hello from a fork\n",
                intent="Produce an artifact on the fork",
            )
            stabilized = runtime.stabilize(root_thread_id, artifact_digest=feature.operation.outputs[0].digest)

            state = runtime.rebuild_state()
            graph = state.operation_graph()

            self.assertIn(root_thread_id, state.threads)
            self.assertIn(fork_thread_id, state.threads)
            self.assertEqual(state.threads[fork_thread_id].forked_from, root_thread_id)
            self.assertEqual(runtime.blobs.get_text(feature.operation.outputs[0]), "hello from syberruntime\n")
            self.assertEqual(runtime.blobs.get_text(fork_feature.operation.outputs[0]), "hello from a fork\n")
            self.assertEqual(
                state.artifacts[feature.operation.outputs[0].digest].stabilized_by,
                stabilized.operation.id,
            )
            self.assertIn([created.operation.id, feature.operation.id], graph["edges"])
            self.assertIn([feature.operation.id, forked.operation.id], graph["edges"])
            self.assertTrue(runtime.replay_is_deterministic())

    def test_log_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp)
            runtime.create_thread(intent="Tamper test")
            log_path = Path(tmp) / "operations.jsonl"
            original = log_path.read_text(encoding="utf-8")
            log_path.write_text(original.replace("Tamper test", "Tampered test"), encoding="utf-8")

            with self.assertRaises(LogIntegrityError):
                OperationLog(log_path).entries(validate=True)

    def test_operation_ids_are_stable_when_appended(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp)
            created = runtime.create_thread(intent="Stable identity")
            before_append_id = created.operation.id
            after_append_id = runtime.log.entries()[0].operation.id

            self.assertEqual(before_append_id, after_append_id)
            self.assertEqual(runtime.log.entries()[0].operation.type, Verb.THREAD_CREATE.value)


if __name__ == "__main__":
    unittest.main()
