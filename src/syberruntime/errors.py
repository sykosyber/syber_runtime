"""Runtime-level errors with Phase 1 semantics."""

from __future__ import annotations


class SyberRuntimeError(RuntimeError):
    pass


class BudgetExceededError(SyberRuntimeError):
    pass


class StabilizationBlockedError(SyberRuntimeError):
    pass


class VerificationError(SyberRuntimeError):
    pass


class AdapterError(SyberRuntimeError):
    pass


class ModelContractError(SyberRuntimeError):
    pass


class RoutingError(SyberRuntimeError):
    pass
