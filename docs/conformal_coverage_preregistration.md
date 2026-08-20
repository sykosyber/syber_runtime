# Held-Out Conformal Coverage Pre-Registration

This protocol closes the held-out coverage criterion in **v1 Phase 2
acceptance** and follows **v1 section 4.4** and the Verification Testing
Playbook Part C-D. It is recorded before generating the conformal coverage
report under docs/empirical_reports.

## Claim Boundary

This is a deterministic mechanism-level acceptance experiment. It demonstrates
that the implemented split-conformal calibrator computes its threshold from a
calibration cohort and achieves nominal coverage on a separate held-out cohort.
It does not establish model-quality calibration or population-level validity.

## Fixed Inputs

- Alpha: 0.20; nominal coverage: 0.80.
- Calibration scores: 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45.
- Held-out scores: 0.08, 0.18, 0.28, 0.38, 0.48.
- Lower nonconformity scores indicate better support.
- Scores are deterministic observed-outcome fixtures, never model-verbalized
  confidence.

## Gate

The cohorts must be disjoint, contain at least five observations each, and the
held-out empirical coverage must be at least 1 - alpha. Any missing, malformed,
or hash-invalid report fails acceptance.
