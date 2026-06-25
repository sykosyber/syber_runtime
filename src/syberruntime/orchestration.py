"""Phase 2 AI operation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syberruntime.ai_contracts import GeneratorOutput, PlannerOutput, VerifierOutput
from syberruntime.operation_log import LogEntry


@dataclass(frozen=True)
class AIOperationResult:
    plan: PlannerOutput
    generator_output: GeneratorOutput
    verifier_output: VerifierOutput
    plan_entry: LogEntry
    feature_entry: LogEntry
    verification_entry: LogEntry
    stabilize_entry: LogEntry | None
    artifact_digest: str
    confidence: dict[str, Any] | None = None

    @property
    def stabilized(self) -> bool:
        return self.stabilize_entry is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "generator_output": self.generator_output.to_dict(),
            "verifier_output": self.verifier_output.to_dict(),
            "plan_entry": self.plan_entry.to_dict(),
            "feature_entry": self.feature_entry.to_dict(),
            "verification_entry": self.verification_entry.to_dict(),
            "stabilize_entry": self.stabilize_entry.to_dict() if self.stabilize_entry else None,
            "artifact_digest": self.artifact_digest,
            "confidence": self.confidence,
            "stabilized": self.stabilized,
        }
