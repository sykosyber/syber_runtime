"""Provider HTTP dialects for the MCP server.

Each provider function takes a resolved ProviderConfig and returns the raw
model text. Contract enforcement happens in `payload`, never here.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from syberruntime.providers.errors import ProviderMCPError


ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 120.0


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


def provider_config_from_arguments(arguments: dict[str, Any]) -> ProviderConfig:
    provider = str(arguments.get("provider", "")).strip().lower()
    if not provider:
        raise ProviderMCPError("Provider argument is required", failure_class="invalid_config")

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
        raise ProviderMCPError(f"Provider {provider} requires api_key_env", failure_class="invalid_config")

    extra_body = arguments.get("extra_body", {})
    if not isinstance(extra_body, dict):
        raise ProviderMCPError("extra_body must be a JSON object", failure_class="invalid_config")
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


def call_provider_text(config: ProviderConfig, *, model_id: str, system: str, prompt: str) -> str:
    if config.provider in {"openai", "deepseek", "openai_compatible"}:
        return _call_openai_compatible(config, model_id=model_id, system=system, prompt=prompt)
    if config.provider == "anthropic":
        return _call_anthropic(config, model_id=model_id, system=system, prompt=prompt)
    if config.provider == "google":
        return _call_google(config, model_id=model_id, system=system, prompt=prompt)
    raise ProviderMCPError(f"Unsupported provider: {config.provider}", failure_class="unsupported_provider")


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
            raise ProviderMCPError(
                "openai_compatible provider requires base_url or endpoint",
                failure_class="invalid_config",
            )
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
        raise ProviderMCPError(
            f"Provider response missing chat content: {data}",
            failure_class="provider_response_shape",
        ) from exc


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
        raise ProviderMCPError(
            f"Anthropic response missing text content: {data}",
            failure_class="provider_response_shape",
        ) from exc
    raise ProviderMCPError(
        f"Anthropic response had no text content: {data}",
        failure_class="provider_response_shape",
    )


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
        raise ProviderMCPError(
            f"Google response missing candidate text: {data}",
            failure_class="provider_response_shape",
        ) from exc


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
        raise ProviderMCPError(f"Provider HTTP {exc.code}: {detail}", failure_class="provider_http") from exc
    except urllib.error.URLError as exc:
        raise ProviderMCPError(f"Provider connection failed: {exc}", failure_class="provider_connection") from exc
    try:
        parsed = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderMCPError(
            "Provider returned invalid JSON response",
            failure_class="provider_response_malformed_json",
        ) from exc
    if not isinstance(parsed, dict):
        raise ProviderMCPError("Provider response must be a JSON object", failure_class="provider_response_not_object")
    return parsed


def _api_key(config: ProviderConfig, *, fallback_env: str | None = None) -> str:
    value = os.environ.get(config.api_key_env)
    if not value and fallback_env is not None:
        value = os.environ.get(fallback_env)
    if not value:
        env_hint = config.api_key_env if fallback_env is None else f"{config.api_key_env} or {fallback_env}"
        raise ProviderMCPError(
            f"Missing provider API key environment variable: {env_hint}",
            failure_class="missing_api_key",
        )
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderMCPError("Optional string config value was not a string", failure_class="invalid_config")
    return value
