"""Agentic Intent Harness v0.

The harness is intentionally bounded: it executes scripted task cases through
the public runtime grammar, records successes and failures, and emits a
machine-readable report for dogfooding and benchmark work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from syberruntime.adapter_config import load_adapter_bundle
from syberruntime.errors import SyberRuntimeError
from syberruntime.hashing import digest_json
from syberruntime.intent import IntentMetadata
from syberruntime.model_capability import model_capability_envelope
from syberruntime.policy import FixedPolicy
from syberruntime.reports import discover_json_reports, read_json_report, write_json_report
from syberruntime.runtime import Runtime


LIVE_SMOKE_ARTIFACT_NAME = "agent-live-smoke.txt"
LIVE_SMOKE_ARTIFACT_CONTENT = "agent-live-smoke-token\n"
LIVE_SMOKE_INTENT = (
    f"Create a local SyberRuntime text artifact named {LIVE_SMOKE_ARTIFACT_NAME} whose content is exactly "
    f"{LIVE_SMOKE_ARTIFACT_CONTENT!r}, then verify it with a deterministic text_equals oracle."
)


@dataclass(frozen=True)
class LiveHarnessTask:
    task_id: str
    intent: str
    artifact_name: str
    expected_content: str
    run_mutation_campaign: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "intent": self.intent,
            "artifact_name": self.artifact_name,
            "expected_content": self.expected_content,
            "run_mutation_campaign": self.run_mutation_campaign,
        }


@dataclass(frozen=True)
class LiveCodeTask:
    """A hard live task: the generator writes code, the harness holds the oracle.

    The `check` (a python_tests suite) never reaches the model in constraint
    form and is the sole discharge authority; the model verifier's review is
    recorded as partial evidence only. The generator cannot pass by echoing
    the intent — only by producing behaviorally correct code.
    """

    task_id: str
    intent: str
    artifact_name: str
    check: dict[str, Any]
    run_mutation_campaign: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "intent": self.intent,
            "artifact_name": self.artifact_name,
            "check": self.check,
            "run_mutation_campaign": self.run_mutation_campaign,
        }


@dataclass(frozen=True)
class HarnessTask:
    task_id: str
    intent: str
    artifact_name: str
    artifact_content: str
    check: dict[str, Any]
    expect_stabilized: bool = True
    run_mutation_campaign: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "intent": self.intent,
            "artifact_name": self.artifact_name,
            "artifact_content": self.artifact_content,
            "check": self.check,
            "expect_stabilized": self.expect_stabilized,
            "run_mutation_campaign": self.run_mutation_campaign,
        }


@dataclass(frozen=True)
class HarnessTaskResult:
    task_id: str
    status: str
    thread_id: str | None
    artifact_digest: str | None
    stabilized: bool
    expected_stabilized: bool
    failure: str | None
    mutation_report: dict[str, Any] | None
    failure_class: str | None = None
    failure_details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "thread_id": self.thread_id,
            "artifact_digest": self.artifact_digest,
            "stabilized": self.stabilized,
            "expected_stabilized": self.expected_stabilized,
            "failure": self.failure,
            "mutation_report": self.mutation_report,
            "failure_class": self.failure_class,
            "failure_details": self.failure_details,
        }


@dataclass(frozen=True)
class HarnessReport:
    report_id: str
    run_id: str
    protocol_path: str
    runtime_root: str
    intent_metadata: IntentMetadata
    task_results: tuple[HarnessTaskResult, ...]
    metrics: dict[str, Any]
    mode: str = "scripted"
    provider_config_path: str | None = None
    model_assignments: dict[str, Any] | None = None
    model_capability_envelope: dict[str, Any] | None = None

    @property
    def attempted_tasks(self) -> int:
        return len(self.task_results)

    @property
    def stabilized_tasks(self) -> int:
        return sum(1 for result in self.task_results if result.stabilized)

    @property
    def blocked_or_failed_tasks(self) -> int:
        return sum(1 for result in self.task_results if result.status != "pass" or not result.stabilized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "protocol_path": self.protocol_path,
            "runtime_root": self.runtime_root,
            "mode": self.mode,
            "provider_config_path": self.provider_config_path,
            "model_assignments": self.model_assignments or {},
            "model_capability_envelope": self.model_capability_envelope or model_capability_envelope(),
            "intent_metadata": self.intent_metadata.to_dict(),
            "task_results": [result.to_dict() for result in self.task_results],
            "summary": {
                "attempted_tasks": self.attempted_tasks,
                "stabilized_tasks": self.stabilized_tasks,
                "blocked_or_failed_tasks": self.blocked_or_failed_tasks,
            },
            "metrics": self.metrics,
        }


def default_scripted_tasks() -> tuple[HarnessTask, ...]:
    return (
        HarnessTask(
            task_id="scripted-pass-001",
            intent="Agent harness creates a validated token artifact.",
            artifact_name="agent-pass.txt",
            artifact_content="agent-harness-pass\n",
            check={"kind": "text_equals", "expected": "agent-harness-pass\n"},
            expect_stabilized=True,
        ),
        HarnessTask(
            task_id="scripted-block-001",
            intent="Agent harness records a failed verification case without hiding it.",
            artifact_name="agent-block.txt",
            artifact_content="agent-harness-block\n",
            check={"kind": "text_equals", "expected": "different-token\n"},
            expect_stabilized=False,
            run_mutation_campaign=False,
        ),
    )


def live_smoke_task(
    *,
    task_id: str = "live-provider-smoke-001",
    intent: str = LIVE_SMOKE_INTENT,
    artifact_name: str = LIVE_SMOKE_ARTIFACT_NAME,
    expected_content: str = LIVE_SMOKE_ARTIFACT_CONTENT,
    run_mutation_campaign: bool = True,
) -> LiveHarnessTask:
    return LiveHarnessTask(
        task_id=task_id,
        intent=intent,
        artifact_name=artifact_name,
        expected_content=expected_content,
        run_mutation_campaign=run_mutation_campaign,
    )


def default_live_scale_tasks() -> tuple[LiveHarnessTask, ...]:
    return (
        live_smoke_task(),
        _exact_live_task(
            task_id="live-provider-scale-002",
            artifact_name="agent-scale-alpha.txt",
            expected_content="agent-scale-alpha-token\n",
        ),
        _exact_live_task(
            task_id="live-provider-scale-003",
            artifact_name="agent-scale-beta.txt",
            expected_content="agent-scale-beta-token\n",
        ),
    )


def _exact_live_task(*, task_id: str, artifact_name: str, expected_content: str) -> LiveHarnessTask:
    intent = (
        f"Create a local SyberRuntime text artifact named {artifact_name} whose content is exactly "
        f"{expected_content!r}, then verify it with a deterministic text_equals oracle."
    )
    return live_smoke_task(
        task_id=task_id,
        intent=intent,
        artifact_name=artifact_name,
        expected_content=expected_content,
    )


MERGE_INTERVALS_INTENT = (
    "Write a complete Python module that defines a function merge_intervals(intervals). "
    "The argument is a list of [start, end] pairs of integers, in arbitrary order, where start <= end. "
    "Return a new list of [start, end] lists (not tuples) in which all overlapping intervals are merged, "
    "intervals that merely touch (one ends where the next starts, e.g. [1, 2] and [2, 3]) are also merged, "
    "and the result is sorted by start. Do not mutate the input list. The module will be imported and its "
    "behavior tested by a held-out deterministic unittest suite; the artifact must be the module source only."
)

MERGE_INTERVALS_TEST_SOURCE = """
import unittest

