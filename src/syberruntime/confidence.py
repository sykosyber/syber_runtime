"""Conformal confidence primitives for Phase 2 triage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConformalSet:
    alpha: float
    threshold: float
    labels: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "threshold": self.threshold,
            "labels": list(self.labels),
        }


@dataclass(frozen=True)
class ConformalCalibrator:
    """Split-conformal threshold over nonconformity scores.

    The runtime supplies scores from observed outcomes; the model never supplies
    verbal confidence. Lower scores mean better support for a candidate label.
    """

    calibration_scores: tuple[float, ...]
    alpha: float = 0.1

    def __post_init__(self) -> None:
        if not self.calibration_scores:
            raise ValueError("At least one calibration score is required")
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        object.__setattr__(self, "calibration_scores", tuple(float(score) for score in self.calibration_scores))

    @property
    def threshold(self) -> float:
        scores = sorted(self.calibration_scores)
        rank = min(len(scores), math.ceil((len(scores) + 1) * (1 - self.alpha)))
        return scores[rank - 1]

    def prediction_set(self, candidate_scores: dict[str, float]) -> ConformalSet:
        threshold = self.threshold
        labels = tuple(sorted(label for label, score in candidate_scores.items() if float(score) <= threshold))
        return ConformalSet(alpha=self.alpha, threshold=threshold, labels=labels)

    def empirical_coverage(self, heldout_scores: tuple[float, ...] | list[float]) -> float:
        if not heldout_scores:
            raise ValueError("At least one held-out score is required")
        covered = sum(1 for score in heldout_scores if float(score) <= self.threshold)
        return covered / len(heldout_scores)
