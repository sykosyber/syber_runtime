"""Model capability envelope metadata for evidence reports."""

from __future__ import annotations

from typing import Any

from syberruntime.hashing import normalize_json


LOWER_BOUND_INTERPRETATION = (
    "This report should be read as a lower-bound operational demonstration under "
    "the recorded model-access constraints, not as a ceiling on SyberRuntime performance."
)


def model_capability_envelope(
    *,
    available_model_roles: dict[str, Any] | None = None,
    constraints: tuple[str, ...] | list[str] | None = None,
    preferred_unavailable_models: tuple[str, ...] | list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Return a canonical model-access envelope for dogfood and harness reports."""

    payload = {
        "claim_scope": "lower-bound operational demonstration",
        "available_model_roles": available_model_roles or {},
        "constraints": list(constraints or ()),
        "preferred_unavailable_models": list(preferred_unavailable_models or ()),
        "expected_impact": (
            "Stronger planner, generator, and verifier models may improve operational throughput and output "
            "quality; comparisons should be made by rerunning the same protocol with updated model assignments."
        ),
        "interpretation": LOWER_BOUND_INTERPRETATION,
        "notes": notes or "",
    }
    normalized = normalize_json(payload)
    if not isinstance(normalized, dict):
        raise TypeError("model capability envelope must normalize to a JSON object")
    return normalized
