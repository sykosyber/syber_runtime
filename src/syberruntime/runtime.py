"""Runtime facade for the operation-primary kernel."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from syberruntime.adapters import ModelAdapter
from syberruntime.ai_contracts import GeneratorOutput, ModelRequest, PlannerOutput, VerifierOutput
from syberruntime.blob_store import BlobStore
from syberruntime.confidence import ConformalCalibrator
from syberruntime.debt import feature_obligation_id
from syberruntime.errors import BudgetExceededError, RoutingError, StabilizationBlockedError
from syberruntime.export import export_prov_document, export_ro_crate
from syberruntime.hashing import digest_bytes, digest_json, normalize_json
from syberruntime.inspector import inspect_artifact
from syberruntime.intent import IntentMetadata, normalize_intent_metadata
from syberruntime.merkle import ConsistencyProof, InclusionProof
from syberruntime.metrics import RuntimeMetrics, compute_runtime_metrics
from syberruntime.models import ArtifactRef, Evaluation, EvaluationStatus, Operation, Provenance, Verb
from syberruntime.mutation import MutationCampaignReport, TextMutationHarness
from syberruntime.operation_log import LogEntry, OperationLog
from syberruntime.orchestration import AIOperationResult
from syberruntime.policy import FixedPolicy
from syberruntime.projections import RuntimeState, fold_operations
from syberruntime.snapshots import Snapshot, SnapshotStore, make_snapshot
from syberruntime.verification import DeterministicVerifier


class Runtime:
    def __init__(self, root: str | Path, *, policy: FixedPolicy | None = None) -> None:
        self.root = Path(root)
        self.blobs = BlobStore(self.root)
        self.log = OperationLog(self.root / "operations.jsonl")
        self.policy = policy or FixedPolicy()
        self.verifier = DeterministicVerifier(self.blobs)
        self.mutation_harness = TextMutationHarness(self.blobs)
        self.snapshots = SnapshotStore(self.root)

    def create_thread(
        self,
        *,
        intent: str,
        actor: str = "human",
        center_id: str = "root",
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        operation_nonce = nonce or uuid4().hex
        metadata = normalize_intent_metadata(intent_metadata)
        thread_id = digest_json({"kind": "thread", "intent": intent, "nonce": operation_nonce})
        operation = Operation.build(
            type=Verb.THREAD_CREATE,
            thread_id=thread_id,
            center_id=center_id,
            params={"intent": intent, "intent_metadata": metadata},
            evaluation=Evaluation(
                question="Is the thread initialized around the stated intent?",
                status=EvaluationStatus.FULL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[_decision("thread_create", intent=intent, intent_metadata=metadata)],
            ),
            nonce=operation_nonce,
        )
        return self.log.append(operation)

    def fork_thread(
        self,
        source_thread_id: str,
        *,
        intent: str,
        actor: str = "human",
        center_id: str = "root",
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        state = self.rebuild_state()
        if source_thread_id not in state.threads:
            raise KeyError(f"Unknown source thread: {source_thread_id}")
        operation_nonce = nonce or uuid4().hex
        metadata = normalize_intent_metadata(intent_metadata)
        thread_id = digest_json(
            {
                "kind": "thread_fork",
                "source_thread_id": source_thread_id,
                "intent": intent,
                "nonce": operation_nonce,
            }
        )
        operation = Operation.build(
            type=Verb.THREAD_FORK,
            thread_id=thread_id,
            center_id=center_id,
            parents=state.threads[source_thread_id].heads,
            params={"source_thread_id": source_thread_id, "intent": intent, "intent_metadata": metadata},
            evaluation=Evaluation(
                question="Does the fork preserve ancestry while opening a separate operation graph?",
                status=EvaluationStatus.FULL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[_decision("thread_fork", intent=intent, intent_metadata=metadata)],
            ),
            nonce=operation_nonce,
        )
        return self.log.append(operation)

    def record_feature(
        self,
        thread_id: str,
        *,
        artifact_name: str,
        content: str | bytes,
        intent: str,
        media_type: str = "text/plain; charset=utf-8",
        generative_mass: float = 1.0,
        blast_radius: float = 1.0,
        criticality: float = 1.0,
        assumptions: tuple[dict, ...] = (),
        self_identified_risks: tuple[str, ...] = (),
        generation_plan: str | None = None,
        model_assignment: dict | None = None,
        actor: str = "human",
        center_id: str = "root",
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        state = self.rebuild_state()
        metadata = normalize_intent_metadata(intent_metadata)
        if thread_id not in state.threads:
            raise KeyError(f"Unknown thread: {thread_id}")

        payload = content.encode("utf-8") if isinstance(content, str) else content
        artifact = ArtifactRef(
            digest=digest_bytes(payload),
            size=len(payload),
            media_type=media_type,
            name=artifact_name,
        )
        profile = self.policy.profile_for(center_id)
        incurred_debt = float(generative_mass) * float(blast_radius) * float(criticality) * profile.accrual_rate
        self._enforce_budget(
            state=state,
            center_id=center_id,
            added_debt=incurred_debt,
        )

        operation_nonce = nonce or uuid4().hex
        obligation_id = feature_obligation_id(
            feature_nonce=operation_nonce,
            artifact_digest=artifact.digest,
            output_index=0,
        )
        debt_payload = {
            "generative_mass": float(generative_mass),
            "blast_radius": float(blast_radius),
            "criticality": float(criticality),
            "accrual_rate": profile.accrual_rate,
            "rigor_profile": profile.name,
            "floor_required": profile.floor_required,
            "obligations": [
                {
                    "id": obligation_id,
                    "artifact_digest": artifact.digest,
                    "generative_mass": float(generative_mass),
                    "blast_radius": float(blast_radius),
                    "criticality": float(criticality),
                    "accrual_rate": profile.accrual_rate,
                    "incurred_debt": incurred_debt,
                    "rigor_profile": profile.name,
                    "floor_required": profile.floor_required,
                }
            ],
        }
        if isinstance(content, str):
            artifact = self.blobs.put_text(content, media_type=media_type, name=artifact_name)
        else:
            artifact = self.blobs.put_bytes(content, media_type=media_type, name=artifact_name)

        operation = Operation.build(
            type=Verb.FEATURE,
            thread_id=thread_id,
            center_id=center_id,
            parents=state.threads[thread_id].heads,
            params={
                "intent": intent,
                "artifact_name": artifact_name,
                "debt": debt_payload,
                "generation_plan": generation_plan,
                "self_identified_risks": list(self_identified_risks),
                "model_assignment": normalize_json(model_assignment or {}),
                "intent_metadata": metadata,
            },
            outputs=(artifact,),
            evaluation=Evaluation(
                question="Did useful possibility increase?",
                obligations=(obligation_id,),
                status=EvaluationStatus.UNVERIFIED,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[_decision("feature", intent=intent, intent_metadata=metadata)],
                assumptions=tuple(assumptions),
            ),
            nonce=operation_nonce,
        )
        return self.log.append(operation)

    def record_plan(
        self,
        thread_id: str,
        *,
        intent: str,
        plan: PlannerOutput,
        actor: str,
        center_id: str = "root",
        model_assignment: dict | None = None,
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        state = self.rebuild_state()
        if thread_id not in state.threads:
            raise KeyError(f"Unknown thread: {thread_id}")

        metadata = normalize_intent_metadata(intent_metadata)
        operation = Operation.build(
            type=Verb.RESEARCH,
            thread_id=thread_id,
            center_id=center_id,
            parents=state.threads[thread_id].heads,
            params={
                "intent": intent,
                "role": "planner",
                "plan": plan.to_dict(),
                "model_assignment": normalize_json(model_assignment or {}),
                "intent_metadata": metadata,
            },
            evaluation=Evaluation(
                question="Is the operation graph for this intent explicit enough to guide work?",
                status=EvaluationStatus.FULL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[
                    _decision(
                        "plan",
                        intent=intent,
                        steps=[step.verb for step in plan.steps],
                        intent_metadata=metadata,
                    )
                ],
            ),
            nonce=nonce,
        )
        return self.log.append(operation)

    def record_test(
        self,
        thread_id: str,
        *,
        artifact_digest: str,
        check: dict,
        intent: str = "Run deterministic verification against the artifact.",
        actor: str = "human",
        center_id: str = "root",
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        state = self.rebuild_state()
        if thread_id not in state.threads:
            raise KeyError(f"Unknown thread: {thread_id}")
        if artifact_digest not in state.artifacts:
            raise KeyError(f"Unknown artifact: {artifact_digest}")

        artifact = state.artifacts[artifact_digest].ref
        open_obligations = state.debt.open_obligations_for_artifact(artifact_digest)
        metadata = normalize_intent_metadata(intent_metadata)
        attempted_obligations = tuple(obligation.id for obligation in open_obligations)
        result = self.verifier.run(artifact, normalize_json(check))
        discharged_obligations = attempted_obligations if result.passed else ()

        operation = Operation.build(
            type=Verb.TEST,
            thread_id=thread_id,
            center_id=center_id,
            parents=state.threads[thread_id].heads,
            inputs=(artifact,),
            params={
                "intent": intent,
                "verification": {
                    **result.to_dict(),
                    "check": normalize_json(check),
                    "attempted_obligations": list(attempted_obligations),
                    "discharged_obligations": list(discharged_obligations),
                },
                "intent_metadata": metadata,
            },
            evaluation=Evaluation(
                question="Did uncertainty decrease?",
                status=EvaluationStatus.FULL if result.passed else EvaluationStatus.PARTIAL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[
                    _decision(
                        "deterministic_test",
                        artifact_digest=artifact_digest,
                        passed=result.passed,
                        intent_metadata=metadata,
                    )
                ],
            ),
            nonce=nonce,
        )
        return self.log.append(operation)

    def record_verify(
        self,
        thread_id: str,
        *,
        artifact_digest: str,
        verifier_output: VerifierOutput,
        intent: str = "Run cross-model verification against the artifact and assumption ledger.",
        actor: str,
        center_id: str = "root",
        model_assignment: dict | None = None,
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        state = self.rebuild_state()
        if thread_id not in state.threads:
            raise KeyError(f"Unknown thread: {thread_id}")
        if artifact_digest not in state.artifacts:
            raise KeyError(f"Unknown artifact: {artifact_digest}")

        artifact = state.artifacts[artifact_digest].ref
        attempted_obligations = tuple(
            obligation.id for obligation in state.debt.open_obligations_for_artifact(artifact_digest)
        )
        passed = verifier_output.verdict == "pass"
        metadata = normalize_intent_metadata(intent_metadata)
        operation = Operation.build(
            type=Verb.VERIFY,
            thread_id=thread_id,
            center_id=center_id,
            parents=state.threads[thread_id].heads,
            inputs=(artifact,),
            params={
                "intent": intent,
                "verification": {
                    "kind": "llm_judge",
                    "passed": passed,
                    "verdict": verifier_output.verdict,
                    "located_errors": [error.to_dict() for error in verifier_output.located_errors],
                    "attempted_obligations": list(attempted_obligations),
                    "discharged_obligations": [],
                    "partial_only": True,
                    "model_assignment": normalize_json(model_assignment or {}),
                },
                "intent_metadata": metadata,
            },
            evaluation=Evaluation(
                question="Is trust justified?",
                status=EvaluationStatus.PARTIAL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[
                    _decision(
                        "cross_model_verify",
                        artifact_digest=artifact_digest,
                        verdict=verifier_output.verdict,
                        intent_metadata=metadata,
                    )
                ],
            ),
            nonce=nonce,
        )
        return self.log.append(operation)

    def run_mutation_campaign(
        self,
        thread_id: str,
        *,
        artifact_digest: str,
        check: dict,
        intent: str = "Measure deterministic verifier discharge efficiency via mutation testing.",
        actor: str = "runtime",
        center_id: str = "root",
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> tuple[LogEntry, MutationCampaignReport]:
        state = self.rebuild_state()
        if thread_id not in state.threads:
            raise KeyError(f"Unknown thread: {thread_id}")
        if artifact_digest not in state.artifacts:
            raise KeyError(f"Unknown artifact: {artifact_digest}")

        artifact = state.artifacts[artifact_digest].ref
        report = self.mutation_harness.run(artifact, normalize_json(check))
        metadata = normalize_intent_metadata(intent_metadata)
        operation = Operation.build(
            type=Verb.VERIFY,
            thread_id=thread_id,
            center_id=center_id,
            parents=state.threads[thread_id].heads,
            inputs=(artifact,),
            params={
                "intent": intent,
                "measurement": {
                    "kind": "mutation_campaign",
                    "verifier_kind": "deterministic",
                    **report.to_dict(),
                },
                "intent_metadata": metadata,
            },
            evaluation=Evaluation(
                question="Was verifier discharge efficiency measured against synthetic faults?",
                status=EvaluationStatus.FULL if report.baseline_passed else EvaluationStatus.PARTIAL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[
                    _decision(
                        "mutation_campaign",
                        artifact_digest=artifact_digest,
                        mutant_count=report.mutant_count,
                        discharge_efficiency=report.discharge_efficiency,
                        intent_metadata=metadata,
                    )
                ],
            ),
            nonce=nonce,
        )
        return self.log.append(operation), report

    def stabilize(
        self,
        thread_id: str,
        *,
        artifact_digest: str | None = None,
        intent: str = "Stabilize the current artifact projection.",
        actor: str = "human",
        center_id: str = "root",
        intent_metadata: IntentMetadata | dict | None = None,
        nonce: str | None = None,
    ) -> LogEntry:
        state = self.rebuild_state()
        if thread_id not in state.threads:
            raise KeyError(f"Unknown thread: {thread_id}")

        thread = state.threads[thread_id]
        digest = artifact_digest or (thread.artifacts[-1] if thread.artifacts else None)
        if digest is None:
            raise ValueError(f"Thread has no artifact to stabilize: {thread_id}")
        if digest not in state.artifacts:
            raise KeyError(f"Unknown artifact: {digest}")
        blocking = state.debt.open_floor_obligations_for_artifact(digest)
        if blocking:
            ids = ", ".join(obligation.id for obligation in blocking)
            raise StabilizationBlockedError(
                f"Artifact {digest} has open floor-rigor verification obligations: {ids}"
            )
        metadata = normalize_intent_metadata(intent_metadata)

        operation = Operation.build(
            type=Verb.STABILIZE,
            thread_id=thread_id,
            center_id=center_id,
            parents=thread.heads,
            inputs=(state.artifacts[digest].ref,),
            params={"intent": intent, "artifact_digest": digest, "intent_metadata": metadata},
            evaluation=Evaluation(
                question="Is this ready to commit as a stabilized projection?",
                status=EvaluationStatus.FULL,
            ),
            provenance=Provenance(
                actor=actor,
                decisions=[_decision("stabilize", artifact_digest=digest, intent_metadata=metadata)],
            ),
            nonce=nonce,
        )
        return self.log.append(operation)

    def rebuild_state(self) -> RuntimeState:
        return fold_operations(self.log.operations(validate=True))

    def operation_graph(self) -> dict:
        return self.rebuild_state().operation_graph()

    def replay_is_deterministic(self) -> bool:
        operations = self.log.operations(validate=True)
        first = fold_operations(operations).to_dict()
        second = fold_operations(operations).to_dict()
        return first == second

    def metrics(self) -> RuntimeMetrics:
        return compute_runtime_metrics(self.rebuild_state())

    def merkle_root_hash(self) -> str:
        return self.log.merkle_root_hash()

    def inclusion_proof(self, index: int) -> InclusionProof:
        return self.log.inclusion_proof(index)

    def consistency_proof(self, old_size: int, new_size: int | None = None) -> ConsistencyProof:
        return self.log.consistency_proof(old_size, new_size)

    def create_snapshot(self) -> Snapshot:
        entries = self.log.entries(validate=True)
        snapshot = make_snapshot(
            log_size=len(entries),
            merkle_root_hash=self.merkle_root_hash(),
            state=self.rebuild_state().to_dict(),
        )
        self.snapshots.write(snapshot)
        return snapshot

    def inspect_artifact(self, artifact_digest: str) -> dict:
        return inspect_artifact(self.rebuild_state(), artifact_digest)

    def export_prov(self) -> dict:
        return export_prov_document(self.rebuild_state())

    def export_ro_crate(self) -> dict:
        return export_ro_crate(self.rebuild_state())

    def shred_blob(self, artifact_digest: str, *, reason: str = "deletion-rights request") -> bool:
        return self.blobs.shred(artifact_digest, reason=reason)

    def run_ai_loop(
        self,
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
        self._validate_routing(planner=planner, generator=generator, verifier=verifier)
        if thread_id is None:
            thread_entry = self.create_thread(
                intent=intent,
                center_id=center_id,
                intent_metadata=intent_metadata,
            )
            thread_id = thread_entry.operation.thread_id
        elif thread_id not in self.rebuild_state().threads:
            raise KeyError(f"Unknown thread: {thread_id}")

        profile = self.policy.profile_for(center_id)
        planner_response = planner.call(
            ModelRequest(
                role="planner",
                operation_type=Verb.RESEARCH.value,
                system=_runtime_constitution(),
                payload={"intent": intent, "center_rigor_profile": profile.name},
            )
        )
        plan = PlannerOutput.from_payload(planner_response.payload)
        plan_entry = self.record_plan(
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
                system=_generator_system(),
                payload={
                    "intent": intent,
                    "artifact_name": artifact_name,
                    "center_rigor_profile": profile.name,
                    "plan": plan.to_dict(),
                },
            )
        )
        generated = GeneratorOutput.from_payload(generator_response.payload)
        feature_entry = self.record_feature(
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
                system=_verifier_system(),
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
            verification_entry = self.record_test(
                thread_id,
                artifact_digest=artifact_digest,
                check=verified.checkable_oracle,
                actor=verifier.spec.model_id,
                center_id=center_id,
                intent="Run verifier-specified deterministic oracle.",
                intent_metadata=intent_metadata,
            )
        else:
            verification_entry = self.record_verify(
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
        state = self.rebuild_state()
        if not state.debt.open_floor_obligations_for_artifact(artifact_digest):
            stabilize_entry = self.stabilize(
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

    def _enforce_budget(self, *, state: RuntimeState, center_id: str, added_debt: float) -> None:
        current = state.debt.residual_debt_for_center(center_id)
        limit = self.policy.max_debt_for(center_id)
        if current + added_debt > limit:
            raise BudgetExceededError(
                f"Debt budget exceeded for center {center_id}: "
                f"current={current}, added={added_debt}, limit={limit}"
            )

    def _validate_routing(
        self,
        *,
        planner: ModelAdapter,
        generator: ModelAdapter,
        verifier: ModelAdapter,
    ) -> None:
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


def _runtime_constitution() -> str:
    return (
        "Work proceeds as typed SyberRuntime operations. Every generative operation incurs "
        "a paired evaluation obligation. Assumptions must be surfaced before artifact creation; "
        "human understanding is the protected resource."
    )


def _generator_system() -> str:
    return (
        "You are performing a Feature operation. Return strict JSON with assumptions, plan, "
        "artifact, and self_identified_risks. State assumptions before artifact content."
    )


def _verifier_system() -> str:
    return (
        "You are performing a Verify operation. Prefer a deterministic checkable oracle. "
        "If no oracle exists, return pass, fail, or uncertain with located errors."
    )


def _candidate_scores(verified: VerifierOutput) -> dict[str, float]:
    if verified.verdict == "pass":
        return {"pass": 0.0, "fail": 1.0, "uncertain": 0.75}
    if verified.verdict == "fail":
        return {"pass": 1.0, "fail": 0.0, "uncertain": 0.75}
    return {"pass": 0.75, "fail": 0.75, "uncertain": 0.0}


def _decision(kind: str, *, intent_metadata: dict, **values: object) -> dict:
    decision = {"kind": kind, **values}
    if intent_metadata:
        decision["intent_metadata"] = intent_metadata
    return decision
