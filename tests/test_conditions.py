"""Condition evaluation for IF lines."""
import unittest

from src.systems.actions.definitions import ActionDef
from tests.helpers import make_battle, make_enemy, make_player, run


class TestConditions(unittest.TestCase):
    def setUp(self):
        self.p = make_player()
        self.e = make_enemy()
        self.battle = make_battle(self.p, [self.e])

    def test_hp_percentage_gate(self):
        run(self.battle, self.p, "IF SELF WITH_STAT HP < 50% BUFF SELF STR 1")
        self.assertEqual(self.p.get_stat("str"), 10)
        self.p.health = 40
        run(self.battle, self.p, "IF SELF WITH_STAT hp_percentage <= 40 BUFF SELF STR 1")
        self.assertEqual(self.p.get_stat("str"), 11)

    def test_last_actor_and_implicit_spell_tag(self):
        spell = ActionDef.from_data("fireball", {"action_string": "DAMAGE ALL_ENEMIES 1"}, "spell")
        self.assertTrue(spell.has_tag("spell"))
        text = "IF LAST_ACTOR IS_PLAYER AND LAST_ACTION ACTION_HAS_TAG spell BUFF SELF STR 5"
        # Nothing logged yet -> false
        self.battle.orchestrator.execute_string(self.e, text, self.battle)
        self.assertEqual(self.e.get_stat("str"), 10)
        self.battle.log.record(self.p, spell, [self.e])
        self.battle.orchestrator.execute_string(self.e, text, self.battle)
        self.assertEqual(self.e.get_stat("str"), 15)

    def test_not_and_parentheses(self):
        text = "IF NOT (SELF HAS_STATUS POISON OR SELF WITH_TAG boss) BUFF SELF STR 1"
        run(self.battle, self.e, text)
        self.assertEqual(self.e.get_stat("str"), 11)
        self.e.add_status("POISON", None)
        run(self.battle, self.e, text)
        self.assertEqual(self.e.get_stat("str"), 11)

    def test_with_stat_falls_back_to_variables(self):
        self.e.set_variable("enraged", True)
        run(self.battle, self.e, "IF SELF WITH_STAT enraged = true BUFF SELF STR 1")
        self.assertEqual(self.e.get_stat("str"), 11)
        run(self.battle, self.e, "IF SELF WITH_STAT missing_var = 1 BUFF SELF STR 1")
        self.assertEqual(self.e.get_stat("str"), 11)
        run(self.battle, self.e, "IF SELF WITH_STAT missing_var != 1 BUFF SELF STR 1")
        self.assertEqual(self.e.get_stat("str"), 12)

    def test_ability_is_ready(self):
        self.e.abilities = [{"ability_id": "breath", "cooldowns": {"self": 2}}]
        text = "IF ABILITY breath IS_READY BUFF SELF STR 1"
        run(self.battle, self.e, text)
        self.assertEqual(self.e.get_stat("str"), 11)
        self.e.set_cooldown("breath", 2)
        run(self.battle, self.e, text)
        self.assertEqual(self.e.get_stat("str"), 11)
        run(self.battle, self.e, "IF ABILITY not_owned IS_READY BUFF SELF STR 1")
        self.assertEqual(self.e.get_stat("str"), 11)

    def test_ally_and_enemy_counts(self):
        other = make_enemy("Other")
        battle = make_battle(self.p, [self.e, other])
        run(battle, self.e, "IF SELF ALLY_COUNT = 1 AND SELF ENEMY_COUNT == 1 BUFF SELF STR 1")
        self.assertEqual(self.e.get_stat("str"), 11)
        other.health = 0
        run(battle, self.e, "IF SELF ALLY_COUNT = 0 BUFF SELF STR 1")
        self.assertEqual(self.e.get_stat("str"), 12)


if __name__ == "__main__":
    unittest.main()
