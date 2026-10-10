"""Command verbs and status effects."""
import unittest

from src.models.status import StatusDef
from tests.helpers import POISON, make_battle, make_enemy, make_player, run


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.p = make_player(int=10)
        self.e = make_enemy(defense=3)
        self.battle = make_battle(self.p, [self.e])

    def test_damage_uses_effective_stats_and_type(self):
        self.p.add_modifier("str", 10)
        result = run(self.battle, self.p, "DAMAGE 1_ENEMY 1.5*STR")
        self.assertEqual(result.total("DAMAGE"), 30 - 3)
        run(self.battle, self.p, "DAMAGE 1_ENEMY 10 FIRE")
        self.assertEqual(self.e.health, 100 - 27 - 10)

    def test_previous_damage_dealt(self):
        self.p.health = 50
        run(self.battle, self.p, "DAMAGE 1_ENEMY 13\nHEAL SELF PREVIOUS_DAMAGE_DEALT")
        self.assertEqual(self.p.health, 60)

    def test_heal_range_and_cap(self):
        self.e.health = 90
        run(self.battle, self.e, "HEAL SELF 20-30")
        self.assertEqual(self.e.health, 100)

    def test_buff_debuff_with_duration(self):
        run(self.battle, self.p, "BUFF SELF DEFENSE 10 2_TURNS\nDEBUFF 1_ENEMY SPEED 30 1_TURN")
        self.assertEqual(self.p.get_stat("defense"), 10)
        self.assertEqual(self.e.get_stat("speed"), 70)
        self.assertEqual(self.p.modifiers[0].timer.remaining, 2)

    def test_reapplying_same_action_refreshes_unless_it_stacks(self):
        from tests.helpers import action
        slow = action("DEBUFF 1_ENEMY SPEED 25 2_TURNS", action_id="grasp")
        rally = action("BUFF SELF STR 4 3_TURNS", action_id="rally", tags=["stacks"])
        for _ in range(3):
            self.battle.orchestrator.execute(self.p, slow, self.battle)
            self.battle.orchestrator.execute(self.p, rally, self.battle)
        self.assertEqual(self.e.get_stat("speed"), 75)
        self.assertEqual(self.p.get_stat("str"), 22)
        self.assertIn("  Goblin's Speed penalty is renewed.", self.battle.messages)

    def test_set_literals(self):
        run(self.battle, self.p, "SET SELF a true\nSET SELF b 3\nSET SELF c hello 2_TURNS")
        self.assertIs(self.p.variables["a"].value, True)
        self.assertEqual(self.p.variables["b"].value, 3)
        self.assertEqual(self.p.variables["c"].value, "hello")
        self.assertIsNotNone(self.p.variables["c"].timer)

    def test_restore(self):
        self.p.resources["stamina"].current = 0
        result = run(self.battle, self.p, "RESTORE SELF STAMINA 25")
        self.assertEqual(self.p.resources["stamina"].current, 25)
        self.assertEqual(result.total("RESTORE"), 25)
        run(self.battle, self.e, "RESTORE SELF MANA 25")  # enemies have no resources: no-op

    def test_cleanse_specific_and_all_debuffs(self):
        self.p.add_status("POISON", None)
        self.p.add_status("MARK", None)  # undefined marker status, not a debuff
        self.p.add_modifier("str", -5)
        self.p.add_modifier("dex", 2)
        run(self.battle, self.p, "CLEANSE SELF ALL_DEBUFFS")
        self.assertEqual([s.name for s in self.p.statuses], ["MARK"])
        self.assertEqual((self.p.get_stat("str"), self.p.get_stat("dex")), (10, 12))
        run(self.battle, self.p, "CLEANSE SELF MARK")
        self.assertEqual(self.p.statuses, [])

    def test_malformed_runtime_line_is_skipped(self):
        with self.assertLogs("textrogue.actions", "WARNING"):
            result = run(self.battle, self.p, "DAMAGE 1_ENEMY 10/(STR-10)\nHEAL SELF 1")
        self.assertIn("error", result.lines[0].skipped_reason)
        self.assertEqual(len(result.lines), 2)


class TestStatuses(unittest.TestCase):
    def test_poison_ticks_bypasses_defense_and_expires(self):
        p, e = make_player(), make_enemy(defense=50)
        battle = make_battle(p, [e])
        run(battle, p, "APPLY 1_ENEMY POISON 3_TURNS")
        for _ in range(4):
            battle.start_turn(e)
            battle.end_turn(e)
        self.assertEqual(e.health, 100 - 3 * 4)
        self.assertFalse(e.has_status("POISON"))
        self.assertIn("  Goblin's POISON wears off.", battle.messages)

    def test_stacking_modes(self):
        statuses = {
            "BLEED": StatusDef.from_data("BLEED", {"stacking": "stack", "hooks": {"on_turn_start": "DAMAGE SELF 1 TRUE"}}),
            "STUN": StatusDef.from_data("STUN", {"stacking": "ignore"}),
            "POISON": POISON,
        }
        p, e = make_player(), make_enemy()
        battle = make_battle(p, [e], statuses=statuses)
        run(battle, p, "APPLY 1_ENEMY BLEED 5_TURNS\nAPPLY 1_ENEMY BLEED 5_TURNS")
        self.assertEqual(e.get_status("BLEED").stacks, 2)
        battle.start_turn(e)
        self.assertEqual(e.health, 98)  # hook runs once per stack
        run(battle, p, "APPLY 1_ENEMY STUN 1_TURN")
        first_timer = e.get_status("STUN").timer
        run(battle, p, "APPLY 1_ENEMY STUN 9_TURNS")
        self.assertIs(e.get_status("STUN").timer, first_timer)
        run(battle, p, "APPLY 1_ENEMY POISON 1_TURN\nAPPLY 1_ENEMY POISON 4_TURNS")
        self.assertEqual(e.get_status("POISON").timer.remaining, 4)
        self.assertEqual(e.get_status("POISON").stacks, 1)

    def test_on_apply_and_on_expire_hooks(self):
        statuses = {"CURSE": StatusDef.from_data("CURSE", {"hooks": {
            "on_apply": "DEBUFF SELF STR 2", "on_expire": "DAMAGE SELF 5 TRUE"}})}
        p, e = make_player(), make_enemy()
        battle = make_battle(p, [e], statuses=statuses)
        run(battle, p, "APPLY 1_ENEMY CURSE 1_TURN")
        self.assertEqual(e.get_stat("str"), 8)
        battle.start_turn(e)
        battle.end_turn(e)
        self.assertEqual(e.health, 95)

    def test_hook_recursion_is_bounded(self):
        statuses = {"ECHO": StatusDef.from_data("ECHO", {"hooks": {"on_damage_taken": "DAMAGE SELF 1 TRUE"}})}
        p, e = make_player(), make_enemy()
        battle = make_battle(p, [e], statuses=statuses)
        e.add_status("ECHO", None)
        run(battle, p, "DAMAGE 1_ENEMY 1 TRUE")
        self.assertGreater(e.health, 90)


if __name__ == "__main__":
    unittest.main()
