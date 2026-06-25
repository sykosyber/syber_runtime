# Phase 2 Traceability

Phase 2 brings the generative loop alive while keeping inference external and
preserving deterministic/replayable runtime state.

| Component | Roadmap requirement |
|---|---|
| Model adapter boundary | v0.6 section 3.7 says inference stays external and every external call is logged as an adapter operation; v1 Phase 2 requires the MCP adapter. |
| MCP stdio tool adapter | v1 section 1 names MCP as the first inference adapter; v1 Phase 2 requires AI operations via MCP. The production adapter performs MCP stdio lifecycle initialization and invokes a configured `tools/call` endpoint while keeping the kernel SDK-free. |
| Runtime constitution and strict contracts | v1 section 4.0 requires every model call to carry the operation ontology and grammar; v1 sections 4.1 and 4.2 require strict JSON outputs. |
| Planner as Research operation | v1 section 4.3 requires a strong planner to emit a typed operation graph; v0.6 section 3.1 defines Research as design-uncertainty reduction. |
| Generator Feature with assumption ledger | v1 section 4.1 requires assumptions before artifact, a plan, the artifact, and self-identified risks; v0.6 section 3.1 defines Feature as generative and debt-incurring. |
| Cross-family verifier routing | v0.6 section 3.5 and RQ4 require verifier errors to decorrelate from generator errors; v1 sections 4.2 and 4.5 require different-family verifier routing. |
| Deterministic-first verifier execution | v0.6 section 3.5 prefers deterministic checks and treats LLM judges as last resort; v1 section 4.2 says Step 1 is to specify a checkable oracle. |
| Partial LLM Verify operation | v0.6 section 3.5 says LLM-judge discharge is partial/sampled, never full; v1 section 4.2 says LLM verdicts are recorded as partial discharge. |
| Conformal calibration primitive | v1 section 4.4 forbids verbal confidence and requires conformal calibration from history; the verification playbook Part C-D gives the same instruction. |
| Known-bad rejection path | v1 Phase 2 acceptance requires a deliberately wrong implementation to be caught and not stabilized; v0.6 section 8 names false discharge as a first-class risk. |

## Acceptance Boundary

The code now supports a full plan -> generate -> verify -> stabilize loop with
deterministic scripted adapters. A real external MCP/model endpoint is still
needed before claiming the "real AI via MCP" acceptance criterion in production.
