from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import FixedPolicy, Runtime, load_adapter_bundle  # noqa: E402
from syberruntime.ai_contracts import PlannerOutput, VerifierOutput  # noqa: E402
from syberruntime.errors import ModelContractError  # noqa: E402
from syberruntime.providers.errors import ProviderMCPError  # noqa: E402
from syberruntime.providers.payload import build_user_prompt, call_provider, extract_json_payload  # noqa: E402


class ProviderMCPTests(unittest.TestCase):
    def test_extract_json_payload_accepts_plain_and_fenced_json(self) -> None:
        self.assertEqual(extract_json_payload('{"ok": true}'), {"ok": True})
        self.assertEqual(extract_json_payload('```json\n{"ok": true}\n```'), {"ok": True})

    def test_extract_json_payload_accepts_embedded_json_object(self) -> None:
        payload = extract_json_payload('Result follows:\n{"ok": true, "nested": {"token": "}"}}\nDone.')

        self.assertEqual(payload, {"ok": True, "nested": {"token": "}"}})

    def test_provider_prompt_constrains_planner_to_runtime_grammar(self) -> None:
        prompt = build_user_prompt(
            {
                "role": "planner",
                "operation_type": "Research",
                "system": "runtime",
                "payload": {"intent": "create a smoke artifact"},
            }
        )

        self.assertIn("You are operating inside SyberRuntime", prompt)
        self.assertIn("Feature", prompt)
        self.assertIn("Verify", prompt)
        self.assertIn("Do not use informal verbs", prompt)
        self.assertIn("SyberRuntime request:\n", prompt)

    def test_provider_prompt_constrains_verifier_oracle_shape_without_answer_injection(self) -> None:
        prompt = build_user_prompt(
            {
                "role": "verifier",
                "operation_type": "Verify",
                "system": "runtime",
                "payload": {
                    "intent": (
                        "Create a local SyberRuntime text artifact named agent-live-smoke.txt whose content "
                        "is exactly 'agent-live-smoke-token\\n', then verify it with a deterministic "
                        "text_equals oracle."
                    ),
                    "artifact": "agent-live-smoke-token\n",
                    "artifact_digest": "digest",
                },
            }
        )

        self.assertIn('"kind":"text_equals"', prompt)
        self.assertIn('"kind":"text_contains"', prompt)
        self.assertIn('"kind":"sha256_equals"', prompt)
        self.assertIn("must never be empty", prompt)
        self.assertIn("alternate keys", prompt)
        # The runtime-side constraints must not restate the expected oracle for
        # the model; the verifier has to derive it from the request itself.
        constraints = prompt.split("SyberRuntime request:\n", 1)[0]
        self.assertNotIn("agent-live-smoke-token", constraints)
        self.assertNotIn("the deterministic oracle must be", constraints)

    def test_provider_prompt_never_injects_expected_artifact_content(self) -> None:
        prompt = build_user_prompt(
            {
                "role": "generator",
                "operation_type": "Feature",
                "system": "runtime",
                "payload": {
                    "intent": (
                        "Create a local SyberRuntime text artifact named agent-scale-alpha.txt whose content "
                        "is exactly 'agent-scale-alpha-token\\n', then verify it with a deterministic "
                        "text_equals oracle."
                    ),
                    "artifact_name": "agent-scale-alpha.txt",
                },
            }
        )

        self.assertIn("not a filename", prompt)
        self.assertIn("actual newline after JSON decoding", prompt)
        # The expected content may appear only inside the raw request echo,
        # never in the runtime-side constraint text.
        constraints = prompt.split("SyberRuntime request:\n", 1)[0]
        self.assertNotIn("agent-scale-alpha-token", constraints)
        self.assertNotIn("must be exactly", constraints)

    def test_planner_contract_rejects_informal_verbs(self) -> None:
        with self.assertRaisesRegex(ModelContractError, "SyberRuntime operation verb"):
            PlannerOutput.from_payload(
                {
                    "steps": [
                        {
                            "verb": "Design",
                            "success_question": "Was a design produced?",
                            "budget_alloc": 1.0,
                            "model_role": "planner",
                        }
                    ],
                    "rationale": "Informal prose verbs are not operation graph verbs.",
                }
            )

    def test_verifier_contract_rejects_unsupported_oracle_kind(self) -> None:
        with self.assertRaisesRegex(ModelContractError, "supported deterministic check"):
            VerifierOutput.from_payload(
                {
                    "checkable_oracle": {"kind": "", "expected": "agent-live-smoke-token\n"},
                    "verdict": "pass",
                    "located_errors": [],
                    "obligation_discharged": True,
                }
            )

    def test_provider_mcp_runs_ai_loop_via_openai_compatible_endpoint(self) -> None:
        with _FakeProviderServer("openai") as provider:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _set_pythonpath()
                os.environ["SYBERRUNTIME_TEST_API_KEY"] = "test-key"
                config = _write_provider_config(
                    root,
                    provider="openai_compatible",
                    base_url=provider.base_url,
                )
                bundle = load_adapter_bundle(config)
                runtime = Runtime(root / "runtime", policy=FixedPolicy(default_profile="production"))

                result = runtime.run_ai_loop(
                    intent="Provider MCP openai-compatible smoke",
                    artifact_name="provider.txt",
                    planner=bundle.planner,
                    generator=bundle.generator,
                    verifier=bundle.verifier,
                )

                self.assertTrue(result.stabilized)
                self.assertIn("provider-token", runtime.blobs.get_text(result.artifact_digest))
                self.assertEqual(provider.request_count, 3)

    def test_provider_mcp_retries_malformed_role_payload_with_error_context(self) -> None:
        with _FakeProviderServer("openai", malformed_once_role="generator") as provider:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _set_pythonpath()
                os.environ["SYBERRUNTIME_TEST_API_KEY"] = "test-key"
                config = _write_provider_config(
                    root,
                    provider="openai_compatible",
                    base_url=provider.base_url,
                )
                bundle = load_adapter_bundle(config)
                runtime = Runtime(root / "runtime", policy=FixedPolicy(default_profile="production"))

                result = runtime.run_ai_loop(
                    intent="Provider MCP retry smoke",
                    artifact_name="provider.txt",
                    planner=bundle.planner,
                    generator=bundle.generator,
                    verifier=bundle.verifier,
                )

                self.assertTrue(result.stabilized)
                self.assertEqual(provider.request_count, 4)
                self.assertIn("Previous provider attempt failed", provider.prompts[-2])
                self.assertIn("failure_class", provider.prompts[-2])

    def test_provider_mcp_retries_schema_mismatch_with_error_context(self) -> None:
        with _FakeProviderServer("openai", schema_mismatch_once_role="verifier") as provider:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _set_pythonpath()
                os.environ["SYBERRUNTIME_TEST_API_KEY"] = "test-key"
                config = _write_provider_config(
                    root,
                    provider="openai_compatible",
                    base_url=provider.base_url,
                )
                bundle = load_adapter_bundle(config)
                runtime = Runtime(root / "runtime", policy=FixedPolicy(default_profile="production"))

                result = runtime.run_ai_loop(
                    intent="Provider MCP schema retry smoke",
                    artifact_name="provider.txt",
                    planner=bundle.planner,
                    generator=bundle.generator,
                    verifier=bundle.verifier,
                )

                self.assertTrue(result.stabilized)
                self.assertEqual(provider.request_count, 4)
                self.assertIn('"failure_class": "schema_mismatch"', provider.prompts[-1])

    def test_provider_mcp_preserves_attempt_diagnostics_after_retry_exhaustion(self) -> None:
        with _FakeProviderServer("openai", always_malformed_role="generator") as provider:
            os.environ["SYBERRUNTIME_TEST_API_KEY"] = "test-key"
            with self.assertRaisesRegex(ProviderMCPError, "after 2 attempt") as raised:
                call_provider(
                    {
                        "provider": "openai_compatible",
                        "api_key_env": "SYBERRUNTIME_TEST_API_KEY",
                        "base_url": provider.base_url,
                        "model": {
                            "model_id": "retry-generator",
                            "family": "test",
                            "roles": ["generator"],
                        },
                        "request": {
                            "role": "generator",
                            "operation_type": "Feature",
                            "system": "runtime",
                            "payload": {"intent": "create provider token", "artifact_name": "provider.txt"},
                        },
                    }
                )

            diagnostic = raised.exception.diagnostic()
            self.assertEqual(diagnostic["failure_class"], "malformed_json")
            self.assertEqual(len(diagnostic["attempts"]), 2)
            self.assertEqual(diagnostic["attempts"][0]["raw_response_preview"], "not valid json")
            self.assertIn("raw_response_sha256", diagnostic["attempts"][0])

    def test_provider_mcp_google_and_anthropic_response_shapes(self) -> None:
        for shape, provider_name in (("google", "google"), ("anthropic", "anthropic")):
            with self.subTest(shape=shape):
                with _FakeProviderServer(shape) as provider:
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        _set_pythonpath()
                        os.environ["SYBERRUNTIME_TEST_API_KEY"] = "test-key"
                        config = _write_provider_config(
                            root,
                            provider=provider_name,
                            endpoint=provider.endpoint,
                        )
                        bundle = load_adapter_bundle(config)
                        runtime = Runtime(root / "runtime", policy=FixedPolicy(default_profile="production"))

                        result = runtime.run_ai_loop(
                            intent=f"Provider MCP {provider_name} smoke",
                            artifact_name="provider.txt",
                            planner=bundle.planner,
                            generator=bundle.generator,
                            verifier=bundle.verifier,
                        )

                        self.assertTrue(result.stabilized)
                        self.assertEqual(provider.request_count, 3)


