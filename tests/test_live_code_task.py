from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import FixedPolicy, IntentMetadata, ModelSpec, Runtime, ScriptedModelAdapter  # noqa: E402
from syberruntime.harness import _run_live_task, default_live_code_tasks  # noqa: E402
from syberruntime.models import Verb  # noqa: E402


CORRECT_MERGE_INTERVALS = '''
def merge_intervals(intervals):
    merged = []
    for start, end in sorted([list(pair) for pair in intervals]):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
'''

# Behaviorally wrong: ignores the touching-intervals rule and mutates input.
WRONG_MERGE_INTERVALS = '''
def merge_intervals(intervals):
    intervals.sort()
    merged = []
    for start, end in intervals:
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
'''


def _metadata() -> IntentMetadata:
    return IntentMetadata(
        intent_source="agent",
        principal="live-code-test",
        acceptance_authority="harness-python-tests-oracle",
        benchmark_id="live-code-test",
        harness_run_id="live-code-test-run",
    )


def _planner() -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(model_id="code-planner", family="planner-family", roles=("planner",)),
        responses=(
            {
                "steps": [
                    {
                        "verb": Verb.FEATURE.value,
                        "success_question": "Did useful possibility increase?",
                        "budget_alloc": 1.0,
                        "model_role": "generator",
                    },
                    {
                        "verb": Verb.VERIFY.value,
                        "success_question": "Is trust justified?",
                        "budget_alloc": 1.0,
                        "model_role": "verifier",
                    },
                ],
                "rationale": "Generate the module, then defer to the harness oracle.",
            },
        ),
    )


def _generator(artifact: str) -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(model_id="code-generator", family="generator-family", roles=("generator",)),
        responses=(
            {
                "assumptions": [
                    {
                        "claim": "The module only needs merge_intervals.",
                        "depends_on": "The held-out suite imports merge_intervals directly.",
                        "confidence_rationale": "The intent names the required function.",
                        "alternatives_considered": "A class-based interval API.",
                    }
                ],
                "plan": "Sort by start, then fold overlapping or touching intervals.",
                "artifact": artifact,
                "self_identified_risks": ["Touching intervals might be treated as disjoint."],
            },
        ),
    )


def _verifier(verdict: str = "pass") -> ScriptedModelAdapter:
    # Deliberately supplies a weak text oracle: for code tasks it must be
    # recorded as partial evidence only and must never discharge.
    return ScriptedModelAdapter(
        spec=ModelSpec(model_id="code-verifier", family="verifier-family", roles=("verifier",)),
        responses=(
            {
                "checkable_oracle": {"kind": "text_contains", "expected": "def merge_intervals"},
                "verdict": verdict,
                "located_errors": [],
                "obligation_discharged": False,
            },
        ),
    )


class LiveCodeTaskTests(unittest.TestCase):
    def test_correct_module_discharges_via_harness_oracle_and_stabilizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            task = default_live_code_tasks()[0]

            result = _run_live_task(
                runtime=runtime,
                metadata=_metadata(),
                config_path="scripted://none",
                task=task,
                planner=_planner(),
                generator=_generator(CORRECT_MERGE_INTERVALS),
                verifier=_verifier(),
            )

            self.assertEqual(result.status, "pass")
            self.assertTrue(result.stabilized)
            state = runtime.rebuild_state()
            self.assertEqual(state.debt.total_residual_debt(), 0.0)
            # The discharging Test operation ran the harness python_tests
            # check, not the model verifier's weak text oracle.
            discharging = [
                op
                for op in state.operations.values()
                if op.type == Verb.TEST.value
                and op.params.get("verification", {}).get("discharged_obligations")
            ]
            self.assertEqual(len(discharging), 1)
            self.assertEqual(
                discharging[0].params["verification"]["check"]["kind"],
                "python_tests",
            )
            # The model verifier's review is present as partial evidence.
            partial_verifies = [op for op in state.operations.values() if op.type == Verb.VERIFY.value]
            self.assertTrue(
                any(
                    op.params.get("verification", {}).get("partial_only") is True
                    for op in partial_verifies
                )
            )

    def test_mutation_campaign_uses_ast_operators_for_code_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            task = default_live_code_tasks()[0]

            result = _run_live_task(
                runtime=runtime,
                metadata=_metadata(),
                config_path="scripted://none",
                task=task,
                planner=_planner(),
                generator=_generator(CORRECT_MERGE_INTERVALS),
                verifier=_verifier(),
            )

            self.assertIsNotNone(result.mutation_report)
            operators = [item["operator"] for item in result.mutation_report["results"]]
            self.assertTrue(operators)
            for operator in operators:
                self.assertTrue(operator.startswith("ast_"), operator)

    def test_behaviorally_wrong_module_fails_and_never_stabilizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
            task = default_live_code_tasks()[0]

            result = _run_live_task(
                runtime=runtime,
                metadata=_metadata(),
                config_path="scripted://none",
                task=task,
                planner=_planner(),
                generator=_generator(WRONG_MERGE_INTERVALS),
                verifier=_verifier(),  # model verifier says pass; it must not matter
            )

            self.assertEqual(result.status, "fail")
            self.assertFalse(result.stabilized)
            state = runtime.rebuild_state()
            self.assertGreater(state.debt.total_residual_debt(), 0.0)
            self.assertIsNone(state.artifacts[result.artifact_digest].stabilized_by)


if __name__ == "__main__":
    unittest.main()
