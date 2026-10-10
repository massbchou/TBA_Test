"""Items through the Action DSL and loot drops."""
import random
import unittest

from src.io.input_provider import ScriptedInput
from src.systems.combat import Combat
from tests.helpers import fixture_loader, make_battle, make_enemy, make_player


class TestItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = fixture_loader()

    def use(self, item_id, caster, enemies):
        battle = make_battle(caster, enemies)
        return battle.orchestrator.execute(caster, self.loader.actions[item_id], battle)

    def test_item_actions(self):
        p = make_player()
        p.health = 10
        self.use("health_potion", p, [make_enemy()])
        self.assertEqual(p.health, 45)
        p.resources["stamina"].current = 0
        self.use("stamina_tonic", p, [make_enemy()])
        self.assertEqual(p.resources["stamina"].current, 25)
        p.add_status("POISON", None)
        self.use("antidote", p, [make_enemy()])
        self.assertFalse(p.has_status("POISON"))
        a, b = make_enemy("A", defense=10), make_enemy("B")
        self.use("fire_bomb", p, [a, b])
        self.assertEqual((a.health, b.health), (75, 75))

    def test_items_are_tagged_item(self):
        self.assertTrue(self.loader.actions["health_potion"].has_tag("item"))

    def test_inventory_stacks(self):
        p = make_player()
        p.add_item("health_potion", 2)
        self.assertTrue(p.remove_item("health_potion"))
        self.assertEqual(p.inventory, {"health_potion": 1})
        self.assertTrue(p.remove_item("health_potion"))
        self.assertEqual(p.inventory, {})
        self.assertFalse(p.remove_item("health_potion"))

    def test_loot_drops_land_in_inventory(self):
        p = self.loader.build_player("Warrior")
        p.inventory = {}
        enemy = make_enemy()
        enemy.loot_table = [
            {"type": "item", "item_id": "fire_bomb", "chance": 1.0, "min_amount": 2, "max_amount": 2},
            {"type": "item", "item_id": "antidote", "chance": 0.0, "min_amount": 1, "max_amount": 1},
            {"type": "gold", "chance": 1.0, "min_amount": 5, "max_amount": 5},
        ]
        combat = Combat(p, self.loader.settings, self.loader, input_provider=ScriptedInput([]),
                        rng=random.Random(0), narrator=lambda s: None)
        combat.enemies = [enemy]
        combat._process_post_combat_rewards()
        self.assertEqual(p.inventory, {"fire_bomb": 2})
        self.assertEqual(p.gold, 5)

    def test_unknown_loot_item_is_reported(self):
        loader = fixture_loader()
        loader.enemies["goblin"]["loot_table"].append({"type": "item", "item_id": "nope", "chance": 1})
        messages = [d.message for d in loader.validate() if d.severity == "error"]
        self.assertTrue(any("unknown item 'nope'" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
