"""Prompt construction and strict payload acceptance for provider calls.

This module turns a SyberRuntime model request into a provider prompt, then
enforces the role contract on whatever comes back, retrying with failure
context up to the configured budget.

Evidence-integrity rule: the prompt must never restate expected artifact
content or oracle values derived from the intent. The model sees the raw
request (including the intent text); the runtime-side constraints describe
only the required JSON *shape*. Injecting expected answers would make the
downstream deterministic verification circular.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from syberruntime.ai_contracts import GeneratorOutput, PlannerOutput, VerifierOutput
from syberruntime.errors import ModelContractError
from syberruntime.providers.clients import call_provider_text, provider_config_from_arguments
from syberruntime.providers.errors import ProviderMCPError


DEFAULT_CONTRACT_RETRIES = 1
RAW_RESPONSE_PREVIEW_CHARS = 1200


def call_provider(arguments: dict[str, Any]) -> dict[str, Any]:
    model = _require_object(arguments, "model")
    request = _require_object(arguments, "request")
    config = provider_config_from_arguments(arguments)
    model_id = str(arguments.get("provider_model") or model.get("model_id"))
    max_contract_retries = _max_contract_retries(arguments)
    attempts: list[dict[str, Any]] = []
    retry_context: dict[str, Any] | None = None

    for attempt_number in range(max_contract_retries + 1):
        prompt = build_user_prompt(request, retry_context=retry_context)
        try:
            text = call_provider_text(config, model_id=model_id, system=str(request["system"]), prompt=prompt)
        except ProviderMCPError as exc:
            if attempts:
                raise ProviderMCPError(
                    str(exc),
                    failure_class=exc.failure_class,
                    attempts=tuple(attempts),
                ) from exc
            raise
        try:
            payload = extract_json_payload(text)
            validate_role_payload(str(request["role"]), payload)
            return payload
        except ProviderMCPError as exc:
            if exc.failure_class not in {"malformed_json", "payload_not_object", "schema_mismatch"}:
                raise
            attempt = _provider_attempt_record(
                attempt_number=attempt_number + 1,
                retry_context_injected=retry_context is not None,
                role=str(request["role"]),
                provider=config.provider,
                model_id=model_id,
                error=exc,
                raw_response=text,
            )
            attempts.append(attempt)
            if attempt_number >= max_contract_retries:
                raise ProviderMCPError(
                    (
                        "Provider did not return an acceptable SyberRuntime JSON payload after "
                        f"{len(attempts)} attempt(s); failure_class={exc.failure_class}"
                    ),
                    failure_class=exc.failure_class,
                    attempts=tuple(attempts),
                ) from exc
            retry_context = attempt

    raise ProviderMCPError("Provider retry loop exited unexpectedly", attempts=tuple(attempts))


def build_user_prompt(request: dict[str, Any], retry_context: dict[str, Any] | None = None) -> str:
    role = str(request["role"])
    prompt = (
        "Return only one JSON object. Do not include Markdown fences, prose, prefaces, or commentary.\n"
        "You are operating inside SyberRuntime. Produce only the requested role payload; do not design "
        "external cloud services, provider integrations, credentials, APIs, repositories, or storage unless "
        "the request explicitly asks for them.\n"
        f"Role: {role}\n"
        f"Required JSON schema summary: {_schema_summary(role)}\n"
        f"Role-specific constraints: {_role_constraints(role)}\n"
    )
    if retry_context is not None:
        prompt += (
            "Previous provider attempt failed before SyberRuntime acceptance.\n"
            f"Failure context: {json.dumps(retry_context, sort_keys=True)}\n"
            "Return a fresh complete payload for the same role. Do not explain or summarize the failure. "
            "Do not quote the previous response. Return only one valid JSON object matching the schema.\n"
        )
    return prompt + "SyberRuntime request:\n" + f"{json.dumps(request, sort_keys=True)}"


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
        return (
            '{"checkable_oracle":{"kind":"text_equals|text_contains|sha256_equals","expected":str}|null,'
            '"verdict":"pass|fail|uncertain","located_errors":[{"where":str,"why":str}],'
            '"obligation_discharged":bool}'
        )
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
            "architecture or setup process. The artifact value must be the artifact content itself, not a "
            "filename, plan, quoted display string, escaped display string, or Markdown block. If the intent "
            "specifies exact text, emit that text verbatim; a \\n escape inside the JSON string means an "
            "actual newline after JSON decoding, not the two literal characters backslash and n."
        )
    if role == "verifier":
        return (
            "If checkable_oracle is not null, it must be exactly one of these JSON shapes: "
            '{"kind":"text_equals","expected":"..."}, {"kind":"text_contains","expected":"..."}, or '
            '{"kind":"sha256_equals","expected":"..."}. The kind field is required and must never be empty. '
            "The expected field is required and must be a string. Do not use alternate keys such as type, "
            "method, check, value, actual, target, or comparator. Use text_equals when the intent specifies "
            "exact content, deriving the expected value from the intent yourself. Use verdict pass only when "
            "the oracle is consistent with the artifact; if the artifact does not meet the expected value, "
            "keep the same oracle shape, set verdict fail, and add located_errors."
        )
    return "Return the requested SyberRuntime role payload."


def validate_role_payload(role: str, payload: dict[str, Any]) -> None:
    try:
        if role == "planner":
            PlannerOutput.from_payload(payload)
        elif role == "generator":
            GeneratorOutput.from_payload(payload)
        elif role == "verifier":
            VerifierOutput.from_payload(payload)
    except ModelContractError as exc:
        raise ProviderMCPError(str(exc), failure_class="schema_mismatch") from exc


def extract_json_payload(text: str) -> dict[str, Any]:
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
            raise ProviderMCPError(
                "Provider JSON payload must be an object",
                failure_class="payload_not_object",
            )
        return payload
    if last_error is None:
        raise ProviderMCPError("Provider did not return valid JSON", failure_class="malformed_json")
    raise ProviderMCPError(
        f"Provider did not return valid JSON: {last_error.msg}",
        failure_class="malformed_json",
    ) from last_error


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


def _max_contract_retries(arguments: dict[str, Any]) -> int:
    value = arguments.get("provider_contract_retries", DEFAULT_CONTRACT_RETRIES)
    try:
        retries = int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderMCPError("provider_contract_retries must be an integer", failure_class="invalid_config") from exc
    return max(0, retries)


def _provider_attempt_record(
    *,
    attempt_number: int,
    retry_context_injected: bool,
    role: str,
    provider: str,
    model_id: str,
    error: ProviderMCPError,
    raw_response: str,
) -> dict[str, Any]:
    encoded = raw_response.encode("utf-8", errors="replace")
    preview = raw_response[:RAW_RESPONSE_PREVIEW_CHARS]
    return {
        "attempt_number": attempt_number,
        "retry_context_injected": retry_context_injected,
        "role": role,
        "provider": provider,
        "model_id": model_id,
        "failure_class": error.failure_class,
        "message": str(error),
        "raw_response_sha256": hashlib.sha256(encoded).hexdigest(),
        "raw_response_size_bytes": len(encoded),
        "raw_response_preview": preview,
        "raw_response_truncated": len(raw_response) > RAW_RESPONSE_PREVIEW_CHARS,
    }


def _require_object(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ProviderMCPError(f"Tool argument {key} must be an object", failure_class="invalid_tool_arguments")
    return value
