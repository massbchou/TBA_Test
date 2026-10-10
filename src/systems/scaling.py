"""Enemy level scaling and spawn-level selection.

An enemy's data ``level`` is its *base level*; its ``stats`` are its stats at that
level. When it spawns at another level, each scaled stat becomes

    base * max(MIN_FACTOR, 1 + rate * (level - base_level))

where ``rate`` is the enemy family's ``growth[stat]`` if set, otherwise the default
from ``settings.combat.enemy_scaling``. Resistances and other stats don't scale.
"""
from __future__ import annotations

import random
from typing import Any

DEFAULT_RATES = {
    "max_health": 0.08,
    "str": 0.05, "dex": 0.05, "int": 0.05, "wis": 0.05,
    "defense": 0.03,
    "speed": 0.01,
}
MIN_FACTOR = 0.4
DEFAULT_LEVEL_VARIANCE = 1


def scaling_rates(settings: dict[str, Any], family_growth: dict[str, float] | None = None) -> dict[str, float]:
    return {**DEFAULT_RATES, **settings.get("combat", {}).get("enemy_scaling", {}), **(family_growth or {})}


def scale_stats(stats: dict[str, Any], base_level: int, level: int, rates: dict[str, float]) -> dict[str, Any]:
    """Returns a copy of ``stats`` scaled from ``base_level`` to ``level``."""
    scaled = dict(stats)
    delta = level - base_level
    for stat, rate in rates.items():
        if stat in scaled and isinstance(scaled[stat], (int, float)):
            scaled[stat] = max(1 if scaled[stat] > 0 else 0, round(scaled[stat] * max(MIN_FACTOR, 1 + rate * delta)))
    return scaled


def band_for_floor(settings: dict[str, Any], floor: int) -> dict[str, Any] | None:
    """The ``combat.rules_by_level_range`` entry covering a floor (the last one if none does)."""
    bands = settings.get("combat", {}).get("rules_by_level_range", [])
    for band in bands:
        if band.get("min_level", 1) <= floor <= band.get("max_level", 999):
            return band
    return bands[-1] if bands else None


def spawn_level(
    slug: str,
    floor: int,
    rng: random.Random,
    settings: dict[str, Any],
    override: dict[str, Any] | None = None,
) -> int:
    """Picks an enemy's level for a floor. First match wins:

    1. ``override[slug]``: an event's ``levels`` map ([lo, hi] or a single number);
    2. the floor band's ``enemy_levels[slug]``;
    3. the floor band's ``level_range``;
    4. the floor +/- ``combat.enemy_level_variance`` (default 1), never below 1.
    """
    band = band_for_floor(settings, floor) or {}
    for source in (override or {}, band.get("enemy_levels", {})):
        if slug in source:
            return _pick(source[slug], rng)
    if "level_range" in band:
        return _pick(band["level_range"], rng)
    variance = int(settings.get("combat", {}).get("enemy_level_variance", DEFAULT_LEVEL_VARIANCE))
    return max(1, floor + rng.randint(-variance, variance))


def _pick(spec: Any, rng: random.Random) -> int:
    if isinstance(spec, (int, float)):
        return max(1, int(spec))
    lo, hi = int(spec[0]), int(spec[1])
    return max(1, rng.randint(min(lo, hi), max(lo, hi)))
