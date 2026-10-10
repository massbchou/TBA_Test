"""Tests for continuous-time turn resolution in Combat."""
import unittest
from src.models.player import Player
from src.models.enemy import Enemy
from src.systems.combat import Combat, CombatResult


class TestCombatTurnOrder(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "combat": {
                "round_time_units": 12500,
            },
            "player": {
                "exp_formula": "100",
                "exp_base": 100,
            },
        }

    def test_speed_advantage_turn_frequency(self):
        """A character with double speed should act twice as often."""
        round_units = 12500
        # Fast character: speed 250 -> cost = 12500 // 250 = 50
        # Slow character: speed 125 -> cost = 12500 // 125 = 100
        fast_player = Player("FastGuy", stats={"max_health": 500, "speed": 250, "str": 5})
        slow_enemy = Enemy("SlowGuy", stats={"max_health": 500, "speed": 125, "str": 5})

        combat = Combat(player=fast_player, settings=self.settings)

        # Simulate 2 rounds of time progression
        # fast guy cost: 50, slow guy cost: 100
        turn_history = []
        participants = [fast_player, slow_enemy]
        for p in participants:
            p.action_time = 0

        for _ in range(6):
            actor = min(participants, key=lambda p: p.action_time)
            turn_history.append(actor.name)
            speed = max(1, int(actor.get_stat("speed")))
            actor.action_time += round_units // speed

        # Expected order:
        # At start: both 0 -> min selects fast_player (first in list) -> time becomes 50
        # Next: slow_enemy (0 vs 50) -> time becomes 100
        # Next: fast_player (50 vs 100) -> time becomes 100
        # Next: fast_player (100 vs 100, first in list) -> time becomes 150
        # Next: slow_enemy (100 vs 150) -> time becomes 200
        # Next: fast_player (150 vs 200) -> time becomes 200
        self.assertEqual(turn_history.count("FastGuy"), 4)
        self.assertEqual(turn_history.count("SlowGuy"), 2)

    def test_combat_victory_resolves(self):
        """Player with high strength defeats weak enemy."""
        player = Player("Mighty", stats={"max_health": 100, "speed": 150, "str": 50, "defense": 0})
        enemy = Enemy("WeakGoblin", stats={"max_health": 15, "speed": 50, "str": 2, "defense": 0})

        combat = Combat(player=player, settings=self.settings)
        result = combat.run([enemy])

        self.assertIs(result, CombatResult.VICTORY)
        self.assertFalse(enemy.is_alive())
        self.assertTrue(player.is_alive())


if __name__ == "__main__":
    unittest.main()
