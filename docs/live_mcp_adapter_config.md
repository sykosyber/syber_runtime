# Live MCP Adapter Configuration

This document defines the current v1 live-adapter handoff. It is intentionally
small: the runtime owns operation logging, contracts, debt, and stabilization;
the model endpoint remains external.

## Roadmap Requirement

| Component | Required by |
|---|---|
| `MCPStdioToolAdapter` endpoint boundary | v0.6 section 3.7 says inference remains external and MCP is the natural first adapter; v1 Phase 2 requires the MCP adapter. |
| `adapter_config.load_adapter_bundle` | v1 Phase 2 requires model routing for planning, implementation, and verification under fixed policy; v1 section 7 requires the full loop with real AI via MCP. |
| `ai-loop` CLI command | v1 Phase 2 requires the plan -> generate -> verify -> stabilize loop to come alive; v1 section 7 requires it to be runnable with real AI via MCP. |
| `acceptance-check --mcp-config` | v1 section 7 defines done as passing the real-AI loop, not merely having adapter code. |
| `examples/mcp_adapter_config.example.json` | v1 section 6 warns MCP/models evolve; the adapter boundary mitigates this by making endpoint replacement local to configuration. |
| `examples/mock_mcp_server.py` | v1 section 6 risk mitigation: a protocol-shaped local fixture keeps the configured path testable without claiming real AI evidence. |
| `syberruntime.provider_mcp` | v1 Phase 2 and v1 section 7 require the MCP loop to reach real model providers while preserving the external inference boundary. |
| Strict role-payload validation | v0.6 section 3.1 defines typed operation verbs and no unverified generation; v1 sections 4.1-4.3 require strict planner/generator/verifier contracts. |
| Contextual retry and failure diagnostics | v0.6 section 3.8 requires inspectable provenance; v1 Phase 2 requires a recoverable MCP boundary; v1 section 7 requires measured evidence for failures as well as successes. |

## Config Shape

The config is a JSON object with `planner`, `generator`, and `verifier`
sections. Each section contains:

- `model`: `model_id`, `family`, `roles`, and optional `strength`.
- `transport`: `mcp_stdio` for the production endpoint path.
- `command`: a non-empty string array that launches the MCP stdio server.
- `tool_name`: the MCP tool invoked with `tools/call`.
- `arguments`: optional static JSON object merged into each tool call.
- `timeout_seconds`: optional wall-clock limit for the adapter call.

Command tokens are expanded with the process environment before execution. On
Windows, `%SYBERRUNTIME_PYTHON%` can point at the exact Python executable used
by the packaged provider MCP server or the local fixture.

Example:

```json
{
  "planner": {
    "transport": "mcp_stdio",
    "model": {
      "model_id": "real-planner",
      "family": "real-planner-family",
      "roles": ["planner"],
      "strength": "strong"
    },
    "command": ["%SYBERRUNTIME_PYTHON%", "-m", "syberruntime.provider_mcp"],
    "tool_name": "syberruntime_model_call",
    "arguments": {
      "provider": "google",
      "api_key_env": "GOOGLE_API_KEY",
      "max_tokens": 2048,
      "temperature": 0
    },
    "timeout_seconds": 60
  }
}
```

The generator and verifier must use different `family` values. The runtime
enforces that split because v0.6 section 3.1 and the verification playbook both
ground verification value in generator/verifier error decorrelation.

## MCP Endpoint Contract

The runtime speaks the MCP stdio lifecycle:

1. Send `initialize`.
2. Send `notifications/initialized`.
3. Send `tools/call` with the configured `tool_name`.

The tool receives these arguments:

```json
{
  "model": {},
  "request": {},
  "provider": "google"
}
```

The tool result must return the strict SyberRuntime role payload as
`structuredContent`, or as JSON in a text content item. Required payloads:

- planner: `steps` and `rationale`; each step `verb` must be one of
  `Feature`, `Test`, `Refactor`, `Research`, `Verify`, `Compress`,
  `Simulate`, or `Stabilize`
- generator: `assumptions`, `plan`, `artifact`, and `self_identified_risks`
- verifier: `verdict`, `located_errors`, optional `checkable_oracle`; non-null
  oracles must use `kind` equal to `text_equals`, `text_contains`, or
  `sha256_equals`, and must include string `expected`

The runtime validates those payloads before recording operations.

The packaged provider MCP endpoint performs one contextual retry by default
when a provider returns malformed JSON, a non-object payload, or a role payload
that fails the strict planner/generator/verifier schema. The retry prompt
includes structured error context and a bounded raw-response preview, but it
does not repair the payload locally. If the retry is exhausted, the MCP result
uses `isError=true` and returns structured diagnostics under
`structuredContent.error` with a `failure_class` and attempt records.

## Smoke Commands

Set `PYTHONPATH` first:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

Run the configured loop:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime ai-loop --config examples\mock_mcp_adapter_config.example.json --intent "Exercise configured adapter path" --artifact-name configured.txt
```

Run acceptance with the same adapter path:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli acceptance-check --mcp-config examples\mock_mcp_adapter_config.example.json
```

The mock server only proves the MCP adapter path. For a real provider smoke
test, use `examples/mcp_adapter_config.example.json`; that will spend real
provider calls. Reaching v1 section 7 `pass` with research meaning still
requires a real provider run and dogfooding reports.
