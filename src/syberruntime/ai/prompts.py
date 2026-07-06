"""Prompt text for the plan -> generate -> verify -> stabilize loop.

Prompts are policy, not kernel: they change at a much higher rate than the
operation grammar and must never depend on kernel internals. Keeping them in
one module makes prompt review independent of runtime review.
"""

from __future__ import annotations


def runtime_constitution() -> str:
    return (
        "Work proceeds as typed SyberRuntime operations. Every generative operation incurs "
        "a paired evaluation obligation. Assumptions must be surfaced before artifact creation; "
        "human understanding is the protected resource."
    )


def generator_system() -> str:
    return (
        "You are performing a Feature operation. Return strict JSON with assumptions, plan, "
        "artifact, and self_identified_risks. State assumptions before artifact content."
    )


def verifier_system() -> str:
    return (
        "You are performing a Verify operation. Prefer a deterministic checkable oracle. "
        "If no oracle exists, return pass, fail, or uncertain with located errors."
    )
