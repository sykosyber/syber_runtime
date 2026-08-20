from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import FixedPolicy, Runtime, load_adapter_bundle  # noqa: E402
from syberruntime.acceptance import run_v1_acceptance_audit  # noqa: E402
from syberruntime.dogfood import (  # noqa: E402
    create_dogfood_report,
    load_dogfood_report,
    write_dogfood_report,
)
from syberruntime.harness import (  # noqa: E402
    default_live_code_tasks,
    default_live_scale_tasks,
    run_live_agent_harness,
    run_scripted_agent_harness,
    write_harness_report,
)
from syberruntime.reports import (  # noqa: E402
    build_evidence_binding,
    canonical_report_id,
    write_json_report,
)


class LiveConfigAndDogfoodTests(unittest.TestCase):
    def test_adapter_config_expands_environment_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = _write_mcp_server(root)
            os.environ["SYBERRUNTIME_TEST_PYTHON"] = sys.executable
            config = _write_adapter_config(root, server, executable="%SYBERRUNTIME_TEST_PYTHON%")

            bundle = load_adapter_bundle(config)

            self.assertEqual(bundle.planner.command[0], sys.executable)

    def test_configured_mcp_stdio_adapters_run_ai_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = _write_mcp_server(Path(tmp))
            config = _write_adapter_config(Path(tmp), server)
            bundle = load_adapter_bundle(config)
            runtime = Runtime(Path(tmp) / "runtime", policy=FixedPolicy(default_profile="production"))

            result = runtime.run_ai_loop(
                intent="Configured live adapter smoke test",
                artifact_name="configured.txt",
                planner=bundle.planner,
                generator=bundle.generator,
                verifier=bundle.verifier,
            )

            self.assertTrue(result.stabilized)
            self.assertEqual(runtime.metrics().residual_debt, 0.0)
            self.assertIn("configured-token", runtime.blobs.get_text(result.artifact_digest))

    def test_acceptance_audit_passes_when_live_config_and_dogfood_report_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = _write_mcp_server(root)
            config = _write_adapter_config(root, server)
            docs = root / "docs"
            docs.mkdir()
            (docs / "rq0_rq6_preregistration.md").write_text("protocol", encoding="utf-8")
            (docs / "conformal_coverage_preregistration.md").write_text("protocol", encoding="utf-8")
            (docs / "phase4_walkthrough.md").write_text("walkthrough", encoding="utf-8")
            (root / "agentic_protocol.md").write_text("protocol", encoding="utf-8")
            (root / "protocol.md").write_text("protocol", encoding="utf-8")
            runtime = Runtime(root / "dogfood-runtime", policy=FixedPolicy(default_profile="production"))
            thread = runtime.create_thread(intent="Dogfood report fixture")
            feature = runtime.record_feature(
                thread.operation.thread_id,
                artifact_name="dogfood.txt",
                content="dogfood-token\n",
                intent="Create dogfood evidence",
                assumptions=(
                    {
                        "claim": "Text is sufficient",
                        "depends_on": "The deterministic check observes exact text",
                        "confidence_rationale": "The test is deterministic",
                        "alternatives_considered": "JSON",
                    },
                ),
            )
            digest = feature.operation.outputs[0].digest
            runtime.record_test(
                thread.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_equals", "expected": "dogfood-token\n"},
            )
            runtime.stabilize(thread.operation.thread_id, artifact_digest=digest)
            runtime.run_mutation_campaign(
                thread.operation.thread_id,
                artifact_digest=digest,
                check={"kind": "text_equals", "expected": "dogfood-token\n"},
            )
            report_dir = root / "reports"
            report = create_dogfood_report(
                runtime,
                protocol_path=root / "protocol.md",
                notes="Synthetic report fixture for acceptance audit coverage.",
                model_constraints=("limited to fixture models",),
                preferred_unavailable_models=("Claude Opus-class planner", "GPT-5.5-class generator"),
                model_envelope_notes="Synthetic acceptance fixture.",
            )
            report_path = write_dogfood_report(report, report_dir / "report.json")
            loaded_report = load_dogfood_report(report_path)
            self.assertIn("limited to fixture models", loaded_report.model_capability_envelope["constraints"])
            self.assertIn(
                "GPT-5.5-class generator",
                loaded_report.model_capability_envelope["preferred_unavailable_models"],
            )
            harness_report_dir = root / "harness-reports"
            harness_report = run_scripted_agent_harness(
                runtime_root=root / "harness-runtime",
                protocol_path=root / "agentic_protocol.md",
                run_id="acceptance-harness-fixture",
            )
            write_harness_report(harness_report, harness_report_dir / "scripted-report.json")
            live_harness_report = run_live_agent_harness(
                runtime_root=root / "live-harness-runtime",
                protocol_path=root / "agentic_protocol.md",
                run_id="acceptance-live-harness-fixture",
                config_path=config,
                model_constraints=("fixture MCP model only",),
                preferred_unavailable_models=("Claude Opus-class verifier",),
            )
            self.assertIn(
                "subprocess-generator",
                json.dumps(live_harness_report.to_dict()["model_capability_envelope"]),
            )
            write_harness_report(live_harness_report, harness_report_dir / "live-report.json")
            scale3_report = run_live_agent_harness(
                runtime_root=root / "live-scale3-runtime",
                protocol_path=root / "agentic_protocol.md",
                run_id="acceptance-live-scale3-fixture",
                config_path=config,
                tasks=default_live_scale_tasks(),
            )
            write_harness_report(scale3_report, harness_report_dir / "scale3-report.json")
            code_report = run_live_agent_harness(
                runtime_root=root / "live-code-runtime",
                protocol_path=root / "agentic_protocol.md",
                run_id="acceptance-live-code-fixture",
                config_path=config,
                tasks=default_live_code_tasks(),
            )
            write_harness_report(code_report, harness_report_dir / "code-report.json")
            _write_empirical_fixtures(root, runtime)

            acceptance = run_v1_acceptance_audit(
                workspace_root=root,
                mcp_config_path=config,
                dogfood_report_dir=report_dir,
                agent_harness_report_dir=harness_report_dir,
            )

            self.assertEqual(acceptance.overall_status, "pass", acceptance.to_dict())
            self.assertEqual(acceptance.failures, ())
            self.assertEqual(acceptance.warnings, ())

    def test_acceptance_rejects_empty_or_legacy_dogfood_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "reports"
            report_dir.mkdir()
            workspace_root = Path(__file__).resolve().parents[1]
            empty_runtime = Runtime(Path(tmp) / "empty-runtime")
            legacy = {
                        "protocol_path": "docs/rq0_rq6_preregistration.md",
                        "runtime_root": str(empty_runtime.root),
                "artifact_digests": [],
                        "metrics": empty_runtime.metrics().to_dict(),
                "notes": "Invalid fixture: no artifact evidence and no model envelope.",
                "scope": "n=1 feasibility evidence",
                "generated_at": "2026-07-21T00:00:00+00:00",
                        "evidence_binding": build_evidence_binding(
                            workspace_root=workspace_root,
                            protocol_path="docs/rq0_rq6_preregistration.md",
                            runtime=empty_runtime,
                        ),
            }
            legacy["report_id"] = canonical_report_id(legacy)
            (report_dir / "legacy-empty.json").write_text(
                json.dumps(legacy),
                encoding="utf-8",
            )

            acceptance = run_v1_acceptance_audit(
                workspace_root=workspace_root,
                dogfood_report_dir=report_dir,
            )
            criterion_by_id = {criterion.id: criterion for criterion in acceptance.criteria}

            dogfood = criterion_by_id["dogfooding_rq0_rq6_results"]
            self.assertEqual(dogfood.status, "fail")
            self.assertIn("has no artifact digests", dogfood.evidence)
            self.assertIn("has no explicit model capability envelope", dogfood.evidence)


