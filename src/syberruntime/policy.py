"""Fixed Phase 1 policy for rigor profiles and verification budgets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RigorProfile:
    name: str
    accrual_rate: float
    floor_required: bool
    deterministic_discharge_efficiency: float = 1.0


DEFAULT_RIGOR_PROFILES: dict[str, RigorProfile] = {
    "exploratory": RigorProfile(name="exploratory", accrual_rate=0.25, floor_required=False),
    "production": RigorProfile(name="production", accrual_rate=1.0, floor_required=True),
    "research-grade": RigorProfile(name="research-grade", accrual_rate=2.0, floor_required=True),
    "safety-critical": RigorProfile(name="safety-critical", accrual_rate=5.0, floor_required=True),
}


@dataclass(frozen=True)
class CenterPolicy:
    profile_name: str
    max_debt: float


class FixedPolicy:
    """Read-only Phase 1 controller policy.

    v0.6 section 3.6 defers self-calibration; v1 keeps policy fixed and makes it
    a projection target later. This object is intentionally simple and explicit.
    """

    def __init__(
        self,
        *,
        default_profile: str = "exploratory",
        default_max_debt: float = 10.0,
        center_policies: dict[str, CenterPolicy] | None = None,
        profiles: dict[str, RigorProfile] | None = None,
    ) -> None:
        self.profiles = dict(profiles or DEFAULT_RIGOR_PROFILES)
        if default_profile not in self.profiles:
            raise ValueError(f"Unknown default rigor profile: {default_profile}")
        self.default_profile = default_profile
        self.default_max_debt = float(default_max_debt)
        self.center_policies = dict(center_policies or {})
        for center_id, policy in self.center_policies.items():
            if policy.profile_name not in self.profiles:
                raise ValueError(f"Unknown rigor profile for center {center_id}: {policy.profile_name}")

    def profile_for(self, center_id: str) -> RigorProfile:
        center_policy = self.center_policies.get(center_id)
        if center_policy is None:
            return self.profiles[self.default_profile]
        return self.profiles[center_policy.profile_name]

    def max_debt_for(self, center_id: str) -> float:
        center_policy = self.center_policies.get(center_id)
        if center_policy is None:
            return self.default_max_debt
        return center_policy.max_debt
