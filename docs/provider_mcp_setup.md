# Provider MCP Setup

This is the practical provider layer for the v1 MCP requirement. It preserves
the roadmap boundary: SyberRuntime records operations and verification debt;
model inference remains external and replaceable.

## Roadmap Requirement

| Component | Required by |
|---|---|
| `syberruntime.provider_mcp` | v0.6 section 3.7 requires externalized inference; v1 Phase 2 requires the MCP adapter; v1 section 7 requires a full real-AI plan -> generate -> verify -> stabilize loop. |
| Google provider path | v1 section 6 warns models evolve; provider selection must be configuration, not kernel logic. |
| DeepSeek/OpenAI-compatible provider path | v1 Phase 2 requires model routing and cross-family verification; DeepSeek can serve as a different verifier family from Google. |
| Anthropic/OpenAI provider paths | v1 section 6 risk mitigation: supported providers can be swapped without changing operation storage or debt semantics. |
| Local fake-provider tests | v1 section 7 requires measured progress and recoverability; provider wiring must be testable without spending model calls. |
| JSON-only role prompting and extraction | v1 sections 4.1 and 4.2 require strict model contracts for generator and verifier outputs; v0.6 section 3.1 requires typed operations rather than prose-only coordination. |
| Planner operation-verb validation | v0.6 section 3.1 defines the open versioned verb set; v1 section 4.3 requires the planner to emit a typed operation graph. |

## Available Providers

| Provider argument | API key env | Endpoint style |
|---|---|---|
| `google` | `GOOGLE_API_KEY`, with `GEMINI_API_KEY` fallback | Gemini `generateContent` |
| `deepseek` | `DEEPSEEK_API_KEY` | OpenAI-compatible chat completions |
| `openai` | `OPENAI_API_KEY` | OpenAI chat completions |
| `anthropic` | `ANTHROPIC_API_KEY` | Anthropic Messages |
| `openai_compatible` | configured by `api_key_env` | custom OpenAI-compatible `base_url` |

The current recommended low-friction config is
`examples/mcp_adapter_config.example.json`: Gemini 2.5 Pro for planning,
Gemini 2.5 Flash for generation, and DeepSeek for verification. This satisfies
the generator/verifier family split while using the keys you already have.

## Environment

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:GOOGLE_API_KEY='...'
$env:DEEPSEEK_API_KEY='...'
```

OpenAI and Anthropic are optional until keys are available:

```powershell
$env:OPENAI_API_KEY='...'
$env:ANTHROPIC_API_KEY='...'
```

## Smoke Command

This command will spend real provider calls:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime ai-loop --config examples\mcp_adapter_config.example.json --intent "Provider-backed MCP smoke" --artifact-name provider-smoke.txt
```

Then run the release-gate check with the same provider config:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli acceptance-check --mcp-config examples\mcp_adapter_config.example.json
```

## Provider Notes

- DeepSeek's current docs list `deepseek-v4-flash` and `deepseek-v4-pro`; older
  names `deepseek-chat` and `deepseek-reasoner` are marked for deprecation on
  July 24, 2026.
- Google examples in the official Gemini API docs use `generateContent` and
  JSON response MIME type. The server requests JSON output, but SyberRuntime
  still validates the returned strict role payload.
- Provider responses are accepted only as JSON objects. The endpoint can recover
  a single balanced JSON object from harmless prose wrapping, but arrays and
  malformed objects remain contract failures.
- Planner steps must use SyberRuntime operation verbs: `Feature`, `Test`,
  `Refactor`, `Research`, `Verify`, `Compress`, `Simulate`, or `Stabilize`.
  Informal verbs such as "Design" or "Summarize" are rejected before they can
  enter the operation graph.
- Anthropic and OpenAI support is implemented but not required for the current
  Google/DeepSeek path.
