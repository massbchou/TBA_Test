"""Base character model shared by players and enemies.

Holds stats plus all per-combat state the Action System manipulates: resources,
timed stat modifiers, status effects, cooldowns and custom variables.

Every ``TURNS`` timer follows one rule: it belongs to its bearer, decrements at
the end of the bearer's turn, skips the turn in which it was applied, and
expires at 0. ``CLOCK`` timers (from ROUNDS / TIME_UNITS durations) expire when
the combat clock reaches ``expires_at``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from src.stats import HEALTH, HP_PERCENTAGE, RESOURCES, canonical_stat, is_known_stat

PHYSICAL = "PHYSICAL"
MIN_DAMAGE = 1
RESISTANCE_CAP = (-100, 90)


@dataclass
class Timer:
    """Expiry tracking for anything with a duration."""
    unit: str  # "TURNS" | "CLOCK"
    remaining: int = 0
    applied_turn: int = 0
    expires_at: float = 0.0

    def tick_turn(self, bearer_turn: int) -> bool:
        """Advances a TURNS timer at the end of its bearer's turn. Returns True when expired."""
        if self.unit != "TURNS":
            return False
        if self.applied_turn != bearer_turn:
            self.remaining -= 1
        return self.remaining <= 0

    def expired_at_clock(self, clock: float) -> bool:
        return self.unit == "CLOCK" and clock >= self.expires_at


@dataclass
class Resource:
    current: int
    maximum: int


@dataclass
class Modifier:
    """A flat, temporary stat change from BUFF / DEBUFF."""
    stat: str
    amount: float
    timer: Timer | None = None
    source: str = ""


@dataclass
class ActiveStatus:
    """A named status effect on a character (e.g. POISON)."""
    name: str
    timer: Timer | None = None
    stacks: int = 1
    source: Any = None


@dataclass
class Variable:
    value: Any
    timer: Timer | None = None


