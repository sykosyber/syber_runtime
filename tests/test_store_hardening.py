from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import OperationLog, Runtime  # noqa: E402


SRC = str(Path(__file__).resolve().parents[1] / "src")


class StoreHardeningTests(unittest.TestCase):
    def test_appends_do_not_trigger_full_rereads(self) -> None:
        """Appends must stay O(new entries): one cold read at most, never per append."""
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp)
            thread = runtime.create_thread(intent="append scaling")
            thread_id = thread.operation.thread_id
            for index in range(40):
                runtime.record_feature(
                    thread_id,
                    artifact_name=f"scale-{index}.txt",
                    content=f"scale-token-{index}\n",
                    intent="Append-scaling regression artifact",
                )

            self.assertLessEqual(runtime.log.full_read_count, 1)
            self.assertEqual(len(runtime.log.entries()), 41)

    def test_two_runtime_instances_interleave_appends_consistently(self) -> None:
        """A second in-process instance must pick up foreign appends incrementally."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_a = Runtime(root)
            runtime_b = Runtime(root)

            thread_a = runtime_a.create_thread(intent="instance a").operation.thread_id
            thread_b = runtime_b.create_thread(intent="instance b").operation.thread_id
            runtime_a.record_feature(
                thread_a, artifact_name="a.txt", content="token-a\n", intent="Instance a artifact"
            )
            runtime_b.record_feature(
                thread_b, artifact_name="b.txt", content="token-b\n", intent="Instance b artifact"
            )

            # A cold instance revalidates the full chain.
            entries = OperationLog(root / "operations.jsonl").entries(validate=True)
            self.assertEqual(len(entries), 4)
            state = runtime_a.rebuild_state()
            self.assertIn(thread_a, state.threads)
            self.assertIn(thread_b, state.threads)

    def test_concurrent_processes_preserve_hash_chain(self) -> None:
        """Two writer processes must serialize via the append lock, not corrupt the chain."""
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from syberruntime import Runtime\n"
            "runtime = Runtime(sys.argv[2])\n"
            "label = sys.argv[3]\n"
            "for index in range(int(sys.argv[4])):\n"
            "    runtime.create_thread(intent=label + str(index))\n"
        )
        appends_per_process = 10
        with tempfile.TemporaryDirectory() as tmp:
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", script, SRC, tmp, f"writer-{worker}-", str(appends_per_process)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for worker in range(2)
            ]
            for process in processes:
                _stdout, stderr = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 0, stderr.decode("utf-8", errors="replace"))

            entries = OperationLog(Path(tmp) / "operations.jsonl").entries(validate=True)
            self.assertEqual(len(entries), 2 * appends_per_process)


if __name__ == "__main__":
    unittest.main()
