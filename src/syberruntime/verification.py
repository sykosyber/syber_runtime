"""Deterministic verifier suite for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syberruntime.blob_store import BlobStore
from syberruntime.errors import VerificationError
from syberruntime.models import ArtifactRef


SUPPORTED_DETERMINISTIC_CHECK_KINDS = frozenset({"text_contains", "text_equals", "sha256_equals"})


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
    """Small deterministic verifier set.

    Phase 1 requires deterministic checks first. Code execution can be added as
    a stricter, sandboxed verifier later; these checks give the grammar a safe
    local discharge path immediately.
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
        raise VerificationError(f"Unsupported deterministic check kind: {kind!r}")
