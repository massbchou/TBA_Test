"""Tests for the safe formula evaluator."""
import unittest
from src.formula import evaluate_formula, FormulaError


class TestFormulaEvaluator(unittest.TestCase):
    def test_simple_arithmetic(self):
        self.assertEqual(evaluate_formula("2 + 3"), 5.0)
        self.assertEqual(evaluate_formula("10 - 4"), 6.0)
        self.assertEqual(evaluate_formula("3 * 7"), 21.0)
        self.assertEqual(evaluate_formula("20 / 4"), 5.0)

    def test_precedence_and_parentheses(self):
        self.assertEqual(evaluate_formula("2 + 3 * 4"), 14.0)
        self.assertEqual(evaluate_formula("(2 + 3) * 4"), 20.0)
        self.assertEqual(evaluate_formula("2 ** 3"), 8.0)
        self.assertEqual(evaluate_formula("2 ** 3 ** 2"), 512.0)  # right-associative

    def test_level_growth_formula(self):
        # "base_exp * (1.1 ** (level - 1))"
        formula = "base_exp * (1.1 ** (level - 1))"
        # level 1: 100 * (1.1 ** 0) = 100
        self.assertAlmostEqual(evaluate_formula(formula, base_exp=100, level=1), 100.0)
        # level 5: 100 * (1.1 ** 4) = 146.41
        self.assertAlmostEqual(evaluate_formula(formula, base_exp=100, level=5), 146.41, places=2)

    def test_variable_case_insensitivity(self):
        self.assertEqual(evaluate_formula("1.5 * str", STR=20), 30.0)
        self.assertEqual(evaluate_formula("STR + dex", str=10, DEX=15), 25.0)

    def test_division_by_zero(self):
        with self.assertRaises(FormulaError):
            evaluate_formula("10 / 0")

    def test_rejects_unsafe_input(self):
        with self.assertRaises(FormulaError):
            evaluate_formula("__import__('os').system('ls')")


if __name__ == "__main__":
    unittest.main()
