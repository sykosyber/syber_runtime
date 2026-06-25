# Phase 1 Traceability

Phase 1 implements the grammar, fixed rigor policy, verification-debt ledger,
and deterministic verification loop required by `SyberRuntime_v1_Implementation_Roadmap.md`.
The research-level authority remains `SyberRuntime_Research_Program_v0.6.md`.

| Component | Roadmap requirement |
|---|---|
| Grammar-created Test obligation for each Feature output | v0.6 section 3.1 requires every generative operation to incur a paired evaluative obligation; v1 Phase 1 says a Feature auto-creates an open Test obligation. |
| Verification-debt ledger projection | v0.6 section 3.5 defines verification debt as accumulated unverified mass; v1 section 2.3 requires a verification-debt ledger projection. |
| Fixed rigor profiles | v0.6 section 3.5 defines named profiles and per-center overrides; v1 section 2.4 requires centers to carry `exploratory`, `production`, `research-grade`, or `safety-critical` profiles. |
| Budget enforcement | v0.6 section 3.5 says debt near budget must trigger verification, human escalation, or halt; v1 Phase 1 requires debt over budget to halt or flag, never silently accumulate. |
| Deterministic verifier | v0.6 section 3.5 prefers deterministic/checkable verification; v1 Phase 1 requires the first verifier to be deterministic. |
| Test operation discharge | v0.6 section 3.1 defines Test as uncertainty reduction and section 3.5 defines discharge; v1 Phase 1 requires passing deterministic Test to discharge the obligation and lower debt. |
| Stabilize gating on floor-rigor debt | v0.6 section 3.5 defines floor rigor and section 3.1 frames Stabilize as a committing act; v1 Phase 1 requires Stabilize to be blocked while floor-rigor debt is open. |
| Patch-style merge helpers and tests | v0.6 section 3.2 requires commuting independent operations and first-class conflict-tolerant states; v1 Phase 1 requires property-style tests for commutation and conflict tolerance. |

## Still Deferred

LLM operations, MCP, conformal confidence, mutation testing, PROV export, the
full Merkle tree, and the inspection UI remain later-phase work. The Phase 1
verifier intentionally supports safe deterministic text/digest checks before
any artifact execution sandbox is introduced.
