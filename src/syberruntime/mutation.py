"""Mutation testing harness for measured discharge efficiency."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from syberruntime.blob_store import BlobStore
from syberruntime.hashing import normalize_json
from syberruntime.models import ArtifactRef
from syberruntime.verification import DeterministicVerifier


@dataclass(frozen=True)
class Mutant:
    operator: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "content": self.content,
        }


@dataclass(frozen=True)
class MutantResult:
    operator: str
    mutant_ref: ArtifactRef
    killed: bool
    verifier_passed: bool
    details: str

    @property
    def survived(self) -> bool:
        return not self.killed

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "mutant_ref": self.mutant_ref.to_dict(),
            "killed": self.killed,
            "survived": self.survived,
            "verifier_passed": self.verifier_passed,
            "details": self.details,
        }


@dataclass(frozen=True)
class MutationCampaignReport:
    artifact_digest: str
    check: dict[str, Any]
    baseline_passed: bool
    results: tuple[MutantResult, ...]

    @property
    def mutant_count(self) -> int:
        return len(self.results)

    @property
    def killed_count(self) -> int:
        return sum(1 for result in self.results if result.killed)

    @property
    def survived_count(self) -> int:
        return sum(1 for result in self.results if result.survived)

    @property
    def discharge_efficiency(self) -> float:
        if not self.results or not self.baseline_passed:
            return 0.0
        return self.killed_count / len(self.results)

    @property
    def false_discharge_rate(self) -> float:
        if not self.results or not self.baseline_passed:
            return 1.0 if self.results else 0.0
        return self.survived_count / len(self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_digest": self.artifact_digest,
            "check": normalize_json(self.check),
            "baseline_passed": self.baseline_passed,
            "mutant_count": self.mutant_count,
            "killed_count": self.killed_count,
            "survived_count": self.survived_count,
            "discharge_efficiency": self.discharge_efficiency,
            "false_discharge_rate": self.false_discharge_rate,
            "results": [result.to_dict() for result in self.results],
        }


class TextMutationHarness:
    def __init__(self, blobs: BlobStore) -> None:
        self.blobs = blobs
        self.verifier = DeterministicVerifier(blobs)

    def run(self, artifact: ArtifactRef, check: dict[str, Any]) -> MutationCampaignReport:
        normalized_check = normalize_json(check)
        original = self.blobs.get_text(artifact)
        baseline = self.verifier.run(artifact, normalized_check)
        mutants = _unique_mutants(original, normalized_check)
        results: list[MutantResult] = []

        for mutant in mutants:
            mutant_ref = self.blobs.put_text(
                mutant.content,
                media_type=artifact.media_type,
                name=f"mutant:{artifact.name or artifact.digest}:{mutant.operator}",
            )
            mutant_verdict = self.verifier.run(mutant_ref, normalized_check)
            # A mutant is killed when the verifier rejects the changed artifact.
            results.append(
                MutantResult(
                    operator=mutant.operator,
                    mutant_ref=mutant_ref,
                    killed=not mutant_verdict.passed,
                    verifier_passed=mutant_verdict.passed,
                    details=mutant_verdict.details,
                )
            )

        return MutationCampaignReport(
            artifact_digest=artifact.digest,
            check=normalized_check,
            baseline_passed=baseline.passed,
            results=tuple(results),
        )


def _unique_mutants(original: str, check: dict[str, Any]) -> tuple[Mutant, ...]:
    candidates = [
        _remove_expected(original, check),
        _append_noise(original),
        _replace_first_word(original),
        _drop_first_line(original),
    ]
    seen = {original}
    mutants: list[Mutant] = []
    for candidate in candidates:
        if candidate is None or candidate.content in seen:
            continue
        seen.add(candidate.content)
        mutants.append(candidate)
    return tuple(mutants)


def _remove_expected(original: str, check: dict[str, Any]) -> Mutant | None:
    expected = check.get("expected")
    if not isinstance(expected, str) or expected == "" or expected not in original:
        return None
    return Mutant(operator="remove_expected_text", content=original.replace(expected, "", 1))


def _append_noise(original: str) -> Mutant:
    suffix = "\nMUTATION: unexpected appended content"
    return Mutant(operator="append_noise", content=original + suffix)


def _replace_first_word(original: str) -> Mutant | None:
    match = re.search(r"[A-Za-z0-9_]+", original)
    if match is None:
        return None
    start, end = match.span()
    return Mutant(operator="replace_first_token", content=original[:start] + "MUTATED" + original[end:])


def _drop_first_line(original: str) -> Mutant | None:
    lines = original.splitlines(keepends=True)
    if len(lines) <= 1:
        return None
    return Mutant(operator="drop_first_line", content="".join(lines[1:]))
