"""Deterministic verifier suite.

Three text-level checks give the grammar a cheap local discharge path; the
`python_tests` check executes a real unittest suite against the artifact in a
restricted worker, so an obligation can be discharged by observed behavior
rather than string comparison.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.blob_store import BlobStore
from syberruntime.errors import VerificationError
from syberruntime.models import ArtifactRef


MODEL_ORACLE_CHECK_KINDS = frozenset({"text_contains", "text_equals", "sha256_equals"})
SUPPORTED_DETERMINISTIC_CHECK_KINDS = MODEL_ORACLE_CHECK_KINDS | {"python_tests"}
DEFAULT_PYTHON_TESTS_TIMEOUT_SECONDS = 120.0
DEFAULT_PYTHON_TESTS_CPU_SECONDS = 30
DEFAULT_PYTHON_TESTS_MEMORY_MB = 256
MAX_PYTHON_TESTS_TIMEOUT_SECONDS = 300.0
MAX_PYTHON_TESTS_CPU_SECONDS = 120
MAX_PYTHON_TESTS_MEMORY_MB = 1024
_FAILURE_OUTPUT_TAIL_CHARS = 800


@dataclass(frozen=True)
class VerificationResult:
    kind: str
    passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "passed": self.passed,
            "details": self.details,
        }


class DeterministicVerifier:
    """Deterministic verifier set.

    Text checks compare content; `python_tests` executes behavior. The check
    payload is recorded verbatim in the operation log, so the oracle that
    discharged an obligation is always reconstructable from provenance.
    """

    def __init__(self, blobs: BlobStore) -> None:
        self.blobs = blobs

    def run(self, artifact: ArtifactRef, check: dict[str, Any]) -> VerificationResult:
        kind = str(check.get("kind", ""))
        if kind == "text_contains":
            expected = str(check["expected"])
            text = self.blobs.get_text(artifact)
            passed = expected in text
            return VerificationResult(
                kind=kind,
                passed=passed,
                details="expected substring found" if passed else "expected substring not found",
            )
        if kind == "text_equals":
            expected = str(check["expected"])
            text = self.blobs.get_text(artifact)
            passed = text == expected
            return VerificationResult(
                kind=kind,
                passed=passed,
                details="text matched exactly" if passed else "text differed",
            )
        if kind == "sha256_equals":
            expected = str(check["expected"])
            passed = artifact.digest == expected
            return VerificationResult(
                kind=kind,
                passed=passed,
                details="digest matched" if passed else "digest differed",
            )
        if kind == "python_tests":
            return self._run_python_tests(artifact, check)
        raise VerificationError(f"Unsupported deterministic check kind: {kind!r}")

    def _run_python_tests(self, artifact: ArtifactRef, check: dict[str, Any]) -> VerificationResult:
        test_source = str(check["test_source"])
        artifact_filename = str(check.get("artifact_filename", "artifact_under_test.py"))
        if artifact_filename != Path(artifact_filename).name or artifact_filename in {"", ".", ".."}:
            raise VerificationError(
                f"python_tests artifact_filename must be a bare filename: {artifact_filename!r}"
            )
        try:
            timeout_seconds = float(check.get("timeout_seconds", DEFAULT_PYTHON_TESTS_TIMEOUT_SECONDS))
            cpu_seconds = int(
                check.get("cpu_seconds", min(DEFAULT_PYTHON_TESTS_CPU_SECONDS, timeout_seconds))
            )
            memory_mb = int(check.get("memory_mb", DEFAULT_PYTHON_TESTS_MEMORY_MB))
        except (TypeError, ValueError, OverflowError) as exc:
            raise VerificationError("python_tests resource limits must be finite numbers") from exc
        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
            or timeout_seconds > MAX_PYTHON_TESTS_TIMEOUT_SECONDS
            or cpu_seconds <= 0
            or cpu_seconds > MAX_PYTHON_TESTS_CPU_SECONDS
            or memory_mb < 64
            or memory_mb > MAX_PYTHON_TESTS_MEMORY_MB
        ):
            raise VerificationError(
                "python_tests limits must satisfy: timeout_seconds in (0, 300], "
                "cpu_seconds in [1, 120], memory_mb in [64, 1024]"
            )
        extra_pythonpath = check.get("pythonpath", [])
        if not isinstance(extra_pythonpath, (list, tuple)) or not all(
            isinstance(item, str) for item in extra_pythonpath
        ):
            raise VerificationError("python_tests pythonpath must be a list of strings")

        resolved_pythonpath: list[str] = []
        for item in extra_pythonpath:
            path = Path(item).resolve(strict=True)
            if not path.is_dir():
                raise VerificationError(f"python_tests pythonpath entry must be a directory: {item!r}")
            resolved_pythonpath.append(str(path))

        content = self.blobs.get_text(artifact)
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp).resolve()
            (workdir / artifact_filename).write_text(content, encoding="utf-8")
            (workdir / "test_oracle_suite.py").write_text(test_source, encoding="utf-8")
            manifest = {
                "workdir": str(workdir),
                "read_roots": resolved_pythonpath,
                "memory_bytes": memory_mb * 1024 * 1024,
                "cpu_seconds": cpu_seconds,
            }
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(Path(__file__).with_name("execution_worker.py"))],
                    cwd=str(workdir),
                    env=_minimal_worker_environment(workdir),
                    input=json.dumps(manifest, sort_keys=True),
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds + 2.0,
                )
            except subprocess.TimeoutExpired:
                return VerificationResult(
                    kind="python_tests",
                    passed=False,
                    details=f"test execution timed out after {timeout_seconds}s",
                )

        if completed.returncode == 0:
            return VerificationResult(kind="python_tests", passed=True, details="test suite passed")
        output = (completed.stderr or "") + (completed.stdout or "")
        tail = output.strip()[-_FAILURE_OUTPUT_TAIL_CHARS:]
        return VerificationResult(
            kind="python_tests",
            passed=False,
            details=f"test suite failed (exit {completed.returncode}): {tail}",
        )


def _minimal_worker_environment(workdir: Path) -> dict[str, str]:
    env = {
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "TEMP": str(workdir),
        "TMP": str(workdir),
    }
    if os.name == "nt":
        for key in ("SystemRoot", "WINDIR"):
            value = os.environ.get(key)
            if value:
                env[key] = value
    return env
