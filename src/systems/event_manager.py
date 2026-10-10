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
        self._recent_enemies: set[str] = set()
        self._player = None

    def generate_choices(self, game_state: GameState) -> list[Event]:
        """Generates the path choices for the current floor.

        Rules: the boss floor offers only the boss; the floor before it always
        offers a rest stop (``pre_boss_rest``); event types below their
        ``min_level`` fall back to a regular battle; no event id appears twice on
        one floor; occurrences offered in the last few floors and spent
        ``once_per_run`` events are not offered again.
        """
        level = game_state.current_level
        events_cfg = self.settings.get("events", {})
        boss_interval = events_cfg.get("boss_level_interval", 10)

        if boss_interval > 0 and level % boss_interval == 0:
            return [self._generate_boss_event(level)]

        self._player = game_state.player
        excluded = game_state.recently_offered() | set(game_state.used_once)
        offered: set[str] = set()
        choices: list[Event] = []
        distributions = events_cfg.get("distributions", {})

        slots = [(False, distributions.get("regular", {}))] * events_cfg.get("next_event_choices", 2)
        slots += [(True, distributions.get("mystery", {}))] * events_cfg.get("mystery_choices", 1)
        pre_boss = boss_interval > 0 and events_cfg.get("pre_boss_rest", False) and (level + 1) % boss_interval == 0

        for index, (is_mystery, dist) in enumerate(slots):
            if pre_boss and index == 0:
                event = self._build_event("rest_stop", level, False, excluded, offered)
            else:
                event = None
                for _ in range(6):
                    event_type = weighted_choice(dist, rng=self.rng) or "regular_combat"
                    event = self._build_event(event_type, level, is_mystery, excluded, offered)
                    if event is not None:
                        break
                if event is None:
                    event = self._generate_regular_combat(level, is_mystery)
            offered.add(event.id)
            choices.append(event)

        game_state.remember_offers([e.id for e in choices if isinstance(e, OccurrenceEvent)])
        self._recent_enemies = {
            e.enemy_id for c in choices if isinstance(c, CombatEvent) and c.subtype == "Regular" for e in c.encounter
        }
        return choices

    def _build_event(
        self, event_type: str, level: int, is_mystery: bool, excluded: set[str], offered: set[str]
    ) -> Event | None:
        """Builds an event of the given type, or None if no eligible event exists."""
        min_level = self.settings.get("events", {}).get("min_level", {}).get(event_type, 1)
        if level < min_level:
            event_type = "regular_combat"
        if event_type == "regular_combat":
            return self._generate_regular_combat(level, is_mystery)
        if event_type == "ordeal_combat":
            event = self._generate_ordeal_combat(level, is_mystery)
            return None if event.id in offered else event
        if event_type in ("normal_occurrence", "reward_occurrence"):
            return self._generate_occurrence(level, event_type == "reward_occurrence", is_mystery, excluded | offered)
        if event_type == "rest_stop":
            return None if "rest_site" in offered else RestEvent(is_mystery=is_mystery, stock=self._shop_stock())
        return self._generate_regular_combat(level, is_mystery)

    def _selectable_choices(self, occurrence: dict[str, Any]) -> int:
        """Top-level choices the current player could pick. An event whose only option is
        'leave' wastes a floor, so it is not offered."""
        from src.systems.events import unmet_requirement

        choices = occurrence.get("choices", {})
        if self._player is None:
            return len(choices)
        return sum(1 for c in choices.values() if unmet_requirement(self._player, c.get("requires")) is None)

    def _shop_stock(self) -> list[str]:
        cfg = self.settings.get("events", {}).get("shop", {})
        pool = [a.id for a in self.data_loader.actions.all() if a.has_tag("shop") and a.price > 0]
        size = min(int(cfg.get("stock_size", 4)), len(pool))
        return sorted(self.rng.sample(pool, size), key=lambda i: self.data_loader.actions[i].price)

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

        candidates = self._band_candidates(rules, "Normal")
        fresh = [c for c in candidates if c not in self._recent_enemies]
        candidates = fresh or candidates  # avoid offering last floor's enemies again when possible

        chosen_slugs = self.rng.choices(candidates, k=num_enemies)
        encounter = [self.data_loader.build_enemy(slug) for slug in chosen_slugs]
        names = ", ".join(e.name for e in encounter)

        return CombatEvent(
            event_id="regular_combat",
            display_name=names,
            description="Something moves on the road ahead.",
            encounter=encounter,
            subtype="Regular",
            is_mystery=is_mystery,
        )

    def _band_candidates(self, rules: dict[str, Any] | None, category: str) -> list[str]:
        """Enemies of a category, narrowed to the band's ``regular_combat.enemy_tags`` (any match) when set."""
        tags = (rules or {}).get("regular_combat", {}).get("enemy_tags")
        candidates = self.data_loader.filter_enemies(categories=[category], any_tags=tags)
        if not candidates:
            candidates = self.data_loader.filter_enemies(categories=[category])
        return candidates or list(self.data_loader.enemies.keys())

    def _generate_ordeal_combat(self, level: int, is_mystery: bool) -> CombatEvent:
        rules = self._get_combat_rules_for_level(level)
        ordeal_rules = rules.get("ordeal_combat", {}) if rules else {}

        preconstructed_weight = ordeal_rules.get("preconstructed_ordeal_weight", 40)
        random_weight = ordeal_rules.get("random_ordeal_weight", 60)

        use_preconstructed = (
            weighted_choice({"preconstructed": preconstructed_weight, "random": random_weight}, rng=self.rng) == "preconstructed"
        )

        preconstructed = [
            (key, data) for key, data in self.data_loader.events.get("preconstructed_ordeals", {}).items()
            if data.get("min_level", 1) <= level
        ]
        if use_preconstructed and preconstructed:
            ordeal_key, ordeal_data = self.rng.choice(preconstructed)
            encounter = [self.data_loader.build_enemy(slug) for slug in ordeal_data.get("enemies", [])]
            return CombatEvent(
                event_id=ordeal_key,
                display_name=ordeal_data.get("display_name", "Ambush"),
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

        elite_candidates = self.data_loader.filter_enemies(categories=["Elite"]) or self._band_candidates(rules, "Normal")
        normal_candidates = self._band_candidates(rules, "Normal")

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
            display_name=names,
            description="The road narrows. Whatever waits here is stronger than the usual stragglers.",
            encounter=encounter,
            subtype="Ordeal",
            is_mystery=is_mystery,
        )

    def _generate_occurrence(
        self, level: int, is_reward: bool, is_mystery: bool, excluded: set[str] | None = None
    ) -> OccurrenceEvent | None:
        excluded = excluded or set()
        occurrences = self.data_loader.events.get("occurrences", {})
        matched = [
            (key, occ) for key, occ in occurrences.items()
            if ("reward" in occ.get("tags", [])) == is_reward
            and key not in excluded
            and occ.get("min_level", 1) <= level
            and self._selectable_choices(occ) >= 2
        ]
        if not matched:
            return None
        key, occ_data = self.rng.choice(matched)
        return OccurrenceEvent(
            event_id=key,
            display_name=occ_data.get("display_name", "Curious Scene"),
            description=occ_data.get("description", "You discover an interesting place."),
            choices=occ_data.get("choices", {}),
            subtype="Reward" if is_reward else "Normal",
            is_mystery=is_mystery,
            once_per_run=bool(occ_data.get("once_per_run", False)),
        )

    def _generate_boss_event(self, level: int) -> CombatEvent:
        boss_events = self.data_loader.events.get("boss_events", {})
        if boss_events:
            key, bdata = self.rng.choice(list(boss_events.items()))
            encounter = [self.data_loader.build_enemy(slug) for slug in bdata.get("enemies", [])]
            return CombatEvent(
                event_id=key,
                display_name=bdata.get("display_name", "The Warden"),
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
            display_name=boss.name,
            description=f"{boss.name} bars the way forward.",
            encounter=[boss],
            subtype="Boss",
            is_mystery=False,
        )
