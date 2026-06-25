"""Strict Phase 2 model-call contracts.

The runtime records model outputs as structured data so process verification can
inspect assumptions, risks, and verifier decisions without trusting prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syberruntime.errors import ModelContractError
from syberruntime.hashing import normalize_json
from syberruntime.models import Verb
from syberruntime.verification import SUPPORTED_DETERMINISTIC_CHECK_KINDS


PLANNER_OPERATION_VERBS = frozenset(
    {
        Verb.FEATURE.value,
        Verb.TEST.value,
        Verb.REFACTOR.value,
        Verb.RESEARCH.value,
        Verb.VERIFY.value,
        Verb.COMPRESS.value,
        Verb.SIMULATE.value,
        Verb.STABILIZE.value,
    }
)


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    family: str
    roles: tuple[str, ...]
    strength: str = "standard"

    def supports(self, role: str) -> bool:
        return role in self.roles

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "family": self.family,
            "roles": list(self.roles),
            "strength": self.strength,
        }


@dataclass(frozen=True)
class ModelRequest:
    role: str
    operation_type: str
    system: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "operation_type": self.operation_type,
            "system": self.system,
            "payload": normalize_json(self.payload),
        }


@dataclass(frozen=True)
class ModelResponse:
    model: ModelSpec
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model.to_dict(),
            "payload": normalize_json(self.payload),
        }


@dataclass(frozen=True)
class Assumption:
    claim: str
    depends_on: str
    confidence_rationale: str
    alternatives_considered: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Assumption":
        _require_keys(
            data,
            "assumption",
            ("claim", "depends_on", "confidence_rationale", "alternatives_considered"),
        )
        return cls(
            claim=str(data["claim"]),
            depends_on=str(data["depends_on"]),
            confidence_rationale=str(data["confidence_rationale"]),
            alternatives_considered=str(data["alternatives_considered"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "depends_on": self.depends_on,
            "confidence_rationale": self.confidence_rationale,
            "alternatives_considered": self.alternatives_considered,
        }


@dataclass(frozen=True)
class PlannedStep:
    verb: str
    success_question: str
    budget_alloc: float
    model_role: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlannedStep":
        _require_keys(data, "planned step", ("verb", "success_question", "budget_alloc", "model_role"))
        verb = str(data["verb"])
        if verb not in PLANNER_OPERATION_VERBS:
            allowed = ", ".join(sorted(PLANNER_OPERATION_VERBS))
            raise ModelContractError(
                f"planned step verb must be a SyberRuntime operation verb ({allowed}); found {verb!r}"
            )
        return cls(
            verb=verb,
            success_question=str(data["success_question"]),
            budget_alloc=float(data["budget_alloc"]),
            model_role=str(data["model_role"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb,
            "success_question": self.success_question,
            "budget_alloc": self.budget_alloc,
            "model_role": self.model_role,
        }


@dataclass(frozen=True)
class PlannerOutput:
    steps: tuple[PlannedStep, ...]
    rationale: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PlannerOutput":
        _require_keys(payload, "planner output", ("steps", "rationale"))
        steps = payload["steps"]
        if not isinstance(steps, list) or not steps:
            raise ModelContractError("planner output must include a non-empty steps list")
        return cls(
            steps=tuple(PlannedStep.from_dict(item) for item in steps),
            rationale=str(payload["rationale"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class GeneratorOutput:
    assumptions: tuple[Assumption, ...]
    plan: str
    artifact: str
    self_identified_risks: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GeneratorOutput":
        _require_keys(payload, "generator output", ("assumptions", "plan", "artifact", "self_identified_risks"))
        assumptions = payload["assumptions"]
        risks = payload["self_identified_risks"]
        if not isinstance(assumptions, list):
            raise ModelContractError("generator assumptions must be a list")
        if not isinstance(risks, list):
            raise ModelContractError("generator self_identified_risks must be a list")
        return cls(
            assumptions=tuple(Assumption.from_dict(item) for item in assumptions),
            plan=str(payload["plan"]),
            artifact=str(payload["artifact"]),
            self_identified_risks=tuple(str(item) for item in risks),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumptions": [assumption.to_dict() for assumption in self.assumptions],
            "plan": self.plan,
            "artifact": self.artifact,
            "self_identified_risks": list(self.self_identified_risks),
        }


@dataclass(frozen=True)
class LocatedError:
    where: str
    why: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocatedError":
        _require_keys(data, "located error", ("where", "why"))
        return cls(where=str(data["where"]), why=str(data["why"]))

    def to_dict(self) -> dict[str, Any]:
        return {"where": self.where, "why": self.why}


@dataclass(frozen=True)
class VerifierOutput:
    checkable_oracle: dict[str, Any] | None
    verdict: str
    located_errors: tuple[LocatedError, ...]
    obligation_discharged: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "VerifierOutput":
        _require_keys(
            payload,
            "verifier output",
            ("checkable_oracle", "verdict", "located_errors", "obligation_discharged"),
        )
        verdict = str(payload["verdict"])
        if verdict not in {"pass", "fail", "uncertain"}:
            raise ModelContractError(f"verifier verdict must be pass, fail, or uncertain; found {verdict!r}")
        located_errors = payload["located_errors"]
        if not isinstance(located_errors, list):
            raise ModelContractError("verifier located_errors must be a list")
        checkable_oracle = payload["checkable_oracle"]
        if checkable_oracle is not None:
            checkable_oracle = normalize_json(checkable_oracle)
            if not isinstance(checkable_oracle, dict):
                raise ModelContractError("verifier checkable_oracle must be null or an object")
            kind = str(checkable_oracle.get("kind", ""))
            if kind not in SUPPORTED_DETERMINISTIC_CHECK_KINDS:
                allowed = ", ".join(sorted(SUPPORTED_DETERMINISTIC_CHECK_KINDS))
                raise ModelContractError(
                    f"verifier checkable_oracle kind must be a supported deterministic check ({allowed}); "
                    f"found {kind!r}"
                )
            if "expected" not in checkable_oracle:
                raise ModelContractError("verifier checkable_oracle missing required key: expected")
        return cls(
            checkable_oracle=checkable_oracle,
            verdict=verdict,
            located_errors=tuple(LocatedError.from_dict(item) for item in located_errors),
            obligation_discharged=bool(payload["obligation_discharged"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkable_oracle": self.checkable_oracle,
            "verdict": self.verdict,
            "located_errors": [error.to_dict() for error in self.located_errors],
            "obligation_discharged": self.obligation_discharged,
        }


def _require_keys(data: dict[str, Any], label: str, keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ModelContractError(f"{label} missing required key(s): {', '.join(missing)}")
