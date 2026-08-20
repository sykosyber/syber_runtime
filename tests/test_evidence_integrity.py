from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime.reports import build_evidence_binding, verify_evidence_binding
from syberruntime.runtime import Runtime


class EvidenceIntegrityTests(unittest.TestCase):
    def test_protocol_digest_is_recomputed_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protocol = root / "protocol.md"
            protocol.write_text("version one", encoding="utf-8")
            binding = build_evidence_binding(
                workspace_root=root,
                protocol_path=protocol,
            )

            verify_evidence_binding(
                binding,
                workspace_root=root,
                label="fixture",
                protocol_path=protocol,
            )
            protocol.write_text("version two", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "protocol_sha256"):
                verify_evidence_binding(
                    binding,
                    workspace_root=root,
                    label="fixture",
                    protocol_path=protocol,
                )

    def test_runtime_merkle_binding_detects_appended_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = Runtime(root / "runtime")
            runtime.create_thread(intent="Initial bound state")
            binding = build_evidence_binding(workspace_root=root, runtime=runtime)

            verify_evidence_binding(
                binding,
                workspace_root=root,
                label="fixture",
                runtime=runtime,
            )
            runtime.create_thread(intent="State appended after report")

            with self.assertRaisesRegex(ValueError, "runtime_log_size"):
                verify_evidence_binding(
                    binding,
                    workspace_root=root,
                    label="fixture",
                    runtime=runtime,
                )


if __name__ == "__main__":
    unittest.main()
