"""Character stats, timers, resources and the damage pipeline."""
import unittest

from src.models.character import Timer
from tests.helpers import make_enemy, make_player


class TestModifiersAndTimers(unittest.TestCase):
    def test_modifier_layering_and_aliases(self):
        c = make_enemy(str=10)
        c.add_modifier("STR", 5)
        c.add_modifier("str", -2)
        self.assertEqual(c.get_stat("STR"), 13)
        self.assertEqual(c.base_stat("str"), 10)

    def test_turn_timer_skips_application_turn(self):
        c = make_enemy()
        c.turn_count = 3
        c.add_modifier("defense", 10, Timer("TURNS", remaining=1, applied_turn=3))
        c.tick_turn_timers()  # end of turn 3: the application turn is skipped
        self.assertEqual(c.get_stat("defense"), 10)
        c.turn_count = 4
        c.tick_turn_timers()
        self.assertEqual(c.get_stat("defense"), 0)

    def test_timer_applied_off_turn_counts_next_turn(self):
        c = make_enemy()
        c.turn_count = 2  # applied during someone else's turn
        c.add_modifier("str", -3, Timer("TURNS", remaining=1, applied_turn=2))
        c.turn_count = 3
        self.assertEqual(c.get_stat("str"), 7)  # still active during its next turn
        c.tick_turn_timers()
        self.assertEqual(c.get_stat("str"), 10)

    def test_cooldown_counts_owner_turns(self):
        c = make_enemy()
        c.turn_count = 1
        c.set_cooldown("slam", 1)
        c.tick_turn_timers()
        c.turn_count = 2
        self.assertFalse(c.is_ready("slam"))
        c.tick_turn_timers()
        self.assertTrue(c.is_ready("slam"))

    def test_clock_timer(self):
        c = make_enemy()
        c.add_status("MARK", Timer("CLOCK", expires_at=200))
        self.assertEqual(c.expire_clock(199), [])
        self.assertEqual([s.name for s in c.expire_clock(200)], ["MARK"])

    def test_clear_combat_state_keeps_permanent_variables(self):
        c = make_enemy()
        c.set_variable("flag", True)
        c.set_variable("temp", 1, Timer("TURNS", remaining=2))
        c.add_status("POISON", None)
        c.set_cooldown("x", 3)
        c.clear_combat_state()
        self.assertTrue(c.has_variable("flag"))
        self.assertFalse(c.has_variable("temp"))
        self.assertEqual(c.statuses, [])
        self.assertTrue(c.is_ready("x"))


class TestResources(unittest.TestCase):
    def test_derived_maxima(self):
        p = make_player(con=14, int=8)
        self.assertEqual(p.resources["stamina"].maximum, 60)
        self.assertEqual(p.resources["mana"].maximum, 10)

    def test_base_change_recalculates_and_raises_current(self):
        p = make_player(con=10)
        p.resources["stamina"].current = 20
        p.modify_base_stat("con", 2)
        self.assertEqual(p.resources["stamina"].maximum, 50)
        self.assertEqual(p.resources["stamina"].current, 30)

    def test_pay_is_atomic(self):
        p = make_player()
        self.assertFalse(p.pay({"stamina": 10, "mana": 999}))
        self.assertEqual(p.resources["stamina"].current, 40)
        self.assertTrue(p.pay({"stamina": 10}))
        self.assertEqual(p.resources["stamina"].current, 30)

    def test_max_health_up_heals_down_clamps(self):
        p = make_player(max_health=100)
        p.health = 50
        p.modify_base_stat("max_health", 20)
        self.assertEqual((p.health, p.get_stat("max_health")), (70, 120))
        p.health = 120
        p.modify_base_stat("max_health", -30)
        self.assertEqual(p.health, 90)


class TestDamagePipeline(unittest.TestCase):
    def test_defense_applies_to_physical_only(self):
        c = make_enemy(defense=5)
        self.assertEqual(c.apply_damage(20, "PHYSICAL"), 15)
        self.assertEqual(c.apply_damage(20, "FIRE"), 20)

    def test_resistance_and_cap(self):
        c = make_enemy(fire_resistance=50)
        self.assertEqual(c.apply_damage(20, "FIRE"), 10)
        c = make_enemy(ice_resistance=500)
        self.assertEqual(c.apply_damage(100, "ICE"), 10)  # capped at 90%
        c = make_enemy(dark_resistance=-50)
        self.assertEqual(c.apply_damage(10, "DARK"), 15)

    def test_minimum_one_damage(self):
        c = make_enemy(defense=100)
        self.assertEqual(c.apply_damage(5, "PHYSICAL"), 1)
        self.assertEqual(c.apply_damage(0, "PHYSICAL"), 0)

    def test_dead_cannot_heal(self):
        c = make_enemy(max_health=10)
        c.apply_damage(50, "TRUE")
        self.assertFalse(c.is_alive())
        self.assertEqual(c.heal(10), 0)


if __name__ == "__main__":
    unittest.main()
