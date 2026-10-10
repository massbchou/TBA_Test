"""Centralized data loader and factory for game entities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.formula import validate_formula
from src.models.enemy import Enemy
from src.models.player import Player
from src.models.status import STACKING_MODES, StatusDef
from src.stats import is_known_stat
from src.systems.actions.definitions import (
    SOURCE_ITEM,
    SOURCE_SPELL,
    SOURCE_TECHNIQUE,
    ActionRegistry,
)
from src.systems.actions.nodes import Diagnostic
from src.systems.actions.parser import parse_program
from src.systems.ai.script_parser import parse_scripts, referenced_abilities
from src.systems.effects import EFFECTS, REQUIRED_PARAMS

REQUIREMENT_KEYS = {"gold", "class", "item", "stat", "level"}
CHOICE_KEYS = {"result_text", "description", "requires", "effects", "choices", "chance", "success", "failure"}

def perk_effects(perk: dict[str, Any]) -> list[dict[str, Any]]:
    """A perk holds either one ``effect`` or a list of ``effects``."""
    return list(perk.get("effects", [])) or ([perk["effect"]] if "effect" in perk else [])


STATUS_HOOKS = ("on_apply", "on_turn_start", "on_turn_end", "on_damage_taken", "on_expire")


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
        self.items: dict[str, dict[str, Any]] = {}
        self.statuses: dict[str, dict[str, Any]] = {}
        self.status_defs: dict[str, StatusDef] = {}
        self.actions: ActionRegistry = ActionRegistry.build()

    @property
    def starting_options(self) -> dict[str, dict[str, Any]]:
        """Backwards compatibility alias for starting_classes."""
        return self.starting_classes

    def perk_name(self, perk_id: str) -> str:
        for perks in self.level_up_perks.values():
            for perk in perks:
                if perk.get("perk_id") == perk_id:
                    return perk.get("name", perk_id)
        return perk_id

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_optional(self, path: Path) -> Any:
        return self._read_json(path) if path.exists() else {}

    def load_all(self) -> None:
        """Loads settings and all content dictionaries, then parses every action."""
        self.settings = self._read_json(self.settings_path)
        self.enemies = self._read_json(self.data_dir / "enemies.json")
        self.abilities = self._read_json(self.data_dir / "abilities.json")
        self.spells = self._read_json(self.data_dir / "spells.json")
        self.events = self._read_json(self.data_dir / "events.json")
        self.starting_classes = self._read_json(self.data_dir / "starting_classes.json")
        self.level_up_perks = self._read_json(self.data_dir / "level_up_perks.json")
        self.items = self._read_optional(self.data_dir / "items.json")
        self.statuses = self._read_optional(self.data_dir / "statuses.json")
        self.status_defs = {name.upper(): StatusDef.from_data(name, d) for name, d in self.statuses.items()}
        self.actions = ActionRegistry.build(self.abilities, self.spells, self.items)

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
            intro=data.get("intro", ""),
            abilities=list(data.get("abilities", [])),
            loot_table=list(data.get("loot_table", [])),
            attack_scripts=list(data.get("attack_scripts", [])),
        )

    def build_player(self, class_name: str, player_name: str = "Hero") -> Player:
        """Constructs a Player model instance from a starting class."""
        if class_name not in self.starting_classes:
            raise KeyError(f"Starting class '{class_name}' not found in data/starting_classes.json")
        data = self.starting_classes[class_name]
        stats = {k: v for k, v in data.get("stats", {}).items() if k != "health"}
        player = Player(
            name=player_name,
            stats=stats,
            level=int(data.get("level", 1)),
            abilities=list(data.get("abilities", [])),
            spells=list(data.get("spells", [])),
            inventory=dict(data.get("starting_items", {})),
            class_name=class_name,
            gold=int(data.get("gold", 0)),
            growth=dict(data.get("growth", {})),
            basic_attack=data.get("basic_attack", "1.0*STR"),
            basic_attack_type=data.get("basic_attack_type", "PHYSICAL"),
            derived_formulas={**self.settings.get("player", {}).get("derived_stats", {}), **data.get("derived_stats", {})},
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
        any_tags: list[str] | None = None,
    ) -> list[str]:
        """Returns enemy slugs matching the category and level constraints, all of
        ``required_tags``, and at least one of ``any_tags``."""
        matched: list[str] = []
        for slug, data in self.enemies.items():
            if categories and data.get("category") not in categories:
                continue

            lvl = int(data.get("level", 1))
            if min_level is not None and lvl < min_level:
                continue
            if max_level is not None and lvl > max_level:
                continue

            enemy_tags = data.get("tags", [])
            if required_tags and not all(tag in enemy_tags for tag in required_tags):
                continue
            if any_tags and not any(tag in enemy_tags for tag in any_tags):
                continue

            matched.append(slug)
        return matched

    # ------------------------------------------------------------ validation

    def validate(self) -> list[Diagnostic]:
        """Checks all loaded data. Returns diagnostics (errors, warnings, and info)."""
        diags: list[Diagnostic] = []

        # Actions: parse errors, plus APPLY of statuses with no definition (legal markers).
        for action in self.actions.all():
            diags += action.diagnostics()
            for line in action.program.lines if action.program else []:
                if line.verb == "APPLY" and line.args[0].upper() not in self.status_defs:
                    diags.append(Diagnostic(
                        "info", f"APPLY of undefined status {line.args[0]!r} (treated as a marker)",
                        line.number, f"{action.source}:{action.id}"))

        # Items: prices for shop stock
        for item_id in self.items:
            action = self.actions[item_id]
            if action.has_tag("shop") and action.price <= 0:
                diags.append(Diagnostic("error", "tagged 'shop' but has no price", source=f"item:{item_id}"))

        # Statuses
        for name, sdef in self.status_defs.items():
            where = f"status:{name}"
            if sdef.stacking not in STACKING_MODES:
                diags.append(Diagnostic("error", f"stacking must be one of {STACKING_MODES}", source=where))
            for hook, script in sdef.hooks.items():
                if hook not in STATUS_HOOKS:
                    diags.append(Diagnostic("error", f"unknown hook {hook!r}", source=where))
                diags += parse_program(script, source=f"{where}.{hook}").diagnostics

        # Enemies: abilities, cooldown maps, scripts, loot
        for slug, data in self.enemies.items():
            where = f"enemy:{slug}"
            enemy = self.build_enemy(slug)
            owned = enemy.ability_ids()
            for entry in data.get("abilities", []):
                aid = entry.get("ability_id") or entry.get("spell_id")
                if aid not in self.actions:
                    diags.append(Diagnostic("error", f"unknown ability {aid!r}", source=where))
                for key in entry.get("cooldowns", {}):
                    if key != "self" and key not in owned:
                        diags.append(Diagnostic("error", f"cooldown key {key!r} is not one of its abilities", source=where))
            scripts, script_diags = parse_scripts(data.get("attack_scripts", []), source=where)
            diags += script_diags
            for script in scripts:
                for stmt in script.lines:
                    for aid in referenced_abilities(stmt):
                        if aid not in owned:
                            diags.append(Diagnostic("error", f"script uses ability {aid!r} it does not own", source=where))
            for loot in data.get("loot_table", []):
                if loot.get("type") == "item" and loot.get("item_id") not in self.items:
                    diags.append(Diagnostic("error", f"loot references unknown item {loot.get('item_id')!r}", source=where))
                elif loot.get("type") not in ("item", "gold"):
                    diags.append(Diagnostic("error", f"unknown loot type {loot.get('type')!r}", source=where))

        # Starting classes
        expected = {"abilities": SOURCE_TECHNIQUE, "spells": SOURCE_SPELL}
        for cls_name, data in self.starting_classes.items():
            where = f"class:{cls_name}"
            for key, source in expected.items():
                for aid in data.get(key, []):
                    action = self.actions.get(aid)
                    if action is None or action.source != source:
                        diags.append(Diagnostic("error", f"{key} entry {aid!r} is not a known {source}", source=where))
            for item_id in data.get("starting_items", {}):
                action = self.actions.get(item_id)
                if action is None or action.source != SOURCE_ITEM:
                    diags.append(Diagnostic("error", f"unknown starting item {item_id!r}", source=where))
            error = validate_formula(data.get("basic_attack", "1.0*STR"), is_known_stat)
            if error:
                diags.append(Diagnostic("error", f"basic_attack: {error}", source=where))
            for stat in data.get("growth", {}):
                if not is_known_stat(stat):
                    diags.append(Diagnostic("error", f"growth stat {stat!r} is not a stat", source=where))

        formulas = [("settings", k, f) for k, f in self.settings.get("player", {}).get("derived_stats", {}).items()]
        formulas += [(f"class:{c}", k, f) for c, d in self.starting_classes.items() for k, f in d.get("derived_stats", {}).items()]
        for where, stat, formula in formulas:
            error = validate_formula(formula, is_known_stat)
            if error:
                diags.append(Diagnostic("error", f"derived_stats.{stat}: {error}", source=where))

        # Perks and occurrences
        for tier, perks in self.level_up_perks.items():
            for perk in perks:
                where = f"perk:{tier}:{perk.get('perk_id')}"
                diags += self._validate_effects(perk_effects(perk), where)
                diags += self._validate_requires(perk.get("requires", {}), where)
        for key, occ in self.events.get("occurrences", {}).items():
            diags += self._validate_choices(occ.get("choices", {}), f"occurrence:{key}")

        # Encounter bands must match at least one enemy
        for band in self.settings.get("combat", {}).get("rules_by_level_range", []):
            tags = band.get("regular_combat", {}).get("enemy_tags")
            if tags and not self.filter_enemies(categories=["Normal"], any_tags=tags):
                diags.append(Diagnostic("error", f"no Normal enemies tagged any of {tags}", source="settings"))

        # Event enemy references
        for section in ("preconstructed_ordeals", "boss_events"):
            for key, event in self.events.get(section, {}).items():
                for slug in event.get("enemies", []):
                    if slug not in self.enemies:
                        diags.append(Diagnostic("error", f"unknown enemy {slug!r}", source=f"{section}:{key}"))
        return diags

    def _validate_effects(self, effects: list[dict[str, Any]], where: str) -> list[Diagnostic]:
        diags = []
        for effect in effects:
            etype = effect.get("type")
            if etype not in EFFECTS:
                diags.append(Diagnostic("error", f"unknown effect type {etype!r}", source=where))
                continue
            missing = [p for p in REQUIRED_PARAMS[etype] if p not in effect]
            if missing:
                diags.append(Diagnostic("error", f"{etype} effect missing {missing}", source=where))
            if etype == "item" and effect.get("item_id") not in self.items:
                diags.append(Diagnostic("error", f"unknown item {effect.get('item_id')!r}", source=where))
            if etype == "learn_action":
                action = self.actions.get(effect.get("action_id"))
                if action is None or action.source not in (SOURCE_TECHNIQUE, SOURCE_SPELL):
                    diags.append(Diagnostic("error", f"learn_action {effect.get('action_id')!r} is not a technique or spell", source=where))
            if etype == "combat":
                for slug in effect.get("enemies", []):
                    if slug not in self.enemies:
                        diags.append(Diagnostic("error", f"combat effect references unknown enemy {slug!r}", source=where))
        return diags

    def _validate_requires(self, requires: dict[str, Any], where: str) -> list[Diagnostic]:
        diags = []
        for key in set(requires) - REQUIREMENT_KEYS:
            diags.append(Diagnostic("error", f"unknown requirement {key!r}", source=where))
        classes = requires.get("class")
        for cls in ([classes] if isinstance(classes, str) else classes or []):
            if cls not in self.starting_classes:
                diags.append(Diagnostic("error", f"requires unknown class {cls!r}", source=where))
        item = requires.get("item")
        for item_id in (item if isinstance(item, dict) else [item] if item else []):
            if item_id not in self.items:
                diags.append(Diagnostic("error", f"requires unknown item {item_id!r}", source=where))
        for stat in requires.get("stat", {}):
            if not is_known_stat(stat):
                diags.append(Diagnostic("error", f"requires unknown stat {stat!r}", source=where))
        return diags

    def _validate_outcome(self, data: dict[str, Any], where: str) -> list[Diagnostic]:
        diags = []
        for key in set(data) - CHOICE_KEYS:
            diags.append(Diagnostic("error", f"unknown choice key {key!r}", source=where))
        diags += self._validate_requires(data.get("requires", {}), where)
        if "chance" in data:
            if not 0 <= float(data["chance"]) <= 1:
                diags.append(Diagnostic("error", "chance must be between 0 and 1", source=where))
            for branch in ("success", "failure"):
                diags += self._validate_outcome(data.get(branch, {}), f"{where} ({branch})")
        elif "choices" in data:
            diags += self._validate_choices(data["choices"], where)
        else:
            diags += self._validate_effects(data.get("effects", []), where)
        return diags

    def _validate_choices(self, choices: dict[str, Any], where: str) -> list[Diagnostic]:
        diags = []
        for label, choice in choices.items():
            diags += self._validate_outcome(choice, f"{where} > {label}")
        if choices and all(c.get("requires") for c in choices.values()):
            diags.append(Diagnostic("warning", "every choice has requirements; add an always-available option", source=where))
        return diags
