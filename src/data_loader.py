"""Centralized data loader and factory for game entities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.enemy import Enemy
from src.models.player import Player


class DataLoader:
    """Loads and validates all game data files, and provides factories for models."""

    def __init__(self, data_dir: str | Path = "data", settings_path: str | Path = "settings.json"):
        self.data_dir = Path(data_dir)
        self.settings_path = Path(settings_path)
        self.settings: dict[str, Any] = {}
        self.enemies: dict[str, dict[str, Any]] = {}
        self.abilities: dict[str, dict[str, Any]] = {}
        self.spells: dict[str, dict[str, Any]] = {}
        self.events: dict[str, Any] = {}
        self.starting_classes: dict[str, dict[str, Any]] = {}
        self.level_up_perks: dict[str, list[dict[str, Any]]] = {}

    @property
    def starting_options(self) -> dict[str, dict[str, Any]]:
        """Backwards compatibility alias for starting_classes."""
        return self.starting_classes

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all(self) -> None:
        """Loads settings and all content dictionaries."""
        self.settings = self._read_json(self.settings_path)
        self.enemies = self._read_json(self.data_dir / "enemies.json")
        self.abilities = self._read_json(self.data_dir / "abilities.json")
        self.spells = self._read_json(self.data_dir / "spells.json")
        self.events = self._read_json(self.data_dir / "events.json")
        self.starting_classes = self._read_json(self.data_dir / "starting_classes.json")
        self.level_up_perks = self._read_json(self.data_dir / "level_up_perks.json")

    def build_enemy(self, slug: str) -> Enemy:
        """Constructs an Enemy model instance from an enemy data slug."""
        if slug not in self.enemies:
            raise KeyError(f"Enemy with slug '{slug}' not found in data/enemies.json")
        data = self.enemies[slug]
        return Enemy(
            name=data["name"],
            stats=dict(data.get("stats", {})),
            tags=list(data.get("tags", [])),
            enemy_id=slug,
            category=data.get("category", "Normal"),
            level=int(data.get("level", 1)),
            abilities=list(data.get("abilities", [])),
            loot_table=list(data.get("loot_table", [])),
            attack_scripts=list(data.get("attack_scripts", [])),
        )

    def build_player(self, class_name: str, player_name: str = "Hero") -> Player:
        """Constructs a Player model instance from a starting class."""
        if class_name not in self.starting_classes:
            raise KeyError(f"Starting class '{class_name}' not found in data/starting_classes.json")
        data = self.starting_classes[class_name]
        player = Player(
            name=player_name,
            stats=dict(data.get("stats", {})),
            level=int(data.get("level", 1)),
        )
        if "player" in self.settings:
            formula = self.settings["player"].get("exp_formula", "100")
            base = self.settings["player"].get("exp_base", 100)
            player.calculate_exp_to_next_level(formula, base)
        return player

    def filter_enemies(
        self,
        required_tags: list[str] | None = None,
        categories: list[str] | None = None,
        min_level: int | None = None,
        max_level: int | None = None,
    ) -> list[str]:
        """Returns enemy slugs matching all tag, category, and level constraints."""
        matched: list[str] = []
        for slug, data in self.enemies.items():
            if categories and data.get("category") not in categories:
                continue

            lvl = int(data.get("level", 1))
            if min_level is not None and lvl < min_level:
                continue
            if max_level is not None and lvl > max_level:
                continue

            if required_tags:
                enemy_tags = data.get("tags", [])
                if not all(tag in enemy_tags for tag in required_tags):
                    continue

            matched.append(slug)
        return matched
