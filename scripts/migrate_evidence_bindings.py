"""Upgrade tracked harness and dogfood reports to canonical bound evidence.

Required by v0.6 sections 3.7-3.8 and v1 section 7. The migration replays each
referenced runtime, recomputes derived metrics/summaries, binds protocol/config
digests and log identity, then replaces the report ID last.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from syberruntime.dogfood import load_dogfood_report
from syberruntime.harness import load_harness_report
from syberruntime.reports import (
    build_evidence_binding,
    canonical_report_id,
    read_json_report,
    write_json_report,
)
from syberruntime.runtime import Runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".")
    args = parser.parse_args()
    root = Path(args.workspace_root).resolve()

    for path in sorted((root / "docs" / "agentic_harness_reports").glob("*.json")):
        _migrate_harness(root, path)
        load_harness_report(path)
    for path in sorted((root / "docs" / "dogfood_reports").glob("*.json")):
        _migrate_dogfood(root, path)
        load_dogfood_report(path)
    return 0


def _migrate_harness(root: Path, path: Path) -> None:
    data = read_json_report(path)
    runtime = Runtime(_resolve(root, data["runtime_root"]))
    task_results = data.get("task_results", [])
    data["summary"] = {
        "attempted_tasks": len(task_results),
        "stabilized_tasks": sum(1 for result in task_results if bool(result.get("stabilized"))),
        "blocked_or_failed_tasks": sum(
            1 for result in task_results if result.get("status") != "pass" or not bool(result.get("stabilized"))
        ),
    }
    data["metrics"] = runtime.metrics().to_dict()
    data["generated_at"] = _runtime_generated_at(runtime, path)
    data["evidence_binding"] = build_evidence_binding(
        workspace_root=root,
        protocol_path=data.get("protocol_path"),
        config_path=data.get("provider_config_path"),
        runtime=runtime,
    )
    data["report_id"] = canonical_report_id(data)
    write_json_report(data, path)


def _migrate_dogfood(root: Path, path: Path) -> None:
    data = read_json_report(path)
    runtime = Runtime(_resolve(root, data["runtime_root"]))
    data["metrics"] = runtime.metrics().to_dict()
    data["generated_at"] = _runtime_generated_at(runtime, path)
    data["evidence_binding"] = build_evidence_binding(
        workspace_root=root,
        protocol_path=data.get("protocol_path"),
        runtime=runtime,
    )
    data["report_id"] = canonical_report_id(data)
    write_json_report(data, path)


def _runtime_generated_at(runtime: Runtime, report_path: Path) -> str:
    timestamps = [
        entry.operation.provenance.ts
        for entry in runtime.log.entries(validate=True)
        if entry.operation.provenance.ts
    ]
    if timestamps:
        return max(timestamps)
    return datetime.fromtimestamp(report_path.stat().st_mtime, timezone.utc).isoformat()


def _resolve(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    raise SystemExit(main())
