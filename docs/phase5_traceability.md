# Phase 5 Traceability

The roadmap defines Phases 0 through 4. This "Phase 5" is therefore not a new
research phase; it is a v1 release-readiness gate derived from the roadmap's
definition of done.

| Component | Roadmap requirement |
|---|---|
| Acceptance audit | v1 section 7 defines v1 done as first-validation gate, plan -> generate -> verify -> stabilize loop, mutation-measured discharge efficiency, pre-registered RQ0/RQ6 dogfooding results, and inspectable provenance/debt/assumption surface. |
| `acceptance-check` CLI | v1 section 7 requires the artifact to be legible to others; a machine-readable audit makes release status reproducible. |
| Explicit warning states | v1 section 7 requires real AI via MCP and dogfooding results. The current kernel has adapter support and a pre-registration protocol, but live MCP/model configuration and real dogfooding results remain outside local-only verification. |
| Agentic harness report audit | v0.6 section 3.8 and v1 section 7 require inspectable provenance; v1 Phase 3 requires measured progress rather than subjective impressions. The harness baseline is audited separately from dogfooding so it can support accountable-intent benchmarking without overclaiming RQ0/RQ6 results. |
| Live harness report visibility | v1 Phase 2 requires real AI via MCP; v1 Phase 3 requires measurement. Live-mode harness reports are audited separately so provider results and failures are visible without replacing deterministic baseline evidence. |
| `scripts/verify.ps1` | v1 section 7 requires reproducible release status. The script runs tests, compile checks, acceptance, and optionally mock live-harness wiring. |
| README | v1 Phase 4 asks for a runnable portfolio demonstrator and written walkthrough; the README gives the package entry point and current acceptance boundary. |

## Current Expected Audit Status

The expected local status is `ready_with_warnings`, not `pass`, until:

1. A live MCP/model endpoint is configured and exercised.
2. RQ0/RQ6 dogfooding results are collected under the pre-registered protocol.

This keeps the release gate honest while preserving momentum.

The local acceptance audit also expects a scripted Agentic Intent Harness
baseline under `docs/agentic_harness_reports/`. Live-mode harness reports are
additional evidence and may record provider failures without replacing the
scripted baseline. Harness reports are engineering evidence for the
accountable-intent harness, not a substitute for live provider or RQ0/RQ6
dogfooding evidence.
