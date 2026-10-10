"""Player combat menu, turn order rules and combat outcomes."""
import random
import unittest

from src.io.input_provider import ScriptedInput
from src.systems.actions.definitions import ActionRegistry
from src.systems.battle import Battle
from src.systems.combat import Combat, CombatResult
from tests.helpers import fixture_loader, make_enemy, make_player

SETTINGS = {
    "combat": {"round_time_units": 12500, "reference_speed": 125, "stamina_regen_per_turn": 5,
               "defend_formula": "5+CON/2", "run": {"disallowed_subtypes": ["Boss"]}},
    "player": {"exp_formula": "100", "exp_base": 100},
}


class _Loader:
    """Minimal stand-in for DataLoader with a custom action registry."""

    def __init__(self, abilities=None, spells=None, items=None):
        self.actions = ActionRegistry.build(abilities, spells, items)
        self.status_defs = {}
        self.items = items or {}


def make_combat(player, answers, loader=None, settings=SETTINGS, seed=0):
    log: list[str] = []
    combat = Combat(player, settings, data_loader=loader or _Loader(), input_provider=ScriptedInput(answers),
                    rng=random.Random(seed), narrator=log.append)
    return combat, log


class TestPlayerActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = fixture_loader()

    def test_technique_costs_stamina(self):
        warrior = self.loader.build_player("Warrior")
        combat, _ = make_combat(warrior, ["Technique", "Heavy Slam"], self.loader)
        result = combat.run([make_enemy(max_health=1, speed=1)])
        self.assertIs(result, CombatResult.VICTORY)
        self.assertEqual(warrior.resources["stamina"].current, 60 - 15 + 5)

    def test_unaffordable_reprompts_without_spending_turn(self):
        warrior = self.loader.build_player("Warrior")
        warrior.resources["stamina"].current = 0
        enemy = make_enemy(max_health=1, speed=1)
        combat, log = make_combat(warrior, ["Technique", "Heavy Slam", "Technique", "Back", "Attack"], self.loader)
        self.assertIs(combat.run([enemy]), CombatResult.VICTORY)
        self.assertIn("You can't afford Heavy Slam right now.", log)
        self.assertEqual(sum(1 for line in log if line.startswith("> ")), 1)

    def test_menu_hides_empty_categories(self):
        warrior = self.loader.build_player("Warrior")
        warrior.inventory = {}
        menus = []

        class Recording(ScriptedInput):
            def choose(self, prompt, options):
                menus.append(list(options))
                return super().choose(prompt, options)

        combat = Combat(warrior, SETTINGS, data_loader=self.loader, input_provider=Recording(["Attack"]),
                        rng=random.Random(0), narrator=lambda s: None)
        combat.run([make_enemy(max_health=1, speed=1)])
        self.assertEqual(menus[0], ["Attack", "Defend", "Technique", "Bag (empty)", "Run"])

    def test_defend_reduces_physical_damage_until_next_turn_ends(self):
        player = make_player(speed=200, con=10)
        enemy = make_enemy(str=20, speed=100, max_health=500)
        combat, log = make_combat(player, ["Defend", "Attack", "Attack", "Run"],
                                  settings={**SETTINGS, "combat": {**SETTINGS["combat"],
                                            "run": {"min_chance": 100, "max_chance": 100}}})
        combat.run([enemy])
        hits = [line for line in log if line.startswith("  Hero takes")]
        self.assertEqual(hits[0], "  Hero takes 10 PHYSICAL damage. (HP 90/100)")  # 20 - (5 + 10/2)
        self.assertEqual(hits[1], "  Hero takes 20 PHYSICAL damage. (HP 70/100)")  # buff expired

    def test_bag_uses_and_consumes_item(self):
        warrior = self.loader.build_player("Warrior")
        warrior.health = 50
        warrior.inventory = {"health_potion": 1}
        combat, log = make_combat(warrior, ["Bag", "Health Potion", "Attack"], self.loader)
        combat.run([make_enemy(max_health=1, speed=1)])
        self.assertIn(f"  {warrior.name} recovers 35 HP. (HP 85/120)", log)
        self.assertEqual(warrior.inventory, {})

    def test_run_success_flees_without_rewards(self):
        player = make_player(speed=300)
        settings = {**SETTINGS, "combat": {**SETTINGS["combat"], "run": {"min_chance": 100, "max_chance": 100}}}
        combat, _ = make_combat(player, ["Run"], settings=settings)
        self.assertIs(combat.run([make_enemy(speed=1)]), CombatResult.FLED)
        self.assertEqual(player.gold, 0)
        self.assertEqual(player.exp, 0)

    def test_run_blocked_in_boss_fight(self):
        player = make_player(speed=300, str=50)
        combat, log = make_combat(player, ["Run", "Attack"])
        result = combat.run([make_enemy(max_health=10, speed=1)], subtype="Boss")
        self.assertIs(result, CombatResult.VICTORY)
        self.assertIn("There is no escape from this fight!", log)

    def test_combat_state_cleared_after_battle(self):
        player = make_player(str=50)
        combat, _ = make_combat(player, ["Defend", "Attack"])
        combat.run([make_enemy(max_health=10, speed=1)])
        self.assertEqual(player.modifiers, [])
        self.assertEqual(player.turn_count, 0)


class TestTurnOrder(unittest.TestCase):
    def test_speed_floor_prevents_lockout(self):
        player = make_player(speed=100, str=10)
        combat, _ = make_combat(player, [])
        player.add_modifier("speed", -500)
        self.assertEqual(combat._turn_speed(player), 50)

    def test_round_length(self):
        battle = Battle(make_player(), [make_enemy()], settings=SETTINGS)
        self.assertEqual(battle.round_length, 100)

    def test_tie_break_speed_then_player(self):
        p, slow, fast = make_player(speed=100), make_enemy("Slow", speed=100), make_enemy("Fast", speed=150)
        battle = Battle(p, [slow, fast])
        self.assertIs(Combat._next_actor(battle), fast)
        fast.action_time = 1
        self.assertIs(Combat._next_actor(battle), p)

    def test_speed_debuff_changes_cadence(self):
        loader = _Loader(abilities={"slow": {"name": "Slow", "action_string": "DEBUFF ALL_ENEMIES SPEED 100 99_TURNS"}})
        player = make_player(speed=100, str=10)
        player.abilities = ["slow"]
        enemy = make_enemy(speed=200, max_health=60, str=0)  # slowed to 100, exactly its 50% speed floor
        combat, log = make_combat(player, ["Technique", "Slow"] + ["Attack"] * 6, loader)
        self.assertIs(combat.run([enemy]), CombatResult.VICTORY)
        actors = [line[0] for line in log if line[:2] in ("> ", "< ")]
        first_player = actors.index(">")
        after = "".join(actors[first_player:])
        self.assertNotIn("<<", after)  # after the debuff, speeds match: strict alternation
        self.assertEqual(actors[:first_player], ["<"])


if __name__ == "__main__":
    unittest.main()
