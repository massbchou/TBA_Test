"""Perks, effects and occurrences."""
import random
import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.game_state import GameState
from src.io.input_provider import ScriptedInput
from src.systems.combat import Combat
from src.systems.events import OccurrenceEvent, RestEvent
from src.systems.perks import PerkManager, tier_for_level
from tests.helpers import fixture_loader, make_enemy, make_player

PERKS = {
    "tier1": [
        {"perk_id": f"p{i}", "name": f"P{i}", "effect": {"type": "stat_change", "stat": "str", "value": 1}}
        for i in range(4)
    ] + [{"perk_id": "once", "name": "Once", "repeatable": False,
          "effect": {"type": "stat_change", "stat": "max_health", "value": 20}}],
    "tier2": [{"perk_id": "t2", "name": "T2", "effect": {"type": "stat_change", "stat": "dex", "value": 5}}],
}
SETTINGS = {"player": {"level_up_perk_choices": 3, "exp_formula": "100", "exp_base": 100},
            "events": {"boss_level_interval": 10}, "combat": {}}


class TestPerks(unittest.TestCase):
    def manager(self, answers=(), seed=0):
        return PerkManager(PERKS, SETTINGS, ScriptedInput(answers), random.Random(seed), narrator=lambda s: None)

    def test_tiers(self):
        self.assertEqual([tier_for_level(lvl, 10) for lvl in (1, 10, 11, 25)], [1, 1, 2, 3])
        self.assertEqual(len(self.manager().pool_for_level(5)), 5)
        self.assertEqual(self.manager().pool_for_level(15)[0]["perk_id"], "t2")
        self.assertEqual(self.manager().pool_for_level(35)[0]["perk_id"], "t2")  # highest available tier

    def test_draw_size_and_non_repeatable(self):
        player = make_player()
        self.assertEqual(len(self.manager().draw(player, 2)), 3)
        player.perks.append("once")
        for seed in range(20):
            self.assertNotIn("once", [p["perk_id"] for p in self.manager(seed=seed).draw(player, 2)])

    def test_draw_smaller_pool(self):
        self.assertEqual(len(self.manager().draw(make_player(), 15)), 1)

    def test_offer_applies_effect(self):
        player = make_player()
        player.health = 50
        chosen = self.manager(answers=["Once"]).offer(player, 2)
        self.assertEqual(chosen["perk_id"], "once")
        self.assertEqual((player.health, player.get_stat("max_health")), (70, 120))
        self.assertEqual(player.perks, ["once"])

    def test_one_offer_per_level_gained(self):
        player = make_player(str=99)
        manager = self.manager(answers=[0, 0])
        combat = Combat(player, SETTINGS, input_provider=ScriptedInput(["Attack"]), rng=random.Random(0),
                        narrator=lambda s: None, perk_manager=manager)
        combat.run([make_enemy(max_health=1, speed=1, exp_reward=250)])
        self.assertEqual(player.level, 3)
        self.assertEqual(len(player.perks), 2)


class TestOccurrences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = fixture_loader()

    def run_event(self, event, player, answers):
        combat = Combat(player, self.loader.settings, self.loader, input_provider=ScriptedInput(answers),
                        narrator=lambda s: None)
        with redirect_stdout(StringIO()) as out:
            event.execute(GameState(player, self.loader.settings), combat)
        return out.getvalue()

    def occurrence(self, key):
        data = self.loader.events["occurrences"][key]
        return OccurrenceEvent(key, data["display_name"], data["description"], data["choices"])

    def test_nested_choice_applies_all_effects(self):
        player = self.loader.build_player("Warrior")
        out = self.run_event(self.occurrence("strange_idol"), player, ["Pray", "Accept"])
        self.assertEqual(player.get_stat("str"), 18)
        self.assertEqual((player.get_stat("max_health"), player.health), (110, 110))
        self.assertIn("You feel stronger", out)

    def test_other_branches(self):
        player = self.loader.build_player("Warrior")
        self.run_event(self.occurrence("strange_idol"), player, ["Pray", "Reject"])
        self.run_event(self.occurrence("strange_idol"), player, ["Smash"])
        self.assertEqual(player.get_stat("str"), 16)
        player.health = 50
        self.run_event(self.occurrence("healing_spring"), player, ["Drink"])
        self.assertEqual(player.health, 70)

    def test_rest_refills_resources(self):
        player = self.loader.build_player("Rogue")
        player.health = 10
        player.resources["mana"].current = 0
        self.run_event(RestEvent(), player, [])
        self.assertEqual(player.health, 55)
        self.assertEqual(player.resources["mana"].current, 20)

    def test_effect_types(self):
        from src.systems.effects import apply_effects
        player = make_player()
        msgs = apply_effects(player, [
            {"type": "gold", "amount": 15}, {"type": "gold", "amount": -100},
            {"type": "item", "item_id": "antidote", "quantity": 2},
            {"type": "restore", "resource": "all"}, {"type": "bogus"},
        ], self.loader)
        self.assertEqual(player.gold, 0)
        self.assertEqual(player.inventory, {"antidote": 2})
        self.assertIn("You obtain Antidote x2.", msgs)
        self.assertTrue(any("Unknown effect type" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()
