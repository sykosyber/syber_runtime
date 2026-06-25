"""Deterministic MCP stdio server for local adapter smoke tests.

This is not a model endpoint. It is a minimal MCP-compatible test server that
answers initialize and tools/call so the runtime can exercise the real MCP
stdio adapter path without external credentials.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    for line in sys.stdin:
        message = json.loads(line)
        method = message.get("method")
        if method == "initialize":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "syberruntime-mock-mcp", "version": "1.0.0"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/call":
            request = message["params"]["arguments"]["request"]
            payload = _model_payload(request)
            _send(
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
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32601, "message": "unknown method"},
                }
            )
    return 0


def _send(message: dict[str, Any]) -> None:
    print(json.dumps(message), flush=True)


def _model_payload(request: dict[str, Any]) -> dict[str, Any]:
    role = str(request["role"])
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
        expected = _expected_text(request)
        return {
            "assumptions": [
                {
                    "claim": "Plain text is sufficient",
                    "depends_on": "The verifier checks a text token",
                    "confidence_rationale": "The oracle is deterministic",
                    "alternatives_considered": "JSON",
                }
            ],
            "plan": "Emit the expected deterministic token.",
            "artifact": expected,
            "self_identified_risks": ["The token could be omitted."],
        }
    if role == "verifier":
        expected = _expected_text(request)
        return {
            "checkable_oracle": {"kind": "text_equals", "expected": expected},
            "verdict": "pass",
            "located_errors": [],
            "obligation_discharged": True,
        }
    raise SystemExit(2)


def _expected_text(request: dict[str, Any]) -> str:
    payload = request.get("payload", {})
    if not isinstance(payload, dict):
        return "configured-token\n"
    intent = str(payload.get("intent", ""))
    artifact_name = str(payload.get("artifact_name", ""))
    artifact = str(payload.get("artifact", ""))
    if (
        artifact_name == "agent-live-smoke.txt"
        or "agent-live-smoke-token" in intent
        or artifact == "agent-live-smoke-token\n"
    ):
        return "agent-live-smoke-token\n"
    return "configured-token\n"


if __name__ == "__main__":
    raise SystemExit(main())
