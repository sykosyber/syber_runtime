"""V1 acceptance audit derived from the roadmap's done criteria."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.adapter_config import load_adapter_bundle
from syberruntime.adapters import ScriptedModelAdapter
from syberruntime.ai_contracts import ModelSpec
from syberruntime.dogfood import discover_dogfood_reports, load_dogfood_report
from syberruntime.empirical import (
    conformal_gate_passes,
    discover_empirical_reports,
    load_empirical_report,
    rq0_rq6_gate_passes,
)
from syberruntime.errors import AdapterError, SyberRuntimeError
from syberruntime.harness import discover_harness_reports, load_harness_report
from syberruntime.policy import FixedPolicy
from syberruntime.reports import (
    build_evidence_binding,
    canonical_report_id,
    file_sha256,
    generated_at_utc,
    read_json_report,
    validate_canonical_report_id,
    validate_evidence_binding,
    validate_generated_at,
    verify_evidence_binding,
)
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
    report_id: str
    overall_status: str
    criteria: tuple[AcceptanceCriterion, ...]
    generated_at: str
    evidence_binding: dict[str, Any]

    @property
    def failures(self) -> tuple[AcceptanceCriterion, ...]:
        return tuple(criterion for criterion in self.criteria if criterion.status == "fail")

    @property
    def warnings(self) -> tuple[AcceptanceCriterion, ...]:
        return tuple(criterion for criterion in self.criteria if criterion.status == "warn")

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "overall_status": self.overall_status,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "failure_count": len(self.failures),
            "warning_count": len(self.warnings),
            "generated_at": self.generated_at,
            "evidence_binding": self.evidence_binding,
        }


def run_v1_acceptance_audit(
    *,
    workspace_root: str | Path | None = None,
    mcp_config_path: str | Path | None = None,
    dogfood_report_dir: str | Path | None = None,
    agent_harness_report_dir: str | Path | None = None,
    empirical_report_dir: str | Path | None = None,
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
    empirical_reports_dir = (
        Path(empirical_report_dir)
        if empirical_report_dir is not None
        else root / "docs" / "empirical_reports"
    )
    criteria.extend(
        _audit_workspace_artifacts(
            root,
            dogfood_report_dir=reports_dir,
            agent_harness_report_dir=harness_reports_dir,
            empirical_report_dir=empirical_reports_dir,
        )
    )
    overall = _overall_status(criteria)
    generated_at = generated_at_utc()
    input_report_ids = _input_report_ids(reports_dir, harness_reports_dir, empirical_reports_dir)
    binding = build_evidence_binding(
        workspace_root=root,
        config_path=mcp_config_path,
        input_report_ids=input_report_ids,
    )
    payload = {
        "overall_status": overall,
        "criteria": [criterion.to_dict() for criterion in criteria],
        "failure_count": sum(1 for criterion in criteria if criterion.status == "fail"),
        "warning_count": sum(1 for criterion in criteria if criterion.status == "warn"),
        "generated_at": generated_at,
        "evidence_binding": binding,
    }
    return AcceptanceReport(
        report_id=canonical_report_id(payload),
        overall_status=overall,
        criteria=tuple(criteria),
        generated_at=generated_at,
        evidence_binding=binding,
    )


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
    empirical_report_dir: Path,
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
        _audit_dogfood_reports(dogfood_report_dir, root),
        _audit_agent_harness_reports(agent_harness_report_dir, root),
        _audit_live_agent_harness_reports(agent_harness_report_dir, root),
        _audit_live_scale3_campaign(agent_harness_report_dir, root),
        _audit_live_code_campaign(agent_harness_report_dir, root),
        *_audit_empirical_reports(empirical_report_dir, root),
    ]
    return criteria


def _audit_empirical_reports(report_dir: Path, root: Path) -> list[AcceptanceCriterion]:
    citations = {
        "heldout_conformal_coverage": "v1 Phase 2 acceptance; v1 section 4.4; v1 section 7",
        "rq0_rq6_controlled_baseline": "v0.6 RQ0 and RQ6; v1 Phase 3 acceptance; v1 section 7",
    }
    reports = discover_empirical_reports(report_dir)
    if not reports:
        return [
            AcceptanceCriterion(
                id=report_type,
                status="fail",
                citation=citation,
                evidence="required empirical report directory is empty or missing",
            )
            for report_type, citation in citations.items()
        ]
    try:
        loaded = [load_empirical_report(path) for path in reports]
        for report in loaded:
            runtime = _report_runtime(root, report)
            verify_evidence_binding(
                report["evidence_binding"],
                workspace_root=root,
                label="empirical",
                protocol_path=report.get("protocol_path"),
                runtime=runtime,
            )
            if runtime is not None:
                _verify_empirical_runtime_claims(report, runtime)
    except (OSError, ValueError, KeyError) as exc:
        return [
            AcceptanceCriterion(
                id=report_type,
                status="fail",
                citation=citation,
                evidence=f"empirical report directory contains invalid evidence: {exc}",
            )
            for report_type, citation in citations.items()
        ]

    by_type: dict[str, list[dict[str, Any]]] = {}
    for report in loaded:
        by_type.setdefault(str(report["report_type"]), []).append(report)

    conformal_reports = by_type.get("heldout_conformal_coverage", [])
    conformal = _latest_report(conformal_reports) if conformal_reports else None
    conformal_passed = conformal is not None and conformal_gate_passes(conformal)
    conformal_result = conformal.get("result", {}) if conformal is not None else {}

    controlled_reports = by_type.get("rq0_rq6_controlled_baseline", [])
    controlled = _latest_report(controlled_reports) if controlled_reports else None
    controlled_passed = controlled is not None and rq0_rq6_gate_passes(controlled)
    return [
        AcceptanceCriterion(
            id="heldout_conformal_coverage",
            status="pass" if conformal_passed else "fail",
            citation=citations["heldout_conformal_coverage"],
            evidence=(
                f"reports={len(conformal_reports)}; calibration_count="
                f"{conformal_result.get('calibration_count')}; heldout_count="
                f"{conformal_result.get('heldout_count')}; empirical_coverage="
                f"{conformal_result.get('empirical_coverage')}; nominal="
                f"{1.0 - _safe_float(conformal_result.get('alpha'), 1.0):.3f}"
            ),
        ),
        AcceptanceCriterion(
            id="rq0_rq6_controlled_baseline",
            status="pass" if controlled_passed else "fail",
            citation=citations["rq0_rq6_controlled_baseline"],
            evidence=(
                f"reports={len(controlled_reports)}; both RQ0 arms and both RQ6 arms "
                f"completed with preregistered known-bad rejection={controlled_passed}"
            ),
        ),
    ]


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
            intent="Create a local text artifact whose content is exactly 'live-mcp-acceptance-token\n'.",
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


def _audit_dogfood_reports(report_dir: Path, root: Path) -> AcceptanceCriterion:
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
        raw_reports = [json.loads(path.read_text(encoding="utf-8")) for path in reports]
        for report, raw_report in zip(loaded, raw_reports, strict=True):
            runtime = Runtime(_resolve_report_path(root, report.runtime_root))
            verify_evidence_binding(
                raw_report["evidence_binding"],
                workspace_root=root,
                label="dogfood",
                protocol_path=report.protocol_path,
                runtime=runtime,
            )
            if report.metrics != runtime.metrics().to_dict():
                raise ValueError("dogfood metrics do not match the bound runtime")
            state = runtime.rebuild_state()
            if any(digest not in state.artifacts for digest in report.artifact_digests):
                raise ValueError("dogfood artifact digest is not present in the bound runtime")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return AcceptanceCriterion(
            id="dogfooding_rq0_rq6_results",
            status="fail",
            citation="v0.6 section 6; v1 Phase 3; v1 section 7",
            evidence=f"dogfooding report directory contains an invalid report: {exc}",
        )
    problems: list[str] = []
    for path, report, raw_report in zip(reports, loaded, raw_reports, strict=True):
        if not report.artifact_digests:
            problems.append(f"{path.name} has no artifact digests")
        envelope = raw_report.get("model_capability_envelope")
        if not isinstance(envelope, dict):
            problems.append(f"{path.name} has no explicit model capability envelope")
        elif not envelope.get("claim_scope") or not envelope.get("interpretation"):
            problems.append(f"{path.name} has an incomplete model capability envelope")
    if problems:
        return AcceptanceCriterion(
            id="dogfooding_rq0_rq6_results",
            status="fail",
            citation="v0.6 section 6; v1 Phase 3; v1 section 7",
            evidence="; ".join(problems),
        )
    artifact_count = sum(len(report.artifact_digests) for report in loaded)
    return AcceptanceCriterion(
        id="dogfooding_rq0_rq6_results",
        status="pass",
        citation="v0.6 section 6; v1 Phase 3; v1 section 7",
        evidence=(
            f"{len(loaded)} dogfooding report(s) found under the pre-registered protocol; "
            f"artifact_digests={artifact_count}; model capability envelopes present"
        ),
    )


def _audit_agent_harness_reports(report_dir: Path, root: Path) -> AcceptanceCriterion:
    reports = discover_harness_reports(report_dir)
    if not reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_baseline",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 3; v1 section 6; v1 section 7",
            evidence="agentic intent harness exists, but no baseline harness report was found",
        )
    try:
        loaded = _load_bound_harness_reports(reports, root)
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


def _audit_live_agent_harness_reports(report_dir: Path, root: Path) -> AcceptanceCriterion:
    reports = discover_harness_reports(report_dir)
    if not reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_live_smoke",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence="no live-mode agentic harness report was found",
        )
    try:
        loaded = _load_bound_harness_reports(reports, root)
    except (OSError, ValueError, KeyError) as exc:
        return AcceptanceCriterion(
            id="agentic_intent_harness_live_smoke",
            status="fail",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence=f"agentic harness report directory contains an invalid report: {exc}",
        )
    live_reports = [
        report
        for report in loaded
        if str(report.get("mode", "scripted")) == "live"
        and "scale3" not in str(report.get("run_id", ""))
        and "code" not in str(report.get("run_id", ""))
    ]
    if not live_reports:
        return AcceptanceCriterion(
            id="agentic_intent_harness_live_smoke",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence="scripted harness baseline exists, but no live-mode harness report was found",
        )
    latest = _latest_report(live_reports)
    summary = latest["summary"]
    attempted = _safe_int(summary.get("attempted_tasks"), 0)
    stabilized = _safe_int(summary.get("stabilized_tasks"), 0)
    failed_tasks = _safe_int(summary.get("blocked_or_failed_tasks"), attempted)
    passed = attempted >= 1 and stabilized == attempted and failed_tasks == 0
    return AcceptanceCriterion(
        id="agentic_intent_harness_live_smoke",
        status="pass" if passed else "fail",
        citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
        evidence=(
            f"{len(live_reports)} direct live smoke report(s) found; latest_run={latest['run_id']}; "
            f"attempted_tasks={attempted}, stabilized_tasks={stabilized}, failed_tasks={failed_tasks}"
        ),
    )


def _audit_live_scale3_campaign(report_dir: Path, root: Path) -> AcceptanceCriterion:
    reports = discover_harness_reports(report_dir)
    if not reports:
        return AcceptanceCriterion(
            id="live_scale3_campaign",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence="no agentic harness reports were found, so no live scale3 campaign evidence is available",
        )
    try:
        loaded = _load_bound_harness_reports(reports, root)
    except (OSError, ValueError, KeyError) as exc:
        return AcceptanceCriterion(
            id="live_scale3_campaign",
            status="fail",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence=f"agentic harness report directory contains an invalid report: {exc}",
        )
    scale3_reports = [
        report
        for report in loaded
        if str(report.get("mode", "scripted")) == "live" and "scale3" in str(report.get("run_id", ""))
    ]
    if not scale3_reports:
        return AcceptanceCriterion(
            id="live_scale3_campaign",
            status="warn",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence="live harness reports exist, but no live scale3 campaign report was found",
        )
    latest = _latest_report(scale3_reports)
    if not _live_scale3_report_passes(latest):
        return AcceptanceCriterion(
            id="live_scale3_campaign",
            status="fail",
            citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
            evidence=(
                f"{len(scale3_reports)} live scale3 campaign report(s) found, but latest_run="
                f"{latest.get('run_id')} did not satisfy the gate"
            ),
        )
    summary = latest["summary"]
    metrics = latest["metrics"]
    killed, total = _mutation_totals(latest)
    return AcceptanceCriterion(
        id="live_scale3_campaign",
        status="pass",
        citation="v0.6 section 3.8; v1 Phase 2; v1 Phase 3; v1 section 7",
        evidence=(
            f"{len(scale3_reports)} live scale3 campaign report(s) found; "
            f"passing_run={latest['run_id']}; "
            f"attempted_tasks={summary.get('attempted_tasks')}, "
            f"stabilized_tasks={summary.get('stabilized_tasks')}, "
            f"validated_artifacts={metrics.get('validated_artifacts')}, "
            f"false_discharge_rate={float(metrics.get('false_discharge_rate', 0.0)):.3f}, "
            f"residual_debt={float(metrics.get('residual_debt', 0.0)):.3f}, "
            f"mutants_killed={killed}/{total}"
        ),
    )


def _audit_live_code_campaign(report_dir: Path, root: Path) -> AcceptanceCriterion:
    reports = discover_harness_reports(report_dir)
    citation = "v0.6 sections 3.5 and 3.8; v1 Phase 1; v1 Phase 3; v1 section 7"
    if not reports:
        return AcceptanceCriterion(
            id="live_code_behavioral_campaign",
            status="warn",
            citation=citation,
            evidence="no agentic harness reports were found, so no hard live code evidence is available",
        )
    try:
        loaded = _load_bound_harness_reports(reports, root)
    except (OSError, ValueError, KeyError) as exc:
        return AcceptanceCriterion(
            id="live_code_behavioral_campaign",
            status="fail",
            citation=citation,
            evidence=f"agentic harness report directory contains an invalid report: {exc}",
        )
    code_reports = [
        report
        for report in loaded
        if str(report.get("mode", "scripted")) == "live" and "code" in str(report.get("run_id", ""))
    ]
    if not code_reports:
        return AcceptanceCriterion(
            id="live_code_behavioral_campaign",
            status="warn",
            citation=citation,
            evidence="live harness reports exist, but no hard live code campaign report was found",
        )
    latest = _latest_report(code_reports)
    task_results = latest.get("task_results", [])
    passed = bool(task_results)
    killed = 0
    total = 0
    for result in task_results:
        mutation = result.get("mutation_report") if isinstance(result, dict) else None
        if result.get("status") != "pass" or not result.get("stabilized") or not isinstance(mutation, dict):
            passed = False
            continue
        check = mutation.get("check", {})
        operators = [item.get("operator", "") for item in mutation.get("results", []) if isinstance(item, dict)]
        if (
            mutation.get("baseline_passed") is not True
            or not isinstance(check, dict)
            or check.get("kind") != "python_tests"
            or not operators
            or any(not str(operator).startswith("ast_") for operator in operators)
        ):
            passed = False
        killed += _safe_int(mutation.get("killed_count"), 0)
        total += _safe_int(mutation.get("mutant_count"), 0)
    passed = passed and total > 0 and killed == total
    return AcceptanceCriterion(
        id="live_code_behavioral_campaign",
        status="pass" if passed else "fail",
        citation=citation,
        evidence=(
            f"{len(code_reports)} hard live code report(s) found; latest_run={latest.get('run_id')}; "
            f"tasks={len(task_results)}, mutants_killed={killed}/{total}; "
            "required_oracle=python_tests; required_mutation_family=ast"
        ),
    )


def _live_scale3_report_passes(report: dict[str, Any]) -> bool:
    summary = report.get("summary", {})
    metrics = report.get("metrics", {})
    task_results = report.get("task_results", [])
    if not isinstance(summary, dict) or not isinstance(metrics, dict) or not isinstance(task_results, list):
        return False
    attempted = _safe_int(summary.get("attempted_tasks"), 0)
    stabilized = _safe_int(summary.get("stabilized_tasks"), 0)
    failed = _safe_int(summary.get("blocked_or_failed_tasks"), 0)
    validated = _safe_int(metrics.get("validated_artifacts"), 0)
    if attempted < 3 or stabilized != attempted or failed != 0 or validated < 3:
        return False
    if _safe_float(metrics.get("false_discharge_rate"), 1.0) != 0.0:
        return False
    if _safe_float(metrics.get("residual_debt"), 1.0) != 0.0:
        return False
    if _safe_float(metrics.get("structural_rigor"), 0.0) < 1.0:
        return False
    if any(result.get("status") != "pass" or not bool(result.get("stabilized")) for result in task_results):
        return False
    killed, total = _mutation_totals(report)
    return total >= attempted and killed == total


def _mutation_totals(report: dict[str, Any]) -> tuple[int, int]:
    killed = 0
    total = 0
    for result in report.get("task_results", []):
        mutation_report = result.get("mutation_report") if isinstance(result, dict) else None
        if not isinstance(mutation_report, dict):
            continue
        if mutation_report.get("baseline_passed") is False:
            return killed, total + 1
        killed += _safe_int(mutation_report.get("killed_count"), 0)
        total += _safe_int(mutation_report.get("mutant_count"), 0)
    return killed, total


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    return max(reports, key=lambda report: (str(report.get("generated_at", "")), str(report.get("run_id", ""))))


def _load_bound_harness_reports(reports: tuple[Path, ...], root: Path) -> list[dict[str, Any]]:
    loaded = [load_harness_report(path) for path in reports]
    for report in loaded:
        runtime = Runtime(_resolve_report_path(root, report["runtime_root"]))
        verify_evidence_binding(
            report["evidence_binding"],
            workspace_root=root,
            label="harness",
            protocol_path=report.get("protocol_path"),
            config_path=report.get("provider_config_path"),
            runtime=runtime,
        )
        _verify_harness_runtime_claims(report, runtime)
    return loaded


def _verify_harness_runtime_claims(report: dict[str, Any], runtime: Runtime) -> None:
    if report.get("metrics") != runtime.metrics().to_dict():
        raise ValueError("harness metrics do not match the bound runtime")
    state = runtime.rebuild_state()
    measurements = [
        operation.params["measurement"]
        for operation in state.operations.values()
        if isinstance(operation.params.get("measurement"), dict)
        and operation.params["measurement"].get("kind") == "mutation_campaign"
    ]
    for result in report.get("task_results", []):
        digest = result.get("artifact_digest")
        if digest is not None:
            artifact = state.artifacts.get(str(digest))
            if artifact is None:
                raise ValueError("harness task artifact is not present in the bound runtime")
            if bool(result.get("stabilized")) != (artifact.stabilized_by is not None):
                raise ValueError("harness stabilization claim does not match the bound runtime")
        mutation = result.get("mutation_report")
        if isinstance(mutation, dict):
            if not any(
                all(measurement.get(key) == value for key, value in mutation.items())
                for measurement in measurements
            ):
                raise ValueError("harness mutation report is not present in the bound runtime")


def _verify_empirical_runtime_claims(report: dict[str, Any], runtime: Runtime) -> None:
    if report.get("report_type") != "rq0_rq6_controlled_baseline":
        return
    operation_arm = report.get("result", {}).get("rq0", {}).get("operation_primary", {})
    metrics = runtime.metrics()
    if operation_arm.get("action_cost") != metrics.action_cost:
        raise ValueError("empirical RQ0 action_cost does not match the bound runtime")
    if operation_arm.get("provenance_completeness") != metrics.provenance_completeness:
        raise ValueError("empirical RQ0 provenance does not match the bound runtime")


def _report_runtime(root: Path, report: dict[str, Any]) -> Runtime | None:
    runtime_root = report.get("runtime_root")
    if runtime_root is None:
        return None
    return Runtime(_resolve_report_path(root, runtime_root))


def _resolve_report_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _input_report_ids(*directories: Path) -> list[str]:
    report_ids: list[str] = []
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                data = read_json_report(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            report_id = data.get("report_id")
            if isinstance(report_id, str):
                report_ids.append(report_id)
    return report_ids


def validate_acceptance_report(data: dict[str, Any]) -> None:
    validate_canonical_report_id(data, label="acceptance")
    validate_evidence_binding(data.get("evidence_binding"), label="acceptance")
    validate_generated_at(data.get("generated_at"), label="acceptance")
    criteria = data.get("criteria")
    if not isinstance(criteria, list):
        raise ValueError("acceptance criteria must be a list")
    failures = sum(1 for item in criteria if isinstance(item, dict) and item.get("status") == "fail")
    warnings = sum(1 for item in criteria if isinstance(item, dict) and item.get("status") == "warn")
    if data.get("failure_count") != failures or data.get("warning_count") != warnings:
        raise ValueError("acceptance failure/warning counts do not match criteria")
    expected_status = "fail" if failures else ("ready_with_warnings" if warnings else "pass")
    if data.get("overall_status") != expected_status:
        raise ValueError("acceptance overall_status does not match criteria")


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
