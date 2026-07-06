from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import (  # noqa: E402
    FixedPolicy,
    ModelContractError,
    ModelSpec,
    RoutingError,
    Runtime,
    ScriptedModelAdapter,
    Verb,
)
from syberruntime.confidence import ConformalCalibrator  # noqa: E402


class Phase2RuntimeTests(unittest.TestCase):
    def test_cross_family_ai_loop_stabilizes_after_deterministic_oracle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))

            result = runtime.run_ai_loop(
                intent="Create a greeting artifact",
                artifact_name="greeting.txt",
                planner=_planner(),
                generator=_generator(artifact="hello from phase two\n"),
                verifier=_verifier(
                    {
                        "checkable_oracle": {"kind": "text_contains", "expected": "phase two"},
                        "verdict": "pass",
                        "located_errors": [],
                        "obligation_discharged": True,
                    }
                ),
            )

            state = runtime.rebuild_state()
            feature = result.feature_entry.operation

            self.assertTrue(result.stabilized)
            self.assertEqual(result.plan_entry.operation.type, Verb.RESEARCH.value)
            self.assertEqual(feature.type, Verb.FEATURE.value)
            self.assertEqual(result.verification_entry.operation.type, Verb.TEST.value)
            self.assertEqual(runtime.blobs.get_text(result.artifact_digest), "hello from phase two\n")
            self.assertEqual(state.debt.total_residual_debt(), 0.0)
            self.assertEqual(
                state.artifacts[result.artifact_digest].stabilized_by,
                result.stabilize_entry.operation.id if result.stabilize_entry else None,
            )
            self.assertEqual(feature.provenance.assumptions[0]["claim"], "Text artifact is sufficient")
            self.assertEqual(feature.params["model_assignment"]["family"], "implementer-family")

    def test_known_bad_generated_artifact_is_not_stabilized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))

            result = runtime.run_ai_loop(
                intent="Create an artifact containing the release token",
                artifact_name="release.txt",
                planner=_planner(),
                generator=_generator(artifact="wrong content\n"),
                verifier=_verifier(
                    {
                        "checkable_oracle": {"kind": "text_contains", "expected": "release-token"},
                        "verdict": "fail",
                        "located_errors": [{"where": "release.txt", "why": "release token is absent"}],
                        "obligation_discharged": False,
                    }
                ),
            )

            state = runtime.rebuild_state()
            obligation_id = result.feature_entry.operation.evaluation.obligations[0]
            obligation = state.debt.obligations[obligation_id]

            self.assertFalse(result.stabilized)
            self.assertIsNone(result.stabilize_entry)
            self.assertEqual(result.verification_entry.operation.type, Verb.TEST.value)
            self.assertEqual(obligation.status, "open")
            self.assertEqual(state.artifacts[result.artifact_digest].stabilized_by, None)

    def test_same_family_generator_and_verifier_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))

            with self.assertRaises(RoutingError):
                runtime.run_ai_loop(
                    intent="Reject correlated verifier",
                    artifact_name="bad-route.txt",
                    planner=_planner(),
                    generator=_generator(artifact="content", family="same-family"),
                    verifier=_verifier(
                        {
                            "checkable_oracle": {"kind": "text_contains", "expected": "content"},
                            "verdict": "pass",
                            "located_errors": [],
                            "obligation_discharged": True,
                        },
                        family="same-family",
                    ),
                )

    def test_llm_only_verifier_records_partial_verify_without_discharge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))

            result = runtime.run_ai_loop(
                intent="Create an artifact with no deterministic oracle",
                artifact_name="judged.txt",
                planner=_planner(),
                generator=_generator(artifact="judged output"),
                verifier=_verifier(
                    {
                        "checkable_oracle": None,
                        "verdict": "pass",
                        "located_errors": [],
                        "obligation_discharged": True,
                    }
                ),
            )

            state = runtime.rebuild_state()
            obligation_id = result.feature_entry.operation.evaluation.obligations[0]

            self.assertFalse(result.stabilized)
            self.assertEqual(result.verification_entry.operation.type, Verb.VERIFY.value)
            self.assertEqual(result.verification_entry.operation.evaluation.status, "partial")
            self.assertEqual(state.debt.obligations[obligation_id].status, "open")

    def test_generator_contract_requires_assumptions_before_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))

            with self.assertRaises(ModelContractError):
                runtime.run_ai_loop(
                    intent="Reject malformed generator",
                    artifact_name="malformed.txt",
                    planner=_planner(),
                    generator=ScriptedModelAdapter(
                        spec=ModelSpec(
                            model_id="bad-generator",
                            family="bad-family",
                            roles=("generator",),
                        ),
                        responses=(
                            {
                                "plan": "skip assumptions",
                                "artifact": "content",
                                "self_identified_risks": [],
                            },
                        ),
                    ),
                    verifier=_verifier(
                        {
                            "checkable_oracle": {"kind": "text_contains", "expected": "content"},
                            "verdict": "pass",
                            "located_errors": [],
                            "obligation_discharged": True,
                        }
                    ),
                )

    def test_conformal_calibrator_uses_empirical_scores_not_verbal_confidence(self) -> None:
        calibrator = ConformalCalibrator(calibration_scores=(0.05, 0.10, 0.20, 0.25, 0.30), alpha=0.2)

        prediction = calibrator.prediction_set({"pass": 0.10, "fail": 0.90})
        coverage = calibrator.empirical_coverage((0.05, 0.15, 0.22, 0.28))

        self.assertEqual(prediction.labels, ("pass",))
        self.assertGreaterEqual(coverage, 0.75)


def _planner() -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(
            model_id="planner-strong",
            family="planner-family",
            roles=("planner",),
            strength="strong",
        ),
        responses=(
            {
                "steps": [
                    {
                        "verb": "Feature",
                        "success_question": "Did useful possibility increase?",
                        "budget_alloc": 1.0,
                        "model_role": "generator",
                    },
                    {
                        "verb": "Verify",
                        "success_question": "Is trust justified?",
                        "budget_alloc": 1.0,
                        "model_role": "verifier",
                    },
                    {
                        "verb": "Stabilize",
                        "success_question": "Is this ready to commit?",
                        "budget_alloc": 1.0,
                        "model_role": "runtime",
                    },
                ],
                "rationale": "Small artifact; use deterministic verification if available.",
            },
        ),
    )


def _generator(*, artifact: str, family: str = "implementer-family") -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(
            model_id=f"{family}-generator",
            family=family,
            roles=("generator",),
            strength="standard",
        ),
        responses=(
            {
                "assumptions": [
                    {
                        "claim": "Text artifact is sufficient",
                        "depends_on": "The user requested a simple artifact",
                        "confidence_rationale": "The acceptance oracle checks text content",
                        "alternatives_considered": "Structured JSON artifact",
                    }
                ],
                "plan": "Write the requested content directly.",
                "artifact": artifact,
                "self_identified_risks": ["The content may omit a required token."],
            },
        ),
    )


def _verifier(payload: dict, *, family: str = "verifier-family") -> ScriptedModelAdapter:
    return ScriptedModelAdapter(
        spec=ModelSpec(
            model_id=f"{family}-verifier",
            family=family,
            roles=("verifier",),
            strength="strong",
        ),
        responses=(payload,),
    )


if __name__ == "__main__":
    unittest.main()