from artifact_under_test import merge_intervals


class MergeIntervalsTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(merge_intervals([]), [])

    def test_single_interval(self):
        self.assertEqual(merge_intervals([[1, 3]]), [[1, 3]])

    def test_overlapping_unsorted_input(self):
        self.assertEqual(merge_intervals([[8, 10], [1, 3], [2, 6]]), [[1, 6], [8, 10]])

    def test_touching_intervals_merge(self):
        self.assertEqual(merge_intervals([[1, 2], [2, 3]]), [[1, 3]])

    def test_contained_intervals_collapse(self):
        self.assertEqual(merge_intervals([[1, 10], [2, 3], [4, 5]]), [[1, 10]])

    def test_disjoint_intervals_sorted_output(self):
        self.assertEqual(merge_intervals([[5, 6], [1, 2]]), [[1, 2], [5, 6]])

    def test_input_is_not_mutated(self):
        intervals = [[8, 10], [1, 3], [2, 6]]
        snapshot = [list(pair) for pair in intervals]
        merge_intervals(intervals)
        self.assertEqual(intervals, snapshot)
"""


def default_live_code_tasks() -> tuple[LiveCodeTask, ...]:
    return (
        LiveCodeTask(
            task_id="live-code-merge-intervals-001",
            intent=MERGE_INTERVALS_INTENT,
            artifact_name="merge_intervals.py",
            check={
                "kind": "python_tests",
                "test_source": MERGE_INTERVALS_TEST_SOURCE,
                "artifact_filename": "artifact_under_test.py",
                "timeout_seconds": 120,
            },
        ),
    )


def run_scripted_agent_harness(
    *,
    runtime_root: str | Path,
    protocol_path: str | Path,
    run_id: str,
    principal: str = "agent-harness-v0",
    benchmark_id: str = "agentic-intent-harness-v0",
    acceptance_authority: str = "deterministic-oracle",
    tasks: tuple[HarnessTask, ...] | None = None,
    model_constraints: tuple[str, ...] | list[str] | None = None,
    preferred_unavailable_models: tuple[str, ...] | list[str] | None = None,
    model_envelope_notes: str | None = None,
) -> HarnessReport:
    runtime = Runtime(runtime_root, policy=FixedPolicy(default_profile="production"))
    metadata = IntentMetadata(
        intent_source="agent",
        principal=principal,
        acceptance_authority=acceptance_authority,
        benchmark_id=benchmark_id,
        harness_run_id=run_id,
    )
    results = tuple(_run_task(runtime, task, metadata) for task in (tasks or default_scripted_tasks()))
    metrics = runtime.metrics().to_dict()
    payload = {
        "mode": "scripted",
        "run_id": run_id,
        "protocol_path": str(protocol_path),
        "runtime_root": str(runtime.root),
        "intent_metadata": metadata.to_dict(),
        "task_results": [result.to_dict() for result in results],
        "metrics": metrics,
        "model_capability_envelope": model_capability_envelope(
            constraints=model_constraints
            or ("scripted harness uses deterministic local fixtures rather than external model calls",),
            preferred_unavailable_models=preferred_unavailable_models,
            notes=model_envelope_notes,
        ),
    }
    return HarnessReport(
        report_id=digest_json(payload),
        run_id=run_id,
        protocol_path=str(protocol_path),
        runtime_root=str(runtime.root),
        intent_metadata=metadata,
        task_results=results,
        metrics=metrics,
        mode="scripted",
        model_capability_envelope=payload["model_capability_envelope"],
    )


def run_live_agent_harness(
    *,
    runtime_root: str | Path,
    protocol_path: str | Path,
    run_id: str,
    config_path: str | Path,
    principal: str = "agent-harness-live-v1",
    benchmark_id: str = "agentic-intent-harness-live-v1",
    acceptance_authority: str = "provider-verifier-and-deterministic-oracle",
    intent: str = LIVE_SMOKE_INTENT,
    artifact_name: str = LIVE_SMOKE_ARTIFACT_NAME,
    run_mutation_campaign: bool = True,
    tasks: tuple[LiveHarnessTask | LiveCodeTask, ...] | None = None,
    model_constraints: tuple[str, ...] | list[str] | None = None,
    preferred_unavailable_models: tuple[str, ...] | list[str] | None = None,
    model_envelope_notes: str | None = None,
) -> HarnessReport:
    runtime = Runtime(runtime_root, policy=FixedPolicy(default_profile="production"))
    metadata = IntentMetadata(
        intent_source="agent",
        principal=principal,
        acceptance_authority=acceptance_authority,
        benchmark_id=benchmark_id,
        harness_run_id=run_id,
    )
    bundle = load_adapter_bundle(config_path)
    model_assignments = {
        "planner": bundle.planner.spec.to_dict(),
        "generator": bundle.generator.spec.to_dict(),
        "verifier": bundle.verifier.spec.to_dict(),
    }
    capability_envelope = model_capability_envelope(
        available_model_roles=model_assignments,
        constraints=model_constraints,
        preferred_unavailable_models=preferred_unavailable_models,
        notes=model_envelope_notes,
    )
    selected_tasks = tasks or (
        live_smoke_task(
            intent=intent,
            artifact_name=artifact_name,
            run_mutation_campaign=run_mutation_campaign,
        ),
    )
    results = tuple(
        _run_live_task(
            runtime=runtime,
            metadata=metadata,
            config_path=config_path,
            task=task,
            planner=bundle.planner,
            generator=bundle.generator,
            verifier=bundle.verifier,
        )
        for task in selected_tasks
    )
    metrics = runtime.metrics().to_dict()
    payload = {
        "mode": "live",
        "run_id": run_id,
        "protocol_path": str(protocol_path),
        "runtime_root": str(runtime.root),
        "provider_config_path": str(config_path),
        "model_assignments": model_assignments,
        "model_capability_envelope": capability_envelope,
        "intent_metadata": metadata.to_dict(),
        "task_results": [result.to_dict() for result in results],
        "metrics": metrics,
    }
    return HarnessReport(
        report_id=digest_json(payload),
        run_id=run_id,
        protocol_path=str(protocol_path),
        runtime_root=str(runtime.root),
        intent_metadata=metadata,
        task_results=results,
        metrics=metrics,
        mode="live",
        provider_config_path=str(config_path),
        model_assignments=model_assignments,
        model_capability_envelope=capability_envelope,
    )


def write_harness_report(report: HarnessReport, output_path: str | Path) -> Path:
    return write_json_report(report.to_dict(), output_path)


def discover_harness_reports(directory: str | Path) -> tuple[Path, ...]:
    return discover_json_reports(directory)


def load_harness_report(path: str | Path) -> dict[str, Any]:
    data = read_json_report(path)
    validate_harness_report(data)
    return data


def validate_harness_report(data: dict[str, Any]) -> None:
    for key in ("report_id", "run_id", "protocol_path", "runtime_root", "intent_metadata", "task_results", "summary", "metrics"):
        if key not in data:
            raise ValueError(f"harness report missing required key: {key}")
    metadata = data["intent_metadata"]
    if not isinstance(metadata, dict):
        raise ValueError("harness report intent_metadata must be an object")
    if metadata.get("intent_source") != "agent":
        raise ValueError("harness report intent_source must be agent")
    if not metadata.get("principal"):
        raise ValueError("harness report principal is required")
    summary = data["summary"]
    if not isinstance(summary, dict):
        raise ValueError("harness report summary must be an object")
    if int(summary.get("attempted_tasks", 0)) < 1:
        raise ValueError("harness report must attempt at least one task")
    mode = str(data.get("mode", "scripted"))
    if mode == "scripted" and int(summary.get("stabilized_tasks", 0)) < 1:
        raise ValueError("harness report must stabilize at least one task")
    task_results = data["task_results"]
    if not isinstance(task_results, list) or not task_results:
        raise ValueError("harness report task_results must be a non-empty list")
    for result in task_results:
        if not isinstance(result, dict):
            raise ValueError("harness report task result must be an object")
        if result.get("status") not in {"pass", "fail"}:
            raise ValueError("harness report task status must be pass or fail")
    metrics = data["metrics"]
    if not isinstance(metrics, dict):
        raise ValueError("harness report metrics must be an object")
    if mode == "scripted" and int(metrics.get("action_cost", 0)) < 1:
        raise ValueError("scripted harness report metrics must include nonzero action_cost")


def _run_live_task(
    *,
    runtime: Runtime,
    metadata: IntentMetadata,
    config_path: str | Path,
    task: LiveHarnessTask | LiveCodeTask,
    planner: Any,
    generator: Any,
    verifier: Any,
) -> HarnessTaskResult:
    thread_id = None
    artifact_digest = None
    deterministic_check = task.check if isinstance(task, LiveCodeTask) else None
    try:
        thread = runtime.create_thread(intent=task.intent, actor=metadata.principal, intent_metadata=metadata)
        thread_id = thread.operation.thread_id
        result = runtime.run_ai_loop(
            intent=task.intent,
            artifact_name=task.artifact_name,
            planner=planner,
            generator=generator,
            verifier=verifier,
            thread_id=thread_id,
            intent_metadata=metadata,
            deterministic_check=deterministic_check,
        )
        artifact_digest = result.artifact_digest
        mutation_report = None
        mutation_check = (
            deterministic_check if deterministic_check is not None else result.verifier_output.checkable_oracle
        )
        if task.run_mutation_campaign and result.stabilized and mutation_check is not None:
            _entry, report = runtime.run_mutation_campaign(
                result.feature_entry.operation.thread_id,
                artifact_digest=result.artifact_digest,
                check=mutation_check,
                actor=metadata.principal,
                intent_metadata=metadata,
            )
            mutation_report = report.to_dict()
        failure = None if result.stabilized else f"live provider task did not stabilize using config {config_path}"
        failure_class = None if result.stabilized else "not_stabilized"
        return HarnessTaskResult(
            task_id=task.task_id,
            status="pass" if result.stabilized else "fail",
            thread_id=result.feature_entry.operation.thread_id,
            artifact_digest=artifact_digest,
            stabilized=result.stabilized,
            expected_stabilized=True,
            failure=failure,
            mutation_report=mutation_report,
            failure_class=failure_class,
        )
    except Exception as exc:  # noqa: BLE001 - provider boundary failures are evidence.
        artifact_digest = artifact_digest or _latest_thread_artifact_digest(runtime, thread_id)
        failure_details = _failure_details(exc)
        return HarnessTaskResult(
            task_id=task.task_id,
            status="fail",
            thread_id=thread_id,
            artifact_digest=artifact_digest,
            stabilized=False,
            expected_stabilized=True,
            failure=str(exc),
            mutation_report=None,
            failure_class=_failure_class(exc, failure_details),
            failure_details=failure_details,
        )


def _failure_details(exc: Exception) -> dict[str, Any] | None:
    diagnostic = getattr(exc, "diagnostic", None)
    return diagnostic if isinstance(diagnostic, dict) else None


def _failure_class(exc: Exception, details: dict[str, Any] | None) -> str:
    if details is not None:
        failure_class = details.get("failure_class")
        if isinstance(failure_class, str) and failure_class:
            return failure_class
    text = str(exc)
    if "checkable_oracle kind" in text or "missing required key" in text:
        return "schema_mismatch"
    if "Provider did not return valid JSON" in text or "invalid JSON" in text:
        return "malformed_json"
    if "MCP tool returned isError=true" in text:
        return "mcp_tool_error"
    return "runtime_exception"


def _latest_thread_artifact_digest(runtime: Runtime, thread_id: str | None) -> str | None:
    if thread_id is None:
        return None
    try:
        state = runtime.rebuild_state()
    except Exception:  # noqa: BLE001 - failure reports should survive projection issues.
        return None
    thread = state.threads.get(thread_id)
    if thread is None or not thread.artifacts:
        return None
    return thread.artifacts[-1]


def _run_task(runtime: Runtime, task: HarnessTask, metadata: IntentMetadata) -> HarnessTaskResult:
    thread_id = None
    artifact_digest = None
    mutation_report = None
    try:
        thread = runtime.create_thread(
            intent=task.intent,
            actor=metadata.principal,
            intent_metadata=metadata,
        )
        thread_id = thread.operation.thread_id
        feature = runtime.record_feature(
            thread_id,
            artifact_name=task.artifact_name,
            content=task.artifact_content,
            intent=task.intent,
            actor=metadata.principal,
            assumptions=(
                {
                    "claim": "Scripted harness content is intentionally simple.",
                    "depends_on": "A deterministic text oracle evaluates the artifact.",
                    "confidence_rationale": "The expected text is fixed in the protocol.",
                    "alternatives_considered": "Live provider generation",
                },
            ),
            intent_metadata=metadata,
        )
        artifact_digest = feature.operation.outputs[0].digest
        runtime.record_test(
            thread_id,
            artifact_digest=artifact_digest,
            check=task.check,
            actor=metadata.principal,
            intent_metadata=metadata,
        )
        if task.run_mutation_campaign:
            _entry, report = runtime.run_mutation_campaign(
                thread_id,
                artifact_digest=artifact_digest,
                check=task.check,
                actor=metadata.principal,
                intent_metadata=metadata,
            )
            mutation_report = report.to_dict()
        runtime.stabilize(
            thread_id,
            artifact_digest=artifact_digest,
            actor=metadata.principal,
            intent_metadata=metadata,
        )
        stabilized = True
        status = "pass" if stabilized == task.expect_stabilized else "fail"
        return HarnessTaskResult(
            task_id=task.task_id,
            status=status,
            thread_id=thread_id,
            artifact_digest=artifact_digest,
            stabilized=stabilized,
            expected_stabilized=task.expect_stabilized,
            failure=None if status == "pass" else "unexpected stabilization outcome",
            mutation_report=mutation_report,
        )
    except (SyberRuntimeError, KeyError, ValueError) as exc:
        stabilized = False
        status = "pass" if not task.expect_stabilized else "fail"
        return HarnessTaskResult(
            task_id=task.task_id,
            status=status,
            thread_id=thread_id,
            artifact_digest=artifact_digest,
            stabilized=stabilized,
            expected_stabilized=task.expect_stabilized,
            failure=str(exc),
            mutation_report=mutation_report,
        )
