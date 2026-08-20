# Archived harness reports (pre-2026-07-05, hinted-era)

These live-mode reports were generated before 2026-07-05, when the provider
prompt path still injected the expected artifact content and oracle extracted
from the task intent (`_exact_content_from_intent`, removed from
`syberruntime/providers/payload.py` on 2026-07-05). Their pass rates therefore
measure instruction-following under answer hints, not independent generation
plus verification, and they must not be cited as live capability evidence.

They are kept for provenance and failure-mode history (see
`docs/current_evidence_examination.md`). They live in this subdirectory —
outside report discovery, which only scans the top level of
`docs/agentic_harness_reports/` — so the `live_scale3_campaign` and
`agentic_intent_harness_live_smoke` acceptance criteria can never silently
fall back to a hinted run.

Current, un-hinted evidence: `agentic-live-004.json` and
`agentic-live-scale3-004.json` in the parent directory. They pass the
hardened local evidence audit; the historical 002 acceptance report predates
the current binding schema.