class _FakeProviderServer:
    def __init__(
        self,
        shape: str,
        *,
        malformed_once_role: str | None = None,
        schema_mismatch_once_role: str | None = None,
        always_malformed_role: str | None = None,
    ) -> None:
        self.shape = shape
        self.malformed_once_role = malformed_once_role
        self.schema_mismatch_once_role = schema_mismatch_once_role
        self.always_malformed_role = always_malformed_role
        self.request_count = 0
        self.prompts: list[str] = []
        self._malformed_once_sent = False
        self._schema_mismatch_once_sent = False
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def endpoint(self) -> str:
        return self.base_url + "/endpoint"

    def __enter__(self) -> "_FakeProviderServer":
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                outer.request_count += 1
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                role = _role_from_provider_body(body, outer.shape)
                outer.prompts.append(_prompt_from_provider_body(body, outer.shape))
                payload = _payload_for_role(role)
                if outer.always_malformed_role == role:
                    provider_text = "not valid json"
                elif outer.malformed_once_role == role and not outer._malformed_once_sent:
                    outer._malformed_once_sent = True
                    provider_text = "not valid json"
                elif outer.schema_mismatch_once_role == role and not outer._schema_mismatch_once_sent:
                    outer._schema_mismatch_once_sent = True
                    provider_text = json.dumps({"verdict": "pass"})
                else:
                    provider_text = json.dumps(payload)
                if outer.shape == "google":
                    response: dict[str, Any] = {
                        "candidates": [{"content": {"parts": [{"text": provider_text}]}}]
                    }
                elif outer.shape == "anthropic":
                    response = {"content": [{"type": "text", "text": provider_text}]}
                else:
                    response = {"choices": [{"message": {"content": provider_text}}]}
                encoded = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *args: Any) -> None:
                return

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        assert self._server is not None
        self._server.shutdown()
        assert self._thread is not None
        self._thread.join(timeout=5)
        self._server.server_close()


