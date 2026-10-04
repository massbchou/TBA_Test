"""Tests for random selection and dice utilities."""
import unittest
from src.utils import weighted_choice, roll_dice


class TestUtils(unittest.TestCase):
    def test_weighted_choice_single(self):
        res = weighted_choice({"only_option": 100})
        self.assertEqual(res, "only_option")

    def test_weighted_choice_empty(self):
        self.assertIsNone(weighted_choice({}))

    def test_weighted_choice_zero_weights(self):
        self.assertIsNone(weighted_choice({"a": 0, "b": 0}))

    def test_weighted_choice_distribution(self):
        counts = {"A": 0, "B": 0}
        for _ in range(1000):
            pick = weighted_choice({"A": 80, "B": 20})
            if pick in counts:
                counts[pick] += 1
        # A should be roughly 80% (give wide tolerance)
        self.assertGreater(counts["A"], 650)
        self.assertLess(counts["A"], 950)

    def test_roll_dice_integer(self):
        self.assertEqual(roll_dice("25"), 25)

    def test_roll_dice_expression(self):
        for _ in range(50):
            roll = roll_dice("1d6+2")
            self.assertGreaterEqual(roll, 3)
            self.assertLessEqual(roll, 8)


if __name__ == "__main__":
    unittest.main()
