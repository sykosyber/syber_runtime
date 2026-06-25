from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import (  # noqa: E402
    FixedPolicy,
    Runtime,
    create_dogfood_report,
    load_adapter_bundle,
    run_v1_acceptance_audit,
    run_live_agent_harness,
    run_scripted_agent_harness,
    write_harness_report,
    write_dogfood_report,
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
            )
            write_dogfood_report(report, report_dir / "report.json")
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
            )
            write_harness_report(live_harness_report, harness_report_dir / "live-report.json")
            docs = root / "docs"
            docs.mkdir()
            (docs / "rq0_rq6_preregistration.md").write_text("protocol", encoding="utf-8")
            (docs / "phase4_walkthrough.md").write_text("walkthrough", encoding="utf-8")

            acceptance = run_v1_acceptance_audit(
                workspace_root=root,
                mcp_config_path=config,
                dogfood_report_dir=report_dir,
                agent_harness_report_dir=harness_report_dir,
            )

            self.assertEqual(acceptance.overall_status, "pass")
            self.assertEqual(acceptance.failures, ())
            self.assertEqual(acceptance.warnings, ())


def _write_mcp_server(root: Path) -> Path:
    server = root / "mcp_server.py"
    server.write_text(
        """
import json
import sys

def send(message):
    print(json.dumps(message), flush=True)


def model_payload(role):
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
            "artifact": "configured-token\\n",
            "self_identified_risks": ["The token could be omitted."],
        }
    if role == "verifier":
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
        role = message["params"]["arguments"]["request"]["role"]
        payload = model_payload(role)
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


if __name__ == "__main__":
    unittest.main()
