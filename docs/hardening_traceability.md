# July 2026 Hardening Traceability

This increment implements five acceptance-critical controls. It does not add a
new roadmap phase.

| Control | Roadmap requirement | Implementation and evidence |
|---|---|---|
| Isolated deterministic execution worker | v1 Phase 1 deterministic verification; v1 Phase 2 known-bad rejection | execution_worker.py runs Python tests under isolated mode, a minimal environment, denied network/process/native loading, constrained file access, and bounded wall/CPU/memory resources. Adversarial tests cover network, filesystem, secret inheritance, and resource inflation. |
| Canonical deletion identifiers and membership | v0.6 section 8; v1 Phase 4 deletion rights | blob_store.py accepts only lowercase 64-character SHA-256 digests and proves resolved containment. Runtime.shred_blob requires artifact-projection membership before payload removal. |
| Fail-closed evidence and acceptance | v0.6 sections 3.7-3.8; v1 section 7 | Reports have canonical IDs, timestamps, Git/config/protocol/log bindings, recomputed summaries and metrics, and bound-runtime validation. Acceptance returns nonzero on failure and includes the hard live code campaign. |
| Held-out conformal and controlled RQ0/RQ6 gates | v1 Phase 2 acceptance; v1 Phase 3 acceptance; v1 section 4.4 | Pre-registered protocols and reports live under docs/empirical_reports. Acceptance recomputes held-out coverage and requires both RQ0 and RQ6 arms with known-bad rejection. Claims remain n=1 feasibility only. |
| Aggregate false discharge | v0.6 section 3.5; v1 Phase 3 measurement | Runtime metrics now compute mutant-weighted false-discharge rates across all campaigns globally and per rigor profile. Later clean campaigns cannot erase earlier survivors. |

## Current Verification Result

scripts/verify.ps1 passes 83 tests, compile checks, and all stored-evidence
criteria. The no-config audit is ready_with_warnings solely because it does not
make a fresh external MCP call. Historical live acceptance reports 001 and 002
predate the binding schema and do not satisfy the current gate; the next
provider-backed acceptance artifact must be written as 003 or later.
The current bound local audit is recorded as
docs/acceptance_reports/local_hardened_acceptance_001.json.
