from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import (  # noqa: E402
    AdapterError,
    IntentMetadata,
    ModelSpec,
    Runtime,
    ScriptedModelAdapter,
    run_live_agent_harness,
    run_scripted_agent_harness,
    validate_harness_report,
    write_harness_report,
)
from syberruntime.harness import (  # noqa: E402
    LIVE_SMOKE_ARTIFACT_CONTENT,
    LIVE_SMOKE_ARTIFACT_NAME,
    LIVE_SMOKE_INTENT,
    _run_live_task,
    default_live_scale_tasks,
    live_smoke_task,
)


class AgentHarnessTests(unittest.TestCase):
    def test_intent_metadata_is_recorded_in_operation_params_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(Path(tmp))
            metadata = IntentMetadata(
                intent_source="agent",
                principal="test-agent",
                acceptance_authority="deterministic-oracle",
                benchmark_id="bench-1",
                harness_run_id="run-1",
            )

            entry = runtime.create_thread(intent="metadata fixture", actor="test-agent", intent_metadata=metadata)
            operation = entry.operation

            self.assertEqual(operation.params["intent_metadata"]["intent_source"], "agent")
            self.assertEqual(operation.provenance.actor, "test-agent")
            self.assertEqual(operation.provenance.decisions[0]["intent_metadata"]["principal"], "test-agent")

    def test_scripted_agent_harness_records_pass_and_expected_blocked_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_scripted_agent_harness(
                runtime_root=Path(tmp) / "runtime",
                protocol_path="docs/agentic_intent_harness.md",
                run_id="test-run",
            )

            data = report.to_dict()

            self.assertEqual(data["summary"]["attempted_tasks"], 2)
            self.assertEqual(data["summary"]["stabilized_tasks"], 1)
            self.assertEqual(data["summary"]["blocked_or_failed_tasks"], 1)
            self.assertEqual([result["status"] for result in data["task_results"]], ["pass", "pass"])
            self.assertFalse(data["task_results"][1]["stabilized"])
            self.assertIn("open floor-rigor verification obligations", data["task_results"][1]["failure"])
            self.assertEqual(data["intent_metadata"]["intent_source"], "agent")
            self.assertGreater(data["metrics"]["action_cost"], 0)

    def test_harness_report_writes_canonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = run_scripted_agent_harness(
                runtime_root=root / "runtime",
                protocol_path="docs/agentic_intent_harness.md",
                run_id="write-run",
            )
            output = write_harness_report(report, root / "report.json")

            loaded = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(loaded["report_id"], report.report_id)
            self.assertEqual(loaded["run_id"], "write-run")

    def test_harness_report_validation_rejects_missing_task_evidence(self) -> None:
        with self.assertRaises(ValueError):
            validate_harness_report(
                {
                    "report_id": "bad",
                    "run_id": "bad",
                    "protocol_path": "protocol",
                    "runtime_root": "runtime",
                    "intent_metadata": {
                        "intent_source": "agent",
                        "principal": "test",
                        "acceptance_authority": "deterministic-oracle",
                    },
                    "task_results": [],
                    "summary": {"attempted_tasks": 0, "stabilized_tasks": 0},
                    "metrics": {"action_cost": 0},
                }
            )

    def test_live_agent_harness_runs_through_mock_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _configure_mock_mcp_environment()
            report = run_live_agent_harness(
                runtime_root=root / "runtime",
                protocol_path="docs/agentic_intent_harness.md",
                run_id="live-mock-run",
                config_path=Path(__file__).resolve().parents[1] / "examples" / "mock_mcp_adapter_config.example.json",
            )
            data = report.to_dict()

            self.assertEqual(data["mode"], "live")
            self.assertEqual(data["summary"]["attempted_tasks"], 1)
            self.assertEqual(data["summary"]["stabilized_tasks"], 1)
            self.assertEqual(data["task_results"][0]["status"], "pass")
            self.assertTrue(data["model_assignments"])
            self.assertIn("mock-generator-family", json.dumps(data["model_assignments"]))
            digest = data["task_results"][0]["artifact_digest"]
            self.assertEqual(Runtime(root / "runtime").blobs.get_text(digest), LIVE_SMOKE_ARTIFACT_CONTENT)

    def test_live_agent_harness_scale3_runs_through_mock_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _configure_mock_mcp_environment()
            report = run_live_agent_harness(
                runtime_root=root / "runtime",
                protocol_path="docs/agentic_intent_harness.md",
                run_id="live-scale-mock-run",
                config_path=Path(__file__).resolve().parents[1] / "examples" / "mock_mcp_adapter_config.example.json",
                tasks=default_live_scale_tasks(),
            )
            data = report.to_dict()

            self.assertEqual(data["summary"]["attempted_tasks"], 3)
            self.assertEqual(data["summary"]["stabilized_tasks"], 3)
            self.assertEqual(data["summary"]["blocked_or_failed_tasks"], 0)
            self.assertEqual(data["metrics"]["generated_artifacts"], 3)
            self.assertEqual(data["metrics"]["validated_artifacts"], 3)
            self.assertEqual(data["metrics"]["false_discharge_rate"], 0.0)
            self.assertEqual(
                [result["task_id"] for result in data["task_results"]],
                ["live-provider-smoke-001", "live-provider-scale-002", "live-provider-scale-003"],
            )

    def test_live_harness_failure_report_can_be_valid_evidence(self) -> None:
        validate_harness_report(
            {
                "mode": "live",
                "report_id": "provider-failure",
                "run_id": "provider-failure",
                "protocol_path": "protocol",
                "runtime_root": "runtime",
                "provider_config_path": "config",
                "model_assignments": {},
                "intent_metadata": {
                    "intent_source": "agent",
                    "principal": "test",
                    "acceptance_authority": "provider",
                },
                "task_results": [
                    {
                        "task_id": "live-provider-smoke-001",
                        "status": "fail",
                        "thread_id": None,
                        "artifact_digest": None,
                        "stabilized": False,
                        "expected_stabilized": True,
                        "failure": "provider unavailable",
                        "mutation_report": None,
                    }
                ],
                "summary": {"attempted_tasks": 1, "stabilized_tasks": 0, "blocked_or_failed_tasks": 1},
                "metrics": {"action_cost": 0},
            }
        )

    def test_live_harness_failure_preserves_partial_artifact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(Path(tmp) / "runtime")
            metadata = IntentMetadata(
                intent_source="agent",
                principal="test-live-agent",
                acceptance_authority="provider-verifier-and-deterministic-oracle",
                benchmark_id="bench-live",
                harness_run_id="run-live",
            )

            result = _run_live_task(
                runtime=runtime,
                metadata=metadata,
                config_path="bad-verifier-config",
                task=live_smoke_task(
                    intent=LIVE_SMOKE_INTENT,
                    artifact_name=LIVE_SMOKE_ARTIFACT_NAME,
                    expected_content=LIVE_SMOKE_ARTIFACT_CONTENT,
                ),
                planner=_scripted_adapter(
                    "planner",
                    "planner-family",
                    {
                        "steps": [
                            {
                                "verb": "Feature",
                                "success_question": "Was the artifact created?",
                                "budget_alloc": 1.0,
                                "model_role": "generator",
                            },
                            {
                                "verb": "Verify",
                                "success_question": "Was the artifact verified?",
                                "budget_alloc": 1.0,
                                "model_role": "verifier",
                            },
                        ],
                        "rationale": "Create then verify the smoke token.",
                    },
                ),
                generator=_scripted_adapter(
                    "generator",
                    "generator-family",
                    {
                        "assumptions": [
                            {
                                "claim": "Plain text is enough",
                                "depends_on": "The oracle checks exact text",
                                "confidence_rationale": "The token is deterministic",
                                "alternatives_considered": "Structured JSON",
                            }
                        ],
                        "plan": "Emit the smoke token.",
                        "artifact": LIVE_SMOKE_ARTIFACT_CONTENT,
                        "self_identified_risks": [],
                    },
                ),
                verifier=_scripted_adapter(
                    "verifier",
                    "verifier-family",
                    {
                        "checkable_oracle": {"kind": "", "expected": LIVE_SMOKE_ARTIFACT_CONTENT},
                        "verdict": "pass",
                        "located_errors": [],
                        "obligation_discharged": True,
                    },
                ),
            )

            self.assertEqual(result.status, "fail")
            self.assertIsNotNone(result.thread_id)
            self.assertIsNotNone(result.artifact_digest)
            self.assertIn("checkable_oracle kind", result.failure or "")
            assert result.artifact_digest is not None
            self.assertEqual(runtime.blobs.get_text(result.artifact_digest), LIVE_SMOKE_ARTIFACT_CONTENT)

    def test_live_harness_records_structured_provider_failure_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(Path(tmp) / "runtime")
            metadata = IntentMetadata(
                intent_source="agent",
                principal="test-live-agent",
                acceptance_authority="provider-verifier-and-deterministic-oracle",
                benchmark_id="bench-live",
                harness_run_id="run-live",
            )

            result = _run_live_task(
                runtime=runtime,
                metadata=metadata,
                config_path="diagnostic-config",
                task=live_smoke_task(),
                planner=_DiagnosticFailingAdapter(
                    role="planner",
                    diagnostic={
                        "failure_class": "malformed_json",
                        "attempts": [
                            {
                                "attempt_number": 1,
                                "raw_response_preview": "not valid json",
                                "raw_response_sha256": "digest",
                            }
                        ],
                    },
                ),
                generator=_scripted_adapter("generator", "generator-family", {}),
                verifier=_scripted_adapter("verifier", "verifier-family", {}),
            )

            self.assertEqual(result.status, "fail")
            self.assertEqual(result.failure_class, "malformed_json")
            self.assertIsNotNone(result.failure_details)
            assert result.failure_details is not None
            self.assertEqual(result.failure_details["attempts"][0]["raw_response_preview"], "not valid json")
            self.assertEqual(result.to_dict()["failure_class"], "malformed_json")


def _configure_mock_mcp_environment() -> None:
    repo = Path(__file__).resolve().parents[1]
    os_path = str(repo / "src")
    import os

    os.environ["SYBERRUNTIME_PYTHON"] = sys.executable
    existing = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os_path if not existing else os_path + os.pathsep + existing


def _scripted_adapter(role: str, family: str, payload: dict) -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(model_id=f"test-{role}", family=family, roles=(role,)),
        responses=(payload,),
    )


class _DiagnosticFailingAdapter:
    def __init__(self, *, role: str, diagnostic: dict) -> None:
        self._spec = ModelSpec(model_id=f"failing-{role}", family="failing-family", roles=(role,))
        self.diagnostic = diagnostic

    @property
    def spec(self) -> ModelSpec:
        return self._spec

    def call(self, _request: object) -> object:
        raise AdapterError("MCP tool returned isError=true", diagnostic=self.diagnostic)


if __name__ == "__main__":
    unittest.main()
