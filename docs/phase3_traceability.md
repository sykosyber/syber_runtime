# Phase 3 Traceability

Phase 3 is the measurement phase: it turns verification from a declared property
into an observed quantity.

| Component | Roadmap requirement |
|---|---|
| Mutation testing harness | v1 Phase 3 requires synthetic fault injection to measure kill rate as measured `discharge_efficiency`; the verification playbook Part C-F makes mutation testing the highest-leverage measurement. |
| Mutation campaign Verify operation | v0.6 section 3.6 says regulators are inside the accounting boundary; measurement of verification is therefore logged as an operation. |
| False-discharge rate | v0.6 section 3.5 names false discharge as a first-class failure; v1 Phase 3 requires false-discharge instrumentation. |
| Runtime metrics | v0.6 section 6 defines action cost, generative return, structural rigor, debt level, downstream defects, and re-comprehension; v1 Phase 3 requires metrics instrumentation. |
| Pre-registration document | v1 section 5 requires pre-registered RQ0/RQ6 comparisons and honest `n=1` framing; v1 Phase 3 acceptance requires reportable results framed as feasibility evidence. |

## Acceptance Boundary

The kernel now reports measured verifier kill/survival behavior for deterministic
checks and computes first-pass runtime metrics from the operation log. Full
dogfooding results still require running the pre-registered study on a real
SyberRuntime-built artifact.
