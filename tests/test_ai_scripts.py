"""Attack Script selection and execution."""
import unittest

from src.data_loader import DataLoader
from src.systems.actions.definitions import ActionRegistry
from src.systems.ai.script_parser import parse_script_line
from src.systems.ai_controller import AIController
from tests.helpers import make_battle, make_enemy, make_player

ABILITIES = {aid: {"name": aid, "action_string": "DAMAGE 1_ENEMY 1"} for aid in ("a", "b", "c", "slam", "wall")}


def scripted_enemy(scripts, abilities=("a", "b", "c")):
    enemy = make_enemy()
    enemy.abilities = [{"ability_id": aid, "cooldowns": {"self": 0}} for aid in abilities]
    enemy.attack_scripts = scripts
    return enemy


class TestScriptRunner(unittest.TestCase):
    def setUp(self):
        self.ai = AIController(actions=ActionRegistry.build(ABILITIES))

    def decide(self, enemy, seed=0):
        action = self.ai.decide_action(enemy, make_battle(make_player(), [enemy], seed=seed))
        return action.id if action else None

    def test_first_true_script_wins_and_lines_loop(self):
        enemy = scripted_enemy([
            {"activation_condition": "IF SELF WITH_TAG nope", "script_lines": ["use_ability c"]},
            {"activation_condition": "IF SELF", "script_lines": ["use_ability a", "", "use_ability b"]},
        ])
        self.assertEqual([self.decide(enemy) for _ in range(4)], ["a", "b", "a", "b"])

    def test_no_condition_met_falls_back_to_first_script(self):
        enemy = scripted_enemy([
            {"activation_condition": "IF SELF WITH_TAG x", "script_lines": ["use_ability a"]},
            {"activation_condition": "IF SELF WITH_TAG y", "script_lines": ["use_ability b"]},
        ])
        self.assertEqual(self.decide(enemy), "a")

    def test_non_interruptible_lock_and_restart(self):
        enemy = scripted_enemy([
            {"activation_condition": "IF SELF WITH_STAT HP > 50%", "interruptible": True, "script_lines": ["use_ability a"]},
            {"activation_condition": "IF SELF WITH_STAT HP <= 50%", "interruptible": False,
             "script_lines": ["use_ability b", "use_ability c", "use_ability c"]},
        ])
        self.assertEqual(self.decide(enemy), "a")
        enemy.health = 40
        self.assertEqual(self.decide(enemy), "b")
        enemy.health = 100  # healed, but locked until the loop finishes
        self.assertEqual([self.decide(enemy), self.decide(enemy)], ["c", "c"])
        self.assertEqual(self.decide(enemy), "a")
        enemy.health = 40
        self.assertEqual(self.decide(enemy), "b")  # switching back restarts at line 0

    def test_skipped_lines_do_not_consume_a_turn(self):
        enemy = scripted_enemy([{"script_lines": ["CHANCE 0 { use_ability a }", "IF SELF WITH_TAG x { use_ability a }", "use_ability b"]}])
        self.assertEqual(self.decide(enemy), "b")

    def test_cooldown_line_is_skipped(self):
        enemy = scripted_enemy([{"script_lines": ["use_ability a", "use_ability b"]}])
        enemy.set_cooldown("a", 2)
        self.assertEqual(self.decide(enemy), "b")

    def test_all_on_cooldown_waits(self):
        enemy = scripted_enemy([{"script_lines": ["use_ability a"]}], abilities=("a",))
        enemy.set_cooldown("a", 1)
        self.assertIsNone(self.decide(enemy))

    def test_full_pass_without_usable_line_falls_back_to_ready_ability(self):
        enemy = scripted_enemy([{"script_lines": ["use_ability a"]}], abilities=("a", "b"))
        enemy.set_cooldown("a", 1)
        self.assertEqual(self.decide(enemy), "b")

    def test_unowned_ability_is_skipped(self):
        enemy = scripted_enemy([{"script_lines": ["use_ability slam", "use_ability a"]}], abilities=("a",))
        self.assertEqual(self.decide(enemy), "a")

    def test_weighted_choice_distribution(self):
        enemy = scripted_enemy([{"script_lines": ["WEIGHTED_CHOICE { WEIGHT 80: use_ability a } { WEIGHT 20: use_ability b }"]}])
        picks = [self.decide(enemy, seed) for seed in range(300)]
        self.assertTrue(200 < picks.count("a") < 280)

    def test_no_scripts_uses_random_ready_ability(self):
        enemy = scripted_enemy([], abilities=("a", "b"))
        enemy.set_cooldown("a", 3)
        self.assertEqual({self.decide(enemy, s) for s in range(20)}, {"b"})

    def test_no_abilities_uses_basic_attack(self):
        self.assertEqual(self.decide(make_enemy()), "attack")

    def test_shared_cooldowns(self):
        enemy = make_enemy()
        enemy.abilities = [{"ability_id": "slam", "cooldowns": {"self": 0}},
                           {"ability_id": "wall", "cooldowns": {"self": 4, "slam": 1}}]
        enemy.trigger_cooldowns("wall")
        self.assertEqual(enemy.cooldowns, {"wall": 4, "slam": 1})

    def test_else_if_chain(self):
        stmt = parse_script_line("IF SELF WITH_TAG a { use_ability a } ELSE IF SELF WITH_TAG b { use_ability b } ELSE { }")
        self.assertEqual(len(stmt.branches), 2)
        self.assertIsNone(stmt.otherwise)


class TestShippedEnemies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader()
        cls.loader.load_all()

    def setUp(self):
        self.ai = AIController(self.loader)

    def test_shaman_heals_only_wounded_allies(self):
        shaman, goblin = self.loader.build_enemy("goblin_shaman"), self.loader.build_enemy("goblin")
        battle = make_battle(make_player(), [shaman, goblin])
        self.assertEqual(self.ai.decide_action(shaman, battle).id, "heavy_slam")
        goblin.health = 10
        heal = self.ai.decide_action(shaman, battle)
        self.assertEqual(heal.id, "minor_heal")
        battle.orchestrator.execute(shaman, heal, battle)
        shaman.trigger_cooldowns("minor_heal")
        self.assertGreater(goblin.health, 10)
        goblin.health = 10
        self.assertEqual(self.ai.decide_action(shaman, battle).id, "heavy_slam")  # heal on cooldown

    def test_troll_locks_into_phase_two(self):
        troll = self.loader.build_enemy("cave_troll")
        battle = make_battle(make_player(), [troll])
        self.assertEqual(self.ai.decide_action(troll, battle).id, "heavy_slam")
        troll.health = 70
        self.assertEqual(self.ai.decide_action(troll, battle).id, "shield_wall")
        self.assertEqual(troll.ai_state.current_script, 1)
        self.assertTrue(troll.ai_state.locked)


if __name__ == "__main__":
    unittest.main()