@dataclass
class Character:
    """Base class for all characters (players and enemies)."""
    name: str
    stats: dict[str, int | float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    health: int = 0
    action_time: int = 0
    resources: dict[str, Resource] = field(default_factory=dict)
    modifiers: list[Modifier] = field(default_factory=list)
    statuses: list[ActiveStatus] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)
    variables: dict[str, Variable] = field(default_factory=dict)
    turn_count: int = 0
    _cooldown_set_turn: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.health <= 0:
            self.health = int(self.get_stat("max_health"))

    # ------------------------------------------------------------------ stats

    def base_stat(self, name: str) -> float:
        return self.stats.get(canonical_stat(name), 0)

    def get_stat(self, name: str) -> int | float:
        """Effective stat value: base plus active flat modifiers.

        Also answers the pseudo-stats ``health``, ``hp_percentage``, resources
        (``stamina`` / ``mana``) and their maxima.
        """
        key = canonical_stat(name)
        if key == HEALTH:
            return self.health
        if key == HP_PERCENTAGE:
            max_hp = self.get_stat("max_health")
            return (self.health / max_hp * 100) if max_hp else 0
        if key in RESOURCES:
            res = self.resources.get(key)
            return res.current if res else 0
        if key in ("max_stamina", "max_mana"):
            res = self.resources.get(key[4:])
            return res.maximum if res else 0
        base = self.stats.get(key, 0)
        return base + sum(m.amount for m in self.modifiers if m.stat == key)

    def lookup(self, name: str) -> tuple[bool, Any]:
        """Resolves a stat, falling back to a custom variable. Returns (found, value)."""
        key = canonical_stat(name)
        if key in self.stats or is_known_stat(key):
            return True, self.get_stat(key)
        var = self.variables.get(name.lower())
        if var is not None:
            return True, var.value
        return False, None

    def formula_value(self, name: str) -> float:
        """Numeric lookup for formulas. Raises KeyError for unknown or non-numeric names."""
        found, value = self.lookup(name)
        if not found or isinstance(value, str) or value is None:
            raise KeyError(name)
        return float(value)

    def modify_base_stat(self, name: str, delta: float) -> None:
        """Permanently changes a base stat (perks, occurrences).

        Raising max_health also heals by the same amount; lowering it clamps health.
        """
        key = canonical_stat(name)
        if key == HEALTH:
            if delta >= 0:
                self.heal(int(delta))
            else:
                self.health = max(0, self.health + int(delta))
            return
        self.stats[key] = self.stats.get(key, 0) + delta
        if key == "max_health":
            if delta > 0:
                self.health += int(delta)
            self.health = min(self.health, int(self.get_stat("max_health")))
        self._on_base_stats_changed()

    def _on_base_stats_changed(self) -> None:
        """Hook for subclasses with derived stats."""

    # ----------------------------------------------------------- health

    def is_alive(self) -> bool:
        """Check if character is alive."""
        return self.health > 0

    def apply_damage(self, amount: float, damage_type: str = PHYSICAL) -> int:
        """Runs the damage pipeline and returns the damage actually dealt.

        Order: resistance for the damage type, then defense (PHYSICAL only), then
        a minimum of 1 for any positive hit.
        """
        if amount <= 0 or not self.is_alive():
            return 0
        dtype = damage_type.upper()
        resistance = self.get_stat(f"{dtype.lower()}_resistance")
        resistance = max(RESISTANCE_CAP[0], min(RESISTANCE_CAP[1], resistance))
        value = amount * (1 - resistance / 100)
        if dtype == PHYSICAL:
            value -= self.get_stat("defense")
        dealt = max(MIN_DAMAGE, math.floor(value + 1e-9))  # epsilon guards float error, e.g. 100 * (1 - 0.9)
        dealt = min(dealt, self.health)
        self.health -= dealt
        return dealt

    def take_damage(self, amount: int) -> int:
        """Apply physical damage. Returns actual damage dealt."""
        return self.apply_damage(amount, PHYSICAL)

    def heal(self, amount: int) -> int:
        """Heal up to max_health. Returns actual amount healed. The dead cannot be healed."""
        if not self.is_alive() or amount <= 0:
            return 0
        max_hp = int(self.get_stat("max_health"))
        before = self.health
        self.health = min(max_hp, self.health + int(amount))
        return self.health - before

    # ---------------------------------------------------------- resources

    def can_afford(self, costs: dict[str, int]) -> bool:
        for name, amount in costs.items():
            res = self.resources.get(name.lower())
            if res is None or res.current < amount:
                return False
        return True

    def pay(self, costs: dict[str, int]) -> bool:
        """Spends all costs atomically. Returns False (spending nothing) if unaffordable."""
        if not self.can_afford(costs):
            return False
        for name, amount in costs.items():
            self.resources[name.lower()].current -= amount
        return True

    def restore_resource(self, name: str, amount: int) -> int:
        """Refills a resource up to its maximum. Returns the amount restored."""
        res = self.resources.get(name.lower())
        if res is None or amount <= 0:
            return 0
        before = res.current
        res.current = min(res.maximum, res.current + int(amount))
        return res.current - before

    # ---------------------------------------------------------- modifiers

    def add_modifier(self, stat: str, amount: float, timer: Timer | None = None, source: str = "") -> Modifier:
        mod = Modifier(canonical_stat(stat), amount, timer, source)
        self.modifiers.append(mod)
        return mod

    # ----------------------------------------------------------- statuses

    def get_status(self, name: str) -> ActiveStatus | None:
        upper = name.upper()
        for status in self.statuses:
            if status.name == upper:
                return status
        return None

    def has_status(self, name: str) -> bool:
        return self.get_status(name) is not None

    def add_status(self, name: str, timer: Timer | None, stacking: str = "refresh", source: Any = None) -> str:
        """Applies a status. Returns 'applied', 'refreshed', 'stacked' or 'ignored'."""
        existing = self.get_status(name)
        if existing is None:
            self.statuses.append(ActiveStatus(name.upper(), timer, 1, source))
            return "applied"
        if stacking == "ignore":
            return "ignored"
        existing.timer = timer
        existing.source = source
        if stacking == "stack":
            existing.stacks += 1
            return "stacked"
        return "refreshed"

    def remove_status(self, name: str) -> bool:
        status = self.get_status(name)
        if status is None:
            return False
        self.statuses.remove(status)
        return True

    def remove_statuses(self, predicate: Callable[[ActiveStatus], bool]) -> list[ActiveStatus]:
        removed = [s for s in self.statuses if predicate(s)]
        self.statuses = [s for s in self.statuses if s not in removed]
        return removed

    # ---------------------------------------------------------- variables

    def set_variable(self, name: str, value: Any, timer: Timer | None = None) -> None:
        self.variables[name.lower()] = Variable(value, timer)

    def has_variable(self, name: str) -> bool:
        return name.lower() in self.variables

    # ---------------------------------------------------------- cooldowns

    def owns(self, action_id: str) -> bool:
        """Whether this character can use the given action. Overridden by subclasses."""
        return False

    def is_ready(self, action_id: str) -> bool:
        return self.cooldowns.get(action_id, 0) <= 0

    def set_cooldown(self, action_id: str, turns: int) -> None:
        self.cooldowns[action_id] = int(turns)
        self._cooldown_set_turn[action_id] = self.turn_count

    # -------------------------------------------------------------- timers

    def tick_turn_timers(self) -> list[ActiveStatus]:
        """End-of-own-turn tick for every TURNS timer. Returns statuses that expired."""
        turn = self.turn_count
        self.modifiers = [m for m in self.modifiers if not (m.timer and m.timer.tick_turn(turn))]
        self.variables = {
            k: v for k, v in self.variables.items() if not (v.timer and v.timer.tick_turn(turn))
        }
        expired = [s for s in self.statuses if s.timer and s.timer.tick_turn(turn)]
        self.statuses = [s for s in self.statuses if s not in expired]
        for action_id, remaining in list(self.cooldowns.items()):
            if remaining > 0 and self._cooldown_set_turn.get(action_id) != turn:
                self.cooldowns[action_id] = remaining - 1
        return expired

    def expire_clock(self, clock: float) -> list[ActiveStatus]:
        """Removes CLOCK timers that have run out. Returns statuses that expired."""
        self.modifiers = [m for m in self.modifiers if not (m.timer and m.timer.expired_at_clock(clock))]
        self.variables = {
            k: v for k, v in self.variables.items() if not (v.timer and v.timer.expired_at_clock(clock))
        }
        expired = [s for s in self.statuses if s.timer and s.timer.expired_at_clock(clock)]
        self.statuses = [s for s in self.statuses if s not in expired]
        return expired

    def clear_combat_state(self) -> None:
        """Drops everything combat-scoped. Variables set without a duration persist."""
        self.modifiers = []
        self.statuses = []
        self.cooldowns = {}
        self._cooldown_set_turn = {}
        self.variables = {k: v for k, v in self.variables.items() if v.timer is None}
        self.turn_count = 0
        self.action_time = 0
