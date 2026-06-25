# Phase 4 Traceability

Phase 4 makes the kernel legible and harder to corrupt.

| Component | Roadmap requirement |
|---|---|
| Merkle history tree root and inclusion proofs | v1 Phase 4 requires the full Merkle history tree with inclusion proofs; Deep Theory section 3.1 identifies Merkle transparency logs as the concrete mechanism for tamper-evident provenance. |
| Consistency proof | v1 Phase 4 requires consistency proofs so the log can prove append-only evolution. The current proof is a full entry-hash audit proof, isolated behind `ConsistencyProof` for later compacting. |
| Schema upcasting | v0.6 section 4 requires versioned events and upcasting; v1 Phase 4 repeats event-schema versioning + upcasting as hardening work. |
| Projection snapshots | v0.6 section 4 requires snapshots and autonomous per-projection rebuild; v1 Phase 4 requires snapshots for rebuild. |
| PROV export | v0.6 section 3.8 requires W3C-PROV-compatible export; v1 Phase 4 requires W3C-PROV / RO-Crate provenance export. |
| RO-Crate export | v0.6 section 3.8 names RO-Crate-style research objects; v1 Phase 4 requires RO-Crate export. |
| Artifact inspection | v1 Phase 4 requires an inspection surface showing operation graph, debt ledger, assumptions, and provenance for any artifact. |
| Deletion-rights path | v0.6 section 8 names deletion rights vs. append-only logs and mitigates with payloads outside the log plus crypto-shredding; v1 Phase 4 requires that path. |
| Walkthrough demonstrator | v1 Phase 4 requires packaging as a runnable portfolio demonstrator with a written walkthrough. |

## Boundary

The inspection surface is CLI/JSON first. A richer UI remains possible, but the
current surface already lets a fresh reader trace a stabilized artifact from
Feature through Test/Verify and Stabilize with debt and assumptions visible.
