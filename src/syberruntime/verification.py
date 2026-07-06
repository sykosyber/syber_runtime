"""Deterministic verifier suite.

Three text-level checks give the grammar a cheap local discharge path; the
`python_tests` check executes a real unittest suite against the artifact in a
subprocess, so an obligation can be discharged by observed behavior rather
than string comparison.

Safety boundary: `python_tests` runs unsandboxed on the local machine. It is
only reachable through runtime- or harness-supplied checks; model-supplied
`checkable_oracle` payloads are restricted to MODEL_ORACLE_CHECK_KINDS (the
text checks) precisely so a model response can never cause code execution.
"""

from __future__ import annotations

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
        timeout_seconds = float(check.get("timeout_seconds", DEFAULT_PYTHON_TESTS_TIMEOUT_SECONDS))
        extra_pythonpath = check.get("pythonpath", [])
        if not isinstance(extra_pythonpath, (list, tuple)) or not all(
            isinstance(item, str) for item in extra_pythonpath
        ):
            raise VerificationError("python_tests pythonpath must be a list of strings")

        content = self.blobs.get_text(artifact)
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / artifact_filename).write_text(content, encoding="utf-8")
            (workdir / "test_oracle_suite.py").write_text(test_source, encoding="utf-8")
            env = dict(os.environ)
            path_entries = [str(workdir), *extra_pythonpath]
            existing = env.get("PYTHONPATH")
            if existing:
                path_entries.append(existing)
            env["PYTHONPATH"] = os.pathsep.join(path_entries)
            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "unittest", "test_oracle_suite"],
                    cwd=str(workdir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
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
