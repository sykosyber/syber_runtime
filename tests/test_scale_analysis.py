from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import BlobStore  # noqa: E402
from syberruntime.reports import canonical_report_id  # noqa: E402
from syberruntime.scale_analysis import analyze_scale3_reports, render_scale3_analysis_markdown  # noqa: E402


class Scale3AnalysisTests(unittest.TestCase):
    def test_scale3_analysis_classifies_progression_and_renders_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_runtime = root / "bad-runtime"
            bad_alpha = BlobStore(bad_runtime).put_text("agent-scale-alpha-token\\n")
            reports = (
                _write_report(
                    root / "scale3-001.json",
                    run_id="agentic-live-scale3-001",
                    runtime_root=bad_runtime,
                    task_results=[
                        _task("live-provider-smoke-001", status="pass", stabilized=True, mutation=True),
                        _task(
                            "live-provider-scale-002",
                            status="fail",
                            stabilized=False,
                            artifact_digest=bad_alpha.digest,
                            failure="live provider task did not stabilize using config examples",
                        ),
                        _task("live-provider-scale-003", status="pass", stabilized=True, mutation=True),
                    ],
                    generated=3,
                    validated=2,
                    residual_debt=1.0,
                    structural_rigor=0.875,
                ),
                _write_report(
                    root / "scale3-002.json",
                    run_id="agentic-live-scale3-002",
                    task_results=[
                        _task("live-provider-smoke-001", status="pass", stabilized=True, mutation=True),
                        _task("live-provider-scale-002", status="pass", stabilized=True, mutation=True),
                        _task(
                            "live-provider-scale-003",
                            status="fail",
                            stabilized=False,
                            failure="MCP tool returned isError=true: Provider did not return valid JSON",
                        ),
                    ],
                    generated=2,
                    validated=2,
                ),
                _write_report(
                    root / "scale3-003.json",
                    run_id="agentic-live-scale3-003",
                    task_results=[
                        _task("live-provider-smoke-001", status="pass", stabilized=True, mutation=True),
                        _task("live-provider-scale-002", status="pass", stabilized=True, mutation=True),
                        _task("live-provider-scale-003", status="pass", stabilized=True, mutation=True),
                    ],
                    generated=3,
                    validated=3,
                ),
            )

            analysis = analyze_scale3_reports(reports)
            markdown = render_scale3_analysis_markdown(analysis)

            self.assertEqual(analysis.run_summaries[0].failure_mode_label, "artifact_content_mismatch")
            self.assertEqual(analysis.run_summaries[1].failure_mode_label, "provider_malformed_json")
            self.assertEqual(analysis.run_summaries[2].failure_mode_label, "none")
            self.assertIn("v1 Phase 3; v0.6 section 3.8; v1 section 7", markdown)
            self.assertIn("artifact precision and provider-boundary failure modes", markdown)
            self.assertIn("| `agentic-live-scale3-003` | 3 | 3 | 0 | 3 | 3 |", markdown)

    def test_scale3_analysis_rejects_non_scale3_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _write_report(
                Path(tmp) / "smoke.json",
                run_id="agentic-live-smoke-003",
                task_results=[_task("live-provider-smoke-001", status="pass", stabilized=True)],
                generated=1,
                validated=1,
            )

            with self.assertRaisesRegex(ValueError, "not a scale3 campaign"):
                analyze_scale3_reports((report,))

    def test_single_scale3_report_uses_regenerated_evidence_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _write_report(
                Path(tmp) / "scale3-004.json",
                run_id="agentic-live-scale3-004",
                task_results=[
                    _task("live-provider-smoke-001", status="pass", stabilized=True, mutation=True),
                    _task("live-provider-scale-002", status="pass", stabilized=True, mutation=True),
                    _task("live-provider-scale-003", status="pass", stabilized=True, mutation=True),
                ],
                generated=3,
                validated=3,
            )

            analysis = analyze_scale3_reports((report,))

            self.assertIn("regenerated scale3 campaign", analysis.apex_inference)
            self.assertNotIn("earlier live runs", analysis.apex_inference)


def _write_report(
    path: Path,
    *,
    run_id: str,
    task_results: list[dict],
    generated: int,
    validated: int,
    runtime_root: Path | None = None,
    residual_debt: float = 0.0,
    structural_rigor: float = 1.0,
) -> Path:
    summary = {
        "attempted_tasks": len(task_results),
        "stabilized_tasks": sum(1 for result in task_results if result["stabilized"]),
        "blocked_or_failed_tasks": sum(1 for result in task_results if result["status"] != "pass"),
    }
    report = {
        "run_id": run_id,
        "protocol_path": "docs/agentic_intent_harness.md",
        "runtime_root": str(runtime_root or path.parent / "runtime"),
        "mode": "live",
        "provider_config_path": "examples/mcp_adapter_config.example.json",
        "model_assignments": {},
        "intent_metadata": {
            "intent_source": "agent",
            "principal": "agent-harness-live-v1",
            "acceptance_authority": "provider-verifier-and-deterministic-oracle",
        },
        "task_results": task_results,
        "summary": summary,
        "metrics": {
            "generated_artifacts": generated,
            "validated_artifacts": validated,
            "false_discharge_rate": 0.0,
            "residual_debt": residual_debt,
            "structural_rigor": structural_rigor,
        },
        "generated_at": "2026-07-21T00:00:00+00:00",
        "evidence_binding": {
            "schema_version": 1,
            "source_revision": "0" * 40,
            "source_dirty": False,
            "protocol_sha256": None,
            "config_sha256": None,
            "runtime_log_size": None,
            "runtime_merkle_root": None,
            "runtime_tail_hash": None,
            "input_report_ids": [],
        },
    }
    report["report_id"] = canonical_report_id(report)
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _task(
    task_id: str,
    *,
    status: str,
    stabilized: bool,
    artifact_digest: str | None = None,
    failure: str | None = None,
    mutation: bool = False,
) -> dict:
    mutation_report = None
    if mutation:
        mutation_report = {"killed_count": 3, "mutant_count": 3}
    return {
        "task_id": task_id,
        "status": status,
        "thread_id": task_id + "-thread",
        "artifact_digest": artifact_digest,
        "stabilized": stabilized,
        "expected_stabilized": True,
        "failure": failure,
        "failure_class": None,
        "failure_details": None,
        "mutation_report": mutation_report,
    }


if __name__ == "__main__":
    unittest.main()
