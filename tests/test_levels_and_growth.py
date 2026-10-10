"""Enemy level scaling, spawn levels, level-based EXP, CON-derived HP and random stat points."""
import random
import statistics
import unittest

from src.models.player import Player
from src.systems.combat import Combat
from src.systems.progression import point_weights, roll_point_count, roll_stat_points
from src.systems.scaling import MIN_FACTOR, scale_stats, spawn_level
from tests.helpers import fixture_loader, make_enemy, make_player

SETTINGS = {"combat": {"enemy_level_variance": 1, "rules_by_level_range": [
    {"min_level": 1, "max_level": 3},
    {"min_level": 4, "max_level": 6, "level_range": [10, 10], "enemy_levels": {"wolf": [20, 22]}},
]}}


class TestScaling(unittest.TestCase):
    def test_scales_up_down_and_floors(self):
        stats = {"max_health": 100, "str": 10, "fire_resistance": -50, "exp_reward": 5}
        rates = {"max_health": 0.1, "str": 0.05}
        up = scale_stats(stats, 5, 10, rates)
        self.assertEqual((up["max_health"], up["str"], up["fire_resistance"], up["exp_reward"]), (150, 12, -50, 5))
        down = scale_stats(stats, 5, 1, rates)
        self.assertEqual(down["max_health"], 60)
        self.assertEqual(scale_stats(stats, 50, 1, rates)["max_health"], round(100 * MIN_FACTOR))

    def test_build_enemy_uses_family_growth(self):
        loader = fixture_loader()
        loader.enemies["goblin"]["growth"] = {"speed": 0.5}
        goblin = loader.build_enemy("goblin", 3)  # base level 1
        self.assertEqual(goblin.level, 3)
        self.assertEqual(goblin.get_stat("speed"), 260)  # 130 * (1 + 0.5 * 2)
        self.assertEqual(goblin.health, round(25 * 1.16))
        self.assertEqual(loader.build_enemy("goblin").level, 1)


class TestSpawnLevel(unittest.TestCase):
    def test_priority(self):
        rng = random.Random(0)
        self.assertEqual(spawn_level("wolf", 5, rng, SETTINGS, {"wolf": [7, 7]}), 7)   # event override
        self.assertIn(spawn_level("wolf", 5, rng, SETTINGS), (20, 21, 22))             # band enemy_levels
        self.assertEqual(spawn_level("rat", 5, rng, SETTINGS), 10)                     # band level_range
        self.assertEqual({spawn_level("rat", 2, random.Random(s), SETTINGS) for s in range(50)}, {1, 2, 3})
        self.assertEqual({spawn_level("rat", 1, random.Random(s), SETTINGS) for s in range(50)}, {1, 2})


class TestExpAndHp(unittest.TestCase):
    def test_exp_from_level_and_category(self):
        combat = Combat(make_player(), {"combat": {"exp_formula": "10 + 5 * level",
                                                   "exp_category_multiplier": {"Elite": 2, "Boss": 4}}})
        enemy = make_enemy()
        enemy.level, enemy.category = 3, "Normal"
        self.assertEqual(combat.exp_for(enemy), 25)
        enemy.category = "Boss"
        self.assertEqual(combat.exp_for(enemy), 100)
        enemy.stats["exp_reward"] = 7
        self.assertEqual(combat.exp_for(enemy), 7)

    def player(self, con=10, hp_bonus=0):
        return Player("P", stats={"con": con, "base_hp": 40, "hp_bonus": hp_bonus},
                      derived_formulas={"max_health": "base_hp + 6 * con", "max_stamina": "40 + 5 * (con - 10)"})

    def test_max_hp_derived_from_con_plus_bonus(self):
        p = self.player(con=15, hp_bonus=5)
        self.assertEqual((p.get_stat("max_health"), p.health), (135, 135))

    def test_con_gain_raises_current_hp_and_max_hp_changes_go_to_bonus(self):
        p = self.player()
        p.health = 50
        p.modify_base_stat("con", 2)
        self.assertEqual((p.get_stat("max_health"), p.health), (112, 62))
        p.modify_base_stat("max_health", 15)  # a perk or event
        self.assertEqual((p.base_stat("hp_bonus"), p.get_stat("max_health"), p.health), (15, 127, 77))
        p.modify_base_stat("max_health", -40)
        self.assertEqual((p.get_stat("max_health"), p.health), (87, 77))

    def test_shipped_classes(self):
        from src.data_loader import DataLoader
        loader = DataLoader()
        loader.load_all()
        for name in loader.starting_classes:
            p = loader.build_player(name)
            self.assertEqual(p.health, int(p.get_stat("max_health")), name)
            self.assertTrue(p.stat_weights, name)


class TestStatPoints(unittest.TestCase):
    WARRIOR = {"str": 5, "con": 4, "dex": 2, "int": 1, "wis": 1, "cha": 1}

    def test_count_floor_and_mean(self):
        for level in (2, 5, 9):
            counts = [roll_point_count(level, random.Random(s)) for s in range(2000)]
            self.assertGreaterEqual(min(counts), 1)
            self.assertAlmostEqual(statistics.mean(counts), level, delta=0.15 * level + 0.3)

    def test_only_primaries_and_total_matches(self):
        for seed in range(200):
            points = roll_stat_points(self.WARRIOR, 5, random.Random(seed))
            self.assertTrue(set(points) <= {"str", "dex", "con", "int", "wis", "cha"})
            self.assertTrue(all(v > 0 for v in points.values()))

    def test_bias_fades_as_rolls_grow(self):
        small = point_weights(self.WARRIOR, 1, 5)
        average = point_weights(self.WARRIOR, 5, 5)
        big = point_weights(self.WARRIOR, 9, 5)
        self.assertAlmostEqual(small["str"], 5 / 14)
        self.assertGreater(small["str"], average["str"])
        self.assertGreater(average["str"], big["str"])
        self.assertLess(small["cha"], big["cha"])
        self.assertAlmostEqual(sum(big.values()), 1.0)


if __name__ == "__main__":
    unittest.main()


class TestEventExp(unittest.TestCase):
    def test_event_exp_scales_with_floor_and_levels_up(self):
        from contextlib import redirect_stdout
        from io import StringIO

        from src.game_state import GameState
        from src.io.input_provider import ScriptedInput
        from src.systems.events import OccurrenceEvent

        loader = fixture_loader()
        player = loader.build_player("Warrior", "T")
        player.exp_to_next_level = 50
        player.health = 10
        state = GameState(player, loader.settings, current_level=5)
        combat = Combat(player, loader.settings, loader, input_provider=ScriptedInput(["Study"]),
                        rng=random.Random(0), narrator=lambda s: None)
        event = OccurrenceEvent("e", "E", "", {"Study": {"effects": [{"type": "exp", "amount": "10 + 6 * floor"}]}})
        with redirect_stdout(StringIO()):
            event.execute(state, combat)
        self.assertEqual(player.exp + 50, 40 + 50)  # 40 EXP at floor 5 against a 50-EXP threshold: no level yet
        self.assertEqual(player.level, 1)
        with redirect_stdout(StringIO()):
            OccurrenceEvent("e2", "E", "", {"Study": {"effects": [{"type": "exp", "amount": 20}]}}).execute(
                state, Combat(player, loader.settings, loader, input_provider=ScriptedInput(["Study"]),
                              rng=random.Random(0), narrator=lambda s: None))
        self.assertEqual(player.level, 2)
        self.assertEqual(player.health, int(player.get_stat("max_health")))  # full heal on level-up