def _role_from_provider_body(body: dict[str, Any], shape: str) -> str:
    text = _prompt_from_provider_body(body, shape)
    marker = "SyberRuntime request:\n"
    request = json.loads(text.split(marker, 1)[1])
    return str(request["role"])


def _prompt_from_provider_body(body: dict[str, Any], shape: str) -> str:
    if shape == "google":
        return str(body["contents"][0]["parts"][0]["text"])
    elif shape == "anthropic":
        return str(body["messages"][0]["content"])
    return str(body["messages"][1]["content"])


def _payload_for_role(role: str) -> dict[str, Any]:
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
            "plan": "Emit the provider token.",
            "artifact": "provider-token\n",
            "self_identified_risks": ["The token could be omitted."],
        }
    if role == "verifier":
        return {
            "checkable_oracle": {"kind": "text_contains", "expected": "provider-token"},
            "verdict": "pass",
            "located_errors": [],
            "obligation_discharged": True,
        }
    raise AssertionError(f"Unexpected role: {role}")


def _write_provider_config(
    root: Path,
    *,
    provider: str,
    base_url: str | None = None,
    endpoint: str | None = None,
) -> Path:
    config = root / "provider_mcp_config.json"
    sections = {}
    for role, family in (
        ("planner", "planner-family"),
        ("generator", "generator-family"),
        ("verifier", "verifier-family"),
    ):
        arguments: dict[str, Any] = {
            "provider": provider,
            "api_key_env": "SYBERRUNTIME_TEST_API_KEY",
            "max_tokens": 512,
        }
        if base_url is not None:
            arguments["base_url"] = base_url
        if endpoint is not None:
            arguments["endpoint"] = endpoint
        sections[role] = {
            "transport": "mcp_stdio",
            "model": {
                "model_id": f"{provider}-{role}",
                "family": family,
                "roles": [role],
                "strength": "standard",
            },
            "command": [sys.executable, "-m", "syberruntime.provider_mcp"],
            "tool_name": "syberruntime_model_call",
            "arguments": arguments,
            "timeout_seconds": 30,
        }
    config.write_text(json.dumps(sections), encoding="utf-8")
    return config


def _set_pythonpath() -> None:
    src = str(Path(__file__).resolve().parents[1] / "src")
    existing = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = src if not existing else src + os.pathsep + existing


if __name__ == "__main__":
    unittest.main()
