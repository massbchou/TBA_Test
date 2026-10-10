"""DELAY semantics."""
import unittest

from tests.helpers import make_battle, make_enemy, make_player, run

RITUAL = """
APPLY SELF ritual_mark 3_TURNS
DELAY BLOCKING TURNS 3 IF SELF HAS_STATUS ritual_mark DAMAGE ALL_ENEMIES 200 DARK
HEAL SELF 100
"""

CHARGE = """
SET SELF is_charging true 1_TURN
DELAY NONBLOCKING TURNS 1 IF SELF EXISTS_VARIABLE is_charging DAMAGE 1_ENEMY CHOICE 5d10 SHOCK
BUFF SELF DEFENSE 50 1_TURN
"""


def own_turn(battle, char, text=None):
    battle.start_turn(char)
    result = run(battle, char, text) if text else None
    battle.end_turn(char)
    return result


class TestDelays(unittest.TestCase):
    def setUp(self):
        self.p = make_player()
        self.e = make_enemy(max_health=300)
        self.battle = make_battle(self.p, [self.e])

    def test_ritual_of_sacrifice_blocking(self):
        self.p.health = 10
        own_turn(self.battle, self.p, RITUAL)
        self.assertEqual(self.p.health, 10)  # HEAL is blocked behind the delay
        own_turn(self.battle, self.p)
        own_turn(self.battle, self.p)
        self.assertEqual(self.e.health, 300)
        self.battle.start_turn(self.p)  # 3rd subsequent turn: fires before acting
        self.assertEqual(self.e.health, 100)
        self.assertEqual(self.p.health, 100)

    def test_defensive_charge_nonblocking(self):
        own_turn(self.battle, self.p, CHARGE)
        self.assertEqual(self.p.get_stat("defense"), 50)  # line 3 ran immediately
        self.battle.start_turn(self.p)
        self.assertLess(self.e.health, 300)  # charge released while is_charging still set

    def test_if_evaluated_at_fire_time(self):
        own_turn(self.battle, self.p, RITUAL)
        self.p.remove_status("ritual_mark")
        for _ in range(3):
            own_turn(self.battle, self.p)
        self.assertEqual(self.e.health, 300)

    def test_caster_death_cancels(self):
        own_turn(self.battle, self.e, "DELAY NONBLOCKING TURNS 1 DAMAGE 1_ENEMY 10")
        self.assertEqual(len(self.battle.scheduler), 1)
        run(self.battle, self.p, "DAMAGE 1_ENEMY 999 TRUE")
        self.assertEqual(len(self.battle.scheduler), 0)
        self.assertEqual(self.p.health, 100)

    def test_rounds_delay_fires_on_clock(self):
        run(self.battle, self.p, "DELAY NONBLOCKING ROUNDS 2 DAMAGE 1_ENEMY 10 TRUE")
        self.battle.advance_clock(199)
        self.assertEqual(self.e.health, 300)
        self.battle.advance_clock(200)  # round length = 12500 / 125 = 100
        self.assertEqual(self.e.health, 290)


if __name__ == "__main__":
    unittest.main()
