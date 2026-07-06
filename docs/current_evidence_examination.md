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
   The report corpus contains four live scale3 campaign runs:
   `agentic-live-scale3-001` stabilized 2/3 tasks, `agentic-live-scale3-002`
   stabilized 2/3 tasks, `agentic-live-scale3-003` stabilized 3/3 hinted-era
   tasks (all three retired to `docs/agentic_harness_reports/archive/`,
   outside acceptance-audit discovery), and `agentic-live-scale3-004`
   regenerated the campaign after exact-answer prompt injection was removed. The regenerated run stabilized 3/3
   tasks with zero false discharge, zero residual debt, full structural rigor,
   and 9/9 mutants killed. This satisfies the dedicated `live_scale3_campaign`
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

6. The real MCP config acceptance pass is now recorded.
   `docs/acceptance_reports/live_mcp_acceptance_002.json` reports
   `overall_status: pass`, `failure_count: 0`, and `warning_count: 0` with the
   real MCP config, dogfood evidence, and regenerated un-hinted scale3 evidence
   supplied.

## Apex Inference

The release-gate evidence path has crossed from `ready_with_warnings` to a
recorded real-config `pass`. The system has demonstrated live provider scale3
recovery, acceptance-gated mutation measurement, a first n=1 dogfood report
under the pre-registered RQ0/RQ6 protocol, and a real MCP/model endpoint
acceptance pass with zero warnings.

## Recommended Sequence

1. Add provider failure analytics only if the next live or dogfood run produces
   repeated provider-boundary failures.
   If failures recur, promote the taxonomy into a standalone report before
   adding a Doctor Call recovery path.

2. Defer Doctor Call until the failure analytics show that retry plus contextual
   diagnostics are insufficient.
   This keeps the core small and lets the recovery design be driven by observed
   failure classes rather than speculative architecture.

## Decision

Preserve the current pass state and avoid adding a Doctor Call or larger
provider analytics subsystem until new repeated failures justify it. The next
highest-leverage work should be packaging the institutional evidence narrative:
what passed, under which model capability envelope, and what claims remain n=1
feasibility rather than population-level effects.
