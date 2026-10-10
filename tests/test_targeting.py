"""Target resolution: groups, filters, quantity, modes and back-references."""
import unittest

from tests.helpers import make_battle, make_enemy, make_player, run


class TestTargeting(unittest.TestCase):
    def test_groups_are_relative_to_caster(self):
        p, e = make_player(), make_enemy()
        battle = make_battle(p, [e])
        run(battle, e, "DAMAGE 1_ENEMY 5")
        self.assertEqual(p.health, 95)

    def test_ally_includes_self(self):
        p, e = make_player(), make_enemy()
        e.health = 50
        battle = make_battle(p, [e])
        run(battle, e, "HEAL 1_ALLY CHOICE 10")
        self.assertEqual(e.health, 60)

    def test_filters_apply_before_quantity(self):
        p = make_player()
        plain, undead = make_enemy("Plain"), make_enemy("Undead", tags=["undead"])
        for seed in range(10):
            plain.health = undead.health = 100
            run(make_battle(p, [plain, undead], seed=seed), p, "DAMAGE 1_ENEMY RANDOM WITH_TAG undead 5")
            self.assertEqual((plain.health, undead.health), (100, 95))

    def test_pool_smaller_than_quantity_hits_each_once(self):
        p, a, b = make_player(), make_enemy("A"), make_enemy("B")
        run(make_battle(p, [a, b]), p, "DAMAGE 3_ENEMIES RANDOM 7")
        self.assertEqual((a.health, b.health), (93, 93))

    def test_choice_prompts_player(self):
        p, a, b = make_player(), make_enemy("A"), make_enemy("B")
        battle = make_battle(p, [a, b], answers=[1])
        run(battle, p, "DAMAGE 1_ENEMY CHOICE 10")
        self.assertEqual((a.health, b.health), (100, 90))

    def test_choice_skips_prompt_when_pool_fits(self):
        p, a = make_player(), make_enemy("A")
        run(make_battle(p, [a], answers=[]), p, "DAMAGE 1_ENEMY CHOICE 10")  # would raise if prompted
        self.assertEqual(a.health, 90)

    def test_dead_characters_are_never_targets(self):
        p, a, b = make_player(), make_enemy("A"), make_enemy("B")
        a.health = 0
        run(make_battle(p, [a, b]), p, "DAMAGE ALL_ENEMIES 10")
        self.assertEqual(b.health, 90)

    def test_back_references(self):
        p, a, b = make_player(), make_enemy("A"), make_enemy("B")
        battle = make_battle(p, [a, b], answers=[1])
        result = run(battle, p, """
            DAMAGE 1_ENEMY CHOICE 1
            APPLY PREVIOUS_TARGETS MARK
            SET SPECIFIC_TARGET target1.1 marked true
            HEAL ALL_TARGETS_LINE1 1
            BUFF SELF STR 1
            SET ALL_TARGETS_SO_FAR seen true
        """)
        self.assertTrue(b.has_status("MARK") and b.has_variable("marked"))
        self.assertFalse(a.has_status("MARK"))
        self.assertEqual(result.lines[3].targets, ["B"])
        self.assertTrue(b.has_variable("seen") and p.has_variable("seen"))
        self.assertFalse(a.has_variable("seen"))

    def test_ai_choice_policy_heals_lowest_hp_percent(self):
        p = make_player()
        big, small = make_enemy("Big", max_health=200), make_enemy("Small", max_health=20)
        big.health, small.health = 90, 15   # 45% vs 75%
        battle = make_battle(p, [big, small])
        run(battle, small, "HEAL 1_ALLY CHOICE 5")
        self.assertEqual((big.health, small.health), (95, 15))

    def test_ai_target_override(self):
        p = make_player()
        a, b = make_enemy("A"), make_enemy("B")
        a.health = 30
        battle = make_battle(p, [a, b])
        run(battle, a, "BUFF 1_ALLY CHOICE STR 3", ai_target="highest_hp")
        self.assertEqual((a.get_stat("str"), b.get_stat("str")), (10, 13))


if __name__ == "__main__":
    unittest.main()
