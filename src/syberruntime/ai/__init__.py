"""AI orchestration layer: drives model adapters through the runtime grammar.

This package sits above the kernel (`syberruntime.runtime`) and below the
evidence tooling. The kernel records operations; this layer decides which
model calls to make, with which prompts, and in what order.
"""

from syberruntime.ai.orchestrator import AIOperationResult, run_ai_loop, validate_routing

__all__ = ["AIOperationResult", "run_ai_loop", "validate_routing"]
