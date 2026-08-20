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

## Layout

- `syberruntime` (package root): the kernel — operation grammar, hash-chained
  log, projections, debt, deterministic verification, Merkle proofs, snapshots.
  The root `__init__` exports only this stable surface.
- `syberruntime.ai`: the orchestration layer — prompts and the
  plan -> generate -> verify -> stabilize loop driving model adapters.
- `syberruntime.providers`: the MCP stdio server split by responsibility
  (`server` framing, `clients` provider HTTP dialects, `payload` prompt/contract
  enforcement). `syberruntime.provider_mcp` remains as a compatibility shim for
  existing adapter configs.
- Evidence tooling (`harness`, `dogfood`, `acceptance`, `scale_analysis`,
  `reports`) is imported from its submodules directly.

The operation log takes an advisory lock on append and caches validated
entries per process, so appends and state rebuilds are O(new entries). A cold
instance (every CLI invocation) still revalidates the full hash chain.

## Run Tests

Use any Python 3.11+ interpreter (`unittest` is the test runner; there are no
third-party dependencies):

```powershell
python -m unittest discover -s tests
```

Run the full local verification gate (resolves Python from
`SYBERRUNTIME_PYTHON`, then `python` on PATH, then the `py` launcher):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Include mock live-harness wiring without provider calls:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -IncludeMockLiveHarness
```

## CLI

```powershell
$env:PYTHONPATH="$PWD\src"
python -m syberruntime.cli --help
```

(Or `pip install -e .` once and use the `syber` entry point without
`PYTHONPATH`.)

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
$env:PYTHONPATH="$PWD\src"
python -m syberruntime.cli acceptance-check
```

Write the real-config acceptance audit to a canonical JSON artifact:

```powershell
python -m syberruntime.cli acceptance-check --mcp-config examples\mcp_adapter_config.example.json --dogfood-report-dir docs\dogfood_reports --output docs\acceptance_reports\live_mcp_acceptance_003.json
```

Expected local status without `--mcp-config` is `ready_with_warnings`. Reports
001 and 002 under `docs/acceptance_reports` are historical provider-pass
artifacts created before canonical report IDs and evidence bindings; they do not
satisfy the current fail-closed gate. The next real-config run must produce
`live_mcp_acceptance_003.json`. The first real RQ0/RQ6 dogfood report is present under
`docs/dogfood_reports/rq0_rq6_run_001.json`.
The scripted Agentic Intent Harness baseline is audited separately and should
pass in the local tree.
Live-mode Agentic Intent Harness reports are also audited separately; absence is
a warning until a live smoke report is intentionally generated. The passing
three-task live scale campaign is audited as `live_scale3_campaign`. The hard
behavioral code campaign, held-out conformal coverage, and controlled RQ0/RQ6
baseline are also mandatory acceptance criteria.

### Evidence-integrity caveat for pre-2026-07-05 live reports

Live harness reports recorded before 2026-07-05 were generated with provider
prompts that restated the expected artifact content and oracle extracted from
the task intent (see `syberruntime.providers.payload` history). Those runs
therefore measured instruction-following under answer hints, not independent
generation plus verification. The hint injection has been removed; live smoke
and scale3 have been regenerated as `agentic-live-004` and
`agentic-live-scale3-004` under the current prompts.

Run the configured adapter smoke path:

```powershell
$env:PYTHONPATH="$PWD\src"
$env:SYBERRUNTIME_PYTHON=(Get-Command python).Source
python -m syberruntime.cli --root .syberruntime ai-loop --config examples\mock_mcp_adapter_config.example.json --intent "Exercise configured adapter path" --artifact-name configured.txt
```

For a real MCP/model endpoint, copy `examples/mcp_adapter_config.example.json`
and replace provider/model fields as needed. See `docs/provider_mcp_setup.md`.

Collect a dogfooding report from a runtime root:

```powershell
python -m syberruntime.cli --root .syberruntime dogfood-report --output docs\dogfood_reports\rq0_rq6_run_001.json --notes "First real n=1 dogfooding run under the pre-registered protocol."
```

When model/API access is constrained, record the envelope instead of
overclaiming:

```powershell
python -m syberruntime.cli --root .syberruntime dogfood-report --output docs\dogfood_reports\rq0_rq6_run_001.json --notes "First real n=1 dogfooding run under the pre-registered protocol." --model-constraint "Available API access did not include preferred frontier models." --preferred-unavailable-model "Claude Opus-class planner/verifier" --preferred-unavailable-model "GPT-5.5-class planner/generator"
```

Run Agentic Intent Harness v0 without spending provider calls:

```powershell
python -m syberruntime.cli --root .syberruntime-agent agent-harness run --run-id agentic-v0-001 --output docs\agentic_harness_reports\agentic-v0-001.json
```

Run Agentic Intent Harness live-mode wiring with the mock MCP server:

```powershell
$env:SYBERRUNTIME_PYTHON=(Get-Command python).Source
python -m syberruntime.cli --root .syberruntime-agent-live-mock agent-harness run --mode live --config examples\mock_mcp_adapter_config.example.json --run-id agentic-live-mock-001 --output docs\agentic_harness_reports\agentic-live-mock-001.json
```

Run the three-task scale campaign through mock MCP wiring:

```powershell
$env:SYBERRUNTIME_PYTHON=(Get-Command python).Source
python -m syberruntime.cli --root .syberruntime-agent-live-scale3-mock agent-harness run --mode live --task-set scale3 --config examples\mock_mcp_adapter_config.example.json --run-id agentic-live-scale3-mock-001 --output docs\agentic_harness_reports\agentic-live-scale3-mock-001.json
```

Analyze existing live `scale3` campaign reports without spending provider calls:

```powershell
python -m syberruntime.cli --root .syberruntime scale3-analysis --report docs\agentic_harness_reports\agentic-live-scale3-004.json --output docs\live_scale3_campaign_analysis.md
```

See `docs/live_mcp_adapter_config.md`, `docs/dogfooding_next_steps.md`, and
`docs/live_release_gate_traceability.md` for roadmap-cited release-gate details.
See `docs/agentic_intent_harness.md` for the agentic benchmark protocol.

## Demo

```powershell
$env:PYTHONPATH="$PWD\src"
python examples\phase4_demo.py
```
