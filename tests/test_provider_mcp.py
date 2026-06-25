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
from syberruntime.provider_mcp import _extract_json_payload  # noqa: E402


class ProviderMCPTests(unittest.TestCase):
    def test_extract_json_payload_accepts_plain_and_fenced_json(self) -> None:
        self.assertEqual(_extract_json_payload('{"ok": true}'), {"ok": True})
        self.assertEqual(_extract_json_payload('```json\n{"ok": true}\n```'), {"ok": True})

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
    def __init__(self, shape: str) -> None:
        self.shape = shape
        self.request_count = 0
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
                payload = _payload_for_role(role)
                if outer.shape == "google":
                    response: dict[str, Any] = {
                        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
                    }
                elif outer.shape == "anthropic":
                    response = {"content": [{"type": "text", "text": json.dumps(payload)}]}
                else:
                    response = {"choices": [{"message": {"content": json.dumps(payload)}}]}
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
    if shape == "google":
        text = body["contents"][0]["parts"][0]["text"]
    elif shape == "anthropic":
        text = body["messages"][0]["content"]
    else:
        text = body["messages"][1]["content"]
    marker = "SyberRuntime request:\n"
    request = json.loads(text.split(marker, 1)[1])
    return str(request["role"])


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
