"""Occurrence gating and outcomes, floor generation rules, shop, camp, growth and save/load."""
import copy
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src import save_manager
from src.game_state import GameState
from src.io.input_provider import ScriptedInput
from src.systems.camp import CONTINUE, QUIT, Camp
from src.systems.combat import Combat
from src.systems.event_manager import EventManager
from src.systems.events import OccurrenceEvent, RestEvent, Shop, unmet_requirement
from src.systems.perks import PerkManager
from tests.helpers import fixture_loader, make_battle, make_enemy, make_player, run


def quiet(fn, *args):
    out = StringIO()
    with redirect_stdout(out):
        result = fn(*args)
    return result, out.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.loader = fixture_loader()
        self.loader.items["health_potion"].update({"price": 20, "tags": ["shop"], "usable_outside_combat": True})
        self.loader.items["fire_bomb"].update({"price": 50, "tags": ["shop"]})
        from src.systems.actions.definitions import ActionRegistry
        self.loader.actions = ActionRegistry.build(self.loader.abilities, self.loader.spells, self.loader.items)
        self.player = self.loader.build_player("Warrior", "Tess")

    def combat(self, answers, seed=0):
        return Combat(self.player, self.loader.settings, self.loader, input_provider=ScriptedInput(answers),
                      rng=random.Random(seed), narrator=lambda s: None)

    def occurrence(self, choices, once=False):
        return OccurrenceEvent("test_occ", "Test", "A test.", choices, once_per_run=once)


class TestOccurrences(Base):
    def test_requirements(self):
        p = self.player
        self.assertEqual(unmet_requirement(p, {"gold": 10}), "requires 10 gold")
        p.gold = 10
        self.assertIsNone(unmet_requirement(p, {"gold": 10, "class": ["Warrior"], "stat": {"str": 16}, "level": 1}))
        self.assertEqual(unmet_requirement(p, {"class": "Rogue"}), "Rogue only")
        self.assertEqual(unmet_requirement(p, {"item": "fire_bomb"}), "requires fire bomb")
        self.assertEqual(unmet_requirement(p, {"stat": {"int": 30}}), "requires INT 30")

    def test_locked_choices_are_not_selectable(self):
        choices = {
            "Buy (40 gold)": {"requires": {"gold": 40}, "effects": [{"type": "item", "item_id": "fire_bomb"}]},
            "Leave": {"effects": []},
        }
        state = GameState(self.player, self.loader.settings)
        combat = self.combat([0])  # index 0 is "Leave": the locked choice is not an option
        _, out = quiet(self.occurrence(choices).execute, state, combat)
        self.assertIn("(locked) Buy (40 gold) - requires 40 gold", out)
        self.assertNotIn("fire_bomb", self.player.inventory)
        self.assertEqual(self.player.gold, 0)

    def test_chance_outcomes(self):
        choices = {"Gamble": {"chance": 0.5,
                              "success": {"effects": [{"type": "gold", "amount": 10}]},
                              "failure": {"effects": [{"type": "gold", "amount": -5}], "result_text": "Lost."}}}
        results = set()
        for seed in range(12):
            self.player.gold = 5
            state = GameState(self.player, self.loader.settings)
            quiet(self.occurrence(choices).execute, state, self.combat(["Gamble"], seed))
            results.add(self.player.gold)
        self.assertEqual(results, {15, 0})

    def test_combat_effect_and_defeat(self):
        choices = {"Fight": {"effects": [{"type": "combat", "enemies": ["goblin"]},
                                         {"type": "gold", "amount": 7}]}}
        state = GameState(self.player, self.loader.settings)
        alive, _ = quiet(self.occurrence(choices).execute, state, self.combat(["Fight"] + ["Attack"] * 10))
        self.assertTrue(alive)
        self.assertGreaterEqual(self.player.gold, 7)
        self.player.health = 1
        self.player.stats["defense"] = 0
        alive, _ = quiet(self.occurrence({"Fight": {"effects": [{"type": "combat", "enemies": ["cave_troll"]},
                                                                {"type": "gold", "amount": 99}]}}).execute,
                         state, self.combat(["Fight"] + ["Defend"] * 50))
        self.assertFalse(alive)

    def test_learn_action_and_once_per_run(self):
        state = GameState(self.player, self.loader.settings)
        event = self.occurrence({"Study": {"effects": [{"type": "learn_action", "action_id": "fireball"}]}}, once=True)
        quiet(event.execute, state, self.combat(["Study"]))
        self.assertIn("fireball", self.player.spells)
        self.assertIn("test_occ", state.used_once)

    def test_validation_catches_bad_occurrences(self):
        self.loader.events["occurrences"]["bad"] = {"choices": {
            "A": {"requires": {"gold": 5, "mood": "happy"}, "effects": [{"type": "learn_action", "action_id": "nope"}]},
            "B": {"requires": {"class": "Bard"}, "chance": 2, "success": {}, "failure": {}},
        }}
        messages = [d.message for d in self.loader.validate() if d.source.startswith("occurrence:bad")]
        for expected in ("unknown requirement 'mood'", "learn_action 'nope'", "unknown class 'Bard'",
                         "chance must be between 0 and 1", "always-available option"):
            self.assertTrue(any(expected in m for m in messages), expected)


