from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import run_v1_acceptance_audit  # noqa: E402


class Phase5AcceptanceTests(unittest.TestCase):
    def test_v1_acceptance_audit_is_ready_with_explicit_warnings(self) -> None:
        workspace_root = Path(__file__).resolve().parents[1]

        report = run_v1_acceptance_audit(workspace_root=workspace_root)
        warning_ids = {criterion.id for criterion in report.warnings}

        self.assertEqual(report.overall_status, "ready_with_warnings")
        self.assertEqual(report.failures, ())
        self.assertIn("live_mcp_real_ai_endpoint", warning_ids)
        self.assertIn("dogfooding_rq0_rq6_results", warning_ids)
        criterion_by_id = {criterion.id: criterion for criterion in report.criteria}
        self.assertEqual(criterion_by_id["agentic_intent_harness_baseline"].status, "pass")
        self.assertIn(
            criterion_by_id["agentic_intent_harness_live_smoke"].status,
            {"pass", "warning"},
        )
        self.assertGreaterEqual(len(report.criteria), 14)

    def test_acceptance_report_is_json_serializable(self) -> None:
        workspace_root = Path(__file__).resolve().parents[1]

        report = run_v1_acceptance_audit(workspace_root=workspace_root).to_dict()

        self.assertEqual(report["failure_count"], 0)
        self.assertEqual(report["overall_status"], "ready_with_warnings")
        self.assertTrue(all("citation" in criterion for criterion in report["criteria"]))


if __name__ == "__main__":
    unittest.main()
