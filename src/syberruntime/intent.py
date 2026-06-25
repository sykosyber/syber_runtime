"""Intent-source metadata for human and agentic operation initiators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syberruntime.hashing import normalize_json


@dataclass(frozen=True)
class IntentMetadata:
    intent_source: str
    principal: str
    acceptance_authority: str
    benchmark_id: str | None = None
    harness_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_source": self.intent_source,
            "principal": self.principal,
            "acceptance_authority": self.acceptance_authority,
            "benchmark_id": self.benchmark_id,
            "harness_run_id": self.harness_run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentMetadata":
        return cls(
            intent_source=str(data["intent_source"]),
            principal=str(data["principal"]),
            acceptance_authority=str(data["acceptance_authority"]),
            benchmark_id=str(data["benchmark_id"]) if data.get("benchmark_id") is not None else None,
            harness_run_id=str(data["harness_run_id"]) if data.get("harness_run_id") is not None else None,
        )


def normalize_intent_metadata(value: IntentMetadata | dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, IntentMetadata):
        return value.to_dict()
    normalized = normalize_json(value)
    if not isinstance(normalized, dict):
        raise TypeError("Intent metadata must be a JSON object")
    return IntentMetadata.from_dict(normalized).to_dict()
