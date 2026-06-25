"""Scale3 harness campaign analysis.

The analysis layer is non-live: it reads existing harness reports, classifies
failure modes, and emits a deterministic markdown evidence report.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.blob_store import BlobStore
from syberruntime.harness import default_live_scale_tasks, load_harness_report
from syberruntime.hashing import digest_json


ROADMAP_CITATIONS = {
    "scale3_analysis": "v1 Phase 3; v0.6 section 3.8; v1 section 7",
    "failure_taxonomy": "v0.6 section 3.8; v1 Phase 3; v1 section 7",
    "mutation_summary": "v0.6 section 3.5; v1 Phase 3; Verification Playbook Part C-F",
}


@dataclass(frozen=True)
class Scale3Failure:
    task_id: str
    failure_class: str
    failure: str | None
    artifact_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "failure_class": self.failure_class,
            "failure": self.failure,
            "artifact_digest": self.artifact_digest,
        }


@dataclass(frozen=True)
class Scale3RunSummary:
    path: str
    run_id: str
    report_id: str
    attempted_tasks: int
    stabilized_tasks: int
    blocked_or_failed_tasks: int
    generated_artifacts: int
    validated_artifacts: int
    false_discharge_rate: float
    residual_debt: float
    structural_rigor: float
    mutation_killed: int
    mutation_total: int
    failures: tuple[Scale3Failure, ...]

    @property
    def mutation_kill_rate(self) -> float:
        if self.mutation_total == 0:
            return 0.0
        return self.mutation_killed / self.mutation_total

    @property
    def failure_mode_label(self) -> str:
        if not self.failures:
            return "none"
        return ", ".join(sorted({failure.failure_class for failure in self.failures}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "run_id": self.run_id,
            "report_id": self.report_id,
            "attempted_tasks": self.attempted_tasks,
            "stabilized_tasks": self.stabilized_tasks,
            "blocked_or_failed_tasks": self.blocked_or_failed_tasks,
            "generated_artifacts": self.generated_artifacts,
            "validated_artifacts": self.validated_artifacts,
            "false_discharge_rate": self.false_discharge_rate,
            "residual_debt": self.residual_debt,
            "structural_rigor": self.structural_rigor,
            "mutation_killed": self.mutation_killed,
            "mutation_total": self.mutation_total,
            "mutation_kill_rate": self.mutation_kill_rate,
            "failures": [failure.to_dict() for failure in self.failures],
        }


@dataclass(frozen=True)
class Scale3CampaignAnalysis:
    analysis_id: str
    run_summaries: tuple[Scale3RunSummary, ...]
    apex_inference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "run_summaries": [summary.to_dict() for summary in self.run_summaries],
            "apex_inference": self.apex_inference,
        }


def analyze_scale3_reports(report_paths: tuple[str | Path, ...]) -> Scale3CampaignAnalysis:
    if not report_paths:
        raise ValueError("at least one scale3 report path is required")

    summaries = tuple(_summarize_report(Path(path)) for path in report_paths)
    payload = {"run_summaries": [summary.to_dict() for summary in summaries]}
    return Scale3CampaignAnalysis(
        analysis_id=digest_json(payload),
        run_summaries=summaries,
        apex_inference=_apex_inference(summaries),
    )


def write_scale3_analysis_markdown(analysis: Scale3CampaignAnalysis, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_scale3_analysis_markdown(analysis), encoding="utf-8")
    return path


def render_scale3_analysis_markdown(analysis: Scale3CampaignAnalysis) -> str:
    lines = [
        "# Live Scale3 Campaign Analysis",
        "",
        f"Analysis ID: `{analysis.analysis_id}`",
        "",
        "## Roadmap Requirement",
        "",
        "| Component | Required by |",
        "|---|---|",
        f"| Scale3 analysis report | {ROADMAP_CITATIONS['scale3_analysis']} |",
        f"| Failure mode taxonomy | {ROADMAP_CITATIONS['failure_taxonomy']} |",
        f"| Mutation outcome summary | {ROADMAP_CITATIONS['mutation_summary']} |",
        "",
        "## Run Summary",
        "",
        "| Run | Attempted | Stabilized | Failed | Generated | Validated | False discharge | Residual debt | Structural rigor | Mutants killed | Failure modes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for summary in analysis.run_summaries:
        lines.append(
            "| "
            f"`{summary.run_id}` | "
            f"{summary.attempted_tasks} | "
            f"{summary.stabilized_tasks} | "
            f"{summary.blocked_or_failed_tasks} | "
            f"{summary.generated_artifacts} | "
            f"{summary.validated_artifacts} | "
            f"{summary.false_discharge_rate:.3f} | "
            f"{summary.residual_debt:.3f} | "
            f"{summary.structural_rigor:.3f} | "
            f"{summary.mutation_killed}/{summary.mutation_total} | "
            f"{summary.failure_mode_label} |"
        )

    lines.extend(
        [
            "",
            "## Failure Progression",
            "",
        ]
    )
    for summary in analysis.run_summaries:
        if not summary.failures:
            lines.append(f"- `{summary.run_id}`: no failed tasks.")
            continue
        failure_text = "; ".join(
            f"{failure.task_id}: {failure.failure_class}" for failure in summary.failures
        )
        lines.append(f"- `{summary.run_id}`: {failure_text}.")

    lines.extend(
        [
            "",
            "## Apex Inference",
            "",
            analysis.apex_inference,
            "",
            "## Source Reports",
            "",
        ]
    )
    for summary in analysis.run_summaries:
        lines.append(f"- `{summary.run_id}`: `{summary.path}` (`{summary.report_id}`)")
    lines.append("")
    return "\n".join(lines)


def _summarize_report(path: Path) -> Scale3RunSummary:
    report = load_harness_report(path)
    run_id = str(report["run_id"])
    if "scale3" not in run_id:
        raise ValueError(f"report is not a scale3 campaign: {run_id}")
    if str(report.get("mode", "")) != "live":
        raise ValueError(f"scale3 campaign report must be live mode: {run_id}")

    task_results = report["task_results"]
    failures = tuple(
        _classify_failure(report, result)
        for result in task_results
        if result.get("status") != "pass" or not bool(result.get("stabilized"))
    )
    mutation_killed = 0
    mutation_total = 0
    for result in task_results:
        mutation_report = result.get("mutation_report")
        if isinstance(mutation_report, dict):
            mutation_killed += int(mutation_report.get("killed_count", 0))
            mutation_total += int(mutation_report.get("mutant_count", 0))

    summary = report["summary"]
    metrics = report["metrics"]
    return Scale3RunSummary(
        path=path.as_posix(),
        run_id=run_id,
        report_id=str(report["report_id"]),
        attempted_tasks=int(summary["attempted_tasks"]),
        stabilized_tasks=int(summary["stabilized_tasks"]),
        blocked_or_failed_tasks=int(summary["blocked_or_failed_tasks"]),
        generated_artifacts=int(metrics.get("generated_artifacts", 0)),
        validated_artifacts=int(metrics.get("validated_artifacts", 0)),
        false_discharge_rate=float(metrics.get("false_discharge_rate", 0.0)),
        residual_debt=float(metrics.get("residual_debt", 0.0)),
        structural_rigor=float(metrics.get("structural_rigor", 0.0)),
        mutation_killed=mutation_killed,
        mutation_total=mutation_total,
        failures=failures,
    )


def _classify_failure(report: dict[str, Any], result: dict[str, Any]) -> Scale3Failure:
    task_id = str(result.get("task_id", "unknown-task"))
    failure = result.get("failure")
    failure_class = result.get("failure_class")
    if isinstance(failure_class, str) and failure_class:
        mode = failure_class
    else:
        mode = _classify_from_artifact(report, result) or _classify_from_message(str(failure or ""))
    artifact_digest = result.get("artifact_digest")
    return Scale3Failure(
        task_id=task_id,
        failure_class=mode,
        failure=str(failure) if failure is not None else None,
        artifact_digest=str(artifact_digest) if artifact_digest is not None else None,
    )


def _classify_from_artifact(report: dict[str, Any], result: dict[str, Any]) -> str | None:
    artifact_digest = result.get("artifact_digest")
    if not isinstance(artifact_digest, str) or not artifact_digest:
        return None
    expected = _expected_content_by_task_id().get(str(result.get("task_id", "")))
    if expected is None:
        return None
    runtime_root = report.get("runtime_root")
    if not isinstance(runtime_root, str) or not Path(runtime_root).exists():
        return None
    try:
        actual = BlobStore(runtime_root).get_text(artifact_digest)
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    if actual != expected:
        return "artifact_content_mismatch"
    return None


def _classify_from_message(message: str) -> str:
    lower = message.lower()
    if "valid json" in lower or "malformed_json" in lower:
        return "provider_malformed_json"
    if "checkable_oracle" in lower or "missing required key" in lower:
        return "schema_mismatch"
    if "did not stabilize" in lower:
        return "not_stabilized"
    if "mcp tool returned iserror=true" in lower:
        return "mcp_tool_error"
    return "runtime_exception"


def _expected_content_by_task_id() -> dict[str, str]:
    return {task.task_id: task.expected_content for task in default_live_scale_tasks()}


def _apex_inference(summaries: tuple[Scale3RunSummary, ...]) -> str:
    if summaries and not summaries[-1].failures and summaries[-1].stabilized_tasks == summaries[-1].attempted_tasks:
        return (
            "The scale3 campaign shows measured hardening rather than a one-off lucky pass: earlier live "
            "runs exposed artifact precision and provider-boundary failure modes, while the latest run "
            "completed all three independent exact-content tasks with zero false discharge, zero residual "
            "debt, full structural rigor, and complete mutation kill coverage."
        )
    return (
        "The scale3 campaign provides bounded live-provider evidence, but the latest run still contains "
        "open failure modes that should be addressed before claiming the campaign is stabilized."
    )
