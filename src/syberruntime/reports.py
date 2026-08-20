"""Shared IO for JSON evidence reports (harness, dogfood, acceptance).

All evidence reports are canonical-JSON files in a flat directory. Writers and
discovery live here so every report kind serializes and sorts identically.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from syberruntime.hashing import canonical_json, digest_json


def write_json_report(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload), encoding="utf-8")
    return path


def discover_json_reports(directory: str | Path) -> tuple[Path, ...]:
    path = Path(directory)
    if not path.exists():
        return ()
    return tuple(sorted(item for item in path.glob("*.json") if item.is_file()))


def read_json_report(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Report must be a JSON object: {path}")
    return data


def generated_at_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def workspace_root_for_evidence_path(path: str | Path) -> Path:
    """Choose the evidence workspace without assuming the process CWD."""

    candidate = Path(path)
    if not candidate.is_absolute():
        return Path.cwd()
    start = candidate.parent
    for parent in (start, *start.parents):
        if (parent / ".git").exists():
            return parent
    return start


def canonical_report_id(payload: dict[str, Any]) -> str:
    return digest_json({key: value for key, value in payload.items() if key != "report_id"})


def validate_canonical_report_id(payload: dict[str, Any], *, label: str) -> None:
    actual = payload.get("report_id")
    expected = canonical_report_id(payload)
    if actual != expected:
        raise ValueError(f"{label} report_id mismatch: expected {expected}, found {actual}")


def validate_generated_at(value: Any, *, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} generated_at must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} generated_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} generated_at must include a timezone")


def file_sha256(path: str | Path | None) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    return sha256(candidate.read_bytes()).hexdigest()


def build_evidence_binding(
    *,
    workspace_root: str | Path,
    protocol_path: str | Path | None = None,
    config_path: str | Path | None = None,
    runtime: Any | None = None,
    input_report_ids: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    revision, dirty = _git_state(root)
    binding: dict[str, Any] = {
        "schema_version": 1,
        "source_revision": revision,
        "source_dirty": dirty,
        "protocol_sha256": file_sha256(_resolve_workspace_path(root, protocol_path)),
        "config_sha256": file_sha256(_resolve_workspace_path(root, config_path)),
        "input_report_ids": sorted(str(item) for item in input_report_ids),
    }
    if runtime is not None:
        entries = runtime.log.entries(validate=True)
        binding.update(
            {
                "runtime_log_size": len(entries),
                "runtime_merkle_root": runtime.merkle_root_hash(),
                "runtime_tail_hash": entries[-1].entry_hash if entries else None,
            }
        )
    else:
        binding.update(
            {
                "runtime_log_size": None,
                "runtime_merkle_root": None,
                "runtime_tail_hash": None,
            }
        )
    return binding


def validate_evidence_binding(binding: Any, *, label: str) -> None:
    if not isinstance(binding, dict):
        raise ValueError(f"{label} evidence_binding must be an object")
    required = {
        "schema_version",
        "source_revision",
        "source_dirty",
        "protocol_sha256",
        "config_sha256",
        "runtime_log_size",
        "runtime_merkle_root",
        "runtime_tail_hash",
        "input_report_ids",
    }
    missing = sorted(required - set(binding))
    if missing:
        raise ValueError(f"{label} evidence_binding missing keys: {', '.join(missing)}")
    revision = binding["source_revision"]
    if revision != "unversioned" and not _is_lower_hex(revision, lengths={40, 64}):
        raise ValueError(f"{label} source_revision must be a 40/64-character lowercase hex revision")
    for key in ("protocol_sha256", "config_sha256", "runtime_merkle_root", "runtime_tail_hash"):
        value = binding[key]
        if value is not None and not _is_lower_hex(value, lengths={64}):
            raise ValueError(f"{label} {key} must be null or a canonical SHA-256 digest")
    if not isinstance(binding["source_dirty"], bool):
        raise ValueError(f"{label} source_dirty must be boolean")
    if not isinstance(binding["input_report_ids"], list):
        raise ValueError(f"{label} input_report_ids must be a list")
    if any(
        not _is_lower_hex(report_id, lengths={64})
        for report_id in binding["input_report_ids"]
    ):
        raise ValueError(f"{label} input_report_ids must contain canonical SHA-256 report IDs")
    if binding["input_report_ids"] != sorted(set(binding["input_report_ids"])):
        raise ValueError(f"{label} input_report_ids must be sorted and unique")
    log_size = binding["runtime_log_size"]
    if log_size is not None and (not isinstance(log_size, int) or isinstance(log_size, bool) or log_size < 0):
        raise ValueError(f"{label} runtime_log_size must be null or a nonnegative integer")
    if log_size == 0 and binding["runtime_tail_hash"] is not None:
        raise ValueError(f"{label} empty runtime binding cannot have a tail hash")


def verify_evidence_binding(
    binding: dict[str, Any],
    *,
    workspace_root: str | Path,
    label: str,
    protocol_path: str | Path | None = None,
    config_path: str | Path | None = None,
    runtime: Any | None = None,
) -> None:
    """Recompute every locally available evidence anchor.

    Required by v0.6 sections 3.7-3.8 and v1 section 7. A canonical report hash
    detects accidental drift; these comparisons prevent a self-consistent but
    detached report from satisfying acceptance.
    """

    validate_evidence_binding(binding, label=label)
    root = Path(workspace_root).resolve()
    for key, declared_path in (
        ("protocol_sha256", protocol_path),
        ("config_sha256", config_path),
    ):
        if declared_path is None:
            if binding[key] is not None:
                raise ValueError(f"{label} {key} is present without a declared path")
            continue
        resolved = _resolve_workspace_path(root, declared_path)
        if resolved is None or not resolved.is_file():
            raise ValueError(f"{label} declared evidence file is missing: {declared_path}")
        actual = file_sha256(resolved)
        if binding[key] != actual:
            raise ValueError(f"{label} {key} does not match {declared_path}")

    if runtime is None:
        if any(
            binding[key] is not None
            for key in ("runtime_log_size", "runtime_merkle_root", "runtime_tail_hash")
        ):
            raise ValueError(f"{label} has runtime anchors but no runtime was supplied")
    else:
        entries = runtime.log.entries(validate=True)
        expected = {
            "runtime_log_size": len(entries),
            "runtime_merkle_root": runtime.merkle_root_hash(),
            "runtime_tail_hash": entries[-1].entry_hash if entries else None,
        }
        for key, value in expected.items():
            if binding[key] != value:
                raise ValueError(f"{label} {key} does not match the runtime log")

    revision = binding["source_revision"]
    if revision != "unversioned":
        try:
            subprocess.run(
                ["git", "-C", str(root), "cat-file", "-e", f"{revision}^{{commit}}"],
                capture_output=True,
                timeout=5,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"{label} source_revision is not available in this repository") from exc


def _resolve_workspace_path(root: Path, path: str | Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _git_state(root: Path) -> tuple[str, bool]:
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        return revision, bool(status.strip())
    except (OSError, subprocess.SubprocessError):
        return "unversioned", True


def _is_lower_hex(value: Any, *, lengths: set[int]) -> bool:
    if not isinstance(value, str) or len(value) not in lengths:
        return False
    return all(char in "0123456789abcdef" for char in value)
