# SyberRuntime

SyberRuntime is an operation-primary, local-first kernel for generative
engineering environments. It treats operations as the source of truth, artifacts
as projections, and verification debt as a bounded accounting signal.

The implementation follows `SyberRuntime_v1_Implementation_Roadmap.md`:

- Phase 0: event-sourced walking skeleton.
- Phase 1: grammar, verification debt, deterministic verification.
- Phase 2: model-adapter contracts and plan -> generate -> verify -> stabilize loop.
- Phase 3: mutation-measured discharge efficiency and runtime metrics.
- Phase 4: hardening, provenance export, inspection, snapshots, deletion-rights path.
- Phase 5: release-readiness audit derived from v1 section 7.

The current release-gate work adds the concrete handoff for the two remaining
v1 section 7 items: configured MCP/model execution and RQ0/RQ6 dogfooding
reports.

## Run Tests

On this Windows workspace, use the bundled Python executable if `python` is not
associated:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Run the full local verification gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Include mock live-harness wiring without provider calls:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -IncludeMockLiveHarness
```

## CLI

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --help
```

Important commands:

- `create-thread`
- `feature`
- `test`
- `stabilize`
- `ai-loop`
- `mutation-campaign`
- `inspect-artifact`
- `metrics`
- `merkle-root`
- `inclusion-proof`
- `consistency-proof`
- `snapshot`
- `export-prov`
- `export-ro-crate`
- `shred-blob`
- `dogfood-report`
- `agent-harness`
- `scale3-analysis`
- `acceptance-check`

## Acceptance Boundary

Run:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli acceptance-check
```

Expected local status is `ready_with_warnings`. The warnings are intentional:
live MCP/model execution and real RQ0/RQ6 dogfooding results require external
configuration and study execution.
The scripted Agentic Intent Harness baseline is audited separately and should
pass in the local tree.
Live-mode Agentic Intent Harness reports are also audited separately; absence is
a warning until a live smoke report is intentionally generated.

Run the configured adapter smoke path:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime ai-loop --config examples\mock_mcp_adapter_config.example.json --intent "Exercise configured adapter path" --artifact-name configured.txt
```

For a real MCP/model endpoint, copy `examples/mcp_adapter_config.example.json`
and replace provider/model fields as needed. See `docs/provider_mcp_setup.md`.

Collect a dogfooding report from a runtime root:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime dogfood-report --output docs\dogfood_reports\rq0_rq6_run_001.json --notes "First real n=1 dogfooding run under the pre-registered protocol."
```

Run Agentic Intent Harness v0 without spending provider calls:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent agent-harness run --run-id agentic-v0-001 --output docs\agentic_harness_reports\agentic-v0-001.json
```

Run Agentic Intent Harness live-mode wiring with the mock MCP server:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent-live-mock agent-harness run --mode live --config examples\mock_mcp_adapter_config.example.json --run-id agentic-live-mock-001 --output docs\agentic_harness_reports\agentic-live-mock-001.json
```

Run the three-task scale campaign through mock MCP wiring:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
$env:SYBERRUNTIME_PYTHON='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime-agent-live-scale3-mock agent-harness run --mode live --task-set scale3 --config examples\mock_mcp_adapter_config.example.json --run-id agentic-live-scale3-mock-001 --output docs\agentic_harness_reports\agentic-live-scale3-mock-001.json
```

Analyze existing live `scale3` campaign reports without spending provider calls:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime scale3-analysis --report docs\agentic_harness_reports\agentic-live-scale3-001.json --report docs\agentic_harness_reports\agentic-live-scale3-002.json --report docs\agentic_harness_reports\agentic-live-scale3-003.json --output docs\live_scale3_campaign_analysis.md
```

See `docs/live_mcp_adapter_config.md`, `docs/dogfooding_next_steps.md`, and
`docs/live_release_gate_traceability.md` for roadmap-cited release-gate details.
See `docs/agentic_intent_harness.md` for the agentic benchmark protocol.

## Demo

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' examples\phase4_demo.py
```
