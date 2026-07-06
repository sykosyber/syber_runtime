from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from syberruntime import BlobStore  # noqa: E402
from syberruntime.mutation import TextMutationHarness, _python_ast_mutants  # noqa: E402


CLAMP_SOURCE = '''"""Clamp a value into an inclusive range."""


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value
'''

CLAMP_TEST_SOURCE = """
import unittest

from artifact_under_test import clamp


class ClampTests(unittest.TestCase):
    def test_below_range(self):
        self.assertEqual(clamp(-5, 0, 10), 0)

    def test_above_range(self):
        self.assertEqual(clamp(15, 0, 10), 10)

    def test_inside_range(self):
        self.assertEqual(clamp(7, 0, 10), 7)

    def test_boundaries_are_inclusive(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)
"""


class AstMutantGenerationTests(unittest.TestCase):
    def test_generates_only_syntactically_valid_mutants(self) -> None:
        mutants = _python_ast_mutants(CLAMP_SOURCE)

        self.assertIsNotNone(mutants)
        self.assertGreater(len(mutants), 0)
        for mutant in mutants:
            ast.parse(mutant.content)  # raises if any mutant is invalid
            self.assertTrue(mutant.operator.startswith("ast_"))

    def test_covers_comparison_swaps(self) -> None:
        mutants = _python_ast_mutants(CLAMP_SOURCE)

        operators = {mutant.operator.rsplit("_line", 1)[0] for mutant in mutants}
        self.assertIn("ast_compare_lt_swap", operators)
        self.assertIn("ast_compare_gt_swap", operators)

    def test_never_mutates_docstrings(self) -> None:
        mutants = _python_ast_mutants(CLAMP_SOURCE)

        for mutant in mutants:
            self.assertIn("Clamp a value into an inclusive range.", mutant.content)

    def test_arithmetic_and_constant_sites(self) -> None:
        source = "def scale(x):\n    return x * 2 + 1\n"
        mutants = _python_ast_mutants(source)

        operators = {mutant.operator.rsplit("_line", 1)[0] for mutant in mutants}
        self.assertIn("ast_binop_add_swap", operators)
        self.assertIn("ast_binop_mult_swap", operators)
        self.assertIn("ast_const_number_increment", operators)

    def test_returns_none_for_unparseable_source(self) -> None:
        self.assertIsNone(_python_ast_mutants("def broken(:\n"))


class AstMutationCampaignTests(unittest.TestCase):
    def test_python_tests_campaign_uses_ast_mutants_and_kills_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text(CLAMP_SOURCE, name="clamp.py")
            check = {"kind": "python_tests", "test_source": CLAMP_TEST_SOURCE, "timeout_seconds": 60}

            report = TextMutationHarness(blobs).run(artifact, check)

            self.assertTrue(report.baseline_passed)
            self.assertGreater(report.mutant_count, 0)
            for result in report.results:
                self.assertTrue(result.operator.startswith("ast_"), result.operator)
            # Every clamp mutant changes observable behavior; the suite must
            # kill all of them by executing, not by syntax failure.
            self.assertEqual(report.survived_count, 0)
            self.assertEqual(report.discharge_efficiency, 1.0)

    def test_text_checks_still_use_text_operators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text("token-alpha\nsecond line\n", name="token.txt")
            check = {"kind": "text_equals", "expected": "token-alpha\nsecond line\n"}

            report = TextMutationHarness(blobs).run(artifact, check)

            operators = {result.operator for result in report.results}
            self.assertIn("append_noise", operators)
            self.assertNotIn("ast_", "".join(operators))

    def test_unparseable_python_falls_back_to_text_operators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blobs = BlobStore(tmp)
            artifact = blobs.put_text("def broken(:\n", name="broken.py")
            check = {"kind": "python_tests", "test_source": CLAMP_TEST_SOURCE, "timeout_seconds": 60}

            report = TextMutationHarness(blobs).run(artifact, check)

            self.assertFalse(report.baseline_passed)
            operators = {result.operator for result in report.results}
            self.assertTrue(operators)
            for operator in operators:
                self.assertFalse(operator.startswith("ast_"))


if __name__ == "__main__":
    unittest.main()
