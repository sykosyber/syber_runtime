"""Plan -> generate -> verify -> stabilize orchestration over the runtime kernel.

The orchestrator owns model routing policy and the AI loop; the runtime kernel
only records grammar operations. Nothing in the kernel imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from syberruntime.adapters import ModelAdapter
from syberruntime.ai.prompts import generator_system, runtime_constitution, verifier_system
from syberruntime.ai_contracts import GeneratorOutput, ModelRequest, PlannerOutput, VerifierOutput
from syberruntime.confidence import ConformalCalibrator
from syberruntime.errors import RoutingError
from syberruntime.intent import IntentMetadata
from syberruntime.models import Verb
from syberruntime.operation_log import LogEntry

if TYPE_CHECKING:
    from syberruntime.runtime import Runtime


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


def validate_routing(*, planner: ModelAdapter, generator: ModelAdapter, verifier: ModelAdapter) -> None:
    if not planner.spec.supports("planner"):
        raise RoutingError(f"Planner model {planner.spec.model_id} does not support planner role")
    if not generator.spec.supports("generator"):
        raise RoutingError(f"Generator model {generator.spec.model_id} does not support generator role")
    if not verifier.spec.supports("verifier"):
        raise RoutingError(f"Verifier model {verifier.spec.model_id} does not support verifier role")
    if generator.spec.family == verifier.spec.family:
        raise RoutingError(
            "Generator and verifier must be from different model families for error decorrelation"
        )


def run_ai_loop(
    runtime: "Runtime",
    *,
    intent: str,
    artifact_name: str,
    planner: ModelAdapter,
    generator: ModelAdapter,
    verifier: ModelAdapter,
    thread_id: str | None = None,
    center_id: str = "root",
    confidence_calibrator: ConformalCalibrator | None = None,
    intent_metadata: IntentMetadata | dict | None = None,
) -> AIOperationResult:
    validate_routing(planner=planner, generator=generator, verifier=verifier)
    if thread_id is None:
        thread_entry = runtime.create_thread(
            intent=intent,
            center_id=center_id,
            intent_metadata=intent_metadata,
        )
        thread_id = thread_entry.operation.thread_id
    elif thread_id not in runtime.rebuild_state().threads:
        raise KeyError(f"Unknown thread: {thread_id}")

    profile = runtime.policy.profile_for(center_id)
    planner_response = planner.call(
        ModelRequest(
            role="planner",
            operation_type=Verb.RESEARCH.value,
            system=runtime_constitution(),
            payload={"intent": intent, "center_rigor_profile": profile.name},
        )
    )
    plan = PlannerOutput.from_payload(planner_response.payload)
    plan_entry = runtime.record_plan(
        thread_id,
        intent=intent,
        plan=plan,
        actor=planner.spec.model_id,
        center_id=center_id,
        model_assignment=planner.spec.to_dict(),
        intent_metadata=intent_metadata,
    )

    generator_response = generator.call(
        ModelRequest(
            role="generator",
            operation_type=Verb.FEATURE.value,
            system=generator_system(),
            payload={
                "intent": intent,
                "artifact_name": artifact_name,
                "center_rigor_profile": profile.name,
                "plan": plan.to_dict(),
            },
        )
    )
    generated = GeneratorOutput.from_payload(generator_response.payload)
    feature_entry = runtime.record_feature(
        thread_id,
        artifact_name=artifact_name,
        content=generated.artifact,
        intent=intent,
        center_id=center_id,
        actor=generator.spec.model_id,
        assumptions=tuple(assumption.to_dict() for assumption in generated.assumptions),
        self_identified_risks=generated.self_identified_risks,
        generation_plan=generated.plan,
        model_assignment=generator.spec.to_dict(),
        intent_metadata=intent_metadata,
    )
    artifact_digest = feature_entry.operation.outputs[0].digest

    verifier_response = verifier.call(
        ModelRequest(
            role="verifier",
            operation_type=Verb.VERIFY.value,
            system=verifier_system(),
            payload={
                "intent": intent,
                "artifact_digest": artifact_digest,
                "artifact": generated.artifact,
                "assumption_ledger": [assumption.to_dict() for assumption in generated.assumptions],
                "self_identified_risks": list(generated.self_identified_risks),
                "center_rigor_profile": profile.name,
            },
        )
    )
    verified = VerifierOutput.from_payload(verifier_response.payload)

    if verified.checkable_oracle is not None:
        verification_entry = runtime.record_test(
            thread_id,
            artifact_digest=artifact_digest,
            check=verified.checkable_oracle,
            actor=verifier.spec.model_id,
            center_id=center_id,
            intent="Run verifier-specified deterministic oracle.",
            intent_metadata=intent_metadata,
        )
    else:
        verification_entry = runtime.record_verify(
            thread_id,
            artifact_digest=artifact_digest,
            verifier_output=verified,
            actor=verifier.spec.model_id,
            center_id=center_id,
            model_assignment=verifier.spec.to_dict(),
            intent_metadata=intent_metadata,
        )

    confidence = None
    if confidence_calibrator is not None:
        candidate_scores = _candidate_scores(verified)
        confidence = confidence_calibrator.prediction_set(candidate_scores).to_dict()

    stabilize_entry = None
    state = runtime.rebuild_state()
    if not state.debt.open_floor_obligations_for_artifact(artifact_digest):
        stabilize_entry = runtime.stabilize(
            thread_id,
            artifact_digest=artifact_digest,
            actor="runtime",
            center_id=center_id,
            intent="Stabilize after successful Phase 2 verification loop.",
            intent_metadata=intent_metadata,
        )

    return AIOperationResult(
        plan=plan,
        generator_output=generated,
        verifier_output=verified,
        plan_entry=plan_entry,
        feature_entry=feature_entry,
        verification_entry=verification_entry,
        stabilize_entry=stabilize_entry,
        artifact_digest=artifact_digest,
        confidence=confidence,
    )


def _candidate_scores(verified: VerifierOutput) -> dict[str, float]:
    if verified.verdict == "pass":
        return {"pass": 0.0, "fail": 1.0, "uncertain": 0.75}
    if verified.verdict == "fail":
        return {"pass": 1.0, "fail": 0.0, "uncertain": 0.75}
    return {"pass": 0.75, "fail": 0.75, "uncertain": 0.0}
