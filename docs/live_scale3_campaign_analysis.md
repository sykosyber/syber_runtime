# Live Scale3 Campaign Analysis

Analysis ID: `e6b4184da896eb3b747b4047c86d76881c1999293a2fe7e20d9afd61a7e6903e`

## Roadmap Requirement

| Component | Required by |
|---|---|
| Scale3 analysis report | v1 Phase 3; v0.6 section 3.8; v1 section 7 |
| Failure mode taxonomy | v0.6 section 3.8; v1 Phase 3; v1 section 7 |
| Mutation outcome summary | v0.6 section 3.5; v1 Phase 3; Verification Playbook Part C-F |

## Run Summary

| Run | Attempted | Stabilized | Failed | Generated | Validated | False discharge | Residual debt | Structural rigor | Mutants killed | Failure modes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `agentic-live-scale3-001` | 3 | 2 | 1 | 3 | 2 | 0.000 | 1.000 | 0.875 | 6/6 | artifact_content_mismatch |
| `agentic-live-scale3-002` | 3 | 2 | 1 | 2 | 2 | 0.000 | 0.000 | 1.000 | 6/6 | provider_malformed_json |
| `agentic-live-scale3-003` | 3 | 3 | 0 | 3 | 3 | 0.000 | 0.000 | 1.000 | 9/9 | none |

## Failure Progression

- `agentic-live-scale3-001`: live-provider-scale-002: artifact_content_mismatch.
- `agentic-live-scale3-002`: live-provider-scale-003: provider_malformed_json.
- `agentic-live-scale3-003`: no failed tasks.

## Apex Inference

The scale3 campaign shows measured hardening rather than a one-off lucky pass: earlier live runs exposed artifact precision and provider-boundary failure modes, while the latest run completed all three independent exact-content tasks with zero false discharge, zero residual debt, full structural rigor, and complete mutation kill coverage.

## Source Reports

- `agentic-live-scale3-001`: `docs/agentic_harness_reports/agentic-live-scale3-001.json` (`5d669e584fe243068e2f7d0a76ee047aabb85f238d24c7ef54d5ff99fc773923`)
- `agentic-live-scale3-002`: `docs/agentic_harness_reports/agentic-live-scale3-002.json` (`f048936c8779d5a2d933bf87948f6755a81e69b64478e182025046a2ee57e51f`)
- `agentic-live-scale3-003`: `docs/agentic_harness_reports/agentic-live-scale3-003.json` (`8c3f0b484b75ff5762fd529103d39ed3c7b800e137d78b4de10f77bc135449fb`)
