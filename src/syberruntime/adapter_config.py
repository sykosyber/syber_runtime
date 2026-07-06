"""Configuration loading for live MCP-style model adapters."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.adapters import MCPStdioToolAdapter, ModelAdapter
from syberruntime.ai_contracts import ModelSpec
from syberruntime.errors import AdapterError


@dataclass(frozen=True)
class AdapterBundle:
    planner: ModelAdapter
    generator: ModelAdapter
    verifier: ModelAdapter


def load_adapter_bundle(path: str | Path) -> AdapterBundle:
    config_path = Path(path)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdapterError(f"Adapter config not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Adapter config is not valid JSON: {config_path}") from exc

    return AdapterBundle(
        planner=_load_mcp_adapter(data, "planner"),
        generator=_load_mcp_adapter(data, "generator"),
        verifier=_load_mcp_adapter(data, "verifier"),
    )


def _load_mcp_adapter(data: dict[str, Any], key: str) -> ModelAdapter:
    section = data.get(key)
    if not isinstance(section, dict):
        raise AdapterError(f"Adapter config missing object section: {key}")
    model = section.get("model")
    if not isinstance(model, dict):
        raise AdapterError(f"Adapter section {key} missing model object")
    command = section.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise AdapterError(f"Adapter section {key} command must be a non-empty string list")

    try:
        model_id = str(model["model_id"])
        family = str(model["family"])
    except KeyError as exc:
        raise AdapterError(f"Adapter section {key} model missing required field: {exc.args[0]}") from exc

    spec = ModelSpec(
        model_id=model_id,
        family=family,
        roles=tuple(str(role) for role in model.get("roles", (key,))),
        strength=str(model.get("strength", "standard")),
    )
    timeout_seconds = float(section.get("timeout_seconds", 60.0))
    expanded_command = tuple(os.path.expandvars(item) for item in command)
    transport = str(section.get("transport", "mcp_stdio"))
    if transport == "mcp_stdio":
        tool_name = section.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name:
            raise AdapterError(f"Adapter section {key} missing non-empty tool_name for mcp_stdio transport")
        static_arguments = section.get("arguments", {})
        if not isinstance(static_arguments, dict):
            raise AdapterError(f"Adapter section {key} arguments must be a JSON object")
        protocol_version = str(section.get("protocol_version", "2025-06-18"))
        return MCPStdioToolAdapter(
            spec=spec,
            command=expanded_command,
            tool_name=tool_name,
            timeout_seconds=timeout_seconds,
            protocol_version=protocol_version,
            static_arguments=static_arguments,
        )
    raise AdapterError(f"Adapter section {key} has unsupported transport: {transport}")
