"""Provider-backed MCP stdio server for SyberRuntime model calls.

The server exposes one MCP tool, `syberruntime_model_call`. The tool receives a
SyberRuntime model spec and model request, calls a configured provider, and
returns the strict role payload as MCP `structuredContent`.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


TOOL_NAME = "syberruntime_model_call"
PROTOCOL_VERSION = "2025-06-18"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 120.0


class ProviderMCPError(Exception):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    api_key_env: str
    base_url: str | None = None
    endpoint: str | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_tokens: int = 2048
    temperature: float = 0.0
    json_mode: bool = True
    extra_body: dict[str, Any] | None = None


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
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
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


def call_provider(arguments: dict[str, Any]) -> dict[str, Any]:
    model = _require_object(arguments, "model")
    request = _require_object(arguments, "request")
    config = _provider_config(arguments)
    prompt = _user_prompt(request)
    model_id = str(arguments.get("provider_model") or model.get("model_id"))

    if config.provider in {"openai", "deepseek", "openai_compatible"}:
        text = _call_openai_compatible(config, model_id=model_id, system=str(request["system"]), prompt=prompt)
    elif config.provider == "anthropic":
        text = _call_anthropic(config, model_id=model_id, system=str(request["system"]), prompt=prompt)
    elif config.provider == "google":
        text = _call_google(config, model_id=model_id, system=str(request["system"]), prompt=prompt)
    else:
        raise ProviderMCPError(f"Unsupported provider: {config.provider}")

    return _extract_json_payload(text)


def _provider_config(arguments: dict[str, Any]) -> ProviderConfig:
    provider = str(arguments.get("provider", "")).strip().lower()
    if not provider:
        raise ProviderMCPError("Provider argument is required")

    api_key_env = arguments.get("api_key_env")
    if not isinstance(api_key_env, str) or not api_key_env:
        api_key_env = {
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
        }.get(provider, "")
    if not api_key_env:
        raise ProviderMCPError(f"Provider {provider} requires api_key_env")

    extra_body = arguments.get("extra_body", {})
    if not isinstance(extra_body, dict):
        raise ProviderMCPError("extra_body must be a JSON object")
    return ProviderConfig(
        provider=provider,
        api_key_env=api_key_env,
        base_url=_optional_string(arguments.get("base_url")),
        endpoint=_optional_string(arguments.get("endpoint")),
        timeout_seconds=float(arguments.get("provider_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        max_tokens=int(arguments.get("max_tokens", 2048)),
        temperature=float(arguments.get("temperature", 0.0)),
        json_mode=bool(arguments.get("json_mode", True)),
        extra_body=extra_body,
    )


def _call_openai_compatible(config: ProviderConfig, *, model_id: str, system: str, prompt: str) -> str:
    api_key = _api_key(config)
    if config.endpoint:
        endpoint = config.endpoint
    else:
        base_url = config.base_url or {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com",
            "openai_compatible": "",
        }[config.provider]
        if not base_url:
            raise ProviderMCPError("openai_compatible provider requires base_url or endpoint")
        endpoint = base_url.rstrip("/") + "/chat/completions"

    body: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "stream": False,
        "max_tokens": config.max_tokens,
    }
    if config.json_mode:
        body["response_format"] = {"type": "json_object"}
    body.update(config.extra_body or {})
    data = _post_json(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        body=body,
        timeout_seconds=config.timeout_seconds,
    )
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderMCPError(f"Provider response missing chat content: {data}") from exc


def _call_anthropic(config: ProviderConfig, *, model_id: str, system: str, prompt: str) -> str:
    api_key = _api_key(config)
    endpoint = config.endpoint or (config.base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
    body: dict[str, Any] = {
        "model": model_id,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    body.update(config.extra_body or {})
    data = _post_json(
        endpoint,
        headers={"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION},
        body=body,
        timeout_seconds=config.timeout_seconds,
    )
    try:
        for item in data["content"]:
            if item.get("type") == "text":
                return str(item["text"])
    except (KeyError, TypeError) as exc:
        raise ProviderMCPError(f"Anthropic response missing text content: {data}") from exc
    raise ProviderMCPError(f"Anthropic response had no text content: {data}")


def _call_google(config: ProviderConfig, *, model_id: str, system: str, prompt: str) -> str:
    api_key = _api_key(config, fallback_env="GEMINI_API_KEY")
    if config.endpoint:
        endpoint = config.endpoint
    else:
        base_url = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        model_path = urllib.parse.quote(model_id, safe="")
        endpoint = f"{base_url}/models/{model_path}:generateContent?key={urllib.parse.quote(api_key)}"
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": config.temperature,
            "maxOutputTokens": config.max_tokens,
            "responseMimeType": "application/json",
        },
    }
    body.update(config.extra_body or {})
    data = _post_json(endpoint, headers={}, body=body, timeout_seconds=config.timeout_seconds)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(str(part.get("text", "")) for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderMCPError(f"Google response missing candidate text: {data}") from exc


def _user_prompt(request: dict[str, Any]) -> str:
    role = str(request["role"])
    return (
        "Return only one JSON object. Do not include Markdown fences, prose, prefaces, or commentary.\n"
        "You are operating inside SyberRuntime. Produce only the requested role payload; do not design "
        "external cloud services, provider integrations, credentials, APIs, repositories, or storage unless "
        "the request explicitly asks for them.\n"
        f"Role: {role}\n"
        f"Required JSON schema summary: {_schema_summary(role)}\n"
        f"Role-specific constraints: {_role_constraints(role)}\n"
        "SyberRuntime request:\n"
        f"{json.dumps(request, sort_keys=True)}"
    )


def _schema_summary(role: str) -> str:
    if role == "planner":
        return (
            '{"steps":[{"verb":"Feature|Test|Refactor|Research|Verify|Compress|Simulate|Stabilize",'
            '"success_question":str,"budget_alloc":number,"model_role":"generator|verifier|planner"}],'
            '"rationale":str}'
        )
    if role == "generator":
        return (
            '{"assumptions":[{"claim":str,"depends_on":str,"confidence_rationale":str,'
            '"alternatives_considered":str}],"plan":str,"artifact":str,"self_identified_risks":[str]}'
        )
    if role == "verifier":
        return '{"checkable_oracle":object|null,"verdict":"pass|fail|uncertain","located_errors":[{"where":str,"why":str}],"obligation_discharged":bool}'
    return "{}"


def _role_constraints(role: str) -> str:
    if role == "planner":
        return (
            "Plan only SyberRuntime operations. Use exact operation verbs from the schema; for the live "
            "smoke path prefer one Feature step with model_role generator followed by one Verify step with "
            "model_role verifier. Do not use informal verbs such as Identify, Define, Design, Sketch, or Summarize."
        )
    if role == "generator":
        return (
            "Create the requested local artifact content in the artifact field. Do not describe a provider "
            "architecture or setup process. If the intent specifies exact text, emit that text verbatim."
        )
    if role == "verifier":
        return (
            "Prefer a deterministic checkable_oracle using text_equals for exact content or text_contains "
            "for substring checks. Use verdict pass only when the oracle is consistent with the artifact."
        )
    return "Return the requested SyberRuntime role payload."


def _extract_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    candidates = [stripped]
    embedded = _first_balanced_json_object(stripped)
    if embedded is not None and embedded != stripped:
        candidates.append(embedded)
    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(payload, dict):
            raise ProviderMCPError("Provider JSON payload must be an object")
        return payload
    if last_error is None:
        raise ProviderMCPError("Provider did not return valid JSON")
    raise ProviderMCPError("Provider did not return valid JSON") from last_error


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderMCPError(f"Provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderMCPError(f"Provider connection failed: {exc}") from exc
    try:
        parsed = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderMCPError("Provider returned invalid JSON response") from exc
    if not isinstance(parsed, dict):
        raise ProviderMCPError("Provider response must be a JSON object")
    return parsed


def _api_key(config: ProviderConfig, *, fallback_env: str | None = None) -> str:
    value = os.environ.get(config.api_key_env)
    if not value and fallback_env is not None:
        value = os.environ.get(fallback_env)
    if not value:
        env_hint = config.api_key_env if fallback_env is None else f"{config.api_key_env} or {fallback_env}"
        raise ProviderMCPError(f"Missing provider API key environment variable: {env_hint}")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderMCPError("Optional string config value was not a string")
    return value


def _require_object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ProviderMCPError(f"Tool argument {key} must be an object")
    return value


def _send(message: dict[str, Any]) -> None:
    print(json.dumps(message), flush=True)


def _json_rpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    raise SystemExit(main())
