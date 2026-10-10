"""Shipped data must load and validate cleanly, and full runs must be reproducible."""
import unittest
from contextlib import redirect_stdout
from io import StringIO

import main
from src.data_loader import DataLoader
from tests.helpers import fixture_loader


class TestDataIntegrity(unittest.TestCase):
    def test_shipped_data_has_no_errors_or_warnings(self):
        loader = DataLoader()
        loader.load_all()
        problems = [str(d) for d in loader.validate() if d.severity != "info"]
        self.assertEqual(problems, [])

    def test_fixture_data_has_no_errors_or_warnings(self):
        problems = [str(d) for d in fixture_loader().validate() if d.severity != "info"]
        self.assertEqual(problems, [])

    def test_every_action_parsed(self):
        loader = DataLoader()
        loader.load_all()
        for action in loader.actions.all():
            if action.action_string is not None:
                self.assertTrue(action.program.lines, action.id)


class TestEndToEnd(unittest.TestCase):
    def play(self, seed: int, floors: int = 6) -> str:
        out = StringIO()
        with self.assertNoLogs("textrogue", level="WARNING"), redirect_stdout(out):
            main.main(["--auto", "--seed", str(seed), "--floors", str(floors)])
        return out.getvalue()

    def test_seeded_runs_are_reproducible(self):
        first = self.play(1)
        self.assertEqual(first, self.play(1))
        self.assertIn("FLOOR 1", first)
        self.assertTrue("GAME OVER" in first or "THE END" in first)

    def test_many_seeds_complete_without_errors(self):
        for seed in range(15):
            with self.subTest(seed=seed):
                out = self.play(seed, floors=10)
                self.assertTrue("GAME OVER" in out or "THE END" in out)


if __name__ == "__main__":
    unittest.main()
