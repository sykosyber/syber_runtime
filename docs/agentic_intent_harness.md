# Agentic Intent Harness v0

Human Intent was the original protected boundary: the runtime exists to keep
generative expansion accountable to a human purpose. For benchmarking and
dogfooding, that boundary should generalize to an accountable intent source.
That source can be human, agentic, or mixed, as long as the operation graph
records who or what originated the intent and how acceptance was judged.

## Roadmap Requirement

| Component | Required by | Current status |
|---|---|
| Intent source metadata | v0.6 section 3.8 requires inspectable provenance; v1 section 7 requires a fresh reader to trace any artifact's making in minutes. | Implemented as `IntentMetadata`, recorded in operation params and provenance decisions. |
| Agentic CLI harness | v1 Phase 3 requires measured RQ0/RQ6 results; v1 section 6 recommends dogfooding the kernel; v1 section 7 requires pre-registered dogfooding evidence. | Implemented as `syber ... agent-harness run`. |
| Harness protocol file | v1 Phase 3 requires pre-registered RQ0/RQ6 comparisons before reporting outcomes. | This file is the v0 protocol and must be amended before changing metrics. |
| Scripted task suite | v0.6 section 6 Tier 1 supports n=1 feasibility evidence; v1 Phase 3 requires measuring the runtime instead of relying on intuition. | Implemented with one expected pass and one expected blocked verification case. |
| Live provider smoke task | v1 Phase 2 requires real AI via MCP; v1 Phase 3 requires measured outcomes; v0.6 section 3.1 requires typed Feature -> Verify grammar. | Implemented as one exact local text artifact plus deterministic `text_equals` verification. |
| Live `scale3` provider campaign | v1 Phase 3 requires measured scaling evidence; v0.6 section 3.6 frames requisite variety as matching generative variety with verification capacity; v0.6 section 3.8 requires inspectable provenance. | Implemented as three exact local text artifacts, each independently planned, generated, verified, stabilized, and mutation-measured in one report. |
| Scale3 campaign analysis report | v1 Phase 3 requires measured outcomes; v0.6 section 3.8 requires inspectable provenance; v1 section 7 requires a fresh reader to trace what happened in minutes. | Implemented as `scale3-analysis`, producing `docs/live_scale3_campaign_analysis.md` from existing live reports without spending provider calls. |
| Failed-run evidence preservation | v0.6 section 3.8 requires inspectable provenance; v1 section 7 requires a fresh reader to trace an artifact's making in minutes. | Failed live runs preserve `thread_id` and `artifact_digest` when those exist, rather than collapsing partial progress into an opaque failure. |
| Provider failure taxonomy in reports | v0.6 section 3.8 requires inspectable provenance; v1 Phase 3 requires measured outcomes; v1 section 7 requires failures to be traceable rather than anecdotal. | Live task results include `failure_class` and provider diagnostics when the MCP boundary exposes them. |
| Human acceptance checkpoint | v0.6 section 1 frames human understanding as the protected resource; agentic intent can originate work, but institutional claims still need accountable review. | Deferred from v0 automation; report review remains human. |

## Inference

Human and agentic intent should not be treated as metaphysically identical.
They should be operationally interchangeable at the runtime boundary.

That means the runtime does not need to privilege "human" as the only valid
initiator. It needs to distinguish:

- `principal`: the accountable source of the goal or benchmark.
- `actor`: the entity performing an operation.
- `intent_source`: human, agent, script, benchmark, or mixed.
- `acceptance_authority`: human, deterministic oracle, tribunal, or benchmark.

This preserves the original ethics of the system while making it testable.

## Harness Shape

Agentic Intent Harness v0 runs SyberRuntime through the CLI:

1. Select scripted tasks from this protocol.
2. Create a thread with `intent_source=agent`.
3. Record a Feature operation with an assumption ledger.
4. Run deterministic tests and mutation campaigns.
5. Attempt stabilization.
6. Inspect the artifact provenance/debt surface.
7. Emit a harness report with metrics, failures, and survived mutants.

The benchmark then becomes: how much validated artifact value does an
autonomous or semi-autonomous intent source produce under measured debt,
verification, and stabilization constraints?

## CLI

Scripted baseline, no provider calls:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent agent-harness run --run-id agentic-v0-001
```

By default, the report is written to:

```text
docs/agentic_harness_reports/<run-id>.json
```

The current baseline report is:

```text
docs/agentic_harness_reports/agentic-v0-001.json
```

Override the output path when running in temporary or CI contexts:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent agent-harness run --run-id agentic-v0-001 --output docs\agentic_harness_reports\agentic-v0-001.json
```

Live provider smoke, spends real provider calls. The default live task is exact
on purpose: create `agent-live-smoke.txt` with content
`agent-live-smoke-token\n`, then verify it with a deterministic `text_equals`
oracle.

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent-live agent-harness run --mode live --config examples\mcp_adapter_config.example.json --run-id agentic-live-smoke-001 --output docs\agentic_harness_reports\agentic-live-smoke-001.json
```

Use the mock MCP config when testing live-mode wiring without provider calls:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent-live-mock agent-harness run --mode live --config examples\mock_mcp_adapter_config.example.json --run-id agentic-live-mock-001 --output docs\agentic_harness_reports\agentic-live-mock-001.json
```

Run the three-task scale campaign with mock MCP wiring:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent-live-scale3-mock agent-harness run --mode live --task-set scale3 --config examples\mock_mcp_adapter_config.example.json --run-id agentic-live-scale3-mock-001 --output docs\agentic_harness_reports\agentic-live-scale3-mock-001.json
```

Using `--task-set scale3` with `examples/mcp_adapter_config.example.json`
spends real provider calls.

Analyze existing live `scale3` reports without making provider calls:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime scale3-analysis --report docs\agentic_harness_reports\agentic-live-scale3-001.json --report docs\agentic_harness_reports\agentic-live-scale3-002.json --report docs\agentic_harness_reports\agentic-live-scale3-003.json --output docs\live_scale3_campaign_analysis.md
```

## V0 Acceptance

The scripted baseline harness report should show:

- `attempted_tasks = 2`
- `stabilized_tasks = 1`
- `blocked_or_failed_tasks = 1`
- one expected blocked task with a stabilization failure caused by open floor-rigor debt
- operation metrics with nonzero action cost

Live-mode reports are additional evidence. They may pass or fail depending on
provider availability and model output quality; failures are valid evidence and
should not replace the scripted baseline. Failed live tasks should include a
`failure_class`; provider-boundary failures may also include bounded raw-attempt
diagnostics under `failure_details`.
`acceptance-check` reports this as `agentic_intent_harness_live_smoke`.

## Risk Boundary

Agentic intent can expose weaknesses faster than manual use, but it also risks
optimizing for the metric surface. The harness must therefore record failed
runs, rejected stabilizations, verifier uncertainty, and survived mutants as
first-class evidence rather than filtering for successful demos.

## Deferred

- Live provider-driven task generation.
- Larger and variable live provider campaigns.
- Automatic dogfood report promotion.
- Human review workflow for accepting or rejecting a harness report.
