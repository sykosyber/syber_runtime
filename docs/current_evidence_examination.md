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

2. The remaining release warnings are not hidden engineering failures.
   Local acceptance remains `ready_with_warnings` because no real MCP config is
   supplied to the local acceptance command and no `docs/dogfood_reports/`
   evidence directory exists. These are external evidence gates, not uncovered
   local test failures.

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

The next acceptance-bearing work is a real pre-registered dogfood run, not a new
runtime subsystem. The system has already demonstrated live provider scale3
recovery and acceptance-gated mutation measurement. The missing proof is that
SyberRuntime can be used on its own continued development and report RQ0/RQ6
results under the pre-registered protocol.

## Recommended Sequence

1. Run the first real dogfood evidence pass.
   Use one small, real SyberRuntime improvement as the subject, record the
   model capability envelope, generate `docs/dogfood_reports/rq0_rq6_run_001.json`,
   and rerun `acceptance-check --dogfood-report-dir docs/dogfood_reports`.

2. Then perform a live config acceptance pass.
   Supply the real MCP config to `acceptance-check --mcp-config` so the
   `live_mcp_real_ai_endpoint` warning can move from warning to pass.

3. Add provider failure analytics only if the next live or dogfood run produces
   repeated provider-boundary failures.
   If failures recur, promote the taxonomy into a standalone report before
   adding a Doctor Call recovery path.

4. Defer Doctor Call until the failure analytics show that retry plus contextual
   diagnostics are insufficient.
   This keeps the core small and lets the recovery design be driven by observed
   failure classes rather than speculative architecture.

## Decision

Proceed with dogfooding next. It is directly required by v0.6 section 6, v1
Phase 3, and v1 section 7; it consumes the newly added evidence schema; and it
is the shortest path from `ready_with_warnings` toward a real release-readiness
pass.
