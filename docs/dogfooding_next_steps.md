# Dogfooding Next Steps

The roadmap's next hard acceptance item is not another local feature. It is the
evidence run: use SyberRuntime to build SyberRuntime work and report RQ0/RQ6
results under the pre-registered protocol.

## Roadmap Requirement

| Component | Required by |
|---|---|
| `docs/rq0_rq6_preregistration.md` | v1 Phase 3 requires pre-registered RQ0 and RQ6 comparisons before reporting results. |
| `dogfood.DogfoodReport` | v1 Phase 3 requires reportable measurements; v1 section 7 requires pre-registered RQ0/RQ6 results from dogfooding. |
| `dogfood-report` CLI command | v1 section 7 requires the evidence to be inspectable and reproducible, not only narrated. |
| `acceptance-check --dogfood-report-dir` | v1 section 7 makes dogfooding evidence part of the done gate. |
| `docs/dogfood_reports/*.json` | v0.6 section 6 defines Tier 1 autobiographical evidence as n=1 feasibility only; v1 section 7 requires those results for the institutional ask. |
| `model_capability_envelope` | v1 section 6 identifies model/API churn as a risk; v1 Phase 3 and section 7 require measured claims to record the model capability envelope under which evidence was produced. |

## Minimum Evidence Run

1. Choose one small, real SyberRuntime improvement.
2. Build it through the operation/debt grammar in a runtime root.
3. Record deterministic checks before judging the outcome.
4. Run a mutation campaign against the stabilized artifact.
5. Capture metrics and artifact digests in a dogfood report.
6. Repeat or compare against a snapshot/commit-only baseline when practical.
7. Report failures and survived mutants without retroactive metric changes.

## Commands

Create a report from the current runtime root:

```powershell
$env:PYTHONPATH='D:\syberlabs\syber_runtime\src'
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime dogfood-report --output docs\dogfood_reports\rq0_rq6_run_001.json --notes "First real n=1 dogfooding run under the pre-registered protocol."
```

When provider access is constrained, record that explicitly:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli --root .syberruntime dogfood-report --output docs\dogfood_reports\rq0_rq6_run_001.json --notes "First real n=1 dogfooding run under the pre-registered protocol." --model-constraint "Available API access did not include preferred frontier planner/generator/verifier models." --preferred-unavailable-model "Claude Opus-class planner/verifier" --preferred-unavailable-model "GPT-5.5-class planner/generator" --model-envelope-notes "Interpret this as a lower-bound operational demonstration, not a ceiling."
```

Audit with dogfooding evidence:

```powershell
& 'C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m syberruntime.cli acceptance-check --dogfood-report-dir docs\dogfood_reports
```

## Claim Boundary

The first report supports existence and feasibility claims only. It does not
support population-level claims, and acceptance should stay at
`ready_with_warnings` until both real MCP execution and real dogfooding evidence
are present.

If the run uses constrained provider access, its claim should be framed as a
lower-bound demonstration of SyberRuntime's control architecture. Stronger
model claims should be deferred until the same protocol is rerun with those
model assignments.
