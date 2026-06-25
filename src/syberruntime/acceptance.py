"""V1 acceptance audit derived from the roadmap's done criteria."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.adapter_config import load_adapter_bundle
from syberruntime.adapters import ScriptedModelAdapter
from syberruntime.ai_contracts import ModelSpec
from syberruntime.dogfood import discover_dogfood_reports, load_dogfood_report
from syberruntime.errors import AdapterError, SyberRuntimeError
from syberruntime.harness import discover_harness_reports, load_harness_report
from syberruntime.policy import FixedPolicy
from syberruntime.runtime import Runtime


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    status: str
    citation: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "citation": self.citation,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class AcceptanceReport:
    overall_status: str
    criteria: tuple[AcceptanceCriterion, ...]

    @property
    def failures(self) -> tuple[AcceptanceCriterion, ...]:
        return tuple(criterion for criterion in self.criteria if criterion.status == "fail")

    @property
    def warnings(self) -> tuple[AcceptanceCriterion, ...]:
        return tuple(criterion for criterion in self.criteria if criterion.status == "warn")

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "failure_count": len(self.failures),
            "warning_count": len(self.warnings),
        }


def run_v1_acceptance_audit(
    *,
    workspace_root: str | Path | None = None,
    mcp_config_path: str | Path | None = None,
    dogfood_report_dir: str | Path | None = None,
    agent_harness_report_dir: str | Path | None = None,
) -> AcceptanceReport:
    criteria: list[AcceptanceCriterion] = []
    with tempfile.TemporaryDirectory() as tmp:
        criteria.extend(_audit_runtime_kernel(tmp, mcp_config_path=mcp_config_path))

    root = Path(workspace_root) if workspace_root is not None else Path.cwd()
    reports_dir = Path(dogfood_report_dir) if dogfood_report_dir is not None else root / "docs" / "dogfood_reports"
    harness_reports_dir = (
        Path(agent_harness_report_dir)
        if agent_harness_report_dir is not None
        else root / "docs" / "agentic_harness_reports"
    )
    criteria.extend(
        _audit_workspace_artifacts(
            root,
            dogfood_report_dir=reports_dir,
            agent_harness_report_dir=harness_reports_dir,
        )
    )
    overall = _overall_status(criteria)
    return AcceptanceReport(overall_status=overall, criteria=tuple(criteria))


def _audit_runtime_kernel(tmp: str, *, mcp_config_path: str | Path | None) -> list[AcceptanceCriterion]:
    criteria: list[AcceptanceCriterion] = []

    phase0 = Runtime(Path(tmp) / "phase0", policy=FixedPolicy(default_profile="exploratory"))
    thread = phase0.create_thread(intent="Acceptance first-validation gate")
    feature = phase0.record_feature(
        thread.operation.thread_id,
        artifact_name="gate.txt",
        content="phase-zero-gate",
        intent="Produce an artifact for the first-validation gate",
    )
    fork = phase0.fork_thread(thread.operation.thread_id, intent="Fork acceptance thread")
    stabilized = phase0.stabilize(thread.operation.thread_id, artifact_digest=feature.operation.outputs[0].digest)
    state = phase0.rebuild_state()
    first_gate_passed = (
        thread.operation.thread_id in state.threads
        and fork.operation.thread_id in state.threads
        and state.artifacts[feature.operation.outputs[0].digest].stabilized_by == stabilized.operation.id
        and phase0.replay_is_deterministic()
    )
    criteria.append(
        _criterion(
            "first_validation_gate",
            first_gate_passed,
            "v0.6 section 6; v1 Phase 0; v1 section 7",
            "create thread, Feature, fork, artifact projection, Stabilize, and deterministic replay verified",
        )
    )

    production = Runtime(Path(tmp) / "production", policy=FixedPolicy(default_profile="production"))
    thread = production.create_thread(intent="Acceptance debt loop")
    feature = production.record_feature(
        thread.operation.thread_id,
        artifact_name="release.txt",
        content="release-token\n",
        intent="Exercise debt grammar",
        assumptions=(
            {
                "claim": "A text token is sufficient",
                "depends_on": "The deterministic check observes exact text",
                "confidence_rationale": "The artifact is small and deterministic",
                "alternatives_considered": "Structured JSON",
            },
        ),
    )
    digest = feature.operation.outputs[0].digest
    production.record_test(
        thread.operation.thread_id,
        artifact_digest=digest,
        check={"kind": "text_equals", "expected": "release-token\n"},
    )
    production.stabilize(thread.operation.thread_id, artifact_digest=digest)
    state = production.rebuild_state()
    criteria.append(
        _criterion(
            "grammar_debt_and_stabilize",
            state.debt.total_residual_debt() == 0.0 and state.artifacts[digest].stabilized_by is not None,
            "v0.6 sections 3.1 and 3.5; v1 Phase 1; v1 section 7",
            "Feature incurred a Test obligation, deterministic Test discharged it, and Stabilize was allowed",
        )
    )

    ai_result = production.run_ai_loop(
        intent="Acceptance scripted AI loop",
        artifact_name="ai.txt",
        planner=_planner(),
        generator=_generator("adapter-token\n"),
        verifier=_verifier(
            {
                "checkable_oracle": {"kind": "text_contains", "expected": "adapter-token"},
                "verdict": "pass",
                "located_errors": [],
                "obligation_discharged": True,
            }
        ),
    )
    criteria.append(
        _criterion(
            "plan_generate_verify_stabilize_adapter_loop",
            ai_result.stabilized,
            "v0.6 section 3.7; v1 Phase 2; v1 section 4; v1 section 7",
            "scripted external adapters completed plan -> generate -> verify -> stabilize under the grammar",
        )
    )
    criteria.append(_audit_live_mcp_loop(Path(tmp) / "live-mcp", mcp_config_path))

    _entry, mutation = production.run_mutation_campaign(
        thread.operation.thread_id,
        artifact_digest=digest,
        check={"kind": "text_equals", "expected": "release-token\n"},
    )
    metrics = production.metrics()
    criteria.append(
        _criterion(
            "mutation_measured_discharge_efficiency",
            mutation.mutant_count > 0 and "production" in metrics.discharge_efficiency_by_profile,
            "v1 Phase 3; Verification Playbook Part C-F; v1 section 7",
            f"mutation campaign measured discharge_efficiency={mutation.discharge_efficiency:.3f}",
        )
    )

    inspection = production.inspect_artifact(digest)
    criteria.append(
        _criterion(
            "inspectable_provenance_debt_assumptions",
            bool(inspection["assumptions"])
            and bool(inspection["verification"])
            and bool(inspection["debt_obligations"])
            and inspection["stabilized_by"] is not None,
            "v0.6 section 3.8; v1 Phase 4; v1 section 7",
            "artifact inspection exposes assumptions, verification operations, debt obligations, and Stabilize",
        )
    )

    inclusion = production.inclusion_proof(0)
    consistency = production.consistency_proof(1)
    snapshot = production.create_snapshot()
    criteria.append(
        _criterion(
            "tamper_evidence_and_snapshot",
            inclusion.verify()
            and consistency.verify()
            and snapshot.merkle_root_hash == production.merkle_root_hash()
            and snapshot.state == production.rebuild_state().to_dict(),
            "Deep Theory section 3.1; v1 Phase 4",
            "Merkle inclusion proof, append-only consistency proof, and projection snapshot verified",
        )
    )

    prov = production.export_prov()
    ro_crate = production.export_ro_crate()
    criteria.append(
        _criterion(
            "prov_rocrate_exports",
            f"artifact:{digest}" in prov["entity"]
            and any(node.get("@id") == f"artifact:{digest}" for node in ro_crate["@graph"]),
            "v0.6 section 3.8; v1 Phase 4",
            "PROV and RO-Crate exports include the stabilized artifact",
        )
    )

    shredded = production.shred_blob(digest, reason="acceptance deletion-rights exercise")
    criteria.append(
        _criterion(
            "deletion_rights_payload_shredding",
            shredded and not production.blobs.exists(digest) and digest in production.rebuild_state().artifacts,
            "v0.6 section 8; v1 Phase 4",
            "content-addressed payload was shredded while operation-log provenance remained inspectable",
        )
    )

    return criteria


def _audit_workspace_artifacts(
    root: Path,
    *,
    dogfood_report_dir: Path,
    agent_harness_report_dir: Path,
) -> list[AcceptanceCriterion]:
    prereg = root / "docs" / "rq0_rq6_preregistration.md"
    walkthrough = root / "docs" / "phase4_walkthrough.md"
    criteria = [
        _criterion(
            "preregistered_rq0_rq6_protocol",
            prereg.exists() and prereg.read_text(encoding="utf-8").strip() != "",
            "v1 Phase 3; v1 section 5; v1 section 7",
            "pre-registration protocol exists before dogfooding measurements",
        ),
        _criterion(
            "written_walkthrough",
            walkthrough.exists() and walkthrough.read_text(encoding="utf-8").strip() != "",
            "v1 Phase 4; v1 section 7",
            "written demonstrator walkthrough exists",
        ),
        _audit_dogfood_reports(dogfood_report_dir),
        _audit_agent_harness_reports(agent_harness_report_dir),
        _audit_live_agent_harness_reports(agent_harness_report_dir),
    ]
    return criteria


def _audit_live_mcp_loop(runtime_root: Path, mcp_config_path: str | Path | None) -> AcceptanceCriterion:
    if mcp_config_path is None:
        return AcceptanceCriterion(
            id="live_mcp_real_ai_endpoint",
            status="warn",
            citation="v1 Phase 2; v1 section 7",
            evidence="adapter boundary and MCP stdio endpoint support exist, but no live MCP/model endpoint config was provided",
        )
    try:
        bundle = load_adapter_bundle(mcp_config_path)
        runtime = Runtime(runtime_root, policy=FixedPolicy(default_profile="production"))
        result = runtime.run_ai_loop(
            intent="Acceptance live MCP-configured loop",
            artifact_name="live-mcp.txt",
            planner=bundle.planner,
            generator=bundle.generator,
            verifier=bundle.verifier,
        )
    except (AdapterError, SyberRuntimeError, OSError, KeyError, ValueError) as exc:
        return AcceptanceCriterion(
            id="live_mcp_real_ai_endpoint",
            status="fail",
            citation="v1 Phase 2; v1 section 7",
            evidence=f"provided MCP adapter config did not complete the live loop: {exc}",
        )
    return AcceptanceCriterion(
        id="live_mcp_real_ai_endpoint",
        status="pass" if result.stabilized else "fail",
        citation="v1 Phase 2; v1 section 7",
        evidence="provided MCP adapter config completed plan -> generate -> verify -> stabilize",
    )


def _audit_dogfood_reports(report_dir: Path) -> AcceptanceCriterion:
    reports = discover_dogfood_reports(report_dir)
    if not reports:
        return AcceptanceCriterion(
            id="dogfooding_rq0_rq6_results",
            status="warn",
            citation="v0.6 section 6; v1 Phase 3; v1 section 7",
            evidence="protocol exists, but real dogfooding results have not yet been collected and reported",
        )
    try:
        loaded = [load_dogfood_report(path) for path in reports]
    except (OSError, ValueError, KeyError) as exc:
        return AcceptanceCriterion(
            id="dogfooding_rq0_rq6_results",
            status="fail",
            citation="v0.6 section 6; v1 Phase 3; v1 section 7",
            evidence=f"dogfooding report directory contains an invalid report: {exc}",
        )
    return AcceptanceCriterion(
        id="dogfooding_rq0_rq6_results",
        status="pass",
        citation="v0.6 section 6; v1 Phase 3; v1 section 7",
        evidence=f"{len(loaded)} dogfooding report(s) found under the pre-registered protocol",
    )


def _audit_agent_harness_reports(report_dir: Path) -> AcceptanceCriterion:
    reports = discover_harness_reports(report_dir)
    if not reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_baseline",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 3; v1 section 6; v1 section 7",
            evidence="agentic intent harness exists, but no baseline harness report was found",
        )
    try:
        loaded = [load_harness_report(path) for path in reports]
    except (OSError, ValueError, KeyError) as exc:
        return AcceptanceCriterion(
            id="agentic_intent_harness_baseline",
            status="fail",
            citation="v0.6 section 3.8; v1 Phase 3; v1 section 6; v1 section 7",
            evidence=f"agentic harness report directory contains an invalid report: {exc}",
        )
    baseline_reports = [report for report in loaded if str(report.get("mode", "scripted")) == "scripted"]
    if not baseline_reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_baseline",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 3; v1 section 6; v1 section 7",
            evidence="harness reports were found, but no scripted baseline harness report was found",
        )
    stabilized = sum(int(report["summary"].get("stabilized_tasks", 0)) for report in baseline_reports)
    attempted = sum(int(report["summary"].get("attempted_tasks", 0)) for report in baseline_reports)
    return AcceptanceCriterion(
        id="agentic_intent_harness_baseline",
        status="pass",
        citation="v0.6 section 3.8; v1 Phase 3; v1 section 6; v1 section 7",
        evidence=(
            f"{len(baseline_reports)} scripted baseline harness report(s) found; "
            f"attempted_tasks={attempted}, stabilized_tasks={stabilized}; "
            f"total_harness_reports={len(loaded)}"
        ),
    )


def _audit_live_agent_harness_reports(report_dir: Path) -> AcceptanceCriterion:
    reports = discover_harness_reports(report_dir)
    if not reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_live_smoke",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence="no live-mode agentic harness report was found",
        )
    try:
        loaded = [load_harness_report(path) for path in reports]
    except (OSError, ValueError, KeyError) as exc:
        return AcceptanceCriterion(
            id="agentic_intent_harness_live_smoke",
            status="fail",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence=f"agentic harness report directory contains an invalid report: {exc}",
        )
    live_reports = [report for report in loaded if str(report.get("mode", "scripted")) == "live"]
    if not live_reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_live_smoke",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence="scripted harness baseline exists, but no live-mode harness report was found",
        )
    stabilized = sum(int(report["summary"].get("stabilized_tasks", 0)) for report in live_reports)
    attempted = sum(int(report["summary"].get("attempted_tasks", 0)) for report in live_reports)
    failed_tasks = sum(
        1
        for report in live_reports
        for result in report.get("task_results", [])
        if result.get("status") != "pass"
    )
    return AcceptanceCriterion(
        id="agentic_intent_harness_live_smoke",
        status="pass",
        citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
        evidence=(
            f"{len(live_reports)} live harness report(s) found; "
            f"attempted_tasks={attempted}, stabilized_tasks={stabilized}, failed_tasks={failed_tasks}"
        ),
    )


def _criterion(id: str, passed: bool, citation: str, evidence: str) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        id=id,
        status="pass" if passed else "fail",
        citation=citation,
        evidence=evidence,
    )


def _overall_status(criteria: list[AcceptanceCriterion]) -> str:
    if any(criterion.status == "fail" for criterion in criteria):
        return "fail"
    if any(criterion.status == "warn" for criterion in criteria):
        return "ready_with_warnings"
    return "pass"


def _planner() -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(model_id="acceptance-planner", family="planner-family", roles=("planner",), strength="strong"),
        responses=(
            {
                "steps": [
                    {
                        "verb": "Feature",
                        "success_question": "Did useful possibility increase?",
                        "budget_alloc": 1.0,
                        "model_role": "generator",
                    },
                    {
                        "verb": "Verify",
                        "success_question": "Is trust justified?",
                        "budget_alloc": 1.0,
                        "model_role": "verifier",
                    },
                ],
                "rationale": "Acceptance loop uses a deterministic oracle when available.",
            },
        ),
    )


def _generator(artifact: str) -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(
            model_id="acceptance-generator",
            family="generator-family",
            roles=("generator",),
            strength="standard",
        ),
        responses=(
            {
                "assumptions": [
                    {
                        "claim": "Plain text is sufficient for the acceptance artifact",
                        "depends_on": "The verifier checks textual content",
                        "confidence_rationale": "The oracle is deterministic",
                        "alternatives_considered": "JSON payload",
                    }
                ],
                "plan": "Emit the requested token.",
                "artifact": artifact,
                "self_identified_risks": ["The artifact might omit the required token."],
            },
        ),
    )


def _verifier(payload: dict[str, Any]) -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(
            model_id="acceptance-verifier",
            family="verifier-family",
            roles=("verifier",),
            strength="strong",
        ),
        responses=(payload,),
    )
