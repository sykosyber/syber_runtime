# Current Evidence Examination

Date: 2026-06-25

## Roadmap Requirement

| Subject | Required by |
|---|---|
| Live MCP/generative loop evidence | v1 Phase 2; v1 section 7 |
| Measured scale evidence and mutation outcomes | v0.6 section 3.5; v0.6 section 3.8; v1 Phase 3; Verification Playbook Part C-F |
| Pre-registered dogfooding results | v0.6 section 6; v1 Phase 3; v1 section 7 |
| Inspectable release evidence | v0.6 section 3.8; v1 Phase 4; v1 section 7 |
| Model-access claim boundary | v1 section 6; v1 Phase 3; v1 section 7 |

## Findings

1. The live scale3 path is no longer merely anecdotal.
   The report corpus contains three live scale3 campaign runs:
   `agentic-live-scale3-001` stabilized 2/3 tasks, `agentic-live-scale3-002`
   stabilized 2/3 tasks, and `agentic-live-scale3-003` stabilized 3/3 tasks
   with zero false discharge, zero residual debt, full structural rigor, and
   9/9 mutants killed. This satisfies the dedicated `live_scale3_campaign`
   acceptance gate.

2. The first dogfood report is now present.
   `docs/dogfood_reports/rq0_rq6_run_001.json` records the acceptance hardening
   dogfood pass with three artifact digests, zero residual debt, zero false
   discharge, full structural rigor, and production discharge efficiency 1.0.

3. The strongest current claim is bounded, not maximal.
   The model capability envelope records that constrained provider/model access
   makes current live evidence a lower-bound operational demonstration. This is
   the correct claim shape until the same protocols are rerun with stronger
   planner, generator, and verifier assignments.

4. Scale3 report promotion has already crossed the useful threshold.
   The campaign has a generated analysis report, a dedicated acceptance
   criterion, README commands, and traceability documentation. Further promotion
   would be mostly presentational until new evidence is produced.

5. Provider failure analytics and Doctor Call are useful but should remain
   secondary until another repeated failure pattern appears.
   Provider failures were valuable during hardening, but the latest scale3 run
   passed. A Doctor Call prototype would add a new control component before the
   next acceptance blocker has been retired.

## Apex Inference

The next acceptance-bearing work is the live config acceptance pass, not a new
runtime subsystem. The system has demonstrated live provider scale3 recovery,
acceptance-gated mutation measurement, and a first n=1 dogfood report under the
pre-registered RQ0/RQ6 protocol. The remaining release warning is the absence of
a supplied real MCP/model endpoint config during local acceptance.

## Recommended Sequence

1. Perform a live config acceptance pass.
   Supply the real MCP config to `acceptance-check --mcp-config` so the
   `live_mcp_real_ai_endpoint` warning can move from warning to pass.

2. Add provider failure analytics only if the next live or dogfood run produces
   repeated provider-boundary failures.
   If failures recur, promote the taxonomy into a standalone report before
   adding a Doctor Call recovery path.

3. Defer Doctor Call until the failure analytics show that retry plus contextual
   diagnostics are insufficient.
   This keeps the core small and lets the recovery design be driven by observed
   failure classes rather than speculative architecture.

## Decision

Proceed with live config acceptance next. Dogfooding has moved from pending to
first-pass evidence; the remaining release-readiness warning is the real
MCP/model endpoint acceptance run required by v1 Phase 2 and v1 section 7.
