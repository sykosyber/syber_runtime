"""Typed error for the provider MCP boundary."""

from __future__ import annotations

from typing import Any


class ProviderMCPError(Exception):
    def __init__(
        self,
        message: str,
        *,
        failure_class: str = "provider_error",
        attempts: tuple[dict[str, Any], ...] = (),
    ) -> None:
        super().__init__(message)
        self.failure_class = failure_class
        self.attempts = attempts

    def diagnostic(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "failure_class": self.failure_class,
            "attempts": list(self.attempts),
        }
