"""Action String and condition grammar."""
import unittest

from src.systems.actions.nodes import (
    AbilityClause, ActionClause, CharClause, CondBinary, CondNot, FilterBinary, FilterNot, FilterPred,
)
from src.systems.actions.parser import ParseError, parse_condition_text, parse_line, parse_program


class TestLineGrammar(unittest.TestCase):
    def test_selector_mode_filter_and_params(self):
        line = parse_line("DAMAGE 2_ENEMIES CHOICE WITH_STAT HP < 50% 1d6+DEX PHYSICAL")
        self.assertEqual(line.verb, "DAMAGE")
        self.assertEqual((line.target.selector.quantity, line.target.selector.group), ("2", "ENEMY"))
        self.assertEqual(line.target.mode, "CHOICE")
        self.assertEqual(line.target.filter, FilterPred("WITH_STAT", ["HP", "<", "50%"]))
        self.assertEqual(line.args[0].kind, "formula")
        self.assertEqual(line.args[1], "PHYSICAL")

    def test_mode_may_follow_filters(self):
        line = parse_line("HEAL 1_ALLY WITH_TAG goblin_kin RANDOM 10")
        self.assertEqual(line.target.mode, "RANDOM")

    def test_filter_grouping_and_precedence(self):
        line = parse_line("HEAL ALL_ALLIES (WITH_TAG undead OR NOT HAS_STATUS POISON) AND WITH_TAG kin 10")
        f = line.target.filter
        self.assertIsInstance(f, FilterBinary)
        self.assertEqual(f.op, "AND")
        self.assertEqual(f.left.op, "OR")
        self.assertIsInstance(f.left.right, FilterNot)
        self.assertEqual(line.args[0].value, 10)

    def test_balanced_formula_parentheses_stay_one_token(self):
        line = parse_line("DAMAGE SELF (STR+2)*2")
        self.assertEqual(line.args[0].text, "(STR+2)*2")

    def test_dice_quantifier_and_singular_duration(self):
        line = parse_line("BUFF 1d3_ALLIES DEFENSE 5 1_TURN")
        self.assertEqual(line.target.selector.quantity, "1D3")
        self.assertEqual(line.args[2].unit, "TURNS")

    def test_back_references(self):
        self.assertEqual(parse_line("HEAL SPECIFIC_TARGET target1.2 5").target.selector.index, 2)
        self.assertEqual(parse_line("HEAL ALL_TARGETS_LINE3 5").target.selector.line, 3)
        self.assertEqual(parse_line("HEAL PREVIOUS_TARGETS 5").target.selector.kind, "previous_targets")

    def test_delay_forms(self):
        a = parse_line("DELAY BLOCKING TURNS 3 IF SELF HAS_STATUS mark DAMAGE ALL_ENEMIES 200 DARK")
        self.assertEqual((a.delay.mode, a.delay.unit, a.delay.amount.value), ("BLOCKING", "TURNS", 3))
        self.assertIsInstance(a.condition, CharClause)
        b = parse_line("DELAY NONBLOCKING 2_ROUNDS HEAL SELF 5")
        self.assertEqual(b.delay.unit, "ROUNDS")

    def test_if_before_delay_is_rejected(self):
        with self.assertRaises(ParseError):
            parse_line("IF SELF DELAY BLOCKING TURNS 1 HEAL SELF 5")

    def test_errors(self):
        for bad in (
            "SMITE 1_ENEMY 5",               # unknown command
            "HEAL SELF",                     # missing amount
            "DAMAGE 1_ENEMY 1.5*STRR",       # unknown stat in formula
            "DAMAGE 1_ENEMY 5 FIRE extra",   # too many params
            "DAMAGE ADJACENT_TO SPECIFIC_TARGET target1.1 5",  # positional is unsupported
            "BUFF SELF STR 5 3_DAYS",        # bad duration
            "HEAL 1_ALLY WITH_STAT HP ~ 5 5",  # bad comparator
        ):
            with self.subTest(bad=bad), self.assertRaises(ParseError):
                parse_line(bad)

    def test_unsupported_positional_message(self):
        with self.assertRaisesRegex(ParseError, "unsupported"):
            parse_line("DAMAGE LEFT_OF SPECIFIC_TARGET target1.1 5")


class TestProgram(unittest.TestCase):
    def test_malformed_lines_dropped_but_numbering_kept(self):
        program = parse_program("""
            # opening comment
            HEAL SELF 5
            NONSENSE HERE

            DAMAGE 1_ENEMY 3   # trailing comment
        """)
        self.assertEqual([l.number for l in program.lines], [1, 3])
        self.assertEqual(len(program.errors), 1)
        self.assertEqual(program.errors[0].line, 2)


class TestConditions(unittest.TestCase):
    def test_clause_chaining_on_subject_keyword(self):
        cond = parse_condition_text("IF LAST_ACTOR IS_PLAYER AND LAST_ACTION ACTION_HAS_TAG spell")
        self.assertIsInstance(cond, CondBinary)
        self.assertIsInstance(cond.left, CharClause)
        self.assertIsInstance(cond.right, ActionClause)

    def test_and_between_filters_stays_in_clause(self):
        cond = parse_condition_text("SELF WITH_TAG a AND WITH_TAG b")
        self.assertIsInstance(cond, CharClause)
        self.assertIsInstance(cond.phrase.filter, FilterBinary)

    def test_ability_not_and_parentheses(self):
        cond = parse_condition_text("NOT (ABILITY breath IS_READY OR SELF HAS_STATUS POISON)")
        self.assertIsInstance(cond, CondNot)
        self.assertIsInstance(cond.operand.left, AbilityClause)

    def test_trailing_garbage_rejected(self):
        with self.assertRaises(ParseError):
            parse_condition_text("SELF WITH_TAG a banana")


if __name__ == "__main__":
    unittest.main()
