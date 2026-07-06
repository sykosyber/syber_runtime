"""MCP stdio framing for the SyberRuntime provider server.

The server exposes one MCP tool, `syberruntime_model_call`. The tool receives a
SyberRuntime model spec and model request, calls a configured provider via
`syberruntime.providers.payload`, and returns the strict role payload as MCP
`structuredContent`.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from syberruntime.providers.errors import ProviderMCPError
from syberruntime.providers.payload import call_provider


TOOL_NAME = "syberruntime_model_call"
PROTOCOL_VERSION = "2025-06-18"


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = _handle_message(json.loads(line))
        except Exception as exc:  # noqa: BLE001 - MCP boundary must not leak tracebacks.
            response = _json_rpc_error(None, -32603, str(exc))
        if response is not None:
            _send(response)
    return 0


def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "syberruntime-provider-mcp", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": [
                    {
                        "name": TOOL_NAME,
                        "description": "Call a configured provider and return a strict SyberRuntime role payload.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "model": {"type": "object"},
                                "request": {"type": "object"},
                                "provider": {"type": "string"},
                            },
                            "required": ["model", "request", "provider"],
                        },
                    }
                ]
            },
        }
    if method == "tools/call":
        return _handle_tool_call(message)
    return _json_rpc_error(message.get("id"), -32601, f"Unknown MCP method: {method}")


def _handle_tool_call(message: dict[str, Any]) -> dict[str, Any]:
    params = message.get("params", {})
    if not isinstance(params, dict):
        return _json_rpc_error(message.get("id"), -32602, "tools/call params must be an object")
    if params.get("name") != TOOL_NAME:
        return _json_rpc_error(message.get("id"), -32602, f"Unknown tool: {params.get('name')}")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return _json_rpc_error(message.get("id"), -32602, "tool arguments must be an object")

    try:
        payload = call_provider(arguments)
    except ProviderMCPError as exc:
        diagnostic = exc.diagnostic()
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "structuredContent": {"error": diagnostic},
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "structuredContent": payload,
            "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
            "isError": False,
        },
    }


def _send(message: dict[str, Any]) -> None:
    print(json.dumps(message), flush=True)


def _json_rpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    raise SystemExit(main())