def _write_mcp_server(root: Path) -> Path:
    server = root / "mcp_server.py"
    server.write_text(
        """
import json
import ast
import re
import sys

def send(message):
    print(json.dumps(message), flush=True)


def exact_content(intent):
    match = re.search(r"content is exactly (?P<literal>'(?:\\\\.|[^'])*'|\\\"(?:\\\\.|[^\\\"])*\\\")", intent)
    if match is None:
        return None
    try:
        value = ast.literal_eval(match.group("literal"))
    except (SyntaxError, ValueError):
        return None
    return value if isinstance(value, str) else None


def model_payload(role, request):
    payload = request.get("payload", {})
    intent = payload.get("intent", "") if isinstance(payload, dict) else ""
    expected = exact_content(str(intent))
    if role == "planner":
        return {
            "steps": [
                {
                    "verb": "Feature",
                    "success_question": "Did useful possibility increase?",
                    "budget_alloc": 1.0,
                    "model_role": "generator",
                },
                {
                    "verb": "Verify",
                    "success_question": "Is trust justified?",
                    "budget_alloc": 1.0,
                    "model_role": "verifier",
                },
            ],
            "rationale": "Use a deterministic textual oracle.",
        }
    if role == "generator":
        if "merge_intervals" in intent:
            return {
                "assumptions": [
                    {
                        "claim": "A sorted fold is sufficient",
                        "depends_on": "The deterministic suite covers boundary cases",
                        "confidence_rationale": "The behavior is deterministic",
                        "alternatives_considered": "Sweep-line implementation",
                    }
                ],
                "plan": "Sort and merge overlapping or touching intervals.",
                "artifact": "def merge_intervals(intervals):\\n    merged = []\\n    for start, end in sorted([list(pair) for pair in intervals]):\\n        if merged and start <= merged[-1][1]:\\n            merged[-1][1] = max(merged[-1][1], end)\\n        else:\\n            merged.append([start, end])\\n    return merged\\n",
                "self_identified_risks": [],
            }
        return {
            "assumptions": [
                {
                    "claim": "Plain text is sufficient",
                    "depends_on": "The verifier checks a text token",
                    "confidence_rationale": "The oracle is deterministic",
                    "alternatives_considered": "JSON",
                }
            ],
            "plan": "Emit the configured token.",
            "artifact": expected if expected is not None else "configured-token\\n",
            "self_identified_risks": ["The token could be omitted."],
        }
    if role == "verifier":
        if expected is not None:
            return {
                "checkable_oracle": {"kind": "text_equals", "expected": expected},
                "verdict": "pass",
                "located_errors": [],
                "obligation_discharged": True,
            }
        return {
            "checkable_oracle": {"kind": "text_contains", "expected": "configured-token"},
            "verdict": "pass",
            "located_errors": [],
            "obligation_discharged": True,
        }
    raise SystemExit(2)


for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        send(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "fixture-mcp", "version": "1.0.0"},
                },
            }
        )
    elif method == "notifications/initialized":
        continue
    elif method == "tools/call":
        request = message["params"]["arguments"]["request"]
        role = request["role"]
        payload = model_payload(role, request)
        send(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {
                    "structuredContent": payload,
                    "content": [{"type": "text", "text": json.dumps(payload)}],
                    "isError": False,
                },
            }
        )
    else:
        send(
            {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {"code": -32601, "message": "unknown method"},
            }
        )
""".lstrip(),
        encoding="utf-8",
    )
    return server


