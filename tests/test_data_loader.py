"""Tests for DataLoader and model factories."""
import unittest
from tests.helpers import fixture_loader
from src.models.enemy import Enemy
from src.models.player import Player


class TestDataLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = fixture_loader()

    def test_load_all_keys_populated(self):
        self.assertIn("player", self.loader.settings)
        self.assertIn("combat", self.loader.settings)
        self.assertIn("goblin", self.loader.enemies)
        self.assertIn("Warrior", self.loader.starting_classes)
        self.assertIn("Warrior", self.loader.starting_options)
        self.assertIn("heavy_slam", self.loader.abilities)
        self.assertIn("fireball", self.loader.spells)

    def test_build_enemy_goblin(self):
        goblin = self.loader.build_enemy("goblin")
        self.assertIsInstance(goblin, Enemy)
        self.assertEqual(goblin.name, "Goblin")
        self.assertEqual(goblin.category, "Normal")
        self.assertEqual(goblin.health, 25)
        self.assertEqual(goblin.get_stat("speed"), 130)
        self.assertIn("tier1", goblin.tags)

    def test_build_player_warrior(self):
        warrior = self.loader.build_player("Warrior", player_name="TestHero")
        self.assertIsInstance(warrior, Player)
        self.assertEqual(warrior.name, "TestHero")
        self.assertEqual(warrior.health, 120)
        self.assertEqual(warrior.get_stat("str"), 16)
        self.assertEqual(warrior.exp_to_next_level, 100)

    def test_filter_enemies_by_category(self):
        normals = self.loader.filter_enemies(categories=["Normal"])
        self.assertIn("goblin", normals)
        self.assertIn("orc_grunt", normals)
        self.assertNotIn("goblin_shaman", normals)  # Shaman is Elite
        self.assertNotIn("cave_troll", normals)    # Troll is Boss


if __name__ == "__main__":
    unittest.main()
