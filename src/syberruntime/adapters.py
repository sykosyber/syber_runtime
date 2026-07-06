"""Model adapter boundary for Phase 2.

Inference remains external to the runtime. Tests use ScriptedModelAdapter for
determinism; production wiring uses an MCP stdio tool endpoint without changing
the operation log.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

from syberruntime.ai_contracts import ModelRequest, ModelResponse, ModelSpec
from syberruntime.errors import AdapterError
from syberruntime.hashing import canonical_json, normalize_json


MCP_PROTOCOL_VERSION = "2025-06-18"


class ModelAdapter(Protocol):
    @property
    def spec(self) -> ModelSpec:
        ...

    def call(self, request: ModelRequest) -> ModelResponse:
        ...


@dataclass(frozen=True)
class ScriptedModelAdapter:
    spec: ModelSpec
    responses: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_remaining", list(self.responses))

    def call(self, request: ModelRequest) -> ModelResponse:
        if not self.spec.supports(request.role):
            raise AdapterError(f"Model {self.spec.model_id} does not support role {request.role}")
        if not self._remaining:
            raise AdapterError(f"Scripted adapter {self.spec.model_id} has no response for {request.role}")
        payload = self._remaining.pop(0)
        return ModelResponse(model=self.spec, payload=normalize_json(payload))


class MCPStdioToolAdapter:
    """MCP stdio client that invokes a configured tool for model calls.

    The adapter starts a real MCP stdio server command, performs the MCP
    lifecycle initialization, sends `notifications/initialized`, then invokes
    one configured `tools/call`. The tool result must expose the strict
    SyberRuntime model payload as `structuredContent` or as JSON text content.
    """

    def __init__(
        self,
        *,
        spec: ModelSpec,
        command: tuple[str, ...],
        tool_name: str,
        timeout_seconds: float = 60.0,
        protocol_version: str = MCP_PROTOCOL_VERSION,
        static_arguments: dict[str, Any] | None = None,
    ) -> None:
        self._spec = spec
        self.command = command
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        self.protocol_version = protocol_version
        self.static_arguments = normalize_json(static_arguments or {})
        if not isinstance(self.static_arguments, dict):
            raise AdapterError("MCP static arguments must be a JSON object")

    @property
    def spec(self) -> ModelSpec:
        return self._spec

    def call(self, request: ModelRequest) -> ModelResponse:
        if not self.spec.supports(request.role):
            raise AdapterError(f"Model {self.spec.model_id} does not support role {request.role}")

        initialize_id = f"{request.role}:initialize"
        call_id = f"{request.role}:tools-call"
        arguments = {
            **self.static_arguments,
            "model": self.spec.to_dict(),
            "request": request.to_dict(),
        }
        messages = (
            {
                "jsonrpc": "2.0",
                "id": initialize_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "SyberRuntime",
                        "version": "0.1.0",
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {
                    "name": self.tool_name,
                    "arguments": arguments,
                },
            },
        )
        responses = _run_mcp_stdio_session(
            command=self.command,
            messages=messages,
            timeout_seconds=self.timeout_seconds,
        )
        initialize_response = _response_for_id(responses, initialize_id)
        _raise_json_rpc_error(initialize_response, "MCP initialize")
        _validate_initialize_result(initialize_response.get("result"))

        call_response = _response_for_id(responses, call_id)
        _raise_json_rpc_error(call_response, "MCP tools/call")
        payload = _payload_from_tool_result(call_response.get("result"))
        return ModelResponse(model=self.spec, payload=payload)


def _run_mcp_stdio_session(
    *,
    command: tuple[str, ...],
    messages: tuple[dict[str, Any], ...],
    timeout_seconds: float,
) -> tuple[dict[str, Any], ...]:
    stdin = "".join(canonical_json(message) + "\n" for message in messages)
    try:
        completed = subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except OSError as exc:
        raise AdapterError(f"Could not start MCP server command {command!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdapterError(f"MCP server command timed out: {command!r}") from exc

    if completed.returncode != 0:
        raise AdapterError(
            f"MCP server command failed with exit code {completed.returncode}: {completed.stderr.strip()}"
        )

    responses = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdapterError("MCP server wrote non-JSON output to stdout") from exc
        if not isinstance(message, dict):
            raise AdapterError("MCP server stdout message must be a JSON object")
        responses.append(message)
    return tuple(responses)


def _response_for_id(responses: tuple[dict[str, Any], ...], response_id: str) -> dict[str, Any]:
    for response in responses:
        if response.get("id") == response_id:
            return response
    raise AdapterError(f"MCP server response missing id {response_id!r}")


def _raise_json_rpc_error(response: dict[str, Any], label: str) -> None:
    if "error" in response:
        raise AdapterError(f"{label} returned JSON-RPC error: {response['error']}")


def _validate_initialize_result(result: Any) -> None:
    if not isinstance(result, dict):
        raise AdapterError("MCP initialize result must be a JSON object")
    capabilities = result.get("capabilities", {})
    if not isinstance(capabilities, dict):
        raise AdapterError("MCP initialize capabilities must be a JSON object")
    if "tools" not in capabilities:
        raise AdapterError("MCP server does not declare the tools capability")


def _payload_from_tool_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise AdapterError("MCP tools/call result must be a JSON object")
    if result.get("isError") is True:
        diagnostic: dict[str, Any] | None = None
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            maybe_error = normalize_json(structured.get("error", structured))
            if isinstance(maybe_error, dict):
                diagnostic = maybe_error
        if diagnostic is not None:
            failure_class = diagnostic.get("failure_class", "provider_error")
            message = diagnostic.get("message", "MCP tool returned isError=true")
            raise AdapterError(
                f"MCP tool returned isError=true: {message}; failure_class={failure_class}",
                diagnostic=diagnostic,
            )
        raise AdapterError(f"MCP tool returned isError=true: {result}")

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return normalize_json(structured)

    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise AdapterError("MCP text content did not contain JSON payload") from exc
                    payload = normalize_json(payload)
                    if not isinstance(payload, dict):
                        raise AdapterError("MCP text payload must decode to a JSON object")
                    return payload

    raise AdapterError("MCP tool result missing structuredContent or JSON text content")
