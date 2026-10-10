"""Dice atoms, resolvers, and amount parsing."""
import random
import unittest

from src.formula import FormulaError, evaluate_formula, validate_formula
from src.systems.actions.parser import ParseError, parse_amount


class TestFormulaDice(unittest.TestCase):
    def test_dice_atoms_are_seeded(self):
        a = evaluate_formula("2d10+3", rng=random.Random(5))
        b = evaluate_formula("2d10+3", rng=random.Random(5))
        self.assertEqual(a, b)
        self.assertTrue(5 <= a <= 23)

    def test_dice_with_stat_resolver(self):
        stats = {"int": 7}
        value = evaluate_formula("1d1+INT", resolver=lambda n: stats[n.lower()])
        self.assertEqual(value, 8)

    def test_unknown_variable_raises(self):
        with self.assertRaises(FormulaError):
            evaluate_formula("1+NOPE", resolver=lambda n: (_ for _ in ()).throw(KeyError(n)))

    def test_validate_formula(self):
        self.assertIsNone(validate_formula("1.5*STR"))
        self.assertIsNotNone(validate_formula("1.5*"))
        self.assertIsNotNone(validate_formula("1.5*STRR", known_name=lambda n: n.lower() == "str"))

    def test_range_versus_subtraction(self):
        self.assertEqual(parse_amount("20-30").kind, "range")
        self.assertEqual(parse_amount("(30-20)").kind, "formula")
        self.assertEqual(parse_amount("25").kind, "int")
        with self.assertRaises(ParseError):
            parse_amount("30-20")  # low > high


if __name__ == "__main__":
    unittest.main()
