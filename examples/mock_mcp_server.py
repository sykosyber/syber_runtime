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
            role = message["params"]["arguments"]["request"]["role"]
            payload = _model_payload(role)
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


def _model_payload(role: str) -> dict[str, Any]:
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
            "artifact": "configured-token\n",
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


if __name__ == "__main__":
    raise SystemExit(main())
