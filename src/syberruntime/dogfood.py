"""Dogfooding report support for RQ0/RQ6 evidence collection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.model_capability import model_capability_envelope
from syberruntime.reports import (
    build_evidence_binding,
    canonical_report_id,
    discover_json_reports,
    generated_at_utc,
    read_json_report,
    validate_canonical_report_id,
    validate_evidence_binding,
    validate_generated_at,
    workspace_root_for_evidence_path,
    write_json_report,
)
from syberruntime.runtime import Runtime


@dataclass(frozen=True)
class DogfoodReport:
    report_id: str
    protocol_path: str
    runtime_root: str
    artifact_digests: tuple[str, ...]
    metrics: dict[str, Any]
    notes: str
    model_capability_envelope: dict[str, Any]
    scope: str = "n=1 feasibility evidence"
    generated_at: str = ""
    evidence_binding: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "protocol_path": self.protocol_path,
            "runtime_root": self.runtime_root,
            "artifact_digests": list(self.artifact_digests),
            "metrics": self.metrics,
            "notes": self.notes,
            "model_capability_envelope": self.model_capability_envelope,
            "scope": self.scope,
            "generated_at": self.generated_at,
            "evidence_binding": self.evidence_binding or {},
        }


def create_dogfood_report(
    runtime: Runtime,
    *,
    protocol_path: str | Path,
    notes: str,
    artifact_digests: tuple[str, ...] | list[str] | None = None,
    model_constraints: tuple[str, ...] | list[str] | None = None,
    preferred_unavailable_models: tuple[str, ...] | list[str] | None = None,
    model_envelope_notes: str | None = None,
) -> DogfoodReport:
    state = runtime.rebuild_state()
    selected = tuple(artifact_digests or tuple(sorted(state.artifacts)))
    envelope = model_capability_envelope(
        constraints=model_constraints,
        preferred_unavailable_models=preferred_unavailable_models,
        notes=model_envelope_notes,
    )
    generated_at = generated_at_utc()
    binding = build_evidence_binding(
        workspace_root=workspace_root_for_evidence_path(protocol_path),
        protocol_path=protocol_path,
        runtime=runtime,
    )
    payload = {
        "protocol_path": str(protocol_path),
        "runtime_root": str(runtime.root),
        "artifact_digests": list(selected),
        "metrics": runtime.metrics().to_dict(),
        "notes": notes,
        "model_capability_envelope": envelope,
        "scope": "n=1 feasibility evidence",
        "generated_at": generated_at,
        "evidence_binding": binding,
    }
    return DogfoodReport(report_id=canonical_report_id(payload), **payload)


def write_dogfood_report(report: DogfoodReport, output_path: str | Path) -> Path:
    return write_json_report(report.to_dict(), output_path)


def discover_dogfood_reports(directory: str | Path) -> tuple[Path, ...]:
    return discover_json_reports(directory)


def load_dogfood_report(path: str | Path) -> DogfoodReport:
    data = read_json_report(path)
    validate_canonical_report_id(data, label="dogfood")
    validate_evidence_binding(data.get("evidence_binding"), label="dogfood")
    validate_generated_at(data.get("generated_at"), label="dogfood")
    return DogfoodReport(
        report_id=str(data["report_id"]),
        protocol_path=str(data["protocol_path"]),
        runtime_root=str(data["runtime_root"]),
        artifact_digests=tuple(str(item) for item in data.get("artifact_digests", [])),
        metrics=dict(data["metrics"]),
        notes=str(data.get("notes", "")),
        model_capability_envelope=dict(
            data.get("model_capability_envelope")
            or model_capability_envelope(
                constraints=("legacy report generated before explicit model capability envelope",)
            )
        ),
        scope=str(data.get("scope", "n=1 feasibility evidence")),
        generated_at=str(data["generated_at"]),
        evidence_binding=dict(data["evidence_binding"]),
    )
