"""Runtime-level errors with Phase 1 semantics."""

from __future__ import annotations

from typing import Any


class SyberRuntimeError(RuntimeError):
    pass


class BudgetExceededError(SyberRuntimeError):
    pass


class StabilizationBlockedError(SyberRuntimeError):
    pass


class VerificationError(SyberRuntimeError):
    pass


class AdapterError(SyberRuntimeError):
    def __init__(self, message: str, *, diagnostic: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


class ModelContractError(SyberRuntimeError):
    pass


class RoutingError(SyberRuntimeError):
    pass
