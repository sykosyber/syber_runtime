# RQ0 / RQ6 Pre-Registration

This protocol is created before running dogfooding measurements so the Phase 3
results are framed as evidence rather than hindsight.

## Scope

The first Phase 3 study is autobiographical `n=1` evidence only. It can support
existence and feasibility claims; it cannot support population-level claims.

## RQ0: Operation As Primitive

Hypothesis: an operation-primary model improves re-comprehension and structural
rigor versus a snapshot/commit-only baseline at acceptable capture cost.

Primary measures:

- Action cost: number of operations required to produce validated artifacts.
- Generative return: validated artifacts divided by action cost.
- Provenance completeness: operations with actor and timestamp provenance.
- Re-comprehension proxy: time to trace a stabilized artifact to its Feature,
  Test/Verify, assumptions, and Stabilize operation.

## RQ6: Verification Debt Grammar

Hypothesis: enforcing Feature -> Test/Verify obligation lowers downstream
defects and false discharge versus unbounded generation without proportional
throughput collapse.

Primary measures:

- Residual verification debt.
- False-discharge rate from mutation campaigns.
- Measured discharge efficiency by rigor profile.
- Stabilization blocks caused by open floor-rigor obligations.

## Protocol

1. Build a small SyberRuntime component twice: once with the operation/debt
   grammar enabled, once with ordinary snapshot notes only.
2. Before judging outcomes, record the intended deterministic checks and mutation
   operators.
3. Run mutation campaigns against stabilized artifacts and record discharge
   efficiency.
4. Report results as feasibility evidence, including failures and survived
   mutants.

## Exclusion Rules

- Do not remove survived mutants from the campaign unless they are exact
  duplicates of the original artifact.
- Do not claim LLM-only Verify operations fully discharge debt.
- Do not change metrics after seeing results without recording an amended
  protocol section.

## Run 002 Addendum (preregistered 2026-07-05, before measurement)

Run 002 is the first dogfood run whose deterministic oracle executes behavior
rather than comparing strings. It is registered here before the measurement
is taken.

### Task

Record the newly implemented `python_tests` execution oracle
(`src/syberruntime/verification.py`) as a SyberRuntime Feature artifact and
discharge its verification obligation by executing a real unittest suite
against that artifact in a subprocess. The run is reflexive by design: the
runtime verifies its own new verifier.

### Design

- Runtime root: `.syberruntime-dogfood-python-tests-002`, rigor profile
  `production` (floor-required obligations gate Stabilize).
- Generator: the Claude Fable 5 coding agent (actor `claude-fable-5`,
  `intent_source: agent`); no provider API in the loop. This bounds the claim:
  the run measures the grammar and oracle, not model capability.
- Feature artifact: the exact source of `src/syberruntime/verification.py`
  at implementation commit time.
- Deterministic check (declared before judging outcomes): `python_tests`
  whose `test_source` imports the artifact file (`artifact_under_test.py`)
  directly and asserts (a) `python_tests` is a supported check kind and the
  model-oracle boundary excludes it, (b) a correct artifact passes a nested
  `python_tests` execution, (c) a behaviorally wrong artifact fails it, and
  (d) the legacy text checks still work. `pythonpath` includes the repo `src`
  so the artifact module can resolve kernel imports.
- Mutation operators (declared before judging outcomes): the existing
  harness set — `append_noise`, `replace_first_token`, `drop_first_line`
  (`remove_expected_text` is inapplicable: the check has no `expected`).
  Expected kill mechanism is real test execution failing, not string drift.

### Measures

RQ0: action cost, generative return, provenance completeness from runtime
metrics; re-comprehension via `inspect-artifact` walkback recorded in the
report notes. RQ6: residual debt, false-discharge rate, discharge efficiency
by profile, and whether Stabilize was blocked before discharge.

### Declared deviations from the base protocol

- Single-arm run: the snapshot-only baseline arm (Protocol step 1) is
  deferred; run 002 supports feasibility claims for the execution-oracle
  discharge path only.
- Survived mutants, if any, will be reported, not excluded.

## Controlled Baseline Run 001 Addendum

This addendum closes the deferred baseline requirement in **v1 Phase 3
acceptance** and is recorded before generating the controlled report under
docs/empirical_reports.

### Fixed Task And Arms

The task is a Python parse_positive_int(value) component. The correct
implementation accepts positive decimal strings and rejects zero, negative
strings, non-decimal strings, and non-string inputs.

- RQ0 operation-primary arm: create the correct component through
  Thread -> Feature -> deterministic python_tests -> Stabilize -> mutation
  campaign, then inspect its provenance/debt/assumption trace.
- RQ0 snapshot baseline arm: store the same correct source plus one ordinary
  JSON notes snapshot, without operation grammar.
- RQ6 grammar-enforced arm: submit a known-bad return int(value)
  implementation; the fixed test suite must fail and Stabilize must be blocked.
- RQ6 unbounded arm: mark the same known-bad source accepted before verification,
  then run the same test suite downstream and record whether the defect appears.

### Fixed Measures And Gate

Record action cost, provenance completeness, and re-comprehension wall time for
both RQ0 arms. Wall time is descriptive and is not a pass threshold. Acceptance
requires both arms to complete. For RQ6, acceptance requires the grammar to
reject and block the known-bad artifact while the unbounded arm demonstrates
that pre-verification acceptance permits the defect downstream.

The report remains autobiographical n=1 feasibility evidence. It cannot support
a population effect or a general throughput claim.
