# Phase 5 Traceability

The roadmap defines Phases 0 through 4. This "Phase 5" is therefore not a new
research phase; it is a v1 release-readiness gate derived from the roadmap's
definition of done.

| Component | Roadmap requirement |
|---|---|
| Acceptance audit | v1 section 7 defines v1 done as first-validation gate, plan -> generate -> verify -> stabilize loop, mutation-measured discharge efficiency, pre-registered RQ0/RQ6 dogfooding results, and inspectable provenance/debt/assumption surface. |
| `acceptance-check` CLI | v1 section 7 requires the artifact to be legible to others; a machine-readable audit makes release status reproducible. |
| Explicit warning states | v1 section 7 requires real AI via MCP and dogfooding results. Local no-config verification warns honestly; historical pre-binding real-config reports cannot satisfy the hardened gate. |
| Agentic harness report audit | v0.6 section 3.8 and v1 section 7 require inspectable provenance; v1 Phase 3 requires measured progress rather than subjective impressions. The harness baseline is audited separately from dogfooding so it can support accountable-intent benchmarking without overclaiming RQ0/RQ6 results. |
| Live harness report visibility | v1 Phase 2 requires real AI via MCP; v1 Phase 3 requires measurement. Live-mode harness reports are audited separately so provider results and failures are visible without replacing deterministic baseline evidence. |
| Live scale3 campaign gate | v0.6 section 3.8 requires inspectable provenance; v1 Phase 2 requires real AI via MCP; v1 Phase 3 requires measured scaling evidence; v1 section 7 requires reproducible release evidence. The gate requires a passing live `scale3` report with all tasks stabilized, zero false discharge, zero residual debt, full structural rigor, and complete mutation kill coverage. |
| `scripts/verify.ps1` | v1 section 7 requires reproducible release status. The script runs tests, compile checks, acceptance, and optionally mock live-harness wiring. |
| README | v1 Phase 4 asks for a runnable portfolio demonstrator and written walkthrough; the README gives the package entry point and current acceptance boundary. |

## Current Audit Status

The expected no-config local status is `ready_with_warnings`, because local-only
verification does not assume external provider credentials. The historical
provider-backed 002 report recorded a pass before canonical evidence binding;
the next current-schema live acceptance must be recorded as 003.

The local acceptance audit also expects a scripted Agentic Intent Harness
baseline under `docs/agentic_harness_reports/`. Live-mode harness reports are
additional evidence and may record provider failures without replacing the
scripted baseline. A passing live `scale3` campaign is now audited separately
as `live_scale3_campaign`. Harness reports are engineering evidence for the
accountable-intent harness, not a substitute for the live provider release
gate. The first RQ0/RQ6 dogfood report is now present under
`docs/dogfood_reports/rq0_rq6_run_001.json`.