def _write_adapter_config(root: Path, server: Path, *, executable: str = sys.executable) -> Path:
    config = root / "mcp_config.json"
    data = {
        "planner": {
            "model": {
                "model_id": "subprocess-planner",
                "family": "planner-family",
                "roles": ["planner"],
                "strength": "strong",
            },
            "transport": "mcp_stdio",
            "command": [executable, str(server)],
            "tool_name": "syberruntime_model_call",
        },
        "generator": {
            "model": {
                "model_id": "subprocess-generator",
                "family": "generator-family",
                "roles": ["generator"],
                "strength": "standard",
            },
            "transport": "mcp_stdio",
            "command": [executable, str(server)],
            "tool_name": "syberruntime_model_call",
        },
        "verifier": {
            "model": {
                "model_id": "subprocess-verifier",
                "family": "verifier-family",
                "roles": ["verifier"],
                "strength": "strong",
            },
            "transport": "mcp_stdio",
            "command": [executable, str(server)],
            "tool_name": "syberruntime_model_call",
        },
    }
    config.write_text(json.dumps(data), encoding="utf-8")
    return config


def _write_empirical_fixtures(root: Path, runtime: Runtime) -> None:
    report_dir = root / "docs" / "empirical_reports"
    conformal = {
        "report_type": "heldout_conformal_coverage",
        "protocol_path": "docs/conformal_coverage_preregistration.md",
        "scope": "n=1 feasibility evidence",
        "generated_at": "2026-07-21T00:00:00+00:00",
        "evidence_binding": build_evidence_binding(
            workspace_root=root,
            protocol_path="docs/conformal_coverage_preregistration.md",
        ),
        "result": {
            "alpha": 0.2,
            "threshold": 0.4,
            "calibration_count": 9,
            "heldout_count": 5,
            "calibration_scores": [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45],
            "heldout_scores": [0.08, 0.18, 0.28, 0.38, 0.48],
            "empirical_coverage": 0.8,
            "cohorts_disjoint": True,
            "scores_from_model_verbal_confidence": False,
        },
    }
    conformal["report_id"] = canonical_report_id(conformal)
    write_json_report(conformal, report_dir / "conformal.json")

    controlled = {
        "report_type": "rq0_rq6_controlled_baseline",
        "protocol_path": "docs/rq0_rq6_preregistration.md",
        "runtime_root": str(runtime.root),
        "scope": "n=1 feasibility evidence",
        "generated_at": "2026-07-21T00:00:01+00:00",
        "evidence_binding": build_evidence_binding(
            workspace_root=root,
            protocol_path="docs/rq0_rq6_preregistration.md",
            runtime=runtime,
        ),
        "result": {
            "preregistered_before_execution": True,
            "rq0": {
                "operation_primary": {
                    "completed": True,
                    "action_cost": runtime.metrics().action_cost,
                    "provenance_completeness": runtime.metrics().provenance_completeness,
                    "recomprehension_seconds": 0.01,
                },
                "snapshot_baseline": {"completed": True, "recomprehension_seconds": 0.02},
            },
            "rq6": {
                "grammar_enforced": {
                    "completed": True,
                    "known_bad_test_passed": False,
                    "stabilization_blocked": True,
                    "accepted_downstream": False,
                },
                "unbounded_generation": {
                    "completed": True,
                    "accepted_before_verification": True,
                    "downstream_defect_detected": True,
                },
            },
        },
    }
    controlled["report_id"] = canonical_report_id(controlled)
    write_json_report(controlled, report_dir / "controlled.json")


if __name__ == "__main__":
    unittest.main()
