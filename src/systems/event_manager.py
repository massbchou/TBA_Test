"""Event Manager for generating floor path choices."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from src.models.enemy import Enemy
from src.rng import get_rng
from src.systems.events import CombatEvent, Event, OccurrenceEvent, RestEvent
from src.utils import weighted_choice

if TYPE_CHECKING:
    from src.data_loader import DataLoader
    from src.game_state import GameState


class EventManager:
    """Handles procedural generation of floor events based on level and configuration."""

    def __init__(self, data_loader: DataLoader, rng: random.Random | None = None):
        self.data_loader = data_loader
        self.settings = data_loader.settings
        self.rng = rng or get_rng()

    def generate_choices(self, game_state: GameState) -> list[Event]:
        """Generates choices for the current floor."""
        level = game_state.current_level
        events_cfg = self.settings.get("events", {})
        boss_interval = events_cfg.get("boss_level_interval", 10)

        # 1. Milestone Boss Floor
        if boss_interval > 0 and level % boss_interval == 0:
            boss_event = self._generate_boss_event(level)
            return [boss_event]

        choices: list[Event] = []

        # 2. Regular choices
        num_regular = events_cfg.get("next_event_choices", 2)
        reg_dist = events_cfg.get("distributions", {}).get("regular", {})
        for _ in range(num_regular):
            event_type = weighted_choice(reg_dist, rng=self.rng) or "regular_combat"
            event = self._build_event(event_type, level, is_mystery=False)
            if event:
                choices.append(event)

        # 3. Mystery choices
        num_mystery = events_cfg.get("mystery_choices", 1)
        mys_dist = events_cfg.get("distributions", {}).get("mystery", {})
        for _ in range(num_mystery):
            event_type = weighted_choice(mys_dist, rng=self.rng) or "regular_combat"
            event = self._build_event(event_type, level, is_mystery=True)
            if event:
                choices.append(event)

        return choices

    def _build_event(self, event_type: str, level: int, is_mystery: bool) -> Event:
        if event_type == "regular_combat":
            return self._generate_regular_combat(level, is_mystery)
        elif event_type == "ordeal_combat":
            return self._generate_ordeal_combat(level, is_mystery)
        elif event_type == "normal_occurrence":
            return self._generate_occurrence(level, is_reward=False, is_mystery=is_mystery)
        elif event_type == "reward_occurrence":
            return self._generate_occurrence(level, is_reward=True, is_mystery=is_mystery)
        elif event_type == "rest_stop":
            return RestEvent(is_mystery=is_mystery)
        else:
            return self._generate_regular_combat(level, is_mystery)

    def _get_combat_rules_for_level(self, level: int) -> dict[str, Any] | None:
        rules_list = self.settings.get("combat", {}).get("rules_by_level_range", [])
        for r in rules_list:
            if r.get("min_level", 1) <= level <= r.get("max_level", 999):
                return r
        if rules_list:
            return rules_list[-1]
        return None

    def _generate_regular_combat(self, level: int, is_mystery: bool) -> CombatEvent:
        rules = self._get_combat_rules_for_level(level)
        count_weights = {"1": 100}
        if rules and "regular_combat" in rules:
            count_weights = rules["regular_combat"].get("enemy_count_weights", count_weights)

        num_enemies = int(weighted_choice(count_weights, rng=self.rng) or 1)

        candidates = self.data_loader.filter_enemies(categories=["Normal"])
        if not candidates:
            candidates = list(self.data_loader.enemies.keys())

        chosen_slugs = self.rng.choices(candidates, k=num_enemies)
        encounter = [self.data_loader.build_enemy(slug) for slug in chosen_slugs]
        names = ", ".join(e.name for e in encounter)

        return CombatEvent(
            event_id="regular_combat",
            display_name=f"Battle: {names}",
            description=f"Hostile creatures block your path: {names}!",
            encounter=encounter,
            subtype="Regular",
            is_mystery=is_mystery,
        )

    def _generate_ordeal_combat(self, level: int, is_mystery: bool) -> CombatEvent:
        rules = self._get_combat_rules_for_level(level)
        ordeal_rules = rules.get("ordeal_combat", {}) if rules else {}

        preconstructed_weight = ordeal_rules.get("preconstructed_ordeal_weight", 40)
        random_weight = ordeal_rules.get("random_ordeal_weight", 60)

        use_preconstructed = (
            weighted_choice({"preconstructed": preconstructed_weight, "random": random_weight}, rng=self.rng) == "preconstructed"
        )

        preconstructed_dict = self.data_loader.events.get("preconstructed_ordeals", {})
        if use_preconstructed and preconstructed_dict:
            ordeal_key, ordeal_data = self.rng.choice(list(preconstructed_dict.items()))
            encounter = [self.data_loader.build_enemy(slug) for slug in ordeal_data.get("enemies", [])]
            return CombatEvent(
                event_id=ordeal_key,
                display_name=f"Ordeal: {ordeal_data.get('display_name', 'Ambush')}",
                description=ordeal_data.get("description", "A deadly ambush!"),
                encounter=encounter,
                subtype="Ordeal",
                is_mystery=is_mystery,
            )

        # Random composition
        comp = ordeal_rules.get("random_composition", {})
        elite_weights = comp.get("elite_count_weights", {"1": 100})
        normal_weights = comp.get("normal_count_weights", {"1": 50, "0": 50})

        num_elites = int(weighted_choice(elite_weights, rng=self.rng) or 1)
        num_normals = int(weighted_choice(normal_weights, rng=self.rng) or 0)

        elite_candidates = self.data_loader.filter_enemies(categories=["Elite"])
        if not elite_candidates:
            elite_candidates = self.data_loader.filter_enemies(categories=["Normal"])

        normal_candidates = self.data_loader.filter_enemies(categories=["Normal"])

        encounter: list[Enemy] = []
        if elite_candidates:
            for slug in self.rng.choices(elite_candidates, k=num_elites):
                encounter.append(self.data_loader.build_enemy(slug))
        if normal_candidates and num_normals > 0:
            for slug in self.rng.choices(normal_candidates, k=num_normals):
                encounter.append(self.data_loader.build_enemy(slug))

        names = ", ".join(e.name for e in encounter)
        return CombatEvent(
            event_id="ordeal_random",
            display_name=f"Ordeal: {names}",
            description=f"A perilous ordeal lies ahead: {names}!",
            encounter=encounter,
            subtype="Ordeal",
            is_mystery=is_mystery,
        )

    def _generate_occurrence(self, level: int, is_reward: bool, is_mystery: bool) -> OccurrenceEvent:
        occurrences = self.data_loader.events.get("occurrences", {})
        matched: list[tuple[str, dict[str, Any]]] = []

        for key, occ in occurrences.items():
            tags = occ.get("tags", [])
            if is_reward and "reward" in tags:
                matched.append((key, occ))
            elif not is_reward and "reward" not in tags:
                matched.append((key, occ))

        if not matched and occurrences:
            matched = list(occurrences.items())

        if matched:
            key, occ_data = self.rng.choice(matched)
            return OccurrenceEvent(
                event_id=key,
                display_name=occ_data.get("display_name", "Curious Scene"),
                description=occ_data.get("description", "You discover an interesting place."),
                choices=occ_data.get("choices", {}),
                subtype="Reward" if is_reward else "Normal",
                is_mystery=is_mystery,
            )

        return OccurrenceEvent(
            event_id="generic_occurrence",
            display_name="Mysterious Pathway",
            description="The stone walls echo with ancient whispers.",
            choices={},
            subtype="Normal",
            is_mystery=is_mystery,
        )

    def _generate_boss_event(self, level: int) -> CombatEvent:
        boss_events = self.data_loader.events.get("boss_events", {})
        if boss_events:
            key, bdata = self.rng.choice(list(boss_events.items()))
            encounter = [self.data_loader.build_enemy(slug) for slug in bdata.get("enemies", [])]
            return CombatEvent(
                event_id=key,
                display_name=f"BOSS: {bdata.get('display_name', 'Dungeon Master')}",
                description=bdata.get("description", "A monumental presence looms before you!"),
                encounter=encounter,
                subtype="Boss",
                is_mystery=False,
            )

        boss_candidates = self.data_loader.filter_enemies(categories=["Boss"])
        if not boss_candidates:
            boss_candidates = list(self.data_loader.enemies.keys())

        slug = self.rng.choice(boss_candidates)
        boss = self.data_loader.build_enemy(slug)
        return CombatEvent(
            event_id=f"boss_{slug}",
            display_name=f"BOSS: {boss.name}",
            description=f"A monstrous boss stands guard: {boss.name}!",
            encounter=[boss],
            subtype="Boss",
            is_mystery=False,
        )
