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
