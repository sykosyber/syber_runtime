# Phase 0 Traceability

This file keeps the first implementation slice tied to the roadmap. The
authoritative roadmap is `SyberRuntime_Research_Program_v0.6.md`; the concrete
v1 build order comes from `SyberRuntime_v1_Implementation_Roadmap.md`.

## Implemented in Phase 0

| Component | Roadmap requirement |
|---|---|
| Python package scaffold | v1 section 1 recommends Python for the single-user local-first kernel; v1 section 8 says to stand up the repo first. |
| Operation model | v0.6 section 3.1 defines Operation as the atomic primitive; v1 section 2.1 gives the v1 operation record. |
| Open verb set with lifecycle verbs | v0.6 section 3.1 says the verb set is open and versioned; v1 Phase 0 requires thread create and fork. |
| Content-addressed blob store | v0.6 section 4 requires content-addressed blobs with lean events; v1 section 2.2 requires a content-addressed blob store. |
| Append-only hash-chained operation log | v0.6 section 4 requires a local-first event-sourced core; v1 section 2.2 requires an append-only hash-chained log. |
| Thread operation DAG | v0.6 section 3.2 defines threads as structured operation graphs; v1 Phase 0 requires thread create and fork. |
| Projection folds | v0.6 section 3.3 defines artifacts as folds/projections over the operation graph; v1 section 2.3 requires materialized projections. |
| Feature operation that writes an artifact | v0.6 section 6 defines the first validation gate; v1 Phase 0 requires a hand-invoked Feature that writes an artifact. |
| Stabilize operation | v0.6 section 3.1 defines Stabilize as the process-to-artifact commitment; v1 Phase 0 requires a Stabilize operation. |
| Replay determinism tests | v1 Phase 0 acceptance requires replaying the log to reproduce identical state; v1 section 5 makes this a validation gate. |

## Explicitly Deferred

Verification debt, rigor profiles, deterministic verifiers, MCP, model routing,
conformal confidence, mutation testing, PROV/RO-Crate export, the full Merkle
history tree, and the inspection UI are Phase 1 through Phase 4 work. This keeps
the walking skeleton aligned with v1 Phase 0.
