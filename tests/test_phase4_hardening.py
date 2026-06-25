from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import ConsistencyProof, FixedPolicy, InclusionProof, Runtime  # noqa: E402


class Phase4HardeningTests(unittest.TestCase):
    def test_merkle_inclusion_and_consistency_proofs_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, thread_id, _digest = _built_runtime(tmp)

            entries = runtime.log.entries()
            root = runtime.merkle_root_hash()
            proof = runtime.inclusion_proof(0)
            consistency = runtime.consistency_proof(1)

            self.assertEqual(proof.root_hash, root)
            self.assertTrue(proof.verify())
            self.assertTrue(consistency.verify())
            self.assertEqual(consistency.old_size, 1)
            self.assertEqual(consistency.new_size, len(entries))

            tampered = InclusionProof(
                tree_size=proof.tree_size,
                leaf_index=proof.leaf_index,
                leaf_hash="0" * 64,
                root_hash=proof.root_hash,
                path=proof.path,
            )
            self.assertFalse(tampered.verify())

            bad_consistency = ConsistencyProof(
                old_size=consistency.old_size,
                new_size=consistency.new_size,
                old_root_hash=consistency.old_root_hash,
                new_root_hash=consistency.new_root_hash,
                prefix_entry_hashes=consistency.prefix_entry_hashes,
                appended_entry_hashes=consistency.appended_entry_hashes[:-1] + ("0" * 64,),
            )
            self.assertFalse(bad_consistency.verify())
            self.assertIn(thread_id, runtime.rebuild_state().threads)

    def test_snapshot_records_replay_state_and_merkle_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _thread_id, _digest = _built_runtime(tmp)

            snapshot = runtime.create_snapshot()
            reloaded = runtime.snapshots.read()

            self.assertEqual(snapshot.to_dict(), reloaded.to_dict())
            self.assertEqual(snapshot.log_size, len(runtime.log.entries()))
            self.assertEqual(snapshot.merkle_root_hash, runtime.merkle_root_hash())
            self.assertEqual(snapshot.state, runtime.rebuild_state().to_dict())

    def test_prov_rocrate_and_artifact_inspection_are_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _thread_id, digest = _built_runtime(tmp)

            inspection = runtime.inspect_artifact(digest)
            prov = runtime.export_prov()
            ro_crate = runtime.export_ro_crate()

            self.assertEqual(inspection["artifact"]["ref"]["digest"], digest)
            self.assertEqual(inspection["assumptions"][0]["claim"], "Text is enough")
            self.assertGreaterEqual(len(inspection["verification"]), 1)
            self.assertIsNotNone(inspection["stabilized_by"])
            self.assertIn(f"artifact:{digest}", prov["entity"])
            self.assertTrue(any(node.get("@id") == f"artifact:{digest}" for node in ro_crate["@graph"]))

    def test_shred_blob_removes_payload_but_keeps_projection_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _thread_id, digest = _built_runtime(tmp)

            self.assertTrue(runtime.blobs.exists(digest))
            shredded = runtime.shred_blob(digest, reason="test deletion")
            state = runtime.rebuild_state()

            self.assertTrue(shredded)
            self.assertFalse(runtime.blobs.exists(digest))
            self.assertIn(digest, state.artifacts)
            with self.assertRaises(FileNotFoundError):
                runtime.blobs.get_text(digest)
            tombstones = (Path(tmp) / "deletion_tombstones.jsonl").read_text(encoding="utf-8")
            self.assertIn("test deletion", tombstones)


def _built_runtime(tmp: str) -> tuple[Runtime, str, str]:
    runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
    thread = runtime.create_thread(intent="Phase 4 hardening")
    feature = runtime.record_feature(
        thread.operation.thread_id,
        artifact_name="phase4.txt",
        content="release-token\n",
        intent="Create hardening artifact",
        assumptions=(
            {
                "claim": "Text is enough",
                "depends_on": "The oracle is textual",
                "confidence_rationale": "The deterministic check observes exact text",
                "alternatives_considered": "Structured JSON",
            },
        ),
    )
    digest = feature.operation.outputs[0].digest
    runtime.record_test(
        thread.operation.thread_id,
        artifact_digest=digest,
        check={"kind": "text_equals", "expected": "release-token\n"},
    )
    runtime.stabilize(thread.operation.thread_id, artifact_digest=digest)
    runtime.run_mutation_campaign(
        thread.operation.thread_id,
        artifact_digest=digest,
        check={"kind": "text_equals", "expected": "release-token\n"},
    )
    return runtime, thread.operation.thread_id, digest


if __name__ == "__main__":
    unittest.main()