class TestFloorGeneration(Base):
    def manager(self, **events_cfg):
        settings = copy.deepcopy(self.loader.settings)
        settings["events"].update(events_cfg)
        self.loader.settings = settings
        return EventManager(self.loader, random.Random(1))

    def test_no_duplicate_occurrences_and_recent_exclusion(self):
        em = self.manager(distributions={"regular": {"normal_occurrence": 1}, "mystery": {"normal_occurrence": 1}})
        state = GameState(self.player, self.loader.settings)
        first = em.generate_choices(state)
        ids = [e.id for e in first]
        self.assertEqual(ids.count("strange_idol"), 1)  # only one normal occurrence exists; others fall back
        second = em.generate_choices(state)
        self.assertNotIn("strange_idol", [e.id for e in second])

    def test_min_level_downgrades_ordeals(self):
        em = self.manager(distributions={"regular": {"ordeal_combat": 1}, "mystery": {"ordeal_combat": 1}},
                          min_level={"ordeal_combat": 3})
        state = GameState(self.player, self.loader.settings)
        self.assertTrue(all(e.subtype == "Regular" for e in em.generate_choices(state)))
        state.current_level = 3
        self.assertIn("Ordeal", [e.subtype for e in em.generate_choices(state)])

    def test_pre_boss_rest_and_boss(self):
        em = self.manager(pre_boss_rest=True, shop={"stock_size": 2})
        state = GameState(self.player, self.loader.settings, current_level=9)
        choices = em.generate_choices(state)
        self.assertIsInstance(choices[0], RestEvent)
        self.assertEqual(choices[0].stock, ["health_potion", "fire_bomb"])
        state.current_level = 10
        self.assertEqual([e.subtype for e in em.generate_choices(state)], ["Boss"])


class TestShopAndCamp(Base):
    def test_buy_and_sell(self):
        self.player.gold = 45
        self.player.inventory = {}
        shop = Shop(["health_potion", "fire_bomb"], self.combat(["Buy Health", "Buy Health", "Sell Health", "Done"]))
        _, out = quiet(shop.visit, self.player)
        self.assertIn("(locked) Buy Fire Bomb - 50g", out)
        self.assertEqual(self.player.inventory, {"health_potion": 1})
        self.assertEqual(self.player.gold, 45 - 40 + 10)

    def test_rest_menu(self):
        self.player.health = 10
        state = GameState(self.player, self.loader.settings)
        self.player.gold = 100
        rest = RestEvent(stock=["health_potion"])
        quiet(rest.execute, state, self.combat(["Trade", "Buy Health", "Done", "Rest"]))
        self.assertEqual(self.player.inventory.get("health_potion"), 3)
        self.assertEqual(self.player.health, 70)

    def test_camp_item_use_and_save(self):
        self.player.health = 50
        self.player.inventory = {"health_potion": 1, "fire_bomb": 1}
        state = GameState(self.player, self.loader.settings)
        saved = []
        camp = Camp(self.combat(["Use", "Health", "Check", "Save"]), save=lambda s: saved.append(s) or "x.json",
                    narrator=lambda s: None)
        self.assertEqual(camp.usable_items(state), ["health_potion"])  # bombs are combat-only
        self.assertEqual(camp.visit(state), QUIT)
        self.assertEqual(self.player.health, 85)
        self.assertEqual(saved, [state])
        self.assertEqual(Camp(self.combat(["Continue"]), narrator=lambda s: None).visit(state), CONTINUE)


class TestCombatRules(Base):
    def test_physical_types_take_defense_and_min_damage(self):
        p, e = make_player(), make_enemy(defense=10)
        settings = {"combat": {"physical_types": ["PHYSICAL", "SWORD"]}}
        battle = make_battle(p, [e], settings=settings)
        run(battle, p, "DAMAGE 1_ENEMY 30 SWORD")
        self.assertEqual(e.health, 80)
        run(battle, p, "DAMAGE 1_ENEMY 30 FIRE")
        self.assertEqual(e.health, 50)
        run(battle, p, "DAMAGE 1_ENEMY 12 SWORD")  # 12 - 10 = 2 < 20% floor of 12 (3)
        self.assertEqual(e.health, 47)

    def test_gold_commands(self):
        p, e = make_player(), make_enemy()
        p.gold = 10
        battle = make_battle(p, [e])
        run(battle, e, "LOSE_GOLD 1_ENEMY 25")
        self.assertEqual(p.gold, 0)
        run(battle, p, "GAIN_GOLD SELF 7\nGAIN_GOLD 1_ENEMY 5")  # enemies hold no gold: no-op
        self.assertEqual(p.gold, 7)

    def _settings(self, **combat):
        settings = copy.deepcopy(self.loader.settings)
        settings["combat"].update(combat)
        return settings

    def test_regen_and_victory_restore(self):
        settings = self._settings(resource_regen={"stamina": 3, "mana": 2}, post_victory_restore=0.5)
        self.player.resources["stamina"].current = 0
        combat = Combat(self.player, settings, self.loader, input_provider=ScriptedInput(["Attack"]),
                        rng=random.Random(0), narrator=lambda s: None, run_stats={})
        combat.run([make_enemy(max_health=1, speed=1, exp_reward=1)])
        stamina = self.player.resources["stamina"]
        self.assertEqual(stamina.current, 3 + stamina.maximum // 2)
        self.assertEqual(combat.run_stats["enemies_defeated"], 1)

    def test_level_up_rolls_points_and_fully_heals(self):
        settings = self._settings()
        settings["player"].update({"exp_formula": "10", "exp_base": 10})
        self.player.exp_to_next_level = 10
        self.player.stat_weights = {"str": 5, "con": 4}
        self.player.health = 5
        self.player.resources["mana"].current = 0
        before = {s: self.player.base_stat(s) for s in ("str", "dex", "con", "int", "wis", "cha")}
        log = []
        combat = Combat(self.player, settings, self.loader, input_provider=ScriptedInput(["Attack"]),
                        rng=random.Random(4), narrator=log.append)
        combat.run([make_enemy(max_health=1, speed=1, exp_reward=10)])
        gained = sum(self.player.base_stat(s) - v for s, v in before.items())
        self.assertEqual(self.player.level, 2)
        self.assertGreaterEqual(gained, 1)
        self.assertEqual(self.player.health, int(self.player.get_stat("max_health")))
        self.assertEqual(self.player.resources["mana"].current, self.player.resources["mana"].maximum)
        self.assertTrue(any(line.startswith(f"    +{int(gained)} stat point") for line in log))

    def test_class_restricted_perks(self):
        perks = {"tier1": [{"perk_id": "w", "name": "W", "requires": {"class": "Warrior"},
                            "effect": {"type": "stat_change", "stat": "str", "value": 1}},
                           {"perk_id": "r", "name": "R", "requires": {"class": "Rogue"},
                            "effect": {"type": "stat_change", "stat": "dex", "value": 1}}]}
        pm = PerkManager(perks, self.loader.settings, ScriptedInput([]), random.Random(0), narrator=lambda s: None)
        self.assertEqual([p["perk_id"] for p in pm.draw(self.player, 2)], ["w"])


class TestSaveLoad(Base):
    def test_round_trip_and_identical_continuation(self):
        p = self.player
        p.gold, p.health, p.perks = 33, 77, ["toughness_1"]
        p.add_item("fire_bomb", 2)
        p.set_variable("met_the_hermit", True)
        p.resources["mana"].current = 1
        state = GameState(p, self.loader.settings, current_level=6, used_once={"idol"})
        state.remember_offers(["strange_idol"])
        rng = random.Random(42)
        with tempfile.TemporaryDirectory() as tmp:
            path = save_manager.save(state, rng, Path(tmp))
            self.assertEqual(save_manager.list_saves(Path(tmp))[0][1], "Tess - Level 1 Warrior, floor 6")
            loaded, loaded_rng = save_manager.load(path, self.loader.settings)
            save_manager.delete(path)
            self.assertFalse(path.exists())
        lp = loaded.player
        for field in ("name", "class_name", "gold", "health", "perks", "inventory", "stats", "abilities", "level", "stat_weights"):
            self.assertEqual(getattr(lp, field), getattr(p, field), field)
        self.assertEqual(lp.resources["mana"].current, 1)
        self.assertTrue(lp.variables["met_the_hermit"].value)
        self.assertEqual((loaded.current_level, loaded.used_once, loaded.recent_offers), (6, {"idol"}, [["strange_idol"]]))
        self.assertEqual([rng.random() for _ in range(5)], [loaded_rng.random() for _ in range(5)])

    def test_unknown_version_rejected(self):
        with self.assertRaises(ValueError):
            save_manager.deserialize({"version": 99}, {})


if __name__ == "__main__":
    unittest.main()


class TestManualRunFixes(Base):
    """Regressions for issues found in manual playtests."""

    def test_camp_can_cast_healing_skills(self):
        self.loader.spells["mend"] = {"name": "Mend", "description": "Heal.", "costs": {"mana": 5},
                                      "usable_outside_combat": True, "action_string": "HEAL SELF 30"}
        from src.systems.actions.definitions import ActionRegistry
        self.loader.actions = ActionRegistry.build(self.loader.abilities, self.loader.spells, self.loader.items)
        self.player.spells = ["mend"]
        self.player.resources["mana"].current = 5
        self.player.health = 50
        state = GameState(self.player, self.loader.settings)
        camp = Camp(self.combat(["Use a skill", "Mend", "Continue"]), narrator=lambda s: None)
        self.assertEqual(camp.visit(state), CONTINUE)
        self.assertEqual((self.player.health, self.player.resources["mana"].current), (80, 0))
        self.assertEqual(camp.usable_skills(state), [])  # can't afford a second cast

    def test_primary_category_listed_first(self):
        menus = []

        class Recording(ScriptedInput):
            def choose(self, prompt, options):
                menus.append(list(options))
                return super().choose(prompt, options)

        self.player.abilities, self.player.spells = ["heavy_slam"], ["fireball", "minor_heal"]
        combat = Combat(self.player, self.loader.settings, self.loader, input_provider=Recording(["Attack"]),
                        rng=random.Random(0), narrator=lambda s: None)
        combat.run([make_enemy(max_health=1, speed=1)])
        self.assertEqual(menus[0][:4], ["Attack", "Defend", "Cast", "Technique"])

    def test_shop_always_stocks_listed_items(self):
        settings = copy.deepcopy(self.loader.settings)
        settings["events"]["shop"] = {"stock_size": 1, "always": ["health_potion"]}
        self.loader.settings = settings
        em = EventManager(self.loader, random.Random(3))
        self.assertEqual(em._shop_stock(), ["health_potion"])

    def test_no_identical_battles_on_one_floor(self):
        settings = copy.deepcopy(self.loader.settings)
        settings["events"]["distributions"] = {"regular": {"regular_combat": 1}, "mystery": {"regular_combat": 1}}
        settings["events"].update(next_event_choices=1, mystery_choices=1)  # fixture has 2 Normal enemies
        self.loader.settings = settings
        for seed in range(20):
            em = EventManager(self.loader, random.Random(seed))
            names = [e.display_name for e in em.generate_choices(GameState(self.player, settings))]
            self.assertEqual(len(names), len(set(names)), names)

    def test_affinity_hint_and_duplicate_labels(self):
        p = make_player()
        a, b = make_enemy("Hollow", fire_resistance=-50), make_enemy("Hollow")
        Combat._label_duplicates([a, b])
        self.assertEqual((a.name, b.name), ("Hollow A", "Hollow B"))
        battle = make_battle(p, [a, b])
        run(battle, p, "DAMAGE ALL_ENEMIES 10 FIRE")
        run(battle, p, "DAMAGE ALL_ENEMIES 10 FIRE")
        self.assertEqual(battle.messages.count("  Hollow A is weak to fire!"), 1)
        self.assertFalse(any("Hollow B is weak" in m for m in battle.messages))

    def test_result_text_before_effects_except_after_fights(self):
        state = GameState(self.player, self.loader.settings)
        event = self.occurrence({"Slip": {"result_text": "You fall.", "effects": [{"type": "hurt", "amount": 5}]}})
        _, out = quiet(event.execute, state, self.combat(["Slip"]))
        self.assertLess(out.index("You fall."), out.index("You lose 5 HP"))
